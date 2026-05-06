"""
01_chat_azure.py — Basic Chat Completions against Azure OpenAI.

Differences vs 01_chat_openai.py:
  - Client class: AzureOpenAI
  - azure_endpoint + api_version are required
  - `model` is the *deployment name*, not the model id
  - Header is `api-key` (handled by SDK)
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

resp = client.chat.completions.create(
    model=os.environ["AZURE_OPENAI_GPT55_DEPLOYMENT"],   # deployment name!
    messages=[
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "What is the capital of France?"},
    ],
)
print(resp.choices[0].message.content)

# Optional: inspect Azure-specific Responsible AI fields
pf = getattr(resp, "prompt_filter_results", None)
if pf:
    print("\n[Azure RAI prompt filter] severity per category:")
    for item in pf:
        print(" ", item)
