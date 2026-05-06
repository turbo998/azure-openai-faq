// 05_validate_deployment.ts — Sanity-check an Azure OpenAI deployment.
import "dotenv/config";
import { AzureOpenAI } from "openai";

const REQUIRED = [
  "AZURE_OPENAI_ENDPOINT",
  "AZURE_OPENAI_API_KEY",
  "AZURE_OPENAI_API_VERSION",
  "AZURE_OPENAI_GPT55_DEPLOYMENT",
];
const missing = REQUIRED.filter((k) => !process.env[k]);
if (missing.length) {
  console.error(`❌ Missing env vars: ${missing.join(", ")}`);
  process.exit(1);
}

const endpoint = process.env.AZURE_OPENAI_ENDPOINT!.replace(/\/$/, "");
console.log(`Endpoint: ${endpoint}`);
console.log(`API ver : ${process.env.AZURE_OPENAI_API_VERSION}`);
console.log(`Chat dep: ${process.env.AZURE_OPENAI_GPT55_DEPLOYMENT}`);
console.log(`Img  dep: ${process.env.AZURE_OPENAI_IMAGE_DEPLOYMENT ?? "(not set)"}`);
console.log("---");

const client = new AzureOpenAI({
  endpoint,
  apiKey: process.env.AZURE_OPENAI_API_KEY!,
  apiVersion: process.env.AZURE_OPENAI_API_VERSION!,
});

// 1. Chat
try {
  const r = await client.chat.completions.create({
    model: process.env.AZURE_OPENAI_GPT55_DEPLOYMENT!,
    messages: [{ role: "user", content: "Reply with exactly the word: OK" }],
    max_tokens: 5,
  });
  console.log(`✅ Chat deployment OK → ${JSON.stringify(r.choices[0].message.content)}`);
} catch (e: any) {
  console.error(`❌ Chat deployment failed: ${e?.name}: ${e?.message}`);
}

// 2. Image (optional)
const imgDep = process.env.AZURE_OPENAI_IMAGE_DEPLOYMENT;
if (imgDep) {
  try {
    const ir = await client.images.generate({
      model: imgDep,
      prompt: "A red dot on a white background",
      size: "1024x1024",
      n: 1,
    });
    const d = ir.data?.[0];
    const hasB64 = !!d?.b64_json;
    const hasUrl = !!d?.url;
    console.log(`✅ Image deployment OK → b64_json=${hasB64} url=${hasUrl}`);
    if (hasUrl) console.log("   ⚠️ Unusual: Azure normally does not return url. Verify SDK/route.");
    if (!hasB64) console.log("   ❌ Expected b64_json on Azure but got none.");
  } catch (e: any) {
    console.error(`❌ Image deployment failed: ${e?.name}: ${e?.message}`);
  }
} else {
  console.log("ℹ️  Skipped image deployment check (AZURE_OPENAI_IMAGE_DEPLOYMENT not set).");
}
