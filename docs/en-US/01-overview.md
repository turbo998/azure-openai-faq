# 01 · Platform Overview

## In one line
- **OpenAI**: OpenAI's own multi-tenant SaaS. Serverless, ready out of the box.
- **Azure OpenAI**: Microsoft hosts OpenAI models on Azure. You first create a *resource* and a *deployment*, then get Azure's auth, networking, compliance and billing on top.

## Differences at a glance

### 1. Resource model
| Item | OpenAI | Azure OpenAI |
|---|---|---|
| Onboarding | Sign up → grab API key | Subscription → create AOAI / AI Foundry resource → create model deployment |
| Billing | OpenAI account | Azure subscription (PAYG / PTU) |
| Region | Global | Region-bound; some models only in select regions |

### 2. API path
- OpenAI: `https://api.openai.com/v1/{path}`
- Azure (v1 route, recommended): `https://{resource}.openai.azure.com/openai/v1/{path}`
- Azure (legacy `deployments` route, still supported): `https://{resource}.openai.azure.com/openai/deployments/{deployment}/{path}?api-version={version}`

### 3. Auth
| Method | OpenAI | Azure OpenAI |
|---|---|---|
| API Key | ✅ `Authorization: Bearer …` | ✅ `api-key: …` |
| Microsoft Entra ID (AAD) | ❌ | ✅ scope `https://cognitiveservices.azure.com/.default` |
| Managed Identity | ❌ | ✅ recommended for prod |

### 4. The `model` field
- OpenAI: model id, e.g. `"gpt-5.5"`, `"gpt-image-2"`.
- Azure OpenAI: **deployment name** you chose at deploy time. Could be anything (`my-prod-llm`).

### 5. Content filter / Responsible AI
- OpenAI: separate [Moderations API](https://platform.openai.com/docs/guides/moderation).
- Azure OpenAI: built-in. Every chat/image response carries `prompt_filter_results` and `content_filter_results`; can hard-block with `400`.

### 6. SDKs
The official `openai` Python / Node SDK supports both:
- Python: `from openai import OpenAI, AzureOpenAI`
- Node: `import OpenAI, { AzureOpenAI } from "openai";`

### 7. Streaming / tools / structured outputs
Largely identical. Some preview features may land sooner on one side. Pin via `api-version`.

## Migration playbook
1. Run [`samples/python/05_validate_deployment.py`](../../samples/python/05_validate_deployment.py).
2. Replace `OpenAI()` with `AzureOpenAI(azure_endpoint=…, api_version=…, api_key=…)`.
3. Replace `model="gpt-5.5"` with `model=os.environ["AZURE_OPENAI_GPT55_DEPLOYMENT"]`.
4. Handle GPT-Image-2 response field difference (see [06](./06-gpt-image-2.md)).
5. For prod, switch to Managed Identity and disable local auth.
