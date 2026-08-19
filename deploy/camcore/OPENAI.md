# Jarvis | CamCore AI — OpenAI hybrid provider

CamCore can run Jarvis in a hybrid configuration: local Ollama inference remains
available at all times, while an optional OpenAI API key enables a cloud provider
for faster or more capable responses when cloud use is intentionally selected.

The OpenAI credential belongs only in the `camcore-jarvis` Portainer runtime
environment. Do not add it to `camcore-websites`, Nginx Proxy Manager, browser
storage, Git, screenshots or support logs.

## Provider modes

The signed-in CamCore portal exposes three choices:

- **Auto** — applies the role-specific CamCore provider policy. CamCore's default
  Auto policy is Local for both members and administrators.
- **Local** — always uses `CAMCORE_JARVIS_MODEL` through Ollama inside CamCore.
- **OpenAI** — uses `CAMCORE_OPENAI_MODEL` through the server-side OpenAI API
  client. If cloud inference is unavailable and fallback is enabled, Jarvis
  automatically retries locally.

Default Auto policy:

- **member** — Local-first. OpenAI is an explicit choice when configured.
- **administrator / Operations** — Local-first. An administrator must explicitly
  choose OpenAI before operational conversation content is sent to the cloud
  provider.

The defaults can be changed in Portainer without rebuilding the image, but the
CamCore production baseline should remain local-first.

## Portainer settings

Add these optional values to the existing `camcore-jarvis` stack:

```dotenv
OPENAI_API_KEY=<OpenAI project API key>
CAMCORE_OPENAI_MODEL=gpt-5.6
CAMCORE_OPENAI_FALLBACK_LOCAL=true
CAMCORE_MEMBER_OPENAI_ENABLED=true
CAMCORE_ADMIN_OPENAI_ENABLED=true
CAMCORE_MEMBER_AUTO_PROVIDER=local
CAMCORE_ADMIN_AUTO_PROVIDER=local
```

If `OPENAI_API_KEY` is blank, the stack continues to run normally in Local-only
mode. The portal marks OpenAI unavailable and Auto resolves locally.

Use a project-scoped OpenAI API key and apply appropriate spend/rate limits in
the OpenAI Platform. API usage is separate from ChatGPT subscription usage.

## Privacy boundary

### Member mode

Member chat remains non-operational regardless of provider:

- no CamCore operations agent tools;
- no administrative Jarvis memory;
- caller-supplied system prompts/tools are discarded;
- provider selection does not elevate permissions.

When OpenAI is explicitly selected, the member conversation can be transmitted
to the OpenAI API. The OpenAI key and Jarvis gateway credential remain
server-side.

### Administrator Operations mode

Local Operations retains the existing CamCore tool and memory behaviour.

OpenAI Operations uses a request-local copy of the CamCore operations agent so
one user's provider selection cannot mutate the shared agent used by another
request. Jarvis does **not** automatically preload administrative memory into an
OpenAI Operations request. The conversation and the minimum necessary results
from approved tool calls can still be transmitted to OpenAI when the cloud
provider is selected.

Choose Local whenever the request should remain fully inside CamCore.

## Fallback behaviour

With `CAMCORE_OPENAI_FALLBACK_LOCAL=true`:

- missing/disabled OpenAI configuration resolves to Local before generation;
- a cloud request that fails before output begins is retried locally;
- the portal receives a provider event and displays that the response fell back
  to Local.

Set the value to `false` if a cloud request should fail closed instead of using
local inference.

## Provider policy controls

Disable OpenAI independently by role:

```dotenv
CAMCORE_MEMBER_OPENAI_ENABLED=false
CAMCORE_ADMIN_OPENAI_ENABLED=true
```

Change Auto preference independently by role if there is a deliberate policy
reason to do so:

```dotenv
CAMCORE_MEMBER_AUTO_PROVIDER=local
CAMCORE_ADMIN_AUTO_PROVIDER=local
```

Only `local` and `openai` are valid Auto targets. The supported CamCore baseline
is `local` for both roles.

## Model and cost accounting

The default cloud model is `gpt-5.6`, the GPT-5.6 Sol alias. CamCore records the
standard input/output rates in OpenJarvis's existing two-value estimator so the
runtime comparison does not accidentally inherit an older generic `gpt-5`
prefix rate.

The Runtime page describes this data as an **estimated cloud-cost comparison**.
It must not be presented as exact billing because cached-input pricing, provider
billing changes and other billing dimensions are not represented by the
upstream two-value estimator.

The provider model can be changed with `CAMCORE_OPENAI_MODEL`, but any replacement
must be supported by the installed OpenJarvis CloudEngine and by the configured
OpenAI account. Review privacy, latency and cost before changing it.

## Verification

After redeploying Jarvis:

1. Confirm the normal local model is still available.
2. Open the private Jarvis interface with an approved CamCore identity.
3. Confirm Auto resolves to **Local** by default.
4. Confirm **Local** and **OpenAI** are visibly distinct choices. If the OpenAI
   key is absent or unavailable, OpenAI must be disabled.
5. Send a short prompt in Local mode and verify the displayed model is the local
   Ollama model.
6. Deliberately select OpenAI, send a short non-sensitive prompt and verify the
   displayed model is the configured OpenAI model.
7. Temporarily test an invalid/unavailable cloud credential only in a controlled
   maintenance window and verify fallback to Local if fallback is enabled.
8. Confirm member accounts remain in private member chat and cannot gain
   Operations access by changing provider or query parameters.

## Rollback

No data migration is required. To disable the cloud provider immediately:

1. remove or blank `OPENAI_API_KEY` in Portainer;
2. redeploy the Jarvis stack.

The portal will return to Local-only operation while the existing Ollama model,
Outline integration and persistent Jarvis data remain unchanged.
