"""
01_chat_openai.py — Basic Chat Completions against OpenAI.
Run:
    pip install -r requirements.txt
    export OPENAI_API_KEY=sk-...
    python 01_chat_openai.py
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

resp = client.chat.completions.create(
    model="gpt-5.5",
    messages=[
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "What is the capital of France?"},
    ],
)
print(resp.choices[0].message.content)
