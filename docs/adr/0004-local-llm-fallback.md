# ADR 0004: Local LLM via Ollama with Cloud Fallback

## Status

Accepted

## Context

The UAE Social Support Application processes citizen PII (Emirates ID numbers, financial data, family details). Government data handling requirements mandate that PII should not egress to third-party APIs unless necessary.

However, local LLM inference requires GPU resources that may not be available in all deployment environments.

## Decision

Use a dual-provider strategy:

- **Primary:** Ollama running locally (Llama 3.2 / Mistral / Qwen models)
- **Fallback:** StreamLake (Azure OpenAI-compatible API) when local GPU is unavailable

Provider switching is controlled by a single `LLM_PROVIDER` environment variable (`ollama` or `streamlake`).

Embeddings always run locally via Ollama (`nomic-embed-text:v1.5`) regardless of LLM provider.

## Alternatives Considered

### Cloud-Only (OpenAI, Azure OpenAI)

Simplest deployment but violates PII egress constraints for government data.

### Local-Only

Most secure but requires GPU in every deployment environment. Not feasible for all deployment scenarios.

### Multi-Cloud Fallback Chain

Add AWS Bedrock, Google Vertex AI as additional fallbacks. Over-engineered for a prototype. Can be added later if needed.

## Consequences

### Positive

- PII stays local by default
- Cloud fallback provides deployment flexibility
- Single environment variable controls provider

### Negative

- Two provider configurations to maintain
- Model behavior may differ between providers (mitigated by using similar model families)

### Risks

- Local Ollama performance depends on available GPU (mitigated by documenting minimum requirements)
