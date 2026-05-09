# Azure OpenAI / Foundry error code cheat sheet

> Hit an error calling Azure OpenAI? Cross-reference here. Covers both **Data Plane** (runtime API calls) and **Control Plane / Foundry** (resource, deployment, quota management) errors.

---

## Contents

- [Quick triage: which side errored?](#quick-triage-which-side-errored)
- [Data plane HTTP status overview](#data-plane-http-status-overview)
- [400 Bad Request breakdown](#400-bad-request-breakdown)
- [401 / 403 auth & permission](#401--403-auth--permission)
- [404 not found](#404-not-found)
- [408 / 504 timeouts](#408--504-timeouts)
- [413 / 422 body issues](#413--422-body-issues)
- [429 throttling — 4 sub-types](#429-throttling--4-sub-types)
- [500 / 502 / 503 service-side](#500--502--503-service-side)
- [Content filter errors in detail](#content-filter-errors-in-detail)
- [Control plane / Foundry error codes](#control-plane--foundry-error-codes)
- [SDK exception mapping](#sdk-exception-mapping)
- [Response headers cheat sheet](#response-headers-cheat-sheet)
- [Minimum log fields](#minimum-log-fields)

---

## Quick triage: which side errored?

```text
x-ms-request-id, path contains /openai/...      → Data plane (inference)
x-ms-correlation-request-id, ARM path           → Control plane (mgmt)
error.code = InsufficientQuota / SkuNotAvailable → Control plane
error.code = content_filter / context_length    → Data plane
```

| | Data plane | Control plane / Foundry |
|---|---|---|
| When | App calls chat / responses / images / embeddings... | Create/update/delete resources, deployments, quotas, keys |
| Endpoint | `https://<resource>.openai.azure.com/openai/...`<br>or `https://<resource>.cognitiveservices.azure.com/openai/...` | `https://management.azure.com/...` |
| Error shape | OpenAI-compatible: `{ error: { code, message, type, param, innererror } }` | ARM standard: `{ error: { code, message, target, details, innerError } }` |
| Request id | `x-ms-request-id` | `x-ms-correlation-request-id` / `x-ms-request-id` |

---

## Data plane HTTP status overview

| Status | Meaning | Retry? | Common cause |
|---:|---|---|---|
| **400** | Bad Request | ❌ | Wrong param, wrong `model`, content filtered, token over context |
| **401** | Authentication | ❌ | Wrong API key, expired AAD token, key used while local auth disabled |
| **403** | Permission Denied | ❌ | Missing RBAC role, AOAI not enabled on sub, IP firewall |
| **404** | Not Found | ❌ | Wrong deployment name, wrong endpoint region, unsupported `api-version` |
| **408** | Request Timeout | ✅ | Client ↔ gateway timeout |
| **413** | Payload Too Large | ❌ | Body > ~250KB (DALL·E / Whisper) |
| **422** | Unprocessable Entity | ❌ | Schema-valid but semantically invalid (e.g. conflicting `tools` and `function_call`) |
| **429** | Too Many Requests | ✅ | See [4 sub-types](#429-throttling--4-sub-types) |
| **500** | Internal Server Error | ✅ | Transient; retry |
| **502** | Bad Gateway | ✅ | Upstream/ingress issue |
| **503** | Service Unavailable | ✅ | Capacity exhausted / maintenance |
| **504** | Gateway Timeout | ✅ | Inference timeout downstream |

> SDKs auto-retry 408 / 429 / ≥500 / connection errors twice with backoff. `max_retries=0` to disable.

---

## 400 Bad Request breakdown

Common `error.code` values:

| `error.code` | Meaning | Fix |
|---|---|---|
| `invalid_request_error` | Generic bad parameter | Check `param` field for the offender |
| `context_length_exceeded` | prompt + `max_tokens` exceed context window | Shrink prompt / reduce `max_tokens` / use larger model |
| `model_not_found` | `model` field doesn't exist | Use **deployment name**, not model name; case-sensitive |
| `content_filter` | RAI hit | See [Content filter](#content-filter-errors-in-detail) |
| `responsibleAIPolicyViolation` | RAI policy block (common on image gen) | Same |
| `tokens_limit_reached_for_default_tier` | Free-tier token limit | Upgrade subscription / request quota |
| `OperationNotSupported` | Operation not supported on this deployment / api-version | Use the right model/API |
| `DeploymentNotFound` | Data-plane can't find the deployment | Check status |
| `invalid_api_version` | `api-version` string wrong | See [API versions](https://learn.microsoft.com/azure/ai-foundry/openai/reference) |
| *`input item ID does not belong to this connection`* | Realtime / Responses API references an item ID from a different session | Rebuild connection/session, don't reuse old IDs; see [FAQ Q17](./99-faq.md#q17-i-get-400-input-item-id-does-not-belong-to-this-connection--what-does-it-mean) |

**Typical 400 content-filter response**:

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

## 401 / 403 auth & permission

| Symptom | Likely |
|---|---|
| 401 + `Access denied due to invalid subscription key` | Wrong API key / wrong subscription |
| 401 + `Bearer token expired` | AAD token expired; `DefaultAzureCredential` should auto-refresh |
| 401 + `Local authentication is disabled` | Resource has `disableLocalAuth=true` and you're using a key — switch to AAD |
| 403, no detail | Missing RBAC: data plane needs `Cognitive Services User` or `Cognitive Services OpenAI User`; fine-tuning also needs `Cognitive Services OpenAI Contributor` |
| 403 + `IP …  is not allowed` | Firewall on; whitelist IP or use Private Endpoint |
| 403 + `Public network access is disabled` | Public access off; must use Private Endpoint |

---

## 404 not found

| Symptom | Fix |
|---|---|
| `The API deployment for this resource does not exist` | `model` must equal **deployment name**, **case-sensitive** |
| `Resource not found` | Wrong endpoint domain (region / name typo) |
| 404 on `/openai/deployments/...` | Legacy route uses `cognitiveservices.azure.com`; new v1 route uses `openai.azure.com/openai/v1/` |
| Invalid `api-version` | Operation not in that api-version; pick a GA/preview that supports it |

---

## 408 / 504 timeouts

- **408**: client → AOAI ingress timeout; usually network jitter.
- **504**: AOAI ingress → inference backend timeout; usually slow generation (long prompt / large `max_tokens` / heavy tools).

Fixes:

- Set client timeout ≥ 600s (image / heavy reasoning often > 60s).
- Use streaming (`stream=True`) to avoid large-body timeouts.
- Reduce `max_tokens` or prompt length.

---

## 413 / 422 body issues

| Status | Code | Fix |
|---|---|---|
| 413 | `RequestEntityTooLarge` | Shrink body (chunk audio, downscale image base64) |
| 422 | `invalid_request_error` (semantic) | Check `tools` + `function_call` and `response_format` + `tools` compatibility |

---

## 429 throttling — 4 sub-types

> Microsoft now officially distinguishes 4 root causes for 429.

| Sub-type | Message keyword | Root cause | Action |
|---|---|---|---|
| **TPM/RPM exceeded** | `Requests to … have been limited` / `Rate limit is exceeded` | Your traffic exceeds the deployment's allocated TPM/RPM | Bump deployment capacity, redistribute, or [request quota](https://aka.ms/oai/stuquotarequest) |
| **System capacity throttling** | `service is temporarily unable to process your request` / `System is experiencing high demand` | Shared GlobalStandard pool is under pressure | Backoff per `retry-after-ms`; if persistent, move to PTU |
| **Temporary rate-limit reduction** | Quota unchanged, but `x-ratelimit-limit-tokens` is lower than your TPM | Pay-as-you-go protective throttling, resolves within hours | Backoff + retry; PTU for stability |
| **`max_tokens` budget burn** | Throttled despite low actual token usage | Rate limit accounts for prompt + `max_tokens`, not billed tokens | Reduce `max_tokens` to realistic values |

How to tell:

- Message contains `exceeded call rate limit` → **RPM exceeded**
- Message contains `exceeded token rate limit` → **TPM exceeded**
- `x-ratelimit-limit-tokens` < your configured TPM → **temporary reduction**
- Server metric `BlockedCalls > 0` and `ServerErrors = 0` → 100% throttling

Full handling: [FAQ Q16](./99-faq.md#q16-what-error-do-i-get-when-i-exceed-rpm--tpm) and [Chapter 07](./07-latency-troubleshooting.md).

---

## 500 / 502 / 503 service-side

| Status | Meaning | Action |
|---|---|---|
| 500 | Inference backend exception | Backoff retry 2–3 times; if persistent, open a ticket with `x-ms-request-id` |
| 502 | Gateway / routing issue | Same |
| 503 | Capacity exhausted | Retry; consider region failover / PTU |

---

## Content filter errors in detail

### 4 categories × 4 severities

```
hate / sexual / violence / self_harm  ×  safe / low / medium / high
```

Default threshold = `medium` (medium and high are blocked). Configurable in Foundry → Safety + security → Content filters.

### Optional binary detectors

| Key | Meaning |
|---|---|
| `jailbreak` | Prompt-injection / jailbreak attempt |
| `protected_material_text` | Output resembles protected text |
| `protected_material_code` | Output resembles public-repo code (impacts Customer Copyright Commitment) |
| `profanity` | Profanity |
| `indirect_attack` | Indirect prompt injection |

### Block vs annotate

- **Block** (HTTP 400 + `code: content_filter`): severity above threshold; the whole response is rejected.
- **Annotate** (200 OK with `prompt_filter_results` / `content_filter_results`): content went through but is tagged — useful for audit.

### Handling pattern

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
        # Show user a friendly message; do NOT echo the original prompt back
```

---

## Control plane / Foundry error codes

> Triggered by management ops: create/update resource, change capacity, list quota, rotate keys. Standard ARM error shape.

| `error.code` | Scenario | Fix |
|---|---|---|
| `InsufficientQuota` | `az resource update --set sku.capacity=N` but subscription RPM/TPM quota is full | Foundry → Quotas → Request quota; type e.g. `Requests Per Minute - GPT 2 Image Generation` |
| `SkuNotAvailable` | Model/SKU not available in chosen region | Pick another region or SKU (GlobalStandard / DataZoneStandard / PTU) |
| `DeploymentModelNotSupported` | Invalid model+version+SKU combo | Check the [Models](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/models) matrix |
| `InvalidApiVersionParameter` | Wrong `api-version` on ARM call | Use latest `2024-10-01` or newer |
| `InvalidResourceFormat` / `InvalidResourceName` | Resource name violates rules | Alphanumeric + hyphens, 2–64 chars |
| `ResourceNotFound` | RG / resource / deployment doesn't exist or you can't see it | Check `--subscription` + RG name |
| `AuthorizationFailed` | Missing management RBAC | `Cognitive Services Contributor` or `Owner` |
| `RegionCapacityExceeded` | Region-wide capacity full | Change region or wait |
| `OperationNotAllowed` | E.g. delete a parent that still has children | Delete children first |
| `ResourceQuotaExceeded` | Subscription resource-count cap | Delete unused / open ticket |
| `ContentFilteringDisabledForResource` | Feature requires RAI but resource has it off | Re-enable RAI |
| `ModelDeprecated` | Using a deprecated model | Migrate to recommended successor |
| `MissingSubscriptionRegistration` / `SubscriptionNotRegistered` | Provider not registered | `az provider register --namespace Microsoft.CognitiveServices` |
| `ConflictingOperation` (HTTP 409) | Concurrent ops on same resource | Backoff retry |

### Foundry portal toast → actual ARM code

| UI message | ARM `error.code` |
|---|---|
| "Quota exceeded" / "Increase your quota" | `InsufficientQuota` |
| "This SKU isn't available in this region" | `SkuNotAvailable` |
| "Model not available for this version of API" | `DeploymentModelNotSupported` |
| "You don't have permission" | `AuthorizationFailed` |

### Fine-tuning specific

| Symptom | Fix |
|---|---|
| Fine-tuning API 403 | Need `Cognitive Services OpenAI Contributor` (not Reader/User) |
| Training job `failed` + file validation error | JSONL schema wrong (`messages` shape, role values) |
| `ModelDeploymentDoesNotExist` when deploying tuned model | Region/model doesn't support fine-tuning deployment; see [matrix](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/models#fine-tuning-models) |

---

## SDK exception mapping

| HTTP | Python `openai` | Node `openai` | .NET `Azure.AI.OpenAI` |
|---|---|---|---|
| 400 | `BadRequestError` | `BadRequestError` | `RequestFailedException(Status=400)` |
| 401 | `AuthenticationError` | `AuthenticationError` | same, 401 |
| 403 | `PermissionDeniedError` | `PermissionDeniedError` | same, 403 |
| 404 | `NotFoundError` | `NotFoundError` | same, 404 |
| 408 | `APITimeoutError` | `APIConnectionTimeoutError` | `OperationCanceledException` |
| 422 | `UnprocessableEntityError` | `UnprocessableEntityError` | same, 422 |
| 429 | `RateLimitError` | `RateLimitError` | same, 429 |
| ≥500 | `InternalServerError` | `InternalServerError` | same, 5xx |
| Network | `APIConnectionError` | `APIConnectionError` | `RequestFailedException` |

**Default auto-retry 2×** for: connection errors / 408 / 429 / ≥500. `max_retries=0` disables.

---

## Response headers cheat sheet

| Header | Purpose |
|---|---|
| `x-ms-request-id` | Data-plane request id — **mandatory for support tickets** |
| `x-ms-correlation-request-id` | Control-plane correlation id |
| `x-ms-error-code` | Some ARM errors include this; matches `error.code` in body |
| `Retry-After` | Seconds to wait before retry (429 / 503) |
| `retry-after-ms` | Millisecond-precision version |
| `x-ratelimit-limit-requests` | Current RPM cap |
| `x-ratelimit-remaining-requests` | Remaining RPM this minute |
| `x-ratelimit-limit-tokens` | Current TPM cap (lower than configured = temporary reduction active) |
| `x-ratelimit-remaining-tokens` | Remaining TPM this minute |
| `azureml-model-deployment` | Hit deployment (PTU / multi-deployment routing) |

---

## Minimum log fields

Whatever happens, **log these**:

```python
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

# On failure also log:
err = {
    "error_code":     body.get("error", {}).get("code"),
    "error_message":  body.get("error", {}).get("message"),
    "innererror_code":(body.get("error", {}).get("innererror") or {}).get("code"),
    "param":          body.get("error", {}).get("param"),
}
```

> Practical tip: **`x-ms-request-id` is the first thing Microsoft support will ask for** — always log it.

---

## References

- [Azure OpenAI: Manage quota & 429 types](https://learn.microsoft.com/azure/foundry/openai/how-to/quota#understanding-429-throttling-errors-and-what-to-do)
- [Azure OpenAI: Error handling — Python / JS / .NET](https://learn.microsoft.com/azure/foundry/openai/supported-languages#error-handling)
- [Azure OpenAI: Content filter overview](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/content-filter)
- [Azure OpenAI: REST API reference (errorBase / innerError)](https://learn.microsoft.com/azure/ai-foundry/openai/reference-preview)
- [Azure OpenAI: Models](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/models)
- [ARM common error responses](https://learn.microsoft.com/azure/azure-resource-manager/management/common-deployment-errors)
