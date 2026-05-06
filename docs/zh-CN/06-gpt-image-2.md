# 06 · GPT-Image-2 在 Azure 上的限制与对照

> ⚠️ **最重要的一条**：Azure OpenAI 的 GPT-Image-2 **不支持返回 `url`，只返回 `b64_json`**。任何在 OpenAI 端依赖 `response.data[0].url` 的代码搬过来都会 break。
>
> 来源：Microsoft Learn 图像生成模型与能力章节（Azure 端响应仅含 `b64_json` 字段）。

## 1. 请求差异

### OpenAI
```python
from openai import OpenAI
client = OpenAI()
img = client.images.generate(
    model="gpt-image-2",
    prompt="A cyberpunk cat playing piano",
    size="1024x1024",
    n=1,
    response_format="url",      # ✅ OpenAI 支持
)
print(img.data[0].url)          # ✅ 直接拿 URL
```

### Azure OpenAI
```python
from openai import AzureOpenAI
client = AzureOpenAI(...)
img = client.images.generate(
    model=os.environ["AZURE_OPENAI_IMAGE_DEPLOYMENT"],   # 部署名
    prompt="A cyberpunk cat playing piano",
    size="1024x1024",
    n=1,
    # ❌ 不要传 response_format="url"，会被忽略或报错
)
b64 = img.data[0].b64_json       # ✅ 仅此字段
```

## 2. 字段对照表
| 字段 | OpenAI | Azure OpenAI |
|---|---|---|
| `data[*].url` | ✅ 默认或显式 `response_format="url"` | ❌ 始终为空 |
| `data[*].b64_json` | ✅ 显式 `response_format="b64_json"` | ✅ **始终返回** |
| `data[*].revised_prompt` | ✅ | ✅ |
| `prompt_filter_results` | ❌ | ✅（在响应顶层） |

## 3. 把 b64 落盘
```python
import base64, pathlib
img_bytes = base64.b64decode(b64)
pathlib.Path("output").mkdir(exist_ok=True)
pathlib.Path("output/cat.png").write_bytes(img_bytes)
```

## 4. Workaround：让前端继续拿 URL（Blob + SAS）
合作伙伴常见的迁移痛点：前端逻辑写的是 `<img src={url} />`，Azure 拿到 b64 后想要个临时 URL。

```python
import base64, uuid, datetime
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

def b64_to_sas_url(b64: str, account: str, container: str, conn_str: str) -> str:
    svc = BlobServiceClient.from_connection_string(conn_str)
    cc = svc.get_container_client(container)
    try:
        cc.create_container()
    except Exception:
        pass
    blob_name = f"{uuid.uuid4()}.png"
    cc.upload_blob(blob_name, base64.b64decode(b64), overwrite=True)
    sas = generate_blob_sas(
        account_name=account,
        container_name=container,
        blob_name=blob_name,
        account_key=svc.credential.account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    )
    return f"https://{account}.blob.core.windows.net/{container}/{blob_name}?{sas}"
```
- 生产建议改用 **User Delegation SAS** + Managed Identity，避免账户密钥。
- 或挂 CDN 给静态分发。

## 5. 其他参数差异速查
| 参数 | OpenAI | Azure | 备注 |
|---|---|---|---|
| `model` | `"gpt-image-2"` | deployment 名 | — |
| `size` | 同步支持的尺寸 | 同 | 部分尺寸某区域可能未启用 |
| `quality` | `"low" / "medium" / "high" / "auto"` | 同 | — |
| `background` | `"transparent" / "opaque" / "auto"` | 同 | — |
| `response_format` | `"url" / "b64_json"` | **忽略 / 始终 b64** | ⚠️ |
| `n` | ✅ | ✅ | — |
| `user` | ✅ | ✅ | Azure 上对滥用追踪有用 |

## 6. 错误对照
| 报错 | 原因 | 处理 |
|---|---|---|
| `AttributeError: 'NoneType' object has no attribute ...` (Azure 拿 url) | 直接读 `url` 而 Azure 只给 b64 | 改读 `b64_json` |
| `content_filter` | RAI 拦截（提示或图像） | 改提示，或申请阈值调整 |
| `ResponsibleAIPolicyViolation` | 触发图像内容策略 | 改提示 |
| `OperationNotSupported` | 在 chat deployment 上调 images | 用图像 deployment |
| `DeploymentNotFound` | 部署名错 / 区域不支持 | `az ... deployment list` 核对 |

## 7. 编辑 / inpaint
GPT-Image-2 也支持 `images.edit` 接口（mask + 输入图）：
```python
edited = client.images.edit(
    model=DEPLOYMENT,
    image=open("base.png","rb"),
    mask=open("mask.png","rb"),
    prompt="give the cat sunglasses",
    size="1024x1024",
)
b64 = edited.data[0].b64_json
```
Azure 行为同上：仅 b64。

## 完整可运行示例
- Python：[`03_image_openai.py`](../../samples/python/03_image_openai.py) · [`03_image_azure.py`](../../samples/python/03_image_azure.py)
- TypeScript：[`03_image_openai.ts`](../../samples/typescript/03_image_openai.ts) · [`03_image_azure.ts`](../../samples/typescript/03_image_azure.ts)

> 如果 Microsoft 后续在 Azure 端启用 `response_format=url`，本文档将更新。截至 2026-05，Azure GPT-Image 系列以 b64_json 为唯一返回。
