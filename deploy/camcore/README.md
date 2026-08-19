# Jarvis | CamCore AI — production deployment

This directory defines the private CamCore production deployment for Jarvis. It is designed for a Portainer Git stack behind the existing Nginx Proxy Manager (NPM) path, with local Ollama inference and explicit CamCore access boundaries.

## Architecture

- `camcore-jarvis` serves the Jarvis web UI and API on container port `8000`.
- `camcore-jarvis-ollama` provides local inference and is not published to the Docker host or proxy network.
- `camcore-jarvis-model-init` ensures the selected Ollama model is present before Jarvis starts.
- `camcore-jarvis-data` persists Jarvis databases, traces, skills, sessions and other runtime state.
- `camcore-jarvis-ollama-models` persists downloaded model data.
- Jarvis joins the Docker network shared with NPM. Ollama does not.
- No service in this stack publishes a host port.
- The production `config.toml` is baked into the immutable Jarvis image at `/etc/openjarvis/camcore-config.toml`.
- Outline is available through its internal MCP endpoint with read-only tool discovery.

Jarvis remains a private CamCore service. Do not create public DNS or a public unauthenticated proxy path for the administrator UI.

## Access model

CamCore production uses two independent checks:

1. **Proxy-to-Jarvis API authentication** — `OPENJARVIS_API_KEY` is injected server-side by the reverse proxy and protects `/v1`, `/api` and metrics routes.
2. **CamCore identity/role boundary** — `CAMCORE_ACCESS_MODE=trusted-proxy` requires a second proxy-only shared secret plus an asserted subject and role.

The trusted identity headers are:

```text
X-CamCore-Proxy-Secret: <CAMCORE_PROXY_IDENTITY_SECRET>
X-CamCore-Subject: <stable authenticated subject>
X-CamCore-Role: member | admin
X-CamCore-Email: <optional email>
X-CamCore-Display-Name: <optional display name>
```

Jarvis trusts those headers **only** when `X-CamCore-Proxy-Secret` matches the runtime secret. Requests must never be allowed to supply or override these headers directly from the public/client side.

### Member boundary

A trusted `member` identity is restricted server-side to the member-safe CamCore portal routes. It cannot reach generic OpenJarvis `/v1` APIs, Operations APIs, agent management, approvals, model management or other administrator surfaces.

### Administrator boundary

A trusted `admin` identity can reach the private administrator UI and explicitly protected Operations APIs. Modifying tools still enforce their own confirmation and capability requirements after authentication.

### SSO integration

The preferred end state is for an authentication/access layer in front of NPM to derive the subject, display name, email and role from the signed-in CamCore/Microsoft identity, then pass only verified identity data to the trusted proxy hop.

Do not let browser JavaScript choose `X-CamCore-Role`. Do not use a query parameter such as `?role=admin` as authorization.

Until claim-based SSO mapping is in place, a private administrator-only host may use a static `admin` identity **only if access to that host is already restricted to administrators by the surrounding private network/access policy**. This is an interim compatibility option, not per-user authentication.

## 1. Required Portainer environment

Set:

```dotenv
CAMCORE_JARVIS_RELEASE=<published main commit SHA>
CAMCORE_JARVIS_MODEL=qwen3.5:4b
CAMCORE_PROXY_NETWORK=<existing NPM Docker network>
OPENJARVIS_API_KEY=<generated secret>
CAMCORE_ACCESS_MODE=trusted-proxy
CAMCORE_PROXY_IDENTITY_SECRET=<second independently generated secret>
CAMCORE_OUTLINE_API_KEY=<read-only Outline API key>
CAMCORE_TZ=Australia/Melbourne
```

Optional Portainer live Docker integration:

```dotenv
CAMCORE_PORTAINER_URL=<internal Portainer API origin>
CAMCORE_PORTAINER_API_KEY=<Portainer access token>
CAMCORE_PORTAINER_VERIFY_TLS=true
```

Optional OpenAI hybrid inference:

```dotenv
OPENAI_API_KEY=
CAMCORE_OPENAI_MODEL=gpt-5.6
CAMCORE_OPENAI_FALLBACK_LOCAL=true
CAMCORE_MEMBER_OPENAI_ENABLED=true
CAMCORE_ADMIN_OPENAI_ENABLED=true
CAMCORE_MEMBER_AUTO_PROVIDER=local
CAMCORE_ADMIN_AUTO_PROVIDER=local
```

`Auto` is local-first. OpenAI remains an explicit option when configured.

Generate the two Jarvis/proxy secrets independently. Do not reuse the Portainer or Outline credential.

## 2. Portainer Git stack

Use:

- Repository: `https://github.com/camcoreau/jarvis`
- Reference: `refs/heads/main`
- Compose path: `deploy/camcore/compose.yaml`
- Stack name: `camcore-jarvis`

`CAMCORE_JARVIS_RELEASE` must be an immutable image tag published by the CamCore image workflow. Do not use `latest`.

The compose file intentionally relies on named volumes and the immutable image rather than bind-mounting Portainer's temporary Git checkout.

## 3. Reverse proxy configuration

