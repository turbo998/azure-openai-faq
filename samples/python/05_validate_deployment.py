"""
05_validate_deployment.py — Quick sanity check for an Azure OpenAI deployment.

Verifies:
  1. AZURE_OPENAI_ENDPOINT is reachable.
  2. Auth (api-key) works.
  3. The deployment names you set actually exist & are callable.

Usage:
    cp ../.env.example ../.env   # then edit
    python 05_validate_deployment.py
"""
import os, sys
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

REQUIRED = [
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_GPT55_DEPLOYMENT",
]
missing = [k for k in REQUIRED if not os.environ.get(k)]
if missing:
    print(f"❌ Missing env vars: {missing}")
    sys.exit(1)

endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
print(f"Endpoint: {endpoint}")
print(f"API ver : {os.environ['AZURE_OPENAI_API_VERSION']}")
print(f"Chat dep: {os.environ['AZURE_OPENAI_GPT55_DEPLOYMENT']}")
print(f"Img  dep: {os.environ.get('AZURE_OPENAI_IMAGE_DEPLOYMENT', '(not set)')}")
print("---")

client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
)

# 1. Chat deployment
try:
    r = client.chat.completions.create(
        model=os.environ["AZURE_OPENAI_GPT55_DEPLOYMENT"],
        messages=[{"role": "user", "content": "Reply with exactly the word: OK"}],
        max_tokens=5,
    )
    print(f"✅ Chat deployment OK → {r.choices[0].message.content!r}")
except Exception as e:
    print(f"❌ Chat deployment failed: {type(e).__name__}: {e}")

# 2. Image deployment (optional)
img_dep = os.environ.get("AZURE_OPENAI_IMAGE_DEPLOYMENT")
if img_dep:
    try:
        ir = client.images.generate(
            model=img_dep,
            prompt="A red dot on a white background",
            size="1024x1024",
            n=1,
        )
        has_b64 = bool(ir.data and ir.data[0].b64_json)
        has_url = bool(ir.data and ir.data[0].url)
        print(f"✅ Image deployment OK → b64_json={has_b64} url={has_url}")
        if has_url:
            print("   ⚠️ Unusual: Azure normally does not return url. Verify SDK/route.")
        if not has_b64:
            print("   ❌ Expected b64_json on Azure but got none.")
    except Exception as e:
        print(f"❌ Image deployment failed: {type(e).__name__}: {e}")
else:
    print("ℹ️  Skipped image deployment check (AZURE_OPENAI_IMAGE_DEPLOYMENT not set).")
