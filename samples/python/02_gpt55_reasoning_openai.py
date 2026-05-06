"""
02_gpt55_reasoning_openai.py — GPT-5.5 with reasoning_effort + streaming on OpenAI.
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

stream = client.chat.completions.create(
    model="gpt-5.5",
    reasoning_effort="medium",
    messages=[
        {"role": "user", "content": "Explain why the sky is blue, briefly."},
    ],
    stream=True,
)
for chunk in stream:
    if not chunk.choices:
        continue
    delta = chunk.choices[0].delta.content or ""
    print(delta, end="", flush=True)
print()
