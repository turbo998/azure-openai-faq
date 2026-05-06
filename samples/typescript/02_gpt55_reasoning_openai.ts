// 02_gpt55_reasoning_openai.ts — GPT-5.5 with reasoning_effort + streaming on OpenAI.
import "dotenv/config";
import OpenAI from "openai";

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const stream = await client.chat.completions.create({
  model: "gpt-5.5",
  reasoning_effort: "medium",
  messages: [{ role: "user", content: "Explain why the sky is blue, briefly." }],
  stream: true,
});

for await (const chunk of stream) {
  if (!chunk.choices?.length) continue;
  process.stdout.write(chunk.choices[0].delta.content ?? "");
}
process.stdout.write("\n");
