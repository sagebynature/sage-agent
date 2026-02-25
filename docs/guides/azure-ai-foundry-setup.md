# Setting Up Providers via Azure AI Foundry

Azure AI Foundry is Microsoft's unified platform for deploying and managing AI models. Sage supports three provider paths through it:

| Path | Models | Auth |
|------|--------|------|
| **Azure AI Foundry project endpoint** | GPT-4o, Claude, Llama, Mistral, Phi — all from one endpoint | API key or Managed Identity |
| **GitHub Models** | GPT-4o, Claude, Llama (via GitHub token) | GitHub PAT |

All paths go through [litellm](https://github.com/BerriAI/litellm) under the hood. Azure AI Foundry project endpoints serve both Azure OpenAI models and serverless models (Claude, Llama, etc.) from a **single endpoint**, so you only need one set of credentials. All model strings use the `azure_ai/` prefix.

---

## Prerequisites

- An Azure subscription with access to [Azure AI Foundry](https://ai.azure.com)
- `sage` installed: `pip install sage`
- `uv` or `pip` for dependency management

---

## Path 1: Azure OpenAI (GPT-4o, o1, etc.)

### 1. Create an Azure OpenAI resource

1. Go to [Azure AI Foundry](https://ai.azure.com) → **Management** → **Azure OpenAI**
2. Create a new resource (or use an existing one)
3. Deploy a model: navigate to your resource → **Deployments** → **Deploy model**
4. Note your **deployment name** (e.g., `gpt-4o-prod`) — this is what goes in the model string

### 2. Collect your credentials

From your Azure OpenAI resource in the Azure Portal:

| Variable | Where to find it |
|----------|-----------------|
| `AZURE_API_KEY` | Resource → **Keys and Endpoint** → Key 1 |
| `AZURE_API_BASE` | Resource → **Keys and Endpoint** → Endpoint (e.g., `https://my-resource.openai.azure.com`) |
| `AZURE_API_VERSION` | Use `2024-10-21` (latest stable) or check [Azure OpenAI API versions](https://learn.microsoft.com/en-us/azure/ai-services/openai/api-version-deprecation) |

### 3. Configure environment variables

```bash
export AZURE_API_KEY="your-api-key"
export AZURE_API_BASE="https://my-resource.openai.azure.com"
export AZURE_API_VERSION="2024-10-21"
```

Or use a `.env` file at the project root:

```ini
AZURE_API_KEY=your-api-key
AZURE_API_BASE=https://my-resource.openai.azure.com
AZURE_API_VERSION=2024-10-21
```

### 4. Reference in `AGENTS.md`

```markdown
---
name: my-assistant
model: azure/gpt-4o-prod    # azure/<your-deployment-name>
description: An Azure OpenAI assistant
---

You are a helpful assistant.
```

Model string format: `azure/<deployment-name>` — the deployment name is what you chose in step 1, **not** the base model name.

### 5. For embeddings (memory recall)

Deploy a text-embedding model in Azure OpenAI (e.g., `text-embedding-3-large`):

```markdown
---
name: my-assistant
model: azure/gpt-4o-prod
memory:
  backend: sqlite
  path: ./memory.db
  embedding: azure/my-embedding-deployment   # azure/<embedding-deployment-name>
---

You are a helpful assistant with persistent memory.
```

---

## Path 2: Azure AI Foundry — Serverless Models (Claude, Llama, Mistral)

Azure AI Foundry's model catalog lets you deploy third-party models (including Anthropic Claude) as serverless API endpoints. No GPU provisioning required.

### 1. Deploy a model from the catalog

1. Go to [Azure AI Foundry](https://ai.azure.com) → **Model catalog**
2. Find your model (e.g., search "Claude")
3. Click **Deploy** → select **Serverless API** (pay-per-token, no infrastructure)
4. Choose or create a project, then deploy

### 2. Collect your credentials

After deployment, go to your project → **Models + endpoints** → select your deployment:

| Variable | Where to find it |
|----------|-----------------|
| `AZURE_AI_API_KEY` | Deployment details → **API key** |
| `AZURE_AI_API_BASE` | Deployment details → **Target URI** (e.g., `https://my-claude.eastus.models.ai.azure.com`) |

> **Note**: Azure AI Foundry serverless endpoints use a *different* env var prefix (`AZURE_AI_*`) from Azure OpenAI (`AZURE_*`). Both can coexist in the same environment.

### 3. Configure environment variables

```bash
export AZURE_AI_API_KEY="your-foundry-api-key"
export AZURE_AI_API_BASE="https://my-claude.eastus.models.ai.azure.com"
```

### 4. Reference in `AGENTS.md`

```markdown
---
name: claude-assistant
model: azure_ai/claude-3-5-sonnet-20241022   # azure_ai/<model-name>
description: A Claude-powered assistant
---

You are a helpful assistant.
```

Model string format: `azure_ai/<model-name>`. Use the base model name (not a deployment name) — litellm maps this to your endpoint.

#### Supported Anthropic models via Azure AI Foundry

| Model | String |
|-------|--------|
| Claude 3.7 Sonnet | `azure_ai/claude-3-7-sonnet-20250219` |
| Claude 3.5 Sonnet v2 | `azure_ai/claude-3-5-sonnet-20241022` |
| Claude 3.5 Haiku | `azure_ai/claude-3-5-haiku-20241022` |

#### Other models from the catalog

```yaml
model: azure_ai/Meta-Llama-3.1-70B-Instruct
model: azure_ai/Mistral-Large-2411
model: azure_ai/Phi-4
```

---

## Path 3: GitHub Models (GitHub Copilot / GitHub Marketplace)

GitHub Models exposes OpenAI, Anthropic, and other models through the GitHub token system, using Azure AI infrastructure under the hood. Useful for development and lower-volume workloads.

### 1. Get a GitHub Personal Access Token

1. Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. Generate a new token (fine-grained or classic)
3. No special scopes are required for GitHub Models — any valid GitHub token works

### 2. Configure environment variables

```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

### 3. Reference in `AGENTS.md`

```markdown
---
name: my-assistant
model: github/gpt-4o
description: A GitHub Models assistant
---

You are a helpful assistant.
```

#### Available models via GitHub

| Model | String |
|-------|--------|
| GPT-4o | `github/gpt-4o` |
| GPT-4o mini | `github/gpt-4o-mini` |
| Claude 3.5 Sonnet | `github/claude-3-5-sonnet` |
| Llama 3.3 70B | `github/meta-llama-3.3-70b-instruct` |
| Phi-4 | `github/phi-4` |

> **Rate limits**: GitHub Models has lower rate limits than direct Azure deployments. Use Azure OpenAI or Azure AI Foundry for production workloads.

---

## Authentication: API Key vs Managed Identity

The examples above use API keys for simplicity. In production (especially on Azure-hosted workloads), prefer **Managed Identity** to avoid storing secrets.

### Managed Identity (Azure OpenAI only)

When running on Azure (App Service, Azure Container Apps, AKS, etc.) with a system-assigned or user-assigned managed identity:

```bash
# No API key needed — litellm picks up the managed identity automatically
export AZURE_API_BASE="https://my-resource.openai.azure.com"
export AZURE_API_VERSION="2024-10-21"
# Optionally set the client ID for user-assigned identity:
export AZURE_CLIENT_ID="your-managed-identity-client-id"
```

litellm uses `azure.identity.DefaultAzureCredential` under the hood when no `AZURE_API_KEY` is set.

### Using a `.env` file

Sage loads `.env` automatically if `python-dotenv` is installed:

```bash
pip install python-dotenv
```

`.env` file:
```ini
# Azure OpenAI
AZURE_API_KEY=...
AZURE_API_BASE=https://my-resource.openai.azure.com
AZURE_API_VERSION=2024-10-21

# Azure AI Foundry (Anthropic, etc.)
AZURE_AI_API_KEY=...
AZURE_AI_API_BASE=https://my-claude.eastus.models.ai.azure.com

# GitHub Models
GITHUB_TOKEN=ghp_...
```

---

## Full `AGENTS.md` Examples

### Azure OpenAI with memory

```markdown
---
name: research-assistant
model: azure/gpt-4o-prod
description: Research assistant with memory
tools:
  - file_read
  - shell
memory:
  backend: sqlite
  path: ./memory.db
  embedding: azure/text-embedding-3-large-prod   # azure/<embedding-deployment-name>
  compaction_threshold: 50
    ---

  You are a research assistant. You help users find, analyze, and summarize information.
```

### Claude via Azure AI Foundry

```markdown
---
name: claude-analyst
model: azure_ai/claude-3-5-sonnet-20241022
description: Data analysis specialist
tools:
  - myapp.tools:analyze_data
memory:
  backend: sqlite
  path: ./memory.db
  embedding: azure_ai/text-embedding-3-large
model_params:
  temperature: 0.3   # OK
  max_tokens: 4096   # OK
  timeout: 30.0      # OK
  # top_p: 0.9       # NOT supported alongside temperature — omit one or the other
  # seed: 42         # NOT supported by Anthropic models via Azure AI Foundry
---

You are a data analyst. You analyze datasets and provide actionable insights.
```

### Multi-model setup (different agents, different providers)

```markdown
# orchestrator.md
---
name: lead-agent
model: azure/gpt-4o-prod
description: Lead orchestrator agent
subagents:
  - name: researcher
    config: researcher.md   # uses azure_ai/claude-3-5-sonnet
  - name: summarizer
    config: summarizer.md   # uses azure/gpt-4o-mini-prod
---

You are the lead agent. Delegate research tasks to the researcher and summarization to the summarizer.
```

---

## `model_params` Compatibility by Provider

Not all parameters in `model_params` are supported by every provider. The table below documents confirmed behaviour on Azure AI Foundry:

| Parameter | Azure OpenAI (`azure/`) | Azure AI Foundry — Anthropic (`azure_ai/claude-*`) |
|-----------|------------------------|-----------------------------------------------------|
| `temperature` | ✅ | ✅ |
| `max_tokens` | ✅ | ✅ |
| `top_p` | ✅ | ⚠️ mutually exclusive with `temperature` — set one or the other, never both |
| `top_k` | ✅ | ✅ |
| `frequency_penalty` | ✅ | ✅ |
| `presence_penalty` | ✅ | ✅ |
| `seed` | ✅ | ❌ not supported — litellm raises `UnsupportedParamsError` |
| `stop` | ✅ | ✅ |
| `timeout` | ✅ | ✅ |
| `response_format` | ✅ | ❌ not supported for Anthropic models |

> **Tip**: If you want to use a parameter that the provider rejects, you can set `litellm.drop_params = True` globally to silently skip unsupported params rather than raising an error. Add `import litellm; litellm.drop_params = True` before constructing your agent in code, or set the environment variable `LITELLM_DROP_PARAMS=true`.

---

## Verifying Your Setup

Use the `sage` CLI to validate credentials before running agents:

```bash
# Validate config (checks model string format)
sage agent validate AGENTS.md

# Run with a test prompt
sage agent run AGENTS.md --input "Say hello and tell me which model you are"
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `AuthenticationError` | Wrong or missing API key | Check `AZURE_API_KEY` / `AZURE_AI_API_KEY` |
| `404 DeploymentNotFound` | Deployment name typo | Verify deployment name in Azure AI Foundry portal |
| `RateLimitError` | Token quota exceeded | Check quota in Azure Portal or switch to a higher-capacity deployment |
| `InvalidRequestError: model` | Wrong model string prefix | Use `azure/` for Azure OpenAI, `azure_ai/` for Foundry serverless |
| `AZURE_API_VERSION` mismatch | API version not supported by deployment | Use `2024-10-21` or check your model's supported versions |
| Managed identity not working | No identity assigned to compute | Assign system/user managed identity in Azure Portal and grant it `Cognitive Services OpenAI User` role |
| `UnsupportedParamsError: azure_ai does not support parameters: ['seed']` | `seed` is OpenAI-specific; Anthropic models reject it | Remove `seed` from `model_params` for any `azure_ai/claude-*` model |
| `temperature and top_p cannot both be specified` | Anthropic's API enforces mutual exclusivity between the two sampling parameters | Keep only one: use `temperature` for most cases; use `top_p` only when nucleus sampling is explicitly needed |

### Enable litellm debug logging

```bash
export LITELLM_LOG=DEBUG
sage agent run AGENTS.md --input "hello"
```

This prints the full request/response to the LLM provider, useful for diagnosing auth and routing issues.
