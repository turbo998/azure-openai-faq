# 03 · Endpoint 与 api-version

## OpenAI：唯一 base URL
```
https://api.openai.com/v1/<path>
```
无版本概念，新特性靠请求体新字段灰度。

## Azure OpenAI：两种路由并存

### A. v1 新路由（推荐，2025 起）
```
https://{resource}.openai.azure.com/openai/v1/<path>
```
- 与 OpenAI 的 path 风格保持一致（如 `/chat/completions`、`/responses`、`/images/generations`）。
- `api-version` 可省略；显式建议传 `preview`。
- SDK 中通过 `azure_endpoint` 指定到 *资源根*（不要带 `/openai/v1`，SDK 会自动拼）。

### B. 旧 deployments 路由（长期兼容）
```
https://{resource}.openai.azure.com/openai/deployments/{deployment}/<path>?api-version={version}
```
- 必须传 `api-version`（GA 版如 `2024-10-21`，预览版如 `2025-01-01-preview`）。
- path 中 `{deployment}` 是部署名。

## 在 SDK 中如何分别使用

### Python — 默认即 v1 行为
```python
from openai import AzureOpenAI

client = AzureOpenAI(
    azure_endpoint="https://my-aoai.openai.azure.com",
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version="preview",   # 或 GA 版本
)
resp = client.chat.completions.create(
    model="my-gpt55-deployment",   # 部署名
    messages=[{"role": "user", "content": "hi"}],
)
```

### TypeScript
```ts
import { AzureOpenAI } from "openai";

const client = new AzureOpenAI({
  endpoint: "https://my-aoai.openai.azure.com",
  apiKey: process.env.AZURE_OPENAI_API_KEY!,
  apiVersion: "preview",
});
const resp = await client.chat.completions.create({
  model: "my-gpt55-deployment",
  messages: [{ role: "user", content: "hi" }],
});
```

## cURL 对照

OpenAI：
```bash
curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.5","messages":[{"role":"user","content":"hi"}]}'
```

Azure OpenAI（旧 deployments 路由）：
```bash
curl "$AZURE_OPENAI_ENDPOINT/openai/deployments/$AZURE_OPENAI_GPT55_DEPLOYMENT/chat/completions?api-version=$AZURE_OPENAI_API_VERSION" \
  -H "api-key: $AZURE_OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hi"}]}'
# ↑ 注意：body 里没有 model 字段，model 体现在 URL 的 deployment 上
```

Azure OpenAI（v1 新路由）：
```bash
curl "$AZURE_OPENAI_ENDPOINT/openai/v1/chat/completions" \
  -H "api-key: $AZURE_OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"my-gpt55-deployment","messages":[{"role":"user","content":"hi"}]}'
```

## 常见踩坑
1. **endpoint 末尾带 `/`** — SDK 拼接出双斜杠，部分代理会 404。统一不带尾斜杠。
2. **endpoint 写成 `https://my-aoai.cognitiveservices.azure.com`** — 这是 Cognitive Services 的通用 endpoint，对 OpenAI 资源用 `*.openai.azure.com`。
3. **新路由代码里仍硬编码 `/openai/deployments/...`** — 双拼接出 404，改用 SDK 让它内部 route。
4. **api-version 跟 SDK 版本不匹配** — 新参数（如 reasoning effort）需要更新到对应 preview API 版本，且 SDK 包要够新。
