# 09 · gpt-image-2 首请求 429 排障 Runbook

> 配套实战手册。**07 章**回答的是「为什么慢」（多数是订阅级配额低），本章回答的是 **「明明只发了 1 个请求，为什么就 429？」** —— 这是 `gpt-image-2` 这种低 RPM 图像模型在生产中最常见、最反直觉的现象。
>
> 来源整合自 Jeff Feng（Microsoft）公开的实测 runbook：[weirdo-github/azure-openai-gpt-image2-429-runbook](https://github.com/weirdo-github/azure-openai-gpt-image2-429-runbook)，本仓库基于原文做了结构化与裁剪。

---

## TL;DR

**「第一个请求就 429」基本不存在**。你看到的「第一个」只是当前 worker/会话视角的第一个，**Azure 后端在该 deployment 上看到的不是第一个**。常见叠加根因：

1. **RPM 不是只按整分钟判断** —— Azure 还会按 **1s / 10s 小窗口** 评估 burst。10 RPM ≠ 一秒打 10 个。
2. **限流是 deployment 级共享** —— 多进程、多 pod、多用户共用同一窗口。
3. **`Standard` / `GlobalStandard` 是共享池** —— 配置 quota 没变，也可能出 system capacity 型 429 或临时降限。
4. **429 有两类，header 不同**：
   - `RateLimitReached`：带 `retry-after` / `x-ratelimit-reset-requests`，按 header 退避即可。
   - `EngineOverloaded`：**可能没有 `retry-after`**，必须客户端自己做指数退避 + 抖动。
5. **SDK 默认会自动重试 429**，一次业务调用底层可能放大成 2–3 次 HTTP，把「你看到的第一次」实际推到窗口尾部。

---

## 官方依据

### 1. gpt-image-2 默认 RPM 极低

| SKU | 默认 quota | 实测可开 |
|---|---|---|
| `GlobalStandard` | 9 RPM（文档） | **实际只能开到 2** |
| `DataZoneStandard` | 3 RPM | — |

> 参考：[Azure OpenAI quotas and limits](https://learn.microsoft.com/en-us/azure/foundry/openai/quotas-limits)
> 也对照本仓库 [07 章配额对比表](./07-latency-troubleshooting.md#配额对比一个真实订阅样本)。

### 2. RPM 按小窗口评估（关键）

> RPM rate limits expect that requests be evenly distributed over a one-minute period. Azure evaluates the incoming request rate over a small period of time, typically **1 or 10 seconds**.

参考：[Manage quota — Understanding rate limits](https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/quota?tabs=rest#understanding-rate-limits)

对低 RPM 模型尤其致命：

| Deployment RPM | 推荐平滑间隔 | 含 20% 安全余量 |
|---:|---:|---:|
| 2 RPM | 30s / req | **36s / req** |
| 9 RPM | 6.7s / req | 8s / req |
| 10 RPM | 6s / req | 7.2s / req |

10 RPM 的 deployment，1 秒内打 2–3 个请求，**整分钟没超但小窗口已经超**。

### 3. 失败请求也计入限流

不成功的请求**仍可能计入 per-minute rate limit**。无退避的盲重试只会让吞吐更差。

参考：[rate limit best practices](https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/quota?tabs=rest#rate-limit-best-practices) · [OpenAI Cookbook - handle rate limits](https://developers.openai.com/cookbook/examples/how_to_handle_rate_limits)

### 4. 共享池保护机制

Azure 把 429 分四类：

- Rate limit exceeded
- **System capacity throttling**
- **Temporary rate limit adjustment**（response header 中的有效 limit **会低于**你配的 quota）
- Token budget exceeded by request parameters

参考：[Understanding 429 throttling errors](https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/quota?tabs=rest#understanding-429-throttling-errors-and-what-to-do)

### 5. SDK 默认自动重试

Azure OpenAI Python SDK 对 429 默认重试 2 次。若再套外层 Tenacity，**一次业务调用 = 4–9 次 HTTP**。规则：**只能有一层重试**。

---

## 本地实测记录

```text
Deployment: gpt-image-2 / GlobalStandard / capacity=2
API: 2025-04-01-preview · Client: raw httpx, max_retries=0
```

### Test 1 · burst + probe（6 并发 + 12 次/秒探针）

```text
200 = 2
429 = 16
```

| 请求 | retry-after | reset | limit |
|---|---|---|---|
| burst-1  | 60 | 60 | 2 |
| probe-1  | 59 | 59 | 2 |
| probe-12 | 44 | 44 | 2 |

观察：`retry-after` 与 `x-ratelimit-reset-requests` **按窗口剩余秒数线性递减**；`x-ratelimit-limit-requests` 始终 = 2；出现过 `EngineOverloaded`（无 `retry-after`）。

### Test 2 · capacity + 1 并发

```text
200 = 2
429 EngineOverloaded = 1
```

等 75s 后单 probe → `200`，`remaining-requests=1`。**单次 429 不会导致长时间不可恢复**。

### Test 3 · 8 并发 + 30 次连续探针

```text
200 = 9 · 429 = 34
```

连续 429 **没有把可见 limit 压低**；窗口结束后能恢复。但这仍是坏策略：**浪费请求预算 + 触发共享池保护**。

---

## 为什么会出现「第一个请求就 429」

| 场景 | 触发 | 排查 |
|---|---|---|
| **A. 你看到的第一个 ≠ deployment 看到的第一个** | 多进程/多 pod/多用户共用 | 做**跨进程共享 token bucket**，不要每个 worker 本地限流 |
| **B. 上一个请求超时但服务端仍在处理** | 客户端 20s 超时，图像生成 30–80s 才返回 | 记录 client request id、对用户点击幂等去重 |
| **C. SDK 自动重试隐藏真实次数** | SDK `max_retries` 默认 ≥ 2，外层又套重试 | 打开 SDK debug logging；外层重试时设 `max_retries=0` |
| **D. 小窗口 burst** | 冷启动/队列恢复/多用户同时点击 | 记录每秒进入请求数；用 **leaky bucket** 而非粗粒度 token bucket |
| **E. `EngineOverloaded` / 共享池过载** | error code = `EngineOverloaded`，无 `retry-after` | 切其他 region；长期高频 → PTU 或工单 |
| **F. 临时有效限额调整** | `x-ratelimit-limit-*` < 配置 quota | 降载、等待恢复、必要时开工单 |

---

## 排障 Runbook

### Step 1 · 每个请求必须记录的字段（最小集）

```text
timestamp_utc, deployment, region, model, status_code
error.code, error.message_prefix
retry-after, retry-after-ms
x-ratelimit-limit-requests, x-ratelimit-remaining-requests, x-ratelimit-reset-requests
x-ratelimit-limit-tokens,   x-ratelimit-remaining-tokens,   x-ratelimit-reset-tokens
x-ms-region, x-request-id, apim-request-id
client_attempt, client_timeout_s, queue_wait_ms, inflight_count
```

少一个字段，就少一种排除可能性。

### Step 2 · 区分 429 类型

| 类型 | 特征 | 处理 |
|---|---|---|
| `RateLimitReached` | 带 `retry-after` / reset header | 按 header 暂停该 deployment |
| `EngineOverloaded` | 通常无 retry header，message 含 too many / busy | **指数退避 + 抖动 + 切 region** |
| 临时有效限额调整 | header 中 effective limit < 配置 quota | 降载、等恢复、开工单 |
| SDK 重试放大 | 应用 1 次 / HTTP 多次 | 关闭双重重试 |
| 小窗口 burst | minute 总量没超但秒级集中 | leaky bucket 平滑出队 |

### Step 3 · 查配置 quota 与 deployment capacity

```bash
az cognitiveservices account deployment show \
  -g <rg> -n <account> --deployment-name gpt-image-2 \
  --query "{deployment:name,sku:sku.name,capacity:sku.capacity,state:properties.provisioningState}" \
  -o table

az cognitiveservices usage list -l <region> \
  --query "[?name.value=='OpenAI.GlobalStandard.gpt-image-2'].{name:name.value,current:currentValue,limit:limit}" \
  -o table
```

### Step 4 · 安全复现实验

**不要暴力撞 429**：

1. 冷却 `max(retry-after, 70s)`
2. 单请求 probe，确认健康
3. `capacity + 1` 并发一次，**一旦出 429 立刻停**
4. 记录所有 headers
5. 等 `max(retry-after, 70s)` 后再单 probe

### Step 5 · 开工单的信号

开单前准备：UTC timestamp、`x-request-id`、`apim-request-id`、region/deployment/SKU/capacity、429 code & headers、同窗口发送速率与 in-flight、Azure Monitor 截图。

**需要升级 / 开工单的信号**：

- 单请求 probe 多次 `EngineOverloaded`
- `x-ratelimit-limit-*` **长时间低于配置 quota**
- 按 `retry-after` 等待后仍长期 429
- 多个 region 同时出现 system capacity 型 429

---

## 生产预防措施

### 1. 跨进程共享 token bucket

不要每个进程各自按 10 RPM 放行 → 用 Redis / durable queue 做**全局** bucket。

```text
2 RPM deployment: 1 req / 36s
9 RPM deployment: 1 req / 8s
```

### 2. 用 leaky bucket，不要 token bucket

Token bucket 允许短时 burst，对低 RPM 不友好。Leaky bucket / paced queue **固定间隔出队**。

### 3. Deployment 级 Circuit Breaker

```text
if retry-after or retry-after-ms exists:
    mark deployment unavailable until now + retry_after + jitter
else:  # EngineOverloaded
    backoff: 2s, 4s, 8s, 16s, max 60s + jitter
```

并把请求**转给其他健康 region**。

### 4. 多区域 health-aware routing

5 个 region × 2 RPM = 全局 10 RPM。**不要 round-robin**，按 `next_available_at` + in-flight + 最近 429 类型 + p95 latency 做路由。

```text
eastus2 | westus3 | polandcentral | swedencentral | uaenorth   各 2 RPM
```

### 5. UX 策略

- 入队后立刻返回 `job_id`
- UI 显示排队位置与预计时间
- 用户重复点击 → 返回同一个 `job_id`，**不新建请求**
- 429 时显示「排队中」，不暴露原始错误

### 6. 重试层只能有一个

```python
# 选 A：用 SDK 重试
client = AzureOpenAI(..., max_retries=5)   # 外层不要再套 Tenacity

# 选 B：自己控制调度
client = AzureOpenAI(..., max_retries=0)   # 在调度层做 retry / 熔断 / 跨 region
```

### 7. 单独处理 `EngineOverloaded`

不一定给 `retry-after` → 当前 deployment 短暂熔断 + 立即切 region + 指数退避；若多 region 同时出现，**降低全局出队速率**。

### 8. 评估 PTU

`GlobalStandard` 共享池无法完全避免抖动。latency-sensitive / mission-critical 业务应考虑 PTU。

> ⚠️ **截至 2026-05-14，gpt-image-2 PTU 尚未上线。** 有产品/技术问题请联系微软团队。

---

## 可复用探针脚本

```python
import asyncio, json, subprocess, time, httpx

RG, ACCOUNT, DEPLOYMENT = "<rg>", "<account>", "gpt-image-2"
API_VERSION = "2025-04-01-preview"

def az_json(args): return json.loads(subprocess.check_output(["az"]+args, text=True))
def az_tsv(args):  return subprocess.check_output(["az"]+args, text=True).strip()

def pick_headers(resp):
    names = ["retry-after","retry-after-ms",
             "x-ratelimit-limit-requests","x-ratelimit-remaining-requests","x-ratelimit-reset-requests",
             "x-ms-region","x-request-id","apim-request-id"]
    lower = {k.lower(): v for k, v in resp.headers.items()}
    return {k: lower.get(k) for k in names if lower.get(k) is not None}

async def one(client, url, headers, label):
    body = {"prompt": f"A tiny test shape. {label}", "n": 1, "size": "1024x1024", "quality": "low"}
    start = time.time()
    resp = await client.post(url, headers=headers, json=body, timeout=180)
    row = {"label": label, "elapsed_s": round(time.time()-start, 3),
           "status": resp.status_code, "headers": pick_headers(resp)}
    if resp.status_code != 200:
        try: row["error"] = resp.json().get("error", {})
        except Exception: row["body_prefix"] = resp.text[:200]
    print(json.dumps(row, ensure_ascii=False))

async def main():
    endpoint = az_json(["cognitiveservices","account","show","-g",RG,"-n",ACCOUNT,
                        "--query","properties.endpoint","-o","json"]).rstrip("/")
    key = az_tsv(["cognitiveservices","account","keys","list","-g",RG,"-n",ACCOUNT,
                  "--query","key1","-o","tsv"])
    url = f"{endpoint}/openai/deployments/{DEPLOYMENT}/images/generations?api-version={API_VERSION}"
    headers = {"api-key": key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(http2=False) as client:
        tasks = [one(client, url, headers, f"cap-plus-one-{i+1}") for i in range(3)]
        await asyncio.gather(*tasks)

asyncio.run(main())
```

---

## 一句话建议

> **不要把 `RPM=10` 理解成「任意时刻可并发 10 个」。** 对 `gpt-image-2` 这种低 RPM 图像模型，要把它当作**慢速队列服务**：每个 deployment 全局平滑节流、按 429 header 熔断、对无 header 的容量型 429 做指数退避 + 跨 region fallback。这比堆重试更能提升用户体验。

---

## 关联章节

- [07 · gpt-image-2 延迟排查实战](./07-latency-troubleshooting.md) —— 配额维度（为什么慢）
- [08 · 错误码速查](./08-error-codes.md) —— 429 / `EngineOverloaded` / `InsufficientQuota` 字段速查
- [99 · FAQ Q16](./99-faq.md) —— RPM/TPM 限流 SDK 吞错问题

## 致谢

原始实测与方法论：Jeff Feng @ Microsoft · [weirdo-github/azure-openai-gpt-image2-429-runbook](https://github.com/weirdo-github/azure-openai-gpt-image2-429-runbook)
