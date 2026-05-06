// 04_aad_auth_azure.ts — Authenticate to Azure OpenAI with Microsoft Entra ID.
//
// Local dev: run `az login` first.
// Cloud: assign a Managed Identity and grant 'Cognitive Services OpenAI User'
// on the Azure OpenAI resource.
import "dotenv/config";
import { DefaultAzureCredential, getBearerTokenProvider } from "@azure/identity";
import { AzureOpenAI } from "openai";

const azureADTokenProvider = getBearerTokenProvider(
  new DefaultAzureCredential(),
  "https://cognitiveservices.azure.com/.default",
);

const client = new AzureOpenAI({
  endpoint: process.env.AZURE_OPENAI_ENDPOINT!,
  apiVersion: process.env.AZURE_OPENAI_API_VERSION ?? "preview",
  azureADTokenProvider,
  // No apiKey — token provider is used instead
});

const resp = await client.chat.completions.create({
  model: process.env.AZURE_OPENAI_GPT55_DEPLOYMENT!,
  messages: [{ role: "user", content: "Ping over AAD!" }],
});
console.log(resp.choices[0].message.content);
