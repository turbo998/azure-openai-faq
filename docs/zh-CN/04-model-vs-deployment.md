# 04 · `model` 字段：模型名 vs 部署名

## 核心差异
| 平台 | `model` 字段值 | 来源 |
|---|---|---|
| OpenAI | 模型 ID，如 `"gpt-5.5"`、`"gpt-image-2"` | 固定，[Model 列表](https://platform.openai.com/docs/models) |
| Azure OpenAI | **Deployment 名**，由你创建 deployment 时指定 | Azure AI Foundry 门户 / `az cognitiveservices account deployment create` |

## 为什么 Azure 用 deployment 而不是模型名
- 一个资源里可以为同一模型创建多个 deployment（不同配额、不同内容过滤策略、不同区域）。
- 同一应用迁移环境（dev / staging / prod）时只换 deployment，模型版本不影响。
- Azure 通过 deployment 隔离配额（TPM / RPM / PTU）。

## 创建 Deployment（CLI 版）
```bash
az cognitiveservices account deployment create \
  --resource-group myRg \
  --name my-aoai \
  --deployment-name my-gpt55 \
  --model-name gpt-5.5 \
  --model-version "2026-04-01" \
  --model-format OpenAI \
  --sku-name "GlobalStandard" \
  --sku-capacity 50
```

之后调用时：
```python
client.chat.completions.create(
    model="my-gpt55",      # ← 这里是 deployment 名
    messages=[...],
)
```

## 推荐做法：把名字塞进环境变量
代码不要硬编码 deployment 名，否则换环境就要改代码：

```python
import os
DEPLOYMENT_GPT55 = os.environ["AZURE_OPENAI_GPT55_DEPLOYMENT"]
DEPLOYMENT_IMAGE = os.environ["AZURE_OPENAI_IMAGE_DEPLOYMENT"]
```

## 调试：验证 deployment 名是否正确
```bash
az cognitiveservices account deployment list \
  --resource-group myRg \
  --name my-aoai \
  --query "[].{name:name, model:properties.model.name, version:properties.model.version}" -o table
```

或运行 [`samples/python/05_validate_deployment.py`](../../samples/python/05_validate_deployment.py)：
```bash
python 05_validate_deployment.py
```

## 常见错误
| 报错 | 原因 | 修复 |
|---|---|---|
| `404 The API deployment for this resource does not exist` | `model` 写的是模型名而非 deployment 名 | 改为 deployment 名 |
| `DeploymentNotFound` | deployment 名拼错 / 大小写错 | 用 CLI 列出确认 |
| `OperationNotSupported` | 模型不支持当前 endpoint（如对图像 deployment 调 chat） | 用对应 endpoint |
| `429 ... ResourceExhausted` | deployment 配额（TPM）打满 | 调高 `sku-capacity` 或拆 deployment |

## 同一应用兼容两边的小技巧
```python
def make_client():
    if os.getenv("USE_AZURE", "false").lower() == "true":
        from openai import AzureOpenAI
        client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        )
        chat_model = os.environ["AZURE_OPENAI_GPT55_DEPLOYMENT"]
    else:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        chat_model = "gpt-5.5"
    return client, chat_model
```
