# 09 · gpt-image-2 First-Request 429 Troubleshooting Runbook

> Companion to **Chapter 07** (which answers *why is it slow* — usually low subscription quota). This chapter answers **"I only sent one request — why did it 429?"** This is the most common, most counter-intuitive failure mode in production for low-RPM image models like `gpt-image-2`.
>
> Adapted with attribution from Jeff Feng (Microsoft): [weirdo-github/azure-openai-gpt-image2-429-runbook](https://github.com/weirdo-github/azure-openai-gpt-image2-429-runbook).

---

## TL;DR

**There's basically no such thing as "the first request got 429."** What you see as "the first" is just the first from one worker / session. The Azure backend on that deployment has seen many more. Typical compounding causes:

1. **RPM isn't only judged on full-minute totals** — Azure also evaluates burst over **1s / 10s sub-windows**. 10 RPM ≠ 10 requests in one second.
2. **Throttling is per-deployment, shared** — multiple processes / pods / users share the same window.
3. **`Standard` / `GlobalStandard` is a shared pool** — even with unchanged quota you can hit system-capacity throttling or temporary effective-limit reductions.
4. **Two flavors of 429** with different headers:
   - `RateLimitReached`: includes `retry-after` / `x-ratelimit-reset-requests`. Honor the header.
   - `EngineOverloaded`: **may have no `retry-after`**. You must do exponential backoff + jitter yourself.
5. **SDKs auto-retry 429 by default.** One business call can become 2–3 HTTP attempts under the hood, putting "your first call" at the tail of the window.

---

## Official references

### 1. gpt-image-2 default RPM is very low

| SKU | Documented quota | Actually allocatable |
|---|---|---|
| `GlobalStandard` | 9 RPM | **Often only 2** |
| `DataZoneStandard` | 3 RPM | — |

See [Azure OpenAI quotas and limits](https://learn.microsoft.com/en-us/azure/foundry/openai/quotas-limits) and the [quota comparison in Ch.07](./07-latency-troubleshooting.md#quota-comparison-a-real-subscription-sample).

### 2. RPM is evaluated over small windows (critical)

> RPM rate limits expect that requests be evenly distributed over a one-minute period. Azure evaluates the incoming request rate over a small period of time, **typically 1 or 10 seconds**.

[Manage quota — Understanding rate limits](https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/quota?tabs=rest#understanding-rate-limits)

Recommended pacing (with ~20% safety margin):

| Deployment RPM | Smooth interval | With safety margin |
|---:|---:|---:|
| 2 RPM | 30s / req | **36s / req** |
| 9 RPM | 6.7s / req | 8s / req |
| 10 RPM | 6s / req | 7.2s / req |

### 3. Failed requests still count against the limit

Unsuccessful requests can still count toward the per-minute rate limit. Naive retries without backoff actively destroy throughput.

[Rate limit best practices](https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/quota?tabs=rest#rate-limit-best-practices) · [OpenAI Cookbook](https://developers.openai.com/cookbook/examples/how_to_handle_rate_limits)

### 4. Shared-pool protection

Azure classifies 429s into four buckets:

- Rate limit exceeded
- **System capacity throttling**
- **Temporary rate limit adjustment** (header effective limit **below** your configured quota)
- Token budget exceeded by request parameters

[Understanding 429 throttling errors](https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/quota?tabs=rest#understanding-429-throttling-errors-and-what-to-do)

### 5. SDKs auto-retry by default

Azure OpenAI Python SDK retries 429 twice by default. If you wrap Tenacity around it, **one logical call becomes 4–9 HTTP requests**. Rule: **exactly one retry layer**.

---

## Local test observations

```text
Deployment: gpt-image-2 / GlobalStandard / capacity=2
API: 2025-04-01-preview · Client: raw httpx, max_retries=0
```

### Test 1 · 6 concurrent burst + 12 probes/sec

```text
200 = 2 · 429 = 16
```

| Request | retry-after | reset | limit |
|---|---|---|---|
| burst-1  | 60 | 60 | 2 |
| probe-1  | 59 | 59 | 2 |
| probe-12 | 44 | 44 | 2 |

`retry-after` and `x-ratelimit-reset-requests` **decrement linearly** with window-remaining seconds. `x-ratelimit-limit-requests` stayed at 2 throughout. `EngineOverloaded` 429s appeared (no `retry-after`).

### Test 2 · capacity + 1 concurrency

```text
200 = 2 · 429 EngineOverloaded = 1
```

After 75s, single probe → `200`, `remaining-requests=1`. **A single 429 does not cause prolonged unavailability.**

### Test 3 · 8 concurrent + 30 sequential probes

```text
200 = 9 · 429 = 34
```

Sustained 429s **did not lower the visible limit**, and the deployment recovered after the window. But it's still a bad strategy — wastes request budget, disturbs business queues, and can trip shared-pool protections at higher traffic.

---

## Why "the first request" gets 429

| Scenario | Root cause | How to investigate |
|---|---|---|
| **A. Your first ≠ deployment's first** | Multi-process / multi-pod / multi-user sharing one deployment | Use a **cross-process shared token bucket**, not per-worker local limits |
| **B. Previous request timed out client-side but is still being processed server-side** | Client 20s timeout, image gen takes 30–80s | Log client request id; deduplicate user clicks idempotently |
| **C. SDK auto-retry hides real request count** | SDK `max_retries` ≥ 2, outer wrapper retries too | Enable SDK debug logging; set `max_retries=0` when wrapping |
| **D. Sub-window burst** | Cold start / queue recovery / simultaneous clicks | Log per-second arrival rate; use **leaky bucket** not coarse token bucket |
| **E. `EngineOverloaded` / shared pool overload** | error code `EngineOverloaded`, no `retry-after` | Failover to other region; if chronic → PTU or support ticket |
| **F. Temporary effective-limit reduction** | `x-ratelimit-limit-*` < configured quota | Shed load, wait for recovery, open ticket if persistent |

---

## Troubleshooting runbook

### Step 1 · Minimum fields to log per request

```text
timestamp_utc, deployment, region, model, status_code
error.code, error.message_prefix
retry-after, retry-after-ms
x-ratelimit-limit-requests, x-ratelimit-remaining-requests, x-ratelimit-reset-requests
x-ratelimit-limit-tokens,   x-ratelimit-remaining-tokens,   x-ratelimit-reset-tokens
x-ms-region, x-request-id, apim-request-id
client_attempt, client_timeout_s, queue_wait_ms, inflight_count
```

Each missing field rules out one fewer hypothesis.

### Step 2 · Classify the 429

| Type | Signal | Action |
|---|---|---|
| `RateLimitReached` | has `retry-after` / reset | Pause this deployment until reset |
| `EngineOverloaded` | usually no retry header; message mentions busy / too many | **Exponential backoff + jitter + region failover** |
| Temp limit adjustment | header effective limit < configured quota | Shed load, wait, ticket if persistent |
| SDK retry amplification | 1 app call → many HTTP attempts | Disable double-retry |
| Sub-window burst | minute total OK but second-level spikes | Leaky-bucket smoothing |

### Step 3 · Check configured quota & deployment capacity

```bash
az cognitiveservices account deployment show \
  -g <rg> -n <account> --deployment-name gpt-image-2 \
  --query "{deployment:name,sku:sku.name,capacity:sku.capacity,state:properties.provisioningState}" \
  -o table

az cognitiveservices usage list -l <region> \
  --query "[?name.value=='OpenAI.GlobalStandard.gpt-image-2'].{name:name.value,current:currentValue,limit:limit}" \
  -o table
```

### Step 4 · Safe reproduction

**Don't brute-force 429s**:

1. Cool down `max(retry-after, 70s)`
2. Single-request probe to confirm health
3. `capacity + 1` concurrent burst — **stop the moment a 429 appears**
4. Capture all headers
5. Wait `max(retry-after, 70s)`, single probe again

### Step 5 · When to open a support ticket

Prepare: UTC timestamps, `x-request-id`, `apim-request-id`, region/deployment/SKU/capacity, 429 codes & headers, send-rate + in-flight during window, Azure Monitor screenshots.

**Escalation signals:**

- Single-probe `EngineOverloaded` repeated
- `x-ratelimit-limit-*` **sustained below** configured quota
- Persistent 429 even after honoring `retry-after`
- Multiple regions simultaneously showing system-capacity 429

---

## Production safeguards

### 1. Cross-process shared token bucket

Don't let each process apply 10 RPM independently — use Redis / a durable queue for a **global** bucket.

```text
2 RPM deployment: 1 req / 36s
9 RPM deployment: 1 req / 8s
```

### 2. Leaky bucket, not token bucket

Token bucket allows short bursts — unfriendly to low-RPM Azure OpenAI deployments. Use leaky bucket / paced queue with **fixed dequeue interval**.

### 3. Per-deployment circuit breaker

```text
if retry-after or retry-after-ms exists:
    mark deployment unavailable until now + retry_after + jitter
else:  # EngineOverloaded
    backoff: 2s, 4s, 8s, 16s, max 60s + jitter
```

Route in-flight requests **to other healthy regions**.

### 4. Multi-region health-aware routing

5 regions × 2 RPM = global pool of 10 RPM. **Avoid round-robin** — route by `next_available_at` + in-flight + recent 429 type + p95 latency.

```text
eastus2 | westus3 | polandcentral | swedencentral | uaenorth   2 RPM each
```

### 5. UX

- Return `job_id` immediately on enqueue
- UI shows queue position + ETA
- Repeated user clicks → same `job_id`, do not create new requests
- On 429, show "queued / retrying", never the raw error

### 6. Exactly one retry layer

```python
# Option A — let SDK retry
client = AzureOpenAI(..., max_retries=5)   # do NOT wrap with Tenacity

# Option B — own the scheduler
client = AzureOpenAI(..., max_retries=0)   # do retry/breaker/region-fallback yourself
```

### 7. Handle `EngineOverloaded` separately

May lack `retry-after` → trip per-deployment breaker + immediate region failover + exponential backoff. If multiple regions overload simultaneously, **reduce global dequeue rate**.

### 8. Consider PTU

GlobalStandard's shared-pool jitter can't be fully eliminated. Latency-sensitive / mission-critical workloads should evaluate Provisioned Throughput Units.

> ⚠️ **As of 2026-05-14, gpt-image-2 PTU is not yet available.** Contact your Microsoft team for product/technical questions.

---

## Reusable probe script

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

## One-liner

> **Don't read `RPM=10` as "10 concurrent at any instant."** Treat `gpt-image-2` as a **slow queue service**: per-deployment global pacing, breaker on 429 headers, exponential backoff + cross-region fallback for header-less capacity 429s. This beats stacking retries every time.

---

## Related chapters

- [07 · gpt-image-2 latency troubleshooting](./07-latency-troubleshooting.md) — quota dimension (why it's slow)
- [08 · Error code cheat sheet](./08-error-codes.md) — 429 / `EngineOverloaded` / `InsufficientQuota`
- [99 · FAQ Q16](./99-faq.md) — RPM/TPM throttling & SDK swallowing errors

## Acknowledgement

Original empirical runbook by Jeff Feng @ Microsoft · [weirdo-github/azure-openai-gpt-image2-429-runbook](https://github.com/weirdo-github/azure-openai-gpt-image2-429-runbook).
