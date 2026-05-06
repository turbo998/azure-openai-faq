# 01 · 平台差异总览

## 一句话定位
- **OpenAI**：由 OpenAI 直营的多租户 SaaS，serverless，开箱即用。
- **Azure OpenAI**：由 Microsoft 在 Azure 上托管 OpenAI 模型，需先创建 *资源（resource）* 和 *部署（deployment）*，享受 Azure 的认证、网络、合规与计费体系。

## 核心差异分类

### 1. 资源模型
| 项 | OpenAI | Azure OpenAI |
|---|---|---|
| 创建步骤 | 注册账号 → 拿 API Key | 创建订阅 → 创建 Azure OpenAI / AI Foundry 资源 → 创建模型 deployment |
| 计费 | OpenAI 账户 | Azure 订阅（PAYG / PTU） |
| 区域 | 全球统一 | 选择 region；部分模型仅特定 region 可用 |

### 2. API 路径
- OpenAI: `https://api.openai.com/v1/{path}`
- Azure（v1 新路由，2025 起推荐）：`https://{resource}.openai.azure.com/openai/v1/{path}`
- Azure（旧 deployments 路由，仍长期支持）：`https://{resource}.openai.azure.com/openai/deployments/{deployment}/{path}?api-version={version}`

### 3. 认证
| 方式 | OpenAI | Azure OpenAI |
|---|---|---|
| API Key | ✅ Header `Authorization: Bearer …` | ✅ Header `api-key: …` |
| AAD / Microsoft Entra ID | ❌ | ✅ Header `Authorization: Bearer <AAD token>`，scope `https://cognitiveservices.azure.com/.default` |
| Managed Identity | ❌ | ✅（推荐生产） |

### 4. `model` 字段语义
- OpenAI：直接传模型 ID，如 `"gpt-5.5"`、`"gpt-image-2"`。
- Azure OpenAI：传 **deployment 名**（创建 deployment 时由你指定），可能与模型 ID 不同。例如你可以把 `gpt-5.5` 模型部署成 `my-prod-llm`，调用时 `model="my-prod-llm"`。

### 5. 内容过滤 / Responsible AI
- OpenAI：调用 [Moderations API](https://platform.openai.com/docs/guides/moderation) 是单独的端点。
- Azure OpenAI：内建。每个 chat / image 响应都会附带 `prompt_filter_results` 与 `content_filter_results`，可能直接 `400` 阻断。可向支持团队申请修改严重等级阈值。

### 6. SDK 差异
- 官方 `openai` Python / Node SDK **同时**支持两边：
  - Python：`from openai import OpenAI, AzureOpenAI`
  - Node：`import OpenAI, { AzureOpenAI } from "openai";`
- 业务代码可通过工厂函数复用大部分逻辑，仅 client 初始化和 `model` 字段不同。

### 7. 流式 / Tools / Structured Outputs
- 大部分接口（Chat、Responses、tools、JSON schema、function calling、streaming）在两边一致。
- 个别新预览特性可能 OpenAI 先上、Azure 滞后数周或反之；以 `api-version` 为准。

## 迁移路线建议
1. 先跑 [`05_validate_deployment.py`](../../samples/python/05_validate_deployment.py) 确认你的 deployment 名 + endpoint + api-version 三件套能通。
2. 把代码里 `OpenAI()` 替换为 `AzureOpenAI(azure_endpoint=…, api_version=…, api_key=…)`。
3. 把 `model="gpt-5.5"` 替换为 `model=os.environ["AZURE_OPENAI_GPT55_DEPLOYMENT"]`。
4. 处理 GPT-Image-2 返回字段差异（见 [06](./06-gpt-image-2.md)）。
5. 上线前换成 AAD / Managed Identity，关闭/轮换 Key。
