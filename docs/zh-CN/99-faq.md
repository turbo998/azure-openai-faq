# 99 · 高频踩坑 FAQ

### Q1. 我把 OpenAI 代码搬到 Azure，`401` / `404` 一堆，从哪儿开始排？
1. 跑 [`05_validate_deployment.py`](../../samples/python/05_validate_deployment.py)，确认 endpoint + key/AAD + deployment 三件套。
2. 检查请求头：是 `api-key` 还是 `Authorization: Bearer`？两者只能选一个。
3. 检查 `model` 字段是模型名还是 **deployment 名**。

### Q2. Azure 上 GPT-Image-2 为什么 `url` 是空的？
设计如此。Azure 只返回 `b64_json`。请改读 b64，需要 URL 自己上 Blob 生成 SAS。详见 [06](./06-gpt-image-2.md)。

### Q3. `api-version` 该填什么？
- v1 新路由：可省略；显式建议 `preview`。
- 旧 deployments 路由：用最新 GA（如 `2024-10-21`）；新预览特性用对应 `*-preview`。
- 最权威：[Azure OpenAI API 版本说明](https://learn.microsoft.com/zh-cn/azure/ai-foundry/openai/reference)。

### Q4. 如何同时支持两边，又不让代码两套？
抽 client 工厂 + `model` 变量；详见 [04 节](./04-model-vs-deployment.md#同一应用兼容两边的小技巧)。

### Q5. Azure 上 streaming 第一个 chunk 没有 content，崩了
Azure 流式首个 chunk 常常只有 `prompt_filter_results`，没有 `choices` 或 `choices[0].delta.content`。代码要：
```python
for chunk in stream:
    if not chunk.choices:
        continue
    delta = chunk.choices[0].delta.content or ""
    ...
```

### Q6. 触发了内容过滤，可以关掉吗？
不能完全关，但可以申请放宽阈值（须业务审核）：
- Azure AI Foundry 门户 → Safety + security → Content filters → 创建自定义策略。
- 仍受限的高风险类别（child sexual exploitation 等）无法放开。

### Q7. 调用速度比 OpenAI 慢？
- 选择就近 region。
- 评估升级到 PTU（Provisioned Throughput Units）或 GlobalStandard。
- 短文本场景检查冷启动；保持 keep-alive。

### Q8. `model` 必须 100% 等于 deployment 名吗？大小写敏感吗？
是。**大小写敏感**，且不能有空格。

### Q9. 我的代码里直接用 `requests.post()` 拼了 URL，怎么迁移？
```diff
- url = "https://api.openai.com/v1/chat/completions"
- headers = {"Authorization": f"Bearer {OPENAI_KEY}"}
- body = {"model": "gpt-5.5", "messages": [...]}

+ url = f"{AOAI_ENDPOINT}/openai/deployments/{DEPLOYMENT}/chat/completions?api-version={API_VERSION}"
+ headers = {"api-key": AOAI_KEY}
+ body = {"messages": [...]}    # 注意：body 里不再放 model
```
（v1 新路由也行，结构与 OpenAI 一致，仅换域名 + 加 `api-key` 头。）

### Q10. JSON Mode / Structured Outputs 两边都支持吗？
都支持。`response_format={"type":"json_object"}` 或 `{"type":"json_schema",...}` 在两边语义一致。Azure 上对应 `api-version` 要够新（`2024-08-01-preview` 起）。

### Q11. Function calling / tools 有差异吗？
基本无差异。注意：
- Azure 上 tool 输出超大可能被 RAI 二次扫描，触发 filter。
- 并发工具调用（parallel tool calls）能力两边均支持。

### Q12. 为什么 OpenAI 上能跑的 prompt 在 Azure 上 400 了？
99% 是 `content_filter`。看响应 `error.innererror.content_filter_result` 字段，定位是 `hate` / `violence` / `sexual` / `self_harm` / `jailbreak` 哪一类、severity 多高。

### Q13. 我能把请求从 OpenAI 一字不改 proxy 到 Azure 吗？
不行。至少要改：
- 域名 + 路径
- 鉴权头
- body 里 `model` 是否需要去掉（旧路由）
- 处理 `b64_json` 的图像响应

可以写个 shim（中间件）做这个翻译，仓库后续示例可补 `samples/proxy-shim/`。

### Q14. 如何判断 OpenAI 出了新模型 / 新参数 Azure 是否支持？
- 看 [Azure OpenAI Models 文档](https://learn.microsoft.com/zh-cn/azure/ai-foundry/openai/concepts/models) 与 [What's new](https://learn.microsoft.com/zh-cn/azure/ai-foundry/openai/whats-new)。
- 看 `api-version` 的 release notes。

### Q15. PTU / GlobalStandard / DataZoneStandard 怎么选？
- **GlobalStandard**：默认；全球容量池，价格友好但有突发限流可能。
- **DataZoneStandard**：欧/美数据驻留场景。
- **PTU**：稳态高 QPS 业务，需要保障吞吐。
- 详见 [Azure OpenAI 部署类型](https://learn.microsoft.com/zh-cn/azure/ai-foundry/openai/how-to/deployment-types)。

### Q16. 客户端 RPM / TPM 超限会报什么错？

**HTTP 层**：`429 Too Many Requests`，带 `Retry-After`（秒）和 `x-ms-request-id`：

```
HTTP/1.1 429 Too Many Requests
Retry-After: 38
x-ratelimit-remaining-requests: 0
x-ratelimit-remaining-tokens: 12000
x-ms-request-id: 8c1f...
```

```json
{
  "error": {
    "code": "429",
    "message": "Requests to the Embeddings_Create Operation under Azure OpenAI API version 2024-10-21 have exceeded call rate limit of your current OpenAI S0 pricing tier. Please retry after 38 seconds. Please go here: https://aka.ms/oai/quotaincrease if you would like to further increase the default rate limit."
  }
}
```

**RPM vs TPM 用文案区分**（HTTP code 一样都是 429）：

| 触发原因 | 错误文案关键词 |
|---|---|
| RPM 超限（每分钟请求数） | `exceeded call rate limit` |
| TPM 超限（每分钟 token 数） | `exceeded token rate limit` |

**SDK 层默认会吞掉**——这是最大的坑：

| SDK | 抛出类型 | 默认行为 |
|---|---|---|
| Python `openai` | `openai.RateLimitError` | **自动重试 2 次**，按 `Retry-After` 退避 → 用完才抛 |
| Node `openai` | `OpenAI.RateLimitError` | 自动重试 2 次 |
| .NET `Azure.AI.OpenAI` | `RequestFailedException` (Status=429) | Azure.Core 重试策略 |
| 直接 REST | 自己看 `response.status_code == 429` | 自己处理 |

⚠️ **应用日志里看不到错误、用户却抱怨慢**，几乎一定是 SDK 在重试 429。把重试关掉让它显式抛出：

```python
from openai import AzureOpenAI, RateLimitError

client = AzureOpenAI(..., max_retries=0)

try:
    resp = client.images.generate(model="my-deployment", ...)
except RateLimitError as e:
    retry_after = int(e.response.headers.get("retry-after", "10"))
    request_id  = e.response.headers.get("x-ms-request-id")
    logger.warning("AOAI 429 rid=%s retry_after=%ds", request_id, retry_after)
    # 自己决定是否重试 / 排队 / 降级
```

**服务端验证**（Azure portal → 资源 → Metrics）：`BlockedCalls > 0` 或 `ClientErrors > 0`，`ServerErrors = 0`，就是限流。

**别和这两个 429 搞混**：
- **Capacity 不足**（control plane，改 deployment 时）：错误码 `InsufficientQuota`，文案 `quota usage is N and the quota limit is N`，是订阅级配额封顶，不是运行时限流。
- **Token 超 context window**：`400 BadRequest` + `context_length_exceeded`，不是 429。

完整排查链路（基准 → 并发 → metric → 配额）见 [07 · gpt-image-2 延迟排查实战](./07-latency-troubleshooting.md)。
