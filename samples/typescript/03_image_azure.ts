// 03_image_azure.ts — GPT-Image-2 on Azure OpenAI.
//
// KEY DIFFERENCES vs OpenAI:
//   - response_format="url" is NOT supported on Azure. Always read b64_json.
//   - `model` is the deployment name.
//   - Optional: upload b64 to Azure Blob and create a SAS URL so existing
//     URL-based clients keep working.
import "dotenv/config";
import { AzureOpenAI } from "openai";
import { mkdirSync, writeFileSync } from "node:fs";
import { Buffer } from "node:buffer";
import { randomUUID } from "node:crypto";
import {
  BlobServiceClient,
  StorageSharedKeyCredential,
  generateBlobSASQueryParameters,
  BlobSASPermissions,
} from "@azure/storage-blob";

const client = new AzureOpenAI({
  endpoint: process.env.AZURE_OPENAI_ENDPOINT!,
  apiKey: process.env.AZURE_OPENAI_API_KEY!,
  apiVersion: process.env.AZURE_OPENAI_API_VERSION ?? "preview",
});

const resp = await client.images.generate({
  model: process.env.AZURE_OPENAI_IMAGE_DEPLOYMENT!,
  prompt: "A cyberpunk cat playing a grand piano on a neon street, photo-realistic",
  size: "1024x1024",
  n: 1,
  // ❌ Do NOT set response_format: "url" — Azure ignores or errors.
});

const data = resp.data?.[0];
if (!data?.b64_json) {
  throw new Error("Azure GPT-Image-2 should always return b64_json, but got none.");
}

mkdirSync("output", { recursive: true });
const imgBytes = Buffer.from(data.b64_json, "base64");
writeFileSync("output/cat_azure.png", imgBytes);
console.log("Saved locally: output/cat_azure.png");

// Optional: upload to Blob and produce a temporary SAS URL.
const connStr = process.env.AZURE_STORAGE_CONNECTION_STRING;
const account = process.env.AZURE_STORAGE_ACCOUNT;
const container = process.env.AZURE_STORAGE_CONTAINER ?? "images";

if (connStr && account) {
  const svc = BlobServiceClient.fromConnectionString(connStr);
  const cc = svc.getContainerClient(container);
  await cc.createIfNotExists();
  const blobName = `${randomUUID()}.png`;
  await cc.getBlockBlobClient(blobName).uploadData(imgBytes);

  // Parse account key from connection string for SAS signing
  const keyMatch = /AccountKey=([^;]+)/.exec(connStr);
  if (!keyMatch) {
    console.warn("AccountKey not found in connection string; skipping SAS URL.");
  } else {
    const cred = new StorageSharedKeyCredential(account, keyMatch[1]);
    const expiresOn = new Date(Date.now() + 60 * 60 * 1000);
    const sas = generateBlobSASQueryParameters(
      {
        containerName: container,
        blobName,
        permissions: BlobSASPermissions.parse("r"),
        expiresOn,
      },
      cred,
    ).toString();
    const sasUrl = `https://${account}.blob.core.windows.net/${container}/${blobName}?${sas}`;
    console.log(`Temporary SAS URL (1h): ${sasUrl}`);
  }
} else {
  console.log("Skipping Blob upload (AZURE_STORAGE_CONNECTION_STRING not set).");
}
