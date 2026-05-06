"""
03_image_openai.py — GPT-Image-2 on OpenAI.
On OpenAI you can choose response_format="url" or "b64_json".
"""
import os, pathlib, base64, urllib.request
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

resp = client.images.generate(
    model="gpt-image-2",
    prompt="A cyberpunk cat playing a grand piano on a neon street, photo-realistic",
    size="1024x1024",
    n=1,
    response_format="url",   # OpenAI honors this
)

out_dir = pathlib.Path("output"); out_dir.mkdir(exist_ok=True)
data = resp.data[0]

if data.url:
    print("URL:", data.url)
    urllib.request.urlretrieve(data.url, out_dir / "cat_openai.png")
elif data.b64_json:
    (out_dir / "cat_openai.png").write_bytes(base64.b64decode(data.b64_json))

print("Saved to output/cat_openai.png")
