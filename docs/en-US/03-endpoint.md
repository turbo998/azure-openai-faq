# 03 · Endpoint and api-version

## OpenAI
```
https://api.openai.com/v1/<path>
```
No version concept; new features ship via new request fields.

## Azure OpenAI: two routes coexist

### A. v1 route (recommended, since 2025)
```
https://{resource}.openai.azure.com/openai/v1/<path>
```
- Path style mirrors OpenAI (`/chat/completions`, `/responses`, `/images/generations`).
- `api-version` optional; pass `preview` explicitly if you want predictable preview features.
- In SDKs, set `azure_endpoint` to the *resource root* (no `/openai/v1`); the SDK appends.

### B. Legacy `deployments` route (still supported)
```
https://{resource}.openai.azure.com/openai/deployments/{deployment}/<path>?api-version={version}
```
- `api-version` is required (GA like `2024-10-21`, preview like `2025-01-01-preview`).
- The path embeds the deployment name.

## SDK examples
Python:
```python
client = AzureOpenAI(
    azure_endpoint="https://my-aoai.openai.azure.com",
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version="preview",
)
resp = client.chat.completions.create(
    model="my-gpt55-deployment",
    messages=[{"role": "user", "content": "hi"}],
)
```

TypeScript:
```ts
const client = new AzureOpenAI({
  endpoint: "https://my-aoai.openai.azure.com",
  apiKey: process.env.AZURE_OPENAI_API_KEY!,
  apiVersion: "preview",
});
```

## cURL side by side
OpenAI:
```bash
curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.5","messages":[{"role":"user","content":"hi"}]}'
```
Azure (legacy route):
```bash
curl "$AZURE_OPENAI_ENDPOINT/openai/deployments/$AZURE_OPENAI_GPT55_DEPLOYMENT/chat/completions?api-version=$AZURE_OPENAI_API_VERSION" \
  -H "api-key: $AZURE_OPENAI_API_KEY" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hi"}]}'
```
Azure (v1 route):
```bash
curl "$AZURE_OPENAI_ENDPOINT/openai/v1/chat/completions" \
  -H "api-key: $AZURE_OPENAI_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"my-gpt55-deployment","messages":[{"role":"user","content":"hi"}]}'
```

## Pitfalls
1. Trailing `/` on endpoint → double slashes through proxies → 404.
2. Using `…cognitiveservices.azure.com` instead of `…openai.azure.com`.
3. Hard-coding `/openai/deployments/...` plus calling SDK's chat method → double-prefix 404.
4. `api-version` mismatch with SDK package version when using new params (e.g., `reasoning_effort`).
