# Azure OpenAI / Foundry 错误码速查

> 调用 Azure OpenAI 时碰到错误，先看本章对照排查。涵盖 **Data Plane（运行时 API 调用）** 和 **Control Plane / Foundry（资源、部署、配额管理）** 两套错误码。

---

## 目录

- [快速判定：是哪一边的错？](#快速判定是哪一边的错)
- [Data Plane HTTP 状态码总览](#data-plane-http-状态码总览)
- [400 Bad Request 细分](#400-bad-request-细分)
- [401 / 403 鉴权与权限](#401--403-鉴权与权限)
- [404 资源未找到](#404-资源未找到)
- [408 / 504 超时](#408--504-超时)
- [413 / 422 请求体问题](#413--422-请求体问题)
- [429 限流（4 种子类型）](#429-限流4-种子类型)
- [500 / 502 / 503 服务端](#500--502--503-服务端)
- [Content Filter 错误详解](#content-filter-错误详解)
- [Control Plane / Foundry 错误码](#control-plane--foundry-错误码)
- [SDK 异常映射](#sdk-异常映射)
- [响应头对照](#响应头对照)
- [给监控的 30 行日志规范](#给监控的-30-行日志规范)

---

## 快速判定：是哪一边的错？

```text
有 x-ms-request-id, 路径含 /openai/...     → Data Plane（推理调用）
有 x-ms-correlation-request-id, ARM 路径   → Control Plane（管理操作）
错误码 InsufficientQuota / SkuNotAvailable → Control Plane
错误码 content_filter / context_length     → Data Plane
```

| | Data Plane | Control Plane / Foundry |
|---|---|---|
| 触发于 | 应用调 chat/responses/images/embeddings... | 创建/更新/删除资源、部署、配额、密钥 |
| 端点 | `https://<resource>.openai.azure.com/openai/...`<br>或 `https://<resource>.cognitiveservices.azure.com/openai/...` | `https://management.azure.com/...` |
| 错误格式 | OpenAI 兼容：`{ error: { code, message, type, param, innererror } }` | ARM 标准：`{ error: { code, message, target, details, innerError } }` |
| 请求 ID | `x-ms-request-id` | `x-ms-correlation-request-id` / `x-ms-request-id` |

---

## Data Plane HTTP 状态码总览

| Status | 含义 | 重试? | 常见原因 |
|---:|---|---|---|
| **400** | Bad Request | ❌ | 参数错、`model` 名错、内容被审核、token 超限 |
| **401** | Authentication | ❌ | API key 错、AAD token 过期、关闭了 local auth 又用 key |
| **403** | Permission Denied | ❌ | RBAC 缺角色、订阅未启用 AOAI、IP 不在防火墙白名单 |
| **404** | Not Found | ❌ | deployment 名错、endpoint 区域错、`api-version` 不支持该接口 |
| **408** | Request Timeout | ✅ | 客户端 / 网关层超时 |
| **413** | Payload Too Large | ❌ | body 超 ~250KB（DALL·E / Whisper 等） |
| **422** | Unprocessable Entity | ❌ | schema 通过但语义错（如 `tools` 与 `function_call` 冲突） |
| **429** | Too Many Requests | ✅ | 见下文 [429 4 种子类型](#429-限流4-种子类型) |
| **500** | Internal Server Error | ✅ | 偶发，重试即可 |
| **502** | Bad Gateway | ✅ | 上游 / 入口故障 |
| **503** | Service Unavailable | ✅ | 容量耗尽 / 维护中 |
| **504** | Gateway Timeout | ✅ | 下游推理超时 |

> SDK 默认对 408 / 429 / ≥500 / 连接错误自动重试 2 次（指数退避），把 `max_retries=0` 关掉才会原样抛。

---

## 400 Bad Request 细分

错误 body 里 `error.code` 常见值：

| `error.code` | 含义 | 修复 |
|---|---|---|
| `invalid_request_error` | 参数无效 | 看 `param` 字段定位字段名 |
| `context_length_exceeded` | prompt + `max_tokens` 超模型上下文 | 缩 prompt / 降 `max_tokens` / 换大窗口模型 |
| `model_not_found` | `model` 字段不存在 | 用 **deployment 名**，不是模型名；且大小写敏感 |
| `content_filter` | 命中 RAI 内容过滤 | 见下方 [Content Filter 详解](#content-filter-错误详解) |
| `responsibleAIPolicyViolation` | RAI 策略阻断（图像生成常见） | 同上 |
| `tokens_limit_reached_for_default_tier` | 免费层 token 超限 | 升订阅 / 申请配额 |
| `OperationNotSupported` | 该 deployment / api-version 不支持此操作（如对 image 模型调 chat） | 用对应模型/API |
| `DeploymentNotFound` | data plane 找不到部署（已被删/未 ready） | 检查部署状态 |
| `invalid_api_version` | `api-version` 字符串错 | 查 [API versions](https://learn.microsoft.com/azure/ai-foundry/openai/reference) |
| *`input item ID does not belong to this connection`* | Realtime / Responses API 引用了不属于当前 session 的 item ID | 重建连接/会话，不复用旧 ID；见 [FAQ Q17](./99-faq.md#q17-报-400-input-item-id-does-not-belong-to-this-connection-怎么回事) |

**典型 400 内容审核响应**：
```json
{
  "error": {
    "code": "content_filter",
    "message": "The response was filtered due to the prompt triggering Azure OpenAI's content management policy.",
    "param": "prompt",
    "type": null,
    "innererror": {
      "code": "ResponsibleAIPolicyViolation",
      "content_filter_result": {
        "hate":      { "filtered": false, "severity": "safe" },
        "sexual":    { "filtered": false, "severity": "safe" },
        "violence":  { "filtered": true,  "severity": "high" },
        "self_harm": { "filtered": false, "severity": "safe" },
        "jailbreak": { "filtered": true,  "detected": true }
      }
    }
  }
}
```

---

## 401 / 403 鉴权与权限

| 现象 | 多半是 |
|---|---|
| 401 + `Access denied due to invalid subscription key` | API key 不对 / 来源订阅不对 |
| 401 + `Bearer token expired` | AAD token 过期，重取 token；DefaultAzureCredential 内部应自动续 |
| 401 + `Local authentication is disabled` | 资源开了 `disableLocalAuth=true`，但你用的是 key — 改用 AAD |
| 403 + `Forbidden` 无更多信息 | RBAC 角色缺：data plane 需 `Cognitive Services User` 或 `Cognitive Services OpenAI User`；微调还要 `Cognitive Services OpenAI Contributor` |
| 403 + `IP …  is not allowed` | 资源开了 firewall，加白名单 IP 或私有终端节点 |
| 403 + `Public network access is disabled` | 资源关掉了公网访问，必须走私有终端节点 |

---

## 404 资源未找到

| 现象 | 修复 |
|---|---|
| `The API deployment for this resource does not exist` | `model` 字段必须 = deployment 名，**大小写敏感** |
| `Resource not found` | endpoint 域名错（区域、resource 名拼错） |
| 路径 `/openai/deployments/...` 返回 404 | 旧路由走 `cognitiveservices.azure.com`，新 v1 路由走 `openai.azure.com/openai/v1/` |
| `api-version` 无效 | 该接口在该 api-version 下不存在；换 GA 版本 |

---

## 408 / 504 超时

- **408**：客户端到 AOAI 入口的超时；通常是网络抖动。
- **504**：AOAI 入口到推理后端超时；通常是模型生成时间过长（长 prompt / 大 `max_tokens` / 复杂 tools）。

修复：
- 设客户端超时 ≥ 600s（图像 / 大模型推理常常 > 60s）。
- 流式（`stream=True`）规避大 body 超时。
- 减小 `max_tokens` / prompt 长度。

---

## 413 / 422 请求体问题

| Status | 错误码 | 修复 |
|---|---|---|
| 413 | `RequestEntityTooLarge` | 减小 body（图像 base64、音频文件分片） |
| 422 | `invalid_request_error` (schema 通过但语义错) | 检查 `tools` + `function_call`、`response_format` 与 `tools` 兼容性 |

---

## 429 限流（4 种子类型）

> 微软官方把 429 拆成 4 种，根因不同 → 处理动作不同。

| 子类型 | 错误关键词 | 根因 | 行动 |
|---|---|---|---|
| **TPM/RPM 超限** | `Requests to … have been limited` / `Rate limit is exceeded` | 你的请求超过了部署的 TPM / RPM 配额 | 加 deployment 容量、跨部署/区域分流，或申请配额提升 |
| **System capacity 抖动** | `service is temporarily unable to process your request` / `System is experiencing high demand` | GlobalStandard 共享池后端瞬时紧张 | 按 `retry-after-ms` 退避；持续则上 PTU |
| **临时降配** | 配额没改，但响应里 `x-ratelimit-limit-tokens` 突然变小 | 共享池保护机制临时给你降速，几小时内恢复 | 降速重试；要稳定吞吐上 PTU |
| **`max_tokens` 撑爆预算** | 看似 token 用得不多但被 429 | 限流是按 prompt + `max_tokens` 估算，不是实际计费 | 把 `max_tokens` 调到接近真实需要 |

判断技巧：
- `error.message` 里 `exceeded call rate limit` → **RPM 超**
- `error.message` 里 `exceeded token rate limit` → **TPM 超**
- 响应头 `x-ratelimit-limit-tokens` < 你的配置 TPM → **临时降配**
- 服务端 metric `BlockedCalls > 0` 且 `ServerErrors = 0` → 100% 是 429

完整 429 处理见 [Q16 FAQ](./99-faq.md#q16-客户端-rpm--tpm-超限会报什么错) 和 [07 章节](./07-latency-troubleshooting.md)。

---

## 500 / 502 / 503 服务端

| Status | 含义 | 行动 |
|---|---|---|
| 500 | 推理后端异常 | 退避重试 2–3 次；持续提工单（带 `x-ms-request-id`） |
| 502 | 网关 / 路由层异常 | 同上 |
| 503 | 容量耗尽 | 重试；考虑切区域 / 部署 / 升 PTU |

---

## Content Filter 错误详解

### 4 大类别 + 4 级 severity

```
hate / sexual / violence / self_harm  ×  safe / low / medium / high
```

默认阈值 = medium（即 medium / high 会被拦）。可在 Foundry 门户 → Safety + security → Content filters 自定义阈值。

### 可选 binary 检测

| key | 含义 |
|---|---|
| `jailbreak` | 用户试图越狱（prompt injection） |
| `protected_material_text` | 输出疑似命中受版权保护文本 |
| `protected_material_code` | 输出疑似命中公开仓库代码（影响 Customer Copyright Commitment） |
| `profanity` | 脏话 |
| `indirect_attack` | 间接 prompt 注入 |

### 阻断 vs 注释

- **阻断**（HTTP 400 + `code: content_filter`）：触发严重类别，整个响应被拒。
- **注释**（200 OK，但 `prompt_filter_results` / `content_filter_results` 出现）：内容通过了，但被打了标签 — 可用于审计。

### 处理样板

```python
from openai import BadRequestError

try:
    resp = client.chat.completions.create(...)
except BadRequestError as e:
    body = getattr(e, "body", None) or {}
    inner = (body.get("error") or {}).get("innererror") or {}
    if inner.get("code") == "ResponsibleAIPolicyViolation":
        cf = inner.get("content_filter_result", {})
        triggered = [k for k, v in cf.items() if isinstance(v, dict) and v.get("filtered")]
        logger.warning("RAI blocked: %s", triggered)
        # 给用户友好提示，不要把原文回显
```

---

## Control Plane / Foundry 错误码

> 发生在创建资源 / 部署、改 capacity、列配额、轮换 key 这类管理操作。错误格式是 ARM 标准。

| `error.code` | 触发场景 | 修复 |
|---|---|---|
| `InsufficientQuota` | `az resource update --set sku.capacity=N` 但订阅级 RPM/TPM 配额已满 | 在 Foundry → Quotas 申请提额；类型如 `Requests Per Minute - GPT 2 Image Generation` |
| `SkuNotAvailable` | 该模型 / SKU 在所选区域不可用 | 换区域，或换 SKU（GlobalStandard / DataZoneStandard / PTU） |
| `DeploymentModelNotSupported` | 模型版本/SKU 组合非法 | 查 [Models](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/models) 支持矩阵 |
| `InvalidApiVersionParameter` | ARM 调用的 `api-version` 错 | 用最新 `2024-10-01` 或更新 |
| `InvalidResourceFormat` / `InvalidResourceName` | 资源名不合规 | 字母数字+连字符，2–64 字符 |
| `ResourceNotFound` | 资源/部署/RG 不存在或权限不够看见 | 检查 `--subscription`、RG 名 |
| `AuthorizationFailed` | RBAC 缺管理角色 | `Cognitive Services Contributor` 或 `Owner` |
| `RegionCapacityExceeded` | 区域整体容量饱和 | 换区域或排队 |
| `OperationNotAllowed` | 比如想删除有子资源的资源 | 先删子资源 |
| `ResourceQuotaExceeded` | 订阅级资源数量上限 | 删除闲置资源 / 提工单 |
| `ContentFilteringDisabledForResource` | 试图用要求 RAI 的特性但资源关了 RAI | 启用 RAI |
| `ModelDeprecated` | 用了下架/将下架的模型 | 升级到推荐继任 |
| `MissingSubscriptionRegistration` | 订阅没注册 `Microsoft.CognitiveServices` provider | `az provider register --namespace Microsoft.CognitiveServices` |
| `SubscriptionNotRegistered` | 同上 | 同上 |
| `ConflictingOperation` (HTTP 409) | 同一资源并发改动 | 退避重试 |

### Foundry portal 常见操作 → 实际 ARM 错误

| 操作失败的弹窗文案 | ARM `error.code` |
|---|---|
| "Quota exceeded" / "Increase your quota" | `InsufficientQuota` |
| "This SKU isn't available in this region" | `SkuNotAvailable` |
| "Model not available for this version of API" | `DeploymentModelNotSupported` |
| "You don't have permission" | `AuthorizationFailed` |

### 微调（Fine-tuning）相关

| 现象 | 修复 |
|---|---|
| 调 fine-tuning API 403 | 需要 `Cognitive Services OpenAI Contributor` 角色（不是 Reader/User） |
| 训练作业 `failed` + 文件验证错 | JSONL schema 不对（`messages` 字段、role 限定） |
| `ModelDeploymentDoesNotExist` 部署微调结果时 | 该模型在该区域不支持微调或部署，查 [模型矩阵](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/models#fine-tuning-models) |

---

## SDK 异常映射

| HTTP | Python `openai` | Node `openai` | .NET `Azure.AI.OpenAI` |
|---|---|---|---|
| 400 | `BadRequestError` | `BadRequestError` | `RequestFailedException(Status=400)` |
| 401 | `AuthenticationError` | `AuthenticationError` | 同上, 401 |
| 403 | `PermissionDeniedError` | `PermissionDeniedError` | 同上, 403 |
| 404 | `NotFoundError` | `NotFoundError` | 同上, 404 |
| 408 | `APITimeoutError` | `APIConnectionTimeoutError` | `OperationCanceledException` |
| 422 | `UnprocessableEntityError` | `UnprocessableEntityError` | 同上, 422 |
| 429 | `RateLimitError` | `RateLimitError` | 同上, 429 |
| ≥500 | `InternalServerError` | `InternalServerError` | 同上, 5xx |
| 网络 | `APIConnectionError` | `APIConnectionError` | `RequestFailedException` |

**默认重试 2 次** 对：连接错误 / 408 / 429 / ≥500。`max_retries=0` 关掉。

---

## 响应头对照

| Header | 用途 |
|---|---|
| `x-ms-request-id` | 数据面请求唯一 ID — **提工单必带** |
| `x-ms-correlation-request-id` | 控制面相关 ID |
| `x-ms-error-code` | 部分 ARM 错误带；和 body 里 `error.code` 一致 |
| `Retry-After` | 秒；重试前等多久（429 / 503） |
| `retry-after-ms` | 毫秒精度版本 |
| `x-ratelimit-limit-requests` | 当前 RPM 上限 |
| `x-ratelimit-remaining-requests` | 这一分钟剩余 RPM |
| `x-ratelimit-limit-tokens` | 当前 TPM 上限（< 配置值时说明被临时降配） |
| `x-ratelimit-remaining-tokens` | 这一分钟剩余 TPM |
| `azureml-model-deployment` | 命中的部署（PTU / 多部署路由场景） |

---

## 给监控的 30 行日志规范

无论中间发生什么，**这几样必记**：

```python
# 成功 / 失败都打
log = {
    "ts": time.time(),
    "op": "chat.completions.create",
    "deployment": deployment,
    "api_version": api_version,
    "status": getattr(resp, "status_code", "ok"),
    "x_ms_request_id": resp.headers.get("x-ms-request-id"),
    "x_ms_error_code": resp.headers.get("x-ms-error-code"),
    "retry_after": resp.headers.get("retry-after"),
    "ratelimit_remaining_requests": resp.headers.get("x-ratelimit-remaining-requests"),
    "ratelimit_remaining_tokens":   resp.headers.get("x-ratelimit-remaining-tokens"),
    "elapsed_ms": int((time.time() - t0) * 1000),
}

# 失败再多打
err = {
    "error_code":     body.get("error", {}).get("code"),
    "error_message":  body.get("error", {}).get("message"),
    "innererror_code":(body.get("error", {}).get("innererror") or {}).get("code"),
    "param":          body.get("error", {}).get("param"),
}
```

> 实战经验：**`x-ms-request-id` 是开微软支持工单时第一个会被问到的字段**，一定记下来。

---

## 参考

- [Azure OpenAI: Manage quota & 429 types](https://learn.microsoft.com/azure/foundry/openai/how-to/quota#understanding-429-throttling-errors-and-what-to-do)
- [Azure OpenAI: Error handling — Python / JS / .NET](https://learn.microsoft.com/azure/foundry/openai/supported-languages#error-handling)
- [Azure OpenAI: Content filter overview](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/content-filter)
- [Azure OpenAI: REST API reference (errorBase / innerError)](https://learn.microsoft.com/azure/ai-foundry/openai/reference-preview)
- [Azure OpenAI: Models](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/models)
- [ARM common error responses](https://learn.microsoft.com/azure/azure-resource-manager/management/common-deployment-errors)
