// 01_chat_openai.ts — Basic Chat Completions against OpenAI.
import "dotenv/config";
import OpenAI from "openai";

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const resp = await client.chat.completions.create({
  model: "gpt-5.5",
  messages: [
    { role: "system", content: "You are concise." },
    { role: "user", content: "What is the capital of France?" },
  ],
});
console.log(resp.choices[0].message.content);
