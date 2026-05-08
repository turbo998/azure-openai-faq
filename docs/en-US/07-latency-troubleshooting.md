# Troubleshooting gpt-image-2 latency

> Customers occasionally report that `gpt-image-2` is "slow in eastus2 / westus3". This chapter walks through a real diagnostic run so you can **prove with data whether you're throttled or actually slow**, then act accordingly. Scripts: [`samples/python/bench/`](../../samples/python/bench).

---

## TL;DR

If you see any of the following, it's almost certainly **subscription-level quota**, not networking or the region:

- 1024×1024 `quality=medium` typically takes 60–100s single-threaded (industry baseline is 15–30s)
- Sporadic "stuck for tens of seconds, then returns"
- App logs show **no errors**, but Azure portal `BlockedCalls` / `ClientErrors` (=429) is climbing

Skip to [§ Recommendations](#recommendations-prioritised).

---

## Why "looks slow" is usually "throttled"

The OpenAI Python / TypeScript SDKs **silently retry 429** (honoring `Retry-After`). Your client just sees one long `await` and never sees the 429. You have to look at server-side metrics:

| Where | What |
|---|---|
| Azure portal → resource → Metrics | `TotalCalls`, `SuccessfulCalls`, `BlockedCalls`, `ClientErrors`, `ServerErrors` |
| Azure portal → AI Foundry → Quotas | RPM / TPM limit per subscription + region + model |
| Client | `AzureOpenAI(..., max_retries=0)` so 429 surfaces |

> ✅ **First move: turn off SDK auto-retry**, then observe.

---

## A real measurement

`gpt-image-2` GlobalStandard, eastus2, capacity=2, AAD, `api-version=2025-04-01-preview`.

| Scenario | runs | mean | p50 | p90 | max | Notes |
|---|---|---|---|---|---|---|
| c=1, quality=medium, 1024² | 10 | **72.7s** | 66.4s | 93.9s | 102.8s | 0 errors |
| c=1, quality=low, 1024² | 5 | **28.9s** | 23.0s | 45.5s | 49.1s | 0 errors |
| c=2, quality=medium | 2 | **85.9s** | — | — | 86.3s | queueing kicks in |
| c=4, quality=low | 4 | **63.7s** | — | — | 85.0s | wall 86s, **6 × 429** |

Server metrics in the same window: `Latency` avg 37.7s / max 94.9s; `BlockedCalls=6`, `ClientErrors=6`, `ServerErrors=0` — server is 100% healthy, **every error is a 429**.

---

## Quota comparison (one real subscription)

| Model (GlobalStandard) | eastus2 RPM limit | westus3 RPM limit |
|---|---:|---:|
| gpt-image-1 | 3 | 3 |
| gpt-image-1-mini | 4 | 4 |
| gpt-image-1.5 | **9** | **9** |
| **gpt-image-2** | **2** | **2** |

> ⚠️ **As a new model, gpt-image-2 ships with a strikingly low default quota** (~2 RPM, ~1/4.5 of gpt-image-1.5). That's why "both eastus2 and westus3 are slow": both regions cap at 2.
>
> The Foundry portal may show a higher deployment capacity, but **the subscription-level quota is the real cap**. Bumping capacity above quota is rejected:
>
> ```text
> InsufficientQuota: ... bigger than the current available capacity 0.
> The current quota usage is 2 and the quota limit is 2 for quota
> "Requests Per Minute - GPT 2 Image Generation".
> ```

---

## Self-diagnosis in 4 steps

### 1. Sequential baseline (single-call latency)

```powershell
az login
python -m venv .venv ; . .venv/Scripts/Activate.ps1
pip install --only-binary=:all: openai azure-identity   # avoid building cryptography from source on Windows

python samples/python/bench/bench.py `
    --endpoint https://<your-resource>.cognitiveservices.azure.com `
    --deployment <your-deployment> `
    --region-tag eastus2 `
    --runs 10
```

Outputs `results-eastus2.json` and `sample-eastus2.png` with per-call `elapsed_s` and p50/p90/p99.

### 2. Concurrent burst (queueing test)

```powershell
python samples/python/bench/bench_concurrent.py `
    --endpoint https://<your-resource>.cognitiveservices.azure.com `
    --deployment <your-deployment> `
    --region-tag eastus2 `
    --concurrency 4 `
    --quality low
```

If c=4 wall ≈ 2–3× c=1 single, and individual elapsed times balloon, you're being queued / throttled.

### 3. Confirm via server metrics

```powershell
$resId = az cognitiveservices account show `
    --name <your-resource> --resource-group <rg> --query id -o tsv

az monitor metrics list --resource $resId `
    --metric "TotalCalls,SuccessfulCalls,BlockedCalls,ClientErrors,ServerErrors" `
    --interval PT15M --output table
```

`BlockedCalls > 0` or `ClientErrors > 0` ⇒ throttling.

### 4. Check subscription quota

```powershell
az cognitiveservices usage list --location eastus2 `
    --query "[?contains(name.value, 'gpt-image-2')].{name:name.value, used:currentValue, limit:limit}" `
    -o table

az cognitiveservices usage list --location westus3 `
    --query "[?contains(name.value, 'gpt-image-2')].{name:name.value, used:currentValue, limit:limit}" `
    -o table
```

If `limit` is tiny (2–3), there's your culprit.

---

## Recommendations (prioritised)

### Immediate (≤ 1 day)

1. **File a quota increase**: raise `OpenAI.GlobalStandard.gpt-image-2` in your target regions to ≥ peak × 1.5.
   - Azure portal → AI Foundry → **Quotas** → pick model + region → Request quota
   - Or open a support ticket; quota type = `"Requests Per Minute - GPT 2 Image Generation"`

2. **Add a client-side semaphore** equal to current capacity:
   ```python
   sem = asyncio.Semaphore(2)        # = current capacity
   async with sem:
       resp = await client.images.generate(...)
   ```

3. **Disable SDK auto-retry** to surface 429s:
   ```python
   client = AzureOpenAI(..., max_retries=0)
   ```

### Short term (≤ 1 week)

4. **Downgrade request params**: prefer `quality="low"`, drop to `512×512` when acceptable. In our test, medium→low alone moved p50 from 66s to 23s.

5. **Temporarily fall back to `gpt-image-1.5`** (≈ 4.5× the RPM in our sample subscription) as a throughput cushion until quota lands. A/B the visual quality first.

6. **Three pieces of client telemetry**:
   - `x-ms-request-id` (mandatory for Microsoft support escalations)
   - HTTP status + `Retry-After`
   - `time-to-first-byte` (image API is sync, but the field aligns with chat/responses streaming)

### Mid term (≤ 1 month)

7. **Multi-region active-active**: with quota in hand, deploy in eastus2 + westus3 + swedencentral and use client-side **hedging** (fire A, after N seconds also fire B, take whichever returns first).

8. **Evaluate PTU** (Provisioned Throughput Units): GlobalStandard is a shared pool with jitter; PTU gives dedicated throughput and a much tighter p99. Whether it pays off depends on peak/avg ratio.

9. **Move to async queue**: push generation onto Service Bus / Storage Queue, show a "generating…" placeholder. UX win typically dwarfs shaving 1–2s off the call.

---

## Re-run scripts

[`samples/python/bench/bench.py`](../../samples/python/bench/bench.py) — sequential
[`samples/python/bench/bench_concurrent.py`](../../samples/python/bench/bench_concurrent.py) — concurrent burst

Run the same commands before and after the quota bump for a clean before/after.

---

## Common misreads

| Symptom | Looks like | Actually is |
|---|---|---|
| High latency but no error logs | "Azure is slow" | SDK swallowed 429s |
| Capacity bump fails | "Portal bug" | **Subscription quota is capped**; capacity can't exceed quota.limit |
| Both eastus2 and westus3 are slow | "Network / region issue" | **Quota is per-subscription × per-region**; new models often have low defaults in both |
| `ServerErrors=0` but users complain | "App bug" | Look at `BlockedCalls` / `ClientErrors` — they're 429 |
| Adding more retries makes it worse | "Need more retries" | More retries → more throttling. Use semaphore first, then exponential backoff |

---

## References

- [Quotas and limits — Azure OpenAI](https://learn.microsoft.com/azure/ai-foundry/openai/quotas-limits)
- [Manage quota — Azure OpenAI](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/quota)
- [Provisioned throughput (PTU)](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/provisioned-throughput-onboarding)
- [Image generation — Azure OpenAI](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/dall-e)
