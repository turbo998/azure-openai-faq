# 04 · `model`: model id vs deployment name

| Platform | `model` value | Source |
|---|---|---|
| OpenAI | model id (e.g. `"gpt-5.5"`) | [models list](https://platform.openai.com/docs/models) |
| Azure OpenAI | **deployment name** chosen by you | Azure AI Foundry / `az cognitiveservices account deployment create` |

## Why deployments
- Multiple deployments per model for separate quotas / filters / regions.
- Stable identifiers across env promotion (dev/staging/prod).
- Quotas (TPM/RPM/PTU) attach to deployments.

## Create a deployment (CLI)
```bash
az cognitiveservices account deployment create \
  --resource-group myRg \
  --name my-aoai \
  --deployment-name my-gpt55 \
  --model-name gpt-5.5 \
  --model-version "2026-04-01" \
  --model-format OpenAI \
  --sku-name "GlobalStandard" \
  --sku-capacity 50
```

## Use envvars, never hard-code
```python
DEPLOYMENT_GPT55 = os.environ["AZURE_OPENAI_GPT55_DEPLOYMENT"]
```

## Validate
```bash
az cognitiveservices account deployment list \
  --resource-group myRg --name my-aoai \
  --query "[].{name:name, model:properties.model.name, version:properties.model.version}" -o table
```
Or run [`samples/python/05_validate_deployment.py`](../../samples/python/05_validate_deployment.py).

## Common errors
| Error | Cause | Fix |
|---|---|---|
| `404 The API deployment for this resource does not exist` | Passed model id instead of deployment name | Use deployment name |
| `DeploymentNotFound` | Typo / case mismatch | Check via CLI |
| `OperationNotSupported` | Wrong endpoint family (chat vs images) | Use the matching deployment |
| `429` | Quota exhausted | Increase capacity or split deployments |

## Dual-platform factory
```python
def make_client():
    if os.getenv("USE_AZURE", "false").lower() == "true":
        from openai import AzureOpenAI
        client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        )
        return client, os.environ["AZURE_OPENAI_GPT55_DEPLOYMENT"]
    from openai import OpenAI
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"]), "gpt-5.5"
```
