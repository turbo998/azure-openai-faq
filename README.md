# Azure OpenAI FAQ — OpenAI 迁移到 Azure OpenAI 实战手册

> 面向合作伙伴/开发者的迁移与调试速查仓库。重点覆盖 **GPT-5.5** 与 **GPT-Image-2** 在 OpenAI 原生 API 与 Azure OpenAI 之间的差异、踩坑和可直接运行的对照示例。
>
> Language: 中文（主） · [English](./docs/en-US/01-overview.md)

---

## 🚀 30 秒速览：OpenAI vs Azure OpenAI

| 维度 | OpenAI | Azure OpenAI |
|---|---|---|
| Endpoint | `https://api.openai.com/v1` | `https://{resource}.openai.azure.com/openai/v1/`（v1 新路由）<br>或 `…/openai/deployments/{deployment}/...?api-version=…`（旧 deployments 路由） |
| 认证 Header | `Authorization: Bearer <key>` | `api-key: <key>` **或** `Authorization: Bearer <AAD token>` |
| `model` 字段值 | 模型名（如 `gpt-5.5`） | **部署名（deployment name）**，可能 ≠ 模型名 |
| `api-version` | 无 | 旧路由必填；v1 新路由可省略，建议显式 `preview` |
| GPT-Image-2 返回格式 | `url` 或 `b64_json` | **仅 `b64_json`**（`response_format=url` 不支持）|
| 内容审核 | 独立 Moderations API | 内建 RAI，响应内含 `prompt_filter_results` / `content_filter_results` |
| AAD / Managed Identity | ❌ | ✅ 推荐生产使用 |
| 区域 / 部署 | 全球 serverless | 区域受限，需先在门户/CLI 创建 deployment |
| Python SDK 入口 | `OpenAI()` | `AzureOpenAI(azure_endpoint=…, api_version=…, api_key=…)` |
| JS SDK 入口 | `new OpenAI({ apiKey })` | `new AzureOpenAI({ endpoint, apiVersion, apiKey })` |

> ⚠️ **最常见的 1 个坑**：Azure OpenAI 的 GPT-Image-2 **不会返回 `url` 字段**。直接把 OpenAI 端的 `response.data[0].url` 代码搬过来一定 `KeyError`/`undefined`。请改读 `b64_json` 后自行落盘或上传到 Blob 生成 SAS URL。详见 [`docs/zh-CN/06-gpt-image-2.md`](./docs/zh-CN/06-gpt-image-2.md)。

---

## 📚 文档导航

### 中文（zh-CN）
1. [平台差异总览](./docs/zh-CN/01-overview.md)
2. [认证：API Key vs AAD / Managed Identity](./docs/zh-CN/02-auth.md)
3. [Endpoint 与 api-version](./docs/zh-CN/03-endpoint.md)
4. [`model` 字段：模型名 vs 部署名（含验证脚本）](./docs/zh-CN/04-model-vs-deployment.md)
5. [GPT-5.5 对照（Chat / Responses / reasoning / stream）](./docs/zh-CN/05-gpt-5.5.md)
6. [GPT-Image-2 对照（含 url 不支持的 workaround）](./docs/zh-CN/06-gpt-image-2.md)
7. [gpt-image-2 延迟排查实战（含基准脚本）](./docs/zh-CN/07-latency-troubleshooting.md)
8. [错误码速查（Data Plane + Foundry Control Plane）](./docs/zh-CN/08-error-codes.md)
9. [gpt-image-2 首请求 429 排障 Runbook（实测）](./docs/zh-CN/09-gpt-image-2-429-runbook.md)
10. [高频踩坑 FAQ](./docs/zh-CN/99-faq.md)

### English (en-US)
- [Overview](./docs/en-US/01-overview.md) · [Auth](./docs/en-US/02-auth.md) · [Endpoint](./docs/en-US/03-endpoint.md) · [Model vs Deployment](./docs/en-US/04-model-vs-deployment.md) · [GPT-5.5](./docs/en-US/05-gpt-5.5.md) · [GPT-Image-2](./docs/en-US/06-gpt-image-2.md) · [Latency troubleshooting](./docs/en-US/07-latency-troubleshooting.md) · [Error codes](./docs/en-US/08-error-codes.md) · [gpt-image-2 429 runbook](./docs/en-US/09-gpt-image-2-429-runbook.md) · [FAQ](./docs/en-US/99-faq.md)

---

## 🧪 Sample Code（OpenAI ↔ Azure OpenAI 对照）

每个场景在 [`samples/python/`](./samples/python) 与 [`samples/typescript/`](./samples/typescript) 各提供 OpenAI、Azure OpenAI 两个版本，文件名后缀 `_openai` / `_azure`：

| # | 场景 | Python | TypeScript |
|---|---|---|---|
| 01 | Chat Completions 基本调用 | `01_chat_*.py` | `01_chat_*.ts` |
| 02 | GPT-5.5 reasoning + 流式 | `02_gpt55_reasoning_*.py` | `02_gpt55_reasoning_*.ts` |
| 03 | GPT-Image-2 图像生成（Azure 含 b64→Blob URL workaround） | `03_image_*.py` | `03_image_*.ts` |
| 04 | AAD / Managed Identity 认证（仅 Azure） | `04_aad_auth_azure.py` | `04_aad_auth_azure.ts` |
| 05 | 部署名验证脚本（仅 Azure） | `05_validate_deployment.py` | `05_validate_deployment.ts` |
| 06 | gpt-image-2 延迟基准（顺序 + 并发） | [`bench/`](./samples/python/bench) | — |

---

## ⚙️ 快速开始

```bash
# 1. 克隆
git clone https://github.com/turbo998/azure-openai-faq.git
cd azure-openai-faq

# 2. 配置环境变量
cp .env.example .env
# 用编辑器填入你的 Key / Endpoint / Deployment 名

# 3. Python
cd samples/python
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -r requirements.txt
python 01_chat_azure.py

# 4. TypeScript
cd ../typescript
npm install
npx tsx 01_chat_azure.ts
```

---

## 🤝 贡献

欢迎提 Issue / PR 补充新坑。PR 时请同步更新中英文档。

## 📝 License

[MIT](./LICENSE)

---

> 本仓库内容综合自 [Microsoft Learn](https://learn.microsoft.com/zh-cn/azure/ai-foundry/openai/) 与 [OpenAI Platform Docs](https://platform.openai.com/docs)。如发现差异已更新，欢迎提 Issue。
