# 99 · FAQ

### Q1. Just moved my OpenAI code to Azure. Many `401`/`404`. Where to start?
1. Run [`05_validate_deployment.py`](../../samples/python/05_validate_deployment.py).
2. Header: `api-key` (Azure) vs `Authorization: Bearer` (OpenAI). Pick one.
3. `model` field: OpenAI takes a model id; Azure takes a **deployment name**.

### Q2. Why is `url` empty on Azure GPT-Image-2?
By design. Azure returns `b64_json` only. See [06](./06-gpt-image-2.md) for the Blob + SAS workaround.

### Q3. What `api-version` should I use?
- v1 route: optional, prefer explicit `preview`.
- Legacy route: latest GA (e.g. `2024-10-21`); preview features need their `*-preview`.
- Truth: [Azure OpenAI API versions](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/reference).

### Q4. How do I support both with one codebase?
Client factory + `model` env var. See [04](./04-model-vs-deployment.md#dual-platform-factory).

### Q5. Streaming on Azure crashes on first chunk
First chunk often only carries `prompt_filter_results`. Guard with `if not chunk.choices: continue`.

### Q6. Can I disable content filter?
Not entirely. You can request severity tuning in AI Foundry → Safety + security → Content filters. Highest-risk categories cannot be disabled.

### Q7. Slower than OpenAI?
Pick a closer region, consider PTU, evaluate keep-alive.

### Q8. Is `model` exact match?
Yes. **Case-sensitive**, no spaces.

### Q9. I'm using raw `requests.post()`. How do I migrate?
```diff
- url = "https://api.openai.com/v1/chat/completions"
- headers = {"Authorization": f"Bearer {OPENAI_KEY}"}
- body = {"model": "gpt-5.5", "messages": [...]}

+ url = f"{AOAI_ENDPOINT}/openai/deployments/{DEPLOYMENT}/chat/completions?api-version={API_VERSION}"
+ headers = {"api-key": AOAI_KEY}
+ body = {"messages": [...]}      # no model in body for legacy route
```

### Q10. JSON mode / Structured Outputs on both?
Yes. `response_format={"type":"json_object"}` or `{"type":"json_schema",...}` works the same. On Azure, use `2024-08-01-preview` or newer.

### Q11. Function calling / tools differences?
None of substance. Watch out: large tool outputs may re-trigger Azure RAI scans.

### Q12. Prompt works on OpenAI but Azure returns 400?
99% likely `content_filter`. Inspect `error.innererror.content_filter_result` for the category and severity.

### Q13. Can I just proxy OpenAI requests to Azure unchanged?
No. At minimum: domain+path, auth header, body `model` (legacy route drops it), and image `b64_json` handling all change. A shim can translate.

### Q14. How do I tell if a new OpenAI feature is on Azure yet?
- [Azure OpenAI Models](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/models) and [What's new](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/whats-new).
- `api-version` release notes.

### Q15. Choosing between PTU / GlobalStandard / DataZoneStandard?
- **GlobalStandard**: default, friendly price, possible bursty throttling.
- **DataZoneStandard**: EU/US data residency.
- **PTU**: predictable high throughput.
- See [deployment types](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/deployment-types).

### Q16. What error do I get when I exceed RPM / TPM?

**HTTP**: `429 Too Many Requests` with `Retry-After` (seconds) and `x-ms-request-id`:

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

**RPM vs TPM** (same HTTP code, different message):

| Cause | Message keyword |
|---|---|
| RPM exceeded (requests/min) | `exceeded call rate limit` |
| TPM exceeded (tokens/min) | `exceeded token rate limit` |

**The SDK swallows it by default** — this is the #1 trap:

| SDK | Exception type | Default behaviour |
|---|---|---|
| Python `openai` | `openai.RateLimitError` | **auto-retry 2×** with `Retry-After` backoff before raising |
| Node `openai` | `OpenAI.RateLimitError` | auto-retry 2× |
| .NET `Azure.AI.OpenAI` | `RequestFailedException` (Status=429) | Azure.Core retry policy |
| Raw REST | `response.status_code == 429` | Up to you |

⚠️ **No error in app logs but users say it's slow** = SDK is retrying 429s. Turn that off so they surface:

```python
from openai import AzureOpenAI, RateLimitError

client = AzureOpenAI(..., max_retries=0)

try:
    resp = client.images.generate(model="my-deployment", ...)
except RateLimitError as e:
    retry_after = int(e.response.headers.get("retry-after", "10"))
    request_id  = e.response.headers.get("x-ms-request-id")
    logger.warning("AOAI 429 rid=%s retry_after=%ds", request_id, retry_after)
    # decide whether to retry, queue, or downgrade
```

**Confirm on the server side** (Azure portal → resource → Metrics): `BlockedCalls > 0` or `ClientErrors > 0`, `ServerErrors = 0` ⇒ throttling.

**Don't confuse with these two**:
- **Capacity shortage** (control plane, when changing a deployment): error code `InsufficientQuota`, message `quota usage is N and the quota limit is N`. That's a subscription quota cap, not a runtime rate limit.
- **Token over context window**: `400 BadRequest` + `context_length_exceeded`, not 429.

Full diagnostic flow (baseline → burst → metrics → quota) in [07 · Latency troubleshooting](./07-latency-troubleshooting.md).

### Q17. I get `400 input item ID does not belong to this connection` — what does it mean?

This error occurs when using the **Realtime API** or **Responses API** (with `previous_response_id` / `input` referencing existing items), and you reference an `item_id` that **does not belong to the current session/connection**.

**Common causes**:
1. **Session mix-up**: Client code reuses an `item_id` from a previous WebSocket connection or API session that the server no longer recognises.
2. **Reconnection without reset**: After a Realtime API WebSocket disconnects and reconnects, all item IDs from the old session are invalid — but the client still sends them in `conversation.item.create` or `response.create`.
3. **Cross-session leakage**: Item IDs from one concurrent connection are accidentally passed to another.
4. **SDK / framework bug**: Some SDKs or middleware layers (e.g. OpenClaw's github-copilot provider) have known intermittent bugs that leak item IDs across sessions.

**Troubleshooting steps**:
1. **Verify item ID origin**: Check that every `item_id` / `input` ID in your request body actually came from the **same** connection/session.
2. **Check connection lifecycle**: After WebSocket reconnection, did you clear your local item list?
3. **Add logging**: Log `session.id` on every new connection; compare it when referencing items.
4. **Restart / rebuild session**: The quickest fix is to discard old session state and start a fresh connection.
5. **Upgrade SDK**: If using OpenAI Python/Node SDK or a third-party framework, upgrade to the latest version.

**For OpenClaw users**:
```bash
# Restart gateway to clear session state
openclaw gateway restart

# If still reproducible, clear session cache then restart
openclaw sessions clear
openclaw gateway restart

# Make sure OpenClaw is up to date
npm update -g openclaw
```

> See also: [OpenClaw Issue #66424](https://github.com/openclaw/openclaw/issues/66424)
