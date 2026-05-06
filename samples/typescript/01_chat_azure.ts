// 01_chat_azure.ts — Basic Chat Completions against Azure OpenAI.
//
// Differences vs 01_chat_openai.ts:
//   - Use AzureOpenAI from "openai"
//   - endpoint + apiVersion required
//   - `model` is the *deployment name*, not the model id
import "dotenv/config";
import { AzureOpenAI } from "openai";

const client = new AzureOpenAI({
  endpoint: process.env.AZURE_OPENAI_ENDPOINT!,
  apiKey: process.env.AZURE_OPENAI_API_KEY!,
  apiVersion: process.env.AZURE_OPENAI_API_VERSION ?? "preview",
});

const resp = await client.chat.completions.create({
  model: process.env.AZURE_OPENAI_GPT55_DEPLOYMENT!, // deployment name!
  messages: [
    { role: "system", content: "You are concise." },
    { role: "user", content: "What is the capital of France?" },
  ],
});
console.log(resp.choices[0].message.content);

// Azure-specific: prompt_filter_results may appear on response
const pfr = (resp as any).prompt_filter_results;
if (pfr) console.log("[Azure RAI prompt filter]", JSON.stringify(pfr, null, 2));
