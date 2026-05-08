# gpt-image-2 延迟排查实战

> 客户反馈"美东 2 / 美西 3 的 `gpt-image-2` 调用很慢"——这一章把一次完整的诊断过程整理出来，帮你**先用数据定位是限流还是真慢**，再做对应处理。脚本见 [`samples/python/bench/`](../../samples/python/bench)。

---

## TL;DR

如果你看到下面任何一种现象，**99% 是订阅级配额不足，而不是网络/区域问题**：

- 单线 1024×1024 medium 普遍 60–100s（业界正常 15–30s）
- 偶发"卡住几十秒后才返回"
- 应用日志没有任何错误，但 Azure portal 上 `BlockedCalls` / `ClientErrors` (=429) 在涨

直接跳到 [§ 行动建议](#行动建议优先级排序)。

---

## 为什么"看起来慢、其实是限流"

OpenAI Python / TypeScript SDK 默认会**自动重试** 429（`Retry-After` 头）。客户端只看到一次很长的 `await`，看不到 429。需要去服务端 metric 才能发现：

| 看哪儿 | 看什么 |
|---|---|
| Azure portal → 资源 → Metrics | `TotalCalls`, `SuccessfulCalls`, `BlockedCalls`, `ClientErrors`, `ServerErrors` |
| Azure portal → AI Foundry → Quotas | 当前订阅 + 区域 + 模型的 RPM/TPM 上限 |
| 客户端关掉重试 | `AzureOpenAI(..., max_retries=0)`，让 429 显式抛出 |

> ✅ **第一招永远是：把 SDK 自动重试关掉**，再观察。

---

## 一次真实测试的数据

测试条件：`gpt-image-2` GlobalStandard，eastus2，capacity=2，AAD 认证，`api-version=2025-04-01-preview`。

| 场景 | runs | mean | p50 | p90 | max | 备注 |
|---|---|---|---|---|---|---|
| c=1, quality=medium, 1024² | 10 | **72.7s** | 66.4s | 93.9s | 102.8s | 0 错误 |
| c=1, quality=low, 1024² | 5 | **28.9s** | 23.0s | 45.5s | 49.1s | 0 错误 |
| c=2, quality=medium | 2 | **85.9s** | — | — | 86.3s | 已开始排队 |
| c=4, quality=low | 4 | **63.7s** | — | — | 85.0s | wall 86s, **6 个 429** |

服务端 metric 同步录到：`Latency` avg 37.7s / max 94.9s；`BlockedCalls=6`、`ClientErrors=6`、`ServerErrors=0` —— 服务端 100% 正常，**全部错误来自 429**。

---

## 配额对比（一个真实订阅样本）

| 模型（GlobalStandard） | eastus2 RPM 上限 | westus3 RPM 上限 |
|---|---:|---:|
| gpt-image-1 | 3 | 3 |
| gpt-image-1-mini | 4 | 4 |
| gpt-image-1.5 | **9** | **9** |
| **gpt-image-2** | **2** | **2** |

> ⚠️ **gpt-image-2 作为新模型，默认订阅配额异常低**（实测 2 RPM，是 gpt-image-1.5 的 ~1/4.5）。这同时解释了客户"美东2、美西3 都慢"——两个区域配额上限都是 2。
>
> 你可能在 Foundry portal 看到 deployment capacity 显示得比这个高，但**真正卡你的是订阅级配额**：试着把 capacity 调大会被直接拒：
>
> ```text
> InsufficientQuota: ... bigger than the current available capacity 0.
> The current quota usage is 2 and the quota limit is 2 for quota
> "Requests Per Minute - GPT 2 Image Generation".
> ```

---

## 自助诊断 4 步

### 1. 跑顺序基准（看单次延迟）

```powershell
# 准备
az login
python -m venv .venv ; . .venv/Scripts/Activate.ps1
pip install --only-binary=:all: openai azure-identity   # Windows 装 cryptography 二进制轮，避源码编译

# 运行
python samples/python/bench/bench.py `
    --endpoint https://<your-resource>.cognitiveservices.azure.com `
    --deployment <your-deployment> `
    --region-tag eastus2 `
    --runs 10
```

输出 `results-eastus2.json`、`sample-eastus2.png`，里面有每次的 `elapsed_s` 与 p50/p90/p99。

### 2. 跑并发突发（看是否被排队）

```powershell
python samples/python/bench/bench_concurrent.py `
    --endpoint https://<your-resource>.cognitiveservices.azure.com `
    --deployment <your-deployment> `
    --region-tag eastus2 `
    --concurrency 4 `
    --quality low
```

如果 c=4 的 wall 时间 ≈ c=1 单次 × 2 ~ 3，且部分 call 的 `elapsed_s` 比单线高很多，就是被服务端排队/限流。

### 3. 看服务端 metric 是不是 429

```powershell
$resId = az cognitiveservices account show `
    --name <your-resource> --resource-group <rg> --query id -o tsv

az monitor metrics list --resource $resId `
    --metric "TotalCalls,SuccessfulCalls,BlockedCalls,ClientErrors,ServerErrors" `
    --interval PT15M --output table
```

`BlockedCalls > 0` 或 `ClientErrors > 0` 时基本可以确认是限流。

### 4. 查订阅配额

```powershell
az cognitiveservices usage list --location eastus2 `
    --query "[?contains(name.value, 'gpt-image-2')].{name:name.value, used:currentValue, limit:limit}" `
    -o table

az cognitiveservices usage list --location westus3 `
    --query "[?contains(name.value, 'gpt-image-2')].{name:name.value, used:currentValue, limit:limit}" `
    -o table
```

如果 `limit` 很小（比如 2、3），就是它。

---

## 行动建议（优先级排序）

### 立即（≤ 1 天）

1. **提交配额申请**：把 `OpenAI.GlobalStandard.gpt-image-2` 在目标区域的 limit 提升到 ≥ 业务峰值 × 1.5。
   - Azure portal → AI Foundry → **Quotas** → 选模型 + 区域 → Request quota
   - 或提工单，quota type = `"Requests Per Minute - GPT 2 Image Generation"`

2. **应用侧加 semaphore 限并发**（= 当前 capacity，不要超）：
   ```python
   sem = asyncio.Semaphore(2)        # = current capacity
   async with sem:
       resp = await client.images.generate(...)
   ```

3. **关掉 SDK 自动重试**，让 429 显式可见：
   ```python
   client = AzureOpenAI(..., max_retries=0)
   ```

### 短期（≤ 1 周）

4. **降级请求参数**：`quality="low"`、必要时降到 `512×512`。实测仅 quality medium→low 一项就把 p50 从 66s 降到 23s。

5. **临时降级到 `gpt-image-1.5`**（同订阅 RPM 通常 ~9，是 4.5×）作为提配额前的吞吐缓冲。图像观感略不同，建议先做 A/B。

6. **客户端可观测性三件套**：
   - 记录 `x-ms-request-id`（出问题给微软支持时必备）
   - 记录 HTTP status + `Retry-After` 头
   - 记录 `time-to-first-byte`（图像 API 是同步返回，TTFB ≈ 总延迟，但同样的字段方便和 chat/responses 流式接口对齐）

### 中期（≤ 1 个月）

7. **多区域 active-active**：申请到配额后，eastus2 + westus3 + swedencentral 等多部署，客户端 hedging（先发 A，N 秒未返回补发 B，先到先用）。

8. **稳态高 QPS 评估 PTU**（Provisioned Throughput Units）：GlobalStandard 是共享池，存在抖动；PTU 提供专用吞吐，p99 显著更稳。是否合算看峰值/均值比与单价。

9. **改异步队列**：图像合成放 Service Bus / Storage Queue，前端给"生成中"占位，从同步阻塞改异步流程，**用户体验提升远大于扣 1–2 秒延迟**。

---

## 复测脚本

[`samples/python/bench/bench.py`](../../samples/python/bench/bench.py) — 顺序串行
[`samples/python/bench/bench_concurrent.py`](../../samples/python/bench/bench_concurrent.py) — 并发突发

提配额、调 capacity 后，跑同样命令做 before/after 对照即可。

---

## 常见误区

| 现象 | 看似 | 实际 |
|---|---|---|
| 延迟很高但日志没错误 | "Azure 慢" | SDK 自动吞了 429 |
| 调大 deployment capacity 失败 | "门户 bug" | **订阅级配额封顶**，capacity 不能超 quota.limit |
| 美东2、美西3 都慢 | "网络/区域问题" | **配额是订阅 + 区域两维独立的**，新模型默认配额各区域都很低 |
| `ServerErrors=0` 但用户说慢 | "应用 bug" | 看 `BlockedCalls` / `ClientErrors`，是 429 |
| 加 retry 越加越慢 | "需要更多 retry" | 越 retry 越被限流；先 semaphore，再考虑指数退避 |

---

## 参考

- [Quotas and limits — Azure OpenAI](https://learn.microsoft.com/azure/ai-foundry/openai/quotas-limits)
- [Manage quota — Azure OpenAI](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/quota)
- [Provisioned throughput (PTU)](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/provisioned-throughput-onboarding)
- [Image generation — Azure OpenAI](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/dall-e)