Create the private proxy host:

- Domain: `jarvis.camcore.network`
- Scheme: `http`
- Forward hostname: `camcore-jarvis`
- Forward port: `8000`
- Websockets: enabled
- Block common exploits: enabled

The browser UI loads as static content, but API requests need the server-side headers.

For the administrator-only private host, the `/` custom location must inject the Jarvis API key and the proxy identity secret. If a verified SSO/access layer is supplying user claims, map those verified values into the CamCore identity headers. Otherwise a static interim administrator identity can be used only on an already administrator-restricted private host.

Example **interim private-admin** NPM location configuration:

```nginx
proxy_set_header Authorization "Bearer <OPENJARVIS_API_KEY>";
proxy_set_header X-CamCore-Proxy-Secret "<CAMCORE_PROXY_IDENTITY_SECRET>";
proxy_set_header X-CamCore-Subject "private-admin-host";
proxy_set_header X-CamCore-Role "admin";
proxy_set_header X-CamCore-Display-Name "CamCore Administrator";

proxy_buffering off;
proxy_cache off;
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
```

When SSO claim forwarding is added, replace the static subject/display name/role with values provided by the trusted authentication layer. Ensure client-supplied versions of the CamCore identity headers are stripped before the trusted values are set.

The two secret-bearing headers must exist only in Portainer/NPM or another trusted runtime secret store, never in the browser bundle or repository.

## 4. Outline knowledge access

Jarvis connects to Outline over the internal Docker bridge:

```text
http://outline:3000/mcp
```

The CamCore profile sends static routing headers for Outline's canonical internal hostname and resolves the bearer credential only from `CAMCORE_OUTLINE_API_KEY` at runtime.

Tool discovery is restricted to:

- `list_documents` — search/list accessible documents;
- `fetch` — retrieve selected document content.

Documentation is authoritative for **documented state**, not current runtime health.

## 5. Portainer Operations boundary

Portainer provides Docker-only evidence:

- environments;
- container state and Docker health;
- allow-listed container metadata;
- CPU, memory and network usage;
- bounded, redacted recent logs;
- confirmation-gated start/stop/restart actions.

Portainer does **not** prove:

- Synology physical disk or SMART state;
- storage-pool health;
- RAID/SHR layout or health;
- filesystem free space;
- NAS hardware health;
- UPS state.

The Operations capability inventory intentionally reports those host/storage capabilities as unavailable until a dedicated read-only source is implemented.

## 6. Internal DNS

Create only the internal DNS record for `jarvis.camcore.network` and point it to the private reverse-proxy path. Keep the administrator UI off public DNS.

## 7. Verify deployment

From an administrator client on the trusted private path:

```bash
curl -I https://jarvis.camcore.network/
curl -s https://jarvis.camcore.network/v1/models
curl -s https://jarvis.camcore.network/v1/camcore/portal/identity
curl -s https://jarvis.camcore.network/v1/camcore/operations/capabilities
curl -s https://jarvis.camcore.network/v1/camcore/operations/overview
```

Expected results:

- the UI loads;
- `/v1/models` succeeds for the admin identity;
- `/identity` reports `admin` and the trusted proxy identity metadata;
- capability inventory reports attached tools without inventing unavailable integrations;
- Operations overview reports `LIVE` Portainer evidence only after a successful Portainer check.

A request sent through a trusted **member** path should receive HTTP 403 for `/v1/models` and `/v1/camcore/operations/*`, while `/v1/camcore/portal/chat/completions` remains available.

Verify startup logs also report the expected Outline tool discovery.

## Model changes

Change `CAMCORE_JARVIS_MODEL` in Portainer and redeploy. The model-init service pulls the selected model before Jarvis starts.

The remote web UI must not expose Ollama directly. Ollama remains an internal service and should load models through the server/deployment path rather than a browser request to `127.0.0.1:11434`.

## Rollback

1. Set `CAMCORE_JARVIS_RELEASE` to the previous known-good published commit SHA.
2. Redeploy the stack.
3. Leave persistent Jarvis and Ollama volumes in place.

If rolling back to a build that predates trusted-proxy identity, also restore the matching NPM configuration for that release. Keep the proxy identity secret stored even if the older build ignores it.

## Backups

Back up:

- `camcore-jarvis-data` — required; contains sensitive runtime state;
- `camcore-jarvis-ollama-models` — optional if model re-download time is acceptable.

Treat Jarvis data backups as sensitive operational data.

## Security posture

The CamCore production profile is deliberately conservative:

- private network/reverse-proxy exposure only;
- local Ollama inference by default;
- separate proxy API key and trusted identity secret;
- server-side member/admin route isolation;
- external analytics disabled;
- Outline read-only knowledge access;
- Portainer allow-listed Docker evidence;
- write/shell tools disabled by default;
- server/block security profile;
- secret and PII scanning;
- SSRF protection and rate limiting;
- audit logging;
- explicit tool confirmation;
- proactive actions and channels disabled.

Expand a capability only after its read/write boundary, approval model, secret handling and audit behaviour are explicit and tested.
