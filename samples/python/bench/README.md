# Image latency benchmark scripts

Two small scripts that helped diagnose a real "gpt-image-2 is slow" report.
See [`docs/zh-CN/07-latency-troubleshooting.md`](../../../docs/zh-CN/07-latency-troubleshooting.md) /
[`docs/en-US/07-latency-troubleshooting.md`](../../../docs/en-US/07-latency-troubleshooting.md)
for the full methodology and findings.

## Files

| Script | Purpose |
|---|---|
| `bench.py` | Sequential single-thread latency. p50 / p90 / p99 / mean. |
| `bench_concurrent.py` | Async burst. Tells you whether the deployment is queueing. |

Both scripts:

- use **AAD** (`DefaultAzureCredential`) — works even when `disableLocalAuth=true`
- set `max_retries=0` so 429s surface as errors instead of hiding inside latency
- write results to `results-<tag>.json` for easy before/after diff

## Quick start

```powershell
az login
python -m venv .venv ; . .venv/Scripts/Activate.ps1
pip install --only-binary=:all: openai azure-identity

# 1. Sequential baseline
python bench.py `
    --endpoint https://<your-resource>.cognitiveservices.azure.com `
    --deployment <your-deployment> `
    --region-tag eastus2 `
    --runs 10

# 2. Concurrent burst
python bench_concurrent.py `
    --endpoint https://<your-resource>.cognitiveservices.azure.com `
    --deployment <your-deployment> `
    --region-tag eastus2 `
    --concurrency 4 `
    --quality low
```

## Reading the numbers

- `bench.py` — single call mean ≫ 30s on 1024×1024 medium ⇒ probably throttled, check server metrics.
- `bench_concurrent.py` — if c=4 wall ≈ 2–3× c=1 single, you're being queued.
- See troubleshooting doc for the 4-step self-diagnosis (latency → burst → metrics → quota).
