// 03_image_openai.ts — GPT-Image-2 on OpenAI; can return url or b64_json.
import "dotenv/config";
import OpenAI from "openai";
import { mkdirSync, writeFileSync } from "node:fs";
import { Buffer } from "node:buffer";

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const resp = await client.images.generate({
  model: "gpt-image-2",
  prompt: "A cyberpunk cat playing a grand piano on a neon street, photo-realistic",
  size: "1024x1024",
  n: 1,
  response_format: "url", // OpenAI honors this
});

mkdirSync("output", { recursive: true });
const data = resp.data![0];

if (data.url) {
  console.log("URL:", data.url);
  const r = await fetch(data.url);
  const buf = Buffer.from(await r.arrayBuffer());
  writeFileSync("output/cat_openai.png", buf);
} else if (data.b64_json) {
  writeFileSync("output/cat_openai.png", Buffer.from(data.b64_json, "base64"));
}
console.log("Saved to output/cat_openai.png");
