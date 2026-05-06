# 02 · 认证差异

## OpenAI：仅 API Key

```http
POST https://api.openai.com/v1/chat/completions
Authorization: Bearer sk-xxxxxxxx
Content-Type: application/json
```

Python：
```python
from openai import OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
```

## Azure OpenAI：API Key 或 AAD（推荐 AAD）

### 方式 A：API Key（最快）
```http
POST https://my-aoai.openai.azure.com/openai/v1/chat/completions
api-key: <your-key>
Content-Type: application/json
```

⚠️ 注意：**`api-key` 头**，不是 `Authorization: Bearer`。

```python
from openai import AzureOpenAI
client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
)
```

### 方式 B：Microsoft Entra ID（AAD Bearer Token）
```http
Authorization: Bearer <AAD access token, scope https://cognitiveservices.azure.com/.default>
```

调用方需要被授予资源的 RBAC 角色：**Cognitive Services OpenAI User**（推理）/ **Cognitive Services OpenAI Contributor**（管理 deployment）。

Python（推荐 `DefaultAzureCredential`，本地用 `az login`，云上自动用 Managed Identity）：
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

TypeScript：
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

## RBAC 配置（一次性）
```bash
az role assignment create \
  --assignee <user-or-mi-objectId> \
  --role "Cognitive Services OpenAI User" \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<aoai-name>
```

## 常见错误
| 报错 | 原因 |
|---|---|
| `401 Access denied due to invalid subscription key` | 用了错误的 Key（订阅 Key vs 资源 Key），或贴错 endpoint |
| `401 PermissionDenied` (AAD) | 缺少 RBAC 角色，或 token 用了错误的 audience/scope |
| `Authorization` 与 `api-key` 同时发 | 选其一即可，混用偶现 401 |
| 本地 AAD 401 | 先 `az login`，再确认 `az account show` 是目标 tenant |

## 安全建议
- **生产禁止用 API Key**；走 Managed Identity。
- Key 必须经 Key Vault，不进代码、不进 git。
- 启用资源的 *Disable local auth*（仅 AAD），强制 AAD。
