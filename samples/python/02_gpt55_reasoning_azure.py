"""
02_gpt55_reasoning_azure.py — GPT-5.5 with reasoning_effort + streaming on Azure OpenAI.

Differences:
  - AzureOpenAI client + api_version
  - model = deployment name
  - First stream chunk on Azure may only carry prompt_filter_results
    -> guard with `if not chunk.choices: continue`
"""
import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "preview"),
)

try:
    stream = client.chat.completions.create(
        model=os.environ["AZURE_OPENAI_GPT55_DEPLOYMENT"],
        reasoning_effort="medium",
        messages=[
            {"role": "user", "content": "Explain why the sky is blue, briefly."},
        ],
        stream=True,
    )
    for chunk in stream:
        if not chunk.choices:    # ← Azure RAI-only chunk; skip
            continue
        delta = chunk.choices[0].delta.content or ""
        print(delta, end="", flush=True)
    print()
except Exception as e:
    # Azure surfaces RAI blocks as 400 error with code 'content_filter'
    print(f"\n[ERROR] {type(e).__name__}: {e}")
