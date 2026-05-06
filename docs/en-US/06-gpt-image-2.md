# 06 · GPT-Image-2 on Azure: limits and migration

> ⚠️ **The single biggest gotcha**: Azure OpenAI's GPT-Image-2 **does not return `url` — only `b64_json`**. Code that relied on `response.data[0].url` from OpenAI WILL break.
>
> Source: Microsoft Learn image generation models & capabilities (Azure responses contain only `b64_json`).

## 1. Request difference

OpenAI:
```python
img = client.images.generate(
    model="gpt-image-2",
    prompt="A cyberpunk cat playing piano",
    size="1024x1024", n=1,
    response_format="url",     # ✅ honored on OpenAI
)
print(img.data[0].url)         # ✅
```

Azure OpenAI:
```python
img = client.images.generate(
    model=os.environ["AZURE_OPENAI_IMAGE_DEPLOYMENT"],
    prompt="A cyberpunk cat playing piano",
    size="1024x1024", n=1,
    # ❌ do NOT pass response_format="url"
)
b64 = img.data[0].b64_json     # ✅ only this field
```

## 2. Field comparison
| Field | OpenAI | Azure OpenAI |
|---|---|---|
| `data[*].url` | ✅ | ❌ always empty |
| `data[*].b64_json` | ✅ when requested | ✅ always |
| `data[*].revised_prompt` | ✅ | ✅ |
| `prompt_filter_results` | ❌ | ✅ on response |

## 3. Save b64 to file
```python
import base64, pathlib
pathlib.Path("output").mkdir(exist_ok=True)
pathlib.Path("output/cat.png").write_bytes(base64.b64decode(b64))
```

## 4. Workaround: keep a URL contract via Blob + SAS
```python
import base64, uuid, datetime
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

def b64_to_sas_url(b64, account, container, conn_str):
    svc = BlobServiceClient.from_connection_string(conn_str)
    cc = svc.get_container_client(container)
    try: cc.create_container()
    except Exception: pass
    name = f"{uuid.uuid4()}.png"
    cc.upload_blob(name, base64.b64decode(b64), overwrite=True)
    sas = generate_blob_sas(
        account_name=account, container_name=container, blob_name=name,
        account_key=svc.credential.account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    )
    return f"https://{account}.blob.core.windows.net/{container}/{name}?{sas}"
```
Production: prefer **User Delegation SAS** with Managed Identity (no account key).

## 5. Other params
| Param | OpenAI | Azure | Notes |
|---|---|---|---|
| `model` | `"gpt-image-2"` | deployment name | — |
| `size` | supported sizes | same | regional availability may vary |
| `quality` | `"low"/"medium"/"high"/"auto"` | same | — |
| `background` | `"transparent"/"opaque"/"auto"` | same | — |
| `response_format` | `"url"/"b64_json"` | **ignored / always b64** | ⚠️ |
| `n` | ✅ | ✅ | — |
| `user` | ✅ | ✅ | abuse-tracking on Azure |

## 6. Errors
| Error | Cause | Fix |
|---|---|---|
| `AttributeError: 'NoneType' .url` (Azure) | Reading `url` when only b64 is returned | Read `b64_json` |
| `content_filter` | RAI prompt/image block | Rephrase / request threshold review |
| `ResponsibleAIPolicyViolation` | Image policy hit | Rephrase |
| `OperationNotSupported` | Calling images on a chat deployment | Use image deployment |
| `DeploymentNotFound` | Wrong name / region | `az ... deployment list` |

## 7. Edits / inpainting
```python
edited = client.images.edit(
    model=DEPLOYMENT, image=open("base.png","rb"), mask=open("mask.png","rb"),
    prompt="give the cat sunglasses", size="1024x1024",
)
b64 = edited.data[0].b64_json
```
Same Azure constraint: b64 only.

## Runnable samples
- Python: [`03_image_openai.py`](../../samples/python/03_image_openai.py) · [`03_image_azure.py`](../../samples/python/03_image_azure.py)
- TypeScript: [`03_image_openai.ts`](../../samples/typescript/03_image_openai.ts) · [`03_image_azure.ts`](../../samples/typescript/03_image_azure.ts)

> If Microsoft enables `response_format=url` on Azure later, this doc will be updated. As of 2026-05, Azure GPT-Image series returns `b64_json` only.
