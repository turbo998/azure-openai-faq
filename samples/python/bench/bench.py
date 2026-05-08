"""
gpt-image-2 latency benchmark against an Azure OpenAI deployment.

Usage:
    az login                                      # uses your interactive identity
    pip install --only-binary=:all: openai azure-identity
    python bench.py \
        --endpoint https://<your-resource>.cognitiveservices.azure.com \
        --deployment <your-deployment> \
        --region-tag eastus2 \
        --runs 10

Outputs:
  - per-call wall time (s)
  - p50 / p90 / p99 / mean / min / max
  - JSON file: results-<region-tag>.json
  - sample PNG: sample-<region-tag>.png

Notes:
  * Uses AAD via DefaultAzureCredential. Works whether or not local auth is disabled.
  * SDK auto-retry is disabled so 429s surface as exceptions instead of being hidden as latency.
"""
from __future__ import annotations
import argparse
import base64
import datetime
import json
import pathlib
import statistics
import sys
import time
import traceback

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI


def percentile(values, p):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return s[f] if f == c else s[f] + (s[c] - s[f]) * (k - f)


def run(args):
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    client = AzureOpenAI(
        azure_endpoint=args.endpoint,
        azure_ad_token_provider=token_provider,
        api_version=args.api_version,
        max_retries=0,
    )

    prompt = (
        "A simple flat-design red circle on a white background, "
        "minimal vector style, centered, no text"
    )

    timings = []
    sample_b64 = None
    start_overall = time.time()

    for i in range(1, args.runs + 1):
        t0 = time.time()
        err = None
        bytes_b64 = 0
        status = "ok"
        try:
            resp = client.images.generate(
                model=args.deployment,
                prompt=prompt,
                size=args.size,
                n=1,
                quality=args.quality,
            )
            data = resp.data[0]
            if data.b64_json:
                bytes_b64 = len(data.b64_json)
                if sample_b64 is None:
                    sample_b64 = data.b64_json
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            status = "error"
        dt = time.time() - t0
        timings.append({
            "i": i,
            "elapsed_s": round(dt, 3),
            "b64_chars": bytes_b64,
            "status": status,
            "error": err,
        })
        print(
            f"  run {i:2d}/{args.runs}: {dt:6.2f}s  status={status}"
            + (f"  err={err}" if err else f"  b64_len={bytes_b64}")
        )

    elapsed_total = time.time() - start_overall
    ok = [t["elapsed_s"] for t in timings if t["status"] == "ok"]
    summary = {
        "region_tag": args.region_tag,
        "endpoint": args.endpoint,
        "deployment": args.deployment,
        "api_version": args.api_version,
        "size": args.size,
        "quality": args.quality,
        "runs": args.runs,
        "ok_runs": len(ok),
        "wall_total_s": round(elapsed_total, 3),
        "stats_s": {
            "min": round(min(ok), 3) if ok else None,
            "max": round(max(ok), 3) if ok else None,
            "mean": round(statistics.mean(ok), 3) if ok else None,
            "p50": round(percentile(ok, 0.50), 3) if ok else None,
            "p90": round(percentile(ok, 0.90), 3) if ok else None,
            "p99": round(percentile(ok, 0.99), 3) if ok else None,
        },
        "timings": timings,
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    print("\n=== SUMMARY ===")
    print(json.dumps(summary["stats_s"], indent=2))
    out = pathlib.Path(f"results-{args.region_tag}.json")
    out.write_text(json.dumps(summary, indent=2))
    print(f"Saved: {out.resolve()}")
    if sample_b64:
        png = pathlib.Path(f"sample-{args.region_tag}.png")
        png.write_bytes(base64.b64decode(sample_b64))
        print(f"Sample image: {png.resolve()}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True,
                    help="https://<resource>.cognitiveservices.azure.com (no trailing slash)")
    ap.add_argument("--deployment", required=True, help="Azure deployment name")
    ap.add_argument("--region-tag", required=True,
                    help="Free-form label baked into output filenames, e.g. eastus2")
    ap.add_argument("--api-version", default="2025-04-01-preview")
    ap.add_argument("--size", default="1024x1024")
    ap.add_argument("--quality", default="medium",
                    help="low | medium | high (model-dependent)")
    ap.add_argument("--runs", type=int, default=10)
    args = ap.parse_args()
    try:
        run(args)
    except Exception:
        traceback.print_exc()
        sys.exit(2)
