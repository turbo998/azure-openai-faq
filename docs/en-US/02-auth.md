# 02 · Authentication

## OpenAI: API key only
```http
POST https://api.openai.com/v1/chat/completions
Authorization: Bearer sk-xxxxxxxx
```
```python
from openai import OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
```

## Azure OpenAI: API key OR AAD (AAD recommended)

### Option A: API key
```http
POST https://my-aoai.openai.azure.com/openai/v1/chat/completions
api-key: <your-key>
```
⚠️ Header is **`api-key`**, not `Authorization: Bearer`.

```python
from openai import AzureOpenAI
client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
)
```

### Option B: Microsoft Entra ID (AAD bearer)
Required RBAC: **Cognitive Services OpenAI User** (inference) / **... Contributor** (manage deployments).

```python
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default",
)
client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    azure_ad_token_provider=token_provider,
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
)
```

```ts
import { DefaultAzureCredential, getBearerTokenProvider } from "@azure/identity";
import { AzureOpenAI } from "openai";

const azureADTokenProvider = getBearerTokenProvider(
  new DefaultAzureCredential(),
  "https://cognitiveservices.azure.com/.default"
);
const client = new AzureOpenAI({
  endpoint: process.env.AZURE_OPENAI_ENDPOINT!,
  apiVersion: process.env.AZURE_OPENAI_API_VERSION!,
  azureADTokenProvider,
});
```

## RBAC setup (one-time)
```bash
az role assignment create \
  --assignee <user-or-mi-objectId> \
  --role "Cognitive Services OpenAI User" \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<aoai-name>
```

## Common errors
| Error | Cause |
|---|---|
| `401 Access denied due to invalid subscription key` | Wrong key or wrong endpoint |
| `401 PermissionDenied` (AAD) | Missing RBAC role, or wrong audience |
| Both `Authorization` and `api-key` sent | Use one, not both |
| Local AAD 401 | `az login` first; check `az account show` is the right tenant |

## Best practices
- **No API keys in production**; use Managed Identity.
- Keys go to Key Vault, never source.
- Enable resource's *Disable local auth* to enforce AAD.
