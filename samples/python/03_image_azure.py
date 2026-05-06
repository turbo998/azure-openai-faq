"""
03_image_azure.py — GPT-Image-2 on Azure OpenAI.

KEY DIFFERENCES vs OpenAI:
  - `response_format="url"` is NOT supported on Azure. Always read b64_json.
  - `model` is the deployment name.
  - Optional: upload b64 to Azure Blob and create a SAS URL so existing
    URL-based clients keep working.
"""
import os, pathlib, base64, uuid, datetime
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "preview"),
)

resp = client.images.generate(
    model=os.environ["AZURE_OPENAI_IMAGE_DEPLOYMENT"],
    prompt="A cyberpunk cat playing a grand piano on a neon street, photo-realistic",
    size="1024x1024",
    n=1,
    # ❌ DO NOT set response_format="url" — Azure ignores or errors.
)

data = resp.data[0]
assert data.b64_json, "Azure GPT-Image-2 should always return b64_json"

out_dir = pathlib.Path("output"); out_dir.mkdir(exist_ok=True)
img_bytes = base64.b64decode(data.b64_json)
local_path = out_dir / "cat_azure.png"
local_path.write_bytes(img_bytes)
print(f"Saved locally: {local_path}")

# Optional: upload to Blob and produce a temporary URL (works around the
# missing 'url' field for clients that demand a URL).
conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
account = os.environ.get("AZURE_STORAGE_ACCOUNT")
container = os.environ.get("AZURE_STORAGE_CONTAINER", "images")

if conn_str and account:
    from azure.storage.blob import (
        BlobServiceClient, generate_blob_sas, BlobSasPermissions,
    )
    svc = BlobServiceClient.from_connection_string(conn_str)
    cc = svc.get_container_client(container)
    try:
        cc.create_container()
    except Exception:
        pass
    blob_name = f"{uuid.uuid4()}.png"
    cc.upload_blob(blob_name, img_bytes, overwrite=True)
    sas = generate_blob_sas(
        account_name=account,
        container_name=container,
        blob_name=blob_name,
        account_key=svc.credential.account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    )
    sas_url = f"https://{account}.blob.core.windows.net/{container}/{blob_name}?{sas}"
    print(f"Temporary SAS URL (1h): {sas_url}")
else:
    print("Skipping Blob upload (AZURE_STORAGE_CONNECTION_STRING not set).")
