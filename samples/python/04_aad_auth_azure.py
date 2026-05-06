"""
04_aad_auth_azure.py — Authenticate to Azure OpenAI with Microsoft Entra ID
using DefaultAzureCredential (recommended for production).

Local dev: `az login` first.
Cloud (App Service / AKS / Function App): assign a Managed Identity and grant it
'Cognitive Services OpenAI User' on the AOAI resource.
"""
import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

load_dotenv()

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default",
)

client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    azure_ad_token_provider=token_provider,         # no api_key needed
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "preview"),
)

resp = client.chat.completions.create(
    model=os.environ["AZURE_OPENAI_GPT55_DEPLOYMENT"],
    messages=[{"role": "user", "content": "Ping over AAD!"}],
)
print(resp.choices[0].message.content)
