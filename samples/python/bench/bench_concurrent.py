"""
Concurrent latency probe — fire N requests in parallel and see if Azure
queues them (a strong signal that subscription quota / deployment capacity
is the bottleneck, not raw model speed).

Usage:
    az login
    pip install --only-binary=:all: openai azure-identity
    python bench_concurrent.py \
        --endpoint https://<your-resource>.cognitiveservices.azure.com \
        --deployment <your-deployment> \
        --region-tag eastus2 \
        --concurrency 4 \
        --quality low

Notes:
  * SDK auto-retry is disabled. 429s surface as errors with status -- that's the point.
  * If c=4 wall ~= 2-3x c=1 single, you're being queued.
"""
from __future__ import annotations
import argparse
import asyncio
import datetime
import json
import pathlib
import statistics
import time

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI


async def one(client, deployment, size, quality, idx):
    t0 = time.time()
    try:
        r = await client.images.generate(
            model=deployment,
            prompt=f"A flat design red circle #{idx}",
            size=size,
            n=1,
            quality=quality,
        )
        return {
            "i": idx,
            "elapsed_s": round(time.time() - t0, 3),
            "status": "ok",
            "b64_len": len(r.data[0].b64_json or ""),
        }
    except Exception as e:
        return {
            "i": idx,
            "elapsed_s": round(time.time() - t0, 3),
            "status": "error",
            "error": f"{type(e).__name__}: {e}",
        }


async def main(args):
    tp = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    client = AsyncAzureOpenAI(
        azure_endpoint=args.endpoint,
        azure_ad_token_provider=tp,
        api_version=args.api_version,
        max_retries=0,
    )
    print(f"=== Concurrent burst: {args.concurrency} parallel calls ===")
    t0 = time.time()
    results = await asyncio.gather(*[
        one(client, args.deployment, args.size, args.quality, i)
        for i in range(1, args.concurrency + 1)
    ])
    wall = time.time() - t0
    for r in sorted(results, key=lambda x: x["i"]):
        print(
            f"  call {r['i']:2d}: {r['elapsed_s']:6.2f}s  status={r['status']}"
            + (f"  err={r.get('error')}" if r.get('error') else "")
        )
    ok = [r["elapsed_s"] for r in results if r["status"] == "ok"]
    print(f"\nWall (gather): {wall:.2f}s  |  ok={len(ok)}/{args.concurrency}")
    if ok:
        print(
            f"min={min(ok):.2f}s  max={max(ok):.2f}s  "
            f"mean={statistics.mean(ok):.2f}s"
        )
    out = pathlib.Path(
        f"results-concurrent-{args.region_tag}-c{args.concurrency}.json"
    )
    out.write_text(json.dumps({
        "wall_s": round(wall, 3),
        "concurrency": args.concurrency,
        "endpoint": args.endpoint,
        "deployment": args.deployment,
        "size": args.size,
        "quality": args.quality,
        "results": results,
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }, indent=2))
    print(f"Saved: {out.resolve()}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--deployment", required=True)
    ap.add_argument("--region-tag", required=True)
    ap.add_argument("--api-version", default="2025-04-01-preview")
    ap.add_argument("--size", default="1024x1024")
    ap.add_argument("--quality", default="medium")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()
    asyncio.run(main(args))
