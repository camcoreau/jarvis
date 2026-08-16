# GPT-5.6 temperature compatibility

CamCore's local Ollama model uses a low temperature (`0.2`) for stable operational behaviour. The configured OpenAI model (`gpt-5.6`) accepts only its default temperature value (`1`).

The CamCore portal provider boundary therefore normalises temperature by provider:

- Local: `0.2`
- OpenAI / GPT-5.6: `1.0`

This applies to member Private chat and administrator Operations requests. If an OpenAI request falls back to Local, the temperature is restored to `0.2` before local generation.

The rule is kept in the CamCore portal layer rather than changing the generic OpenJarvis cloud engine, preserving upstream engine behaviour while matching the production provider policy.
