// 02_gpt55_reasoning_azure.ts — GPT-5.5 reasoning_effort + streaming on Azure OpenAI.
//
// Notes:
//   - First stream chunk on Azure may carry only prompt_filter_results.
//     Always guard with `if (!chunk.choices?.length) continue;`.
import "dotenv/config";
import { AzureOpenAI } from "openai";

const client = new AzureOpenAI({
  endpoint: process.env.AZURE_OPENAI_ENDPOINT!,
  apiKey: process.env.AZURE_OPENAI_API_KEY!,
  apiVersion: process.env.AZURE_OPENAI_API_VERSION ?? "preview",
});

try {
  const stream = await client.chat.completions.create({
    model: process.env.AZURE_OPENAI_GPT55_DEPLOYMENT!,
    reasoning_effort: "medium",
    messages: [{ role: "user", content: "Explain why the sky is blue, briefly." }],
    stream: true,
  });

  for await (const chunk of stream) {
    if (!chunk.choices?.length) continue; // ← Azure RAI-only chunk
    process.stdout.write(chunk.choices[0].delta.content ?? "");
  }
  process.stdout.write("\n");
} catch (err: any) {
  // Azure surfaces RAI as 400 with code 'content_filter'
  console.error(`\n[ERROR] ${err?.name}: ${err?.message}`);
  if (err?.error?.innererror) console.error(JSON.stringify(err.error.innererror, null, 2));
}
