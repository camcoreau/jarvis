# Jarvis | CamCore AI — production deployment

This directory defines the private CamCore production deployment for Jarvis. It is designed for a Portainer Git stack behind the existing Nginx Proxy Manager (NPM) path, with local Ollama inference and explicit CamCore access boundaries.

## Architecture

- `camcore-jarvis` serves the Jarvis web UI and API on container port `8000`.
- `camcore-jarvis-ollama` provides local inference and is not published to the Docker host or proxy network.
- `camcore-jarvis-model-init` ensures the selected Ollama model is present before Jarvis starts.
- `camcore-jarvis-data` persists Jarvis databases, traces, skills, sessions and other runtime state.
- `camcore-jarvis-ollama-models` persists downloaded model data.
- Jarvis and Ollama communicate over the internal `camcore-jarvis-ai` network.
- Ollama is the only service from this stack attached to the pre-created external `${CAMCORE_AI_NETWORK:-camcore-ai-backend}` network.
- The separately managed AI frontend stack can therefore reach Ollama without joining Jarvis's internal network or receiving any Jarvis credential.
- Jarvis joins the Docker network shared with NPM. Ollama does not.
- No service in this stack publishes a host port.
- The production `config.toml` is baked into the immutable Jarvis image at `/etc/openjarvis/camcore-config.toml`.
- Outline is available through its internal MCP endpoint with read-only tool discovery.

The public AI frontend is a separate deployment with its own repository,
identity configuration, data volume, lifecycle and rollback. This repository
owns only Jarvis, the shared Ollama inference service and the private network
contract; frontend-specific secrets and configuration do not belong here.

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

The bundled Jarvis SPA is an administrator workspace and uses the generic Operations agent API. A member-facing site should use the dedicated `/v1/camcore/portal/*` member API rather than embedding the administrator SPA.

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
CAMCORE_AI_NETWORK=camcore-ai-backend
CAMCORE_PROXY_NETWORK=<existing NPM Docker network>
OPENJARVIS_API_KEY=<generated secret>
CAMCORE_ACCESS_MODE=trusted-proxy
CAMCORE_PROXY_IDENTITY_SECRET=<second independently generated secret>
CAMCORE_OUTLINE_API_KEY=<read-only Outline API key>
CAMCORE_TZ=Australia/Melbourne
```

Generate the two Jarvis/proxy secrets independently. Do not reuse the Portainer, Outline or provider credentials.

`CAMCORE_AI_NETWORK` must name a pre-created, private bridge network shared
with the separately managed AI frontend stack. Keep the default
`camcore-ai-backend` unless the matching frontend deployment uses a different
explicit name. Do not attach NPM, databases, Jarvis or unrelated workloads to
this network. The stable inference endpoint on this network is
`http://camcore-ollama:11434`.

## 2. Optional read-only Operations integrations

A blank optional credential does not prevent Jarvis from starting. The corresponding tool remains visible as an available capability but returns a precise server-side configuration error until configured. This preserves capability truthfulness without making optional services hard dependencies.

### Portainer — Docker only

```dotenv
CAMCORE_PORTAINER_URL=<internal Portainer API origin>
CAMCORE_PORTAINER_API_KEY=<Portainer access token>
CAMCORE_PORTAINER_VERIFY_TLS=true
```

Portainer provides environments, allow-listed container state/health, resource statistics, bounded/redacted logs, and confirmation-gated start/stop/restart. It is not evidence for Synology storage or host health.

### Better Stack — uptime and active incidents

```dotenv
CAMCORE_BETTERSTACK_API_TOKEN=<Uptime API token>
CAMCORE_BETTERSTACK_TEAM=<optional team name>
```

The tool returns monitor names/statuses, last check time, status counts and bounded unresolved incident metadata. It deliberately omits monitored URLs, request headers, response bodies and other raw monitor configuration.

Use a token that can read the required Uptime resources and nothing more than necessary.

### YouTrack — read-only operational work

```dotenv
CAMCORE_YOUTRACK_URL=https://tasks.camcore.network
CAMCORE_YOUTRACK_TOKEN=<read-only/service token>
CAMCORE_YOUTRACK_QUERY=#Unresolved
```

Jarvis requests at most 50 issues matching the server-configured query and returns only the issue ID, summary, project, resolution/update state and the allow-listed operational fields `State`, `Priority`, `Assignee`, `Service`, `Impact` and `Category` when present.

The model cannot supply a YouTrack URL, token or arbitrary search query.

### Home Assistant — explicit entity allow-list

```dotenv
CAMCORE_HOMEASSISTANT_URL=https://home.camcore.network
CAMCORE_HOMEASSISTANT_TOKEN=<long-lived access token>
CAMCORE_HOMEASSISTANT_ENTITIES=sensor.example,binary_sensor.example
```

Jarvis can request only entity IDs in `CAMCORE_HOMEASSISTANT_ENTITIES`. Returned attributes are limited to `friendly_name`, `unit_of_measurement` and `device_class`; arbitrary attributes and location data are not returned.

Do not add person/device trackers or location-sensitive entities unless there is a specific operational requirement.

### Microsoft 365 — service health only

```dotenv
CAMCORE_M365_TENANT_ID=<tenant id>
CAMCORE_M365_CLIENT_ID=<app registration client id>
CAMCORE_M365_CLIENT_SECRET=<client secret>
```

Create a dedicated Entra application with only the Microsoft Graph application permission required for service communications: `ServiceHealth.Read.All`, with administrator consent. Jarvis uses the client-credentials flow and requests `https://graph.microsoft.com/.default` server-side.

The tool reads subscribed service health and current service issues. It does not read mail, files, users, devices or configuration and has no write method.

### GitHub — repository allow-list

```dotenv
CAMCORE_GITHUB_REPOSITORIES=camcoreau/jarvis,camcoreau/camcore-websites
CAMCORE_GITHUB_TOKEN=<read-only fine-grained token>
```

The tool reads bounded open-issue and GitHub Actions state only for repositories listed in `CAMCORE_GITHUB_REPOSITORIES`. Use a fine-grained read-only token so Operations does not depend on low anonymous API rate limits and can cover private repositories where required.

No repository target can be supplied by the model.

### CamCore Media — aggregate Tautulli activity

```dotenv
CAMCORE_TAUTULLI_URL=<internal Tautulli origin>
CAMCORE_TAUTULLI_API_KEY=<Tautulli API key>
```

Jarvis calls Tautulli's `get_activity` command but converts the session-rich response into aggregate operational evidence before it reaches the model. Returned data is limited to:

- current stream count;
- transcode/direct-play/direct-stream counts;
- LAN/WAN stream counts;
- aggregate bandwidth;
- media-type counts;
- transcode-decision counts;
- playing/paused session-state counts.

Jarvis does **not** return Tautulli usernames, IP addresses, player identities, media titles, file paths or individual viewing history.

### Synology DSM — API discovery only

```dotenv
CAMCORE_SYNOLOGY_URL=<fixed DSM origin>
```

Jarvis calls only the documented `SYNO.API.Info` discovery endpoint and returns advertised `SYNO.API.*`, `SYNO.Core.*` and `SYNO.Storage.*` API names/versions. This is capability discovery, not an authenticated storage-health integration.

It must not be used as evidence for:

- physical disk or SMART state;
- storage-pool health;
- RAID/SHR layout or health;
- filesystem free space;
- NAS hardware health;
- UPS state.

Those remain unavailable until a documented, supportable read-only source is implemented.

## 3. Optional OpenAI hybrid inference

```dotenv
OPENAI_API_KEY=
CAMCORE_OPENAI_MODEL=gpt-5.6
CAMCORE_OPENAI_FALLBACK_LOCAL=true
CAMCORE_MEMBER_OPENAI_ENABLED=true
CAMCORE_ADMIN_OPENAI_ENABLED=true
CAMCORE_MEMBER_AUTO_PROVIDER=local
CAMCORE_ADMIN_AUTO_PROVIDER=local
```

`Auto` is local-first. OpenAI remains an explicit option when configured. See `OPENAI.md` for the provider boundary and rollback procedure.

## 4. Portainer Git stack

Use:

- Repository: `https://github.com/camcoreau/jarvis`
- Reference: `refs/heads/main`
- Compose path: `deploy/camcore/compose.yaml`
- Stack name: `camcore-jarvis`

`CAMCORE_JARVIS_RELEASE` must be an immutable image tag published by the CamCore image workflow. Do not use `latest`.

The compose file intentionally relies on named volumes and the immutable image rather than bind-mounting Portainer's temporary Git checkout.

Before the first deployment, create a private bridge network named
`camcore-ai-backend` (or the exact `CAMCORE_AI_NETWORK` value) in the same
Docker environment. Compose treats it as external and fails closed when the
network is absent. Attach only Ollama and the separately managed AI frontend to
it; configure that frontend to use `http://camcore-ollama:11434`. Jarvis remains
on `camcore-jarvis-ai` plus the NPM proxy network.

## 5. Reverse proxy configuration

Create the private proxy host:

- Domain: `jarvis.camcore.network`
- Scheme: `http`
- Forward hostname: `camcore-jarvis`
- Forward port: `8000`
- Websockets: enabled
- Block common exploits: enabled

The browser UI loads as static content, but API requests need the server-side headers.

For the administrator-only private host, the `/` custom location must inject the Jarvis API key and proxy identity secret. If a verified SSO/access layer is supplying user claims, map those verified values into the CamCore identity headers. Otherwise a static interim administrator identity can be used only on an already administrator-restricted private host.

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

## 6. Outline knowledge access

Jarvis connects to Outline over the internal Docker bridge:

```text
http://outline:3000/mcp
```

The CamCore profile sends static routing headers for Outline's canonical internal hostname and resolves the bearer credential only from `CAMCORE_OUTLINE_API_KEY` at runtime.

Tool discovery is restricted to:

- `list_documents` — search/list accessible documents;
- `fetch` — retrieve selected document content.

Documentation is authoritative for **documented state**, not current runtime health.

## 7. Internal DNS

Create only the internal DNS record for `jarvis.camcore.network` and point it to the private reverse-proxy path. Keep the administrator UI off public DNS.

## 8. Verify deployment

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
- `/identity` reports `admin` and trusted proxy identity metadata;
- capability inventory distinguishes attached capabilities from unavailable ones;
- each configured Operations source reports `LIVE` only after a successful current provider request;
- unconfigured optional integrations report a configuration error without taking down the rest of Operations;
- CamCore Media reports aggregate-only Tautulli activity and no viewer/media identity;
- Synology reports capability discovery and explicitly does not claim storage health.

A request sent through a trusted **member** path should receive HTTP 403 for `/v1/models` and `/v1/camcore/operations/*`, while `/v1/camcore/portal/chat/completions` remains available.

Verify startup logs also report the expected Outline tool discovery.

## Model changes

Change `CAMCORE_JARVIS_MODEL` in Portainer and redeploy. The model-init service pulls the selected model before Jarvis starts.

The remote web UI never preloads through client-local Ollama. Model preload is a desktop/Tauri-only optimisation; the server/deployment path owns Ollama in web mode.

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
- an explicit cross-stack AI network on which Ollama is the only Jarvis-stack service;
- separate proxy API key and trusted identity secret;
- server-side member/admin route isolation;
- external analytics disabled;
- Outline read-only knowledge access;
- Portainer allow-listed Docker evidence;
- Better Stack, YouTrack, Home Assistant, M365 and GitHub integrations are read-only and fixed-target/allow-listed;
- CamCore Media uses aggregate-only Tautulli activity;
- Synology DSM integration is discovery-only, not storage-health telemetry;
- write/shell tools disabled by default;
- server/block security profile;
- secret and PII scanning;
- SSRF protection and rate limiting;
- audit logging;
- explicit tool confirmation;
- proactive actions and channels disabled.

Expand a capability only after its read/write boundary, approval model, secret handling and audit behaviour are explicit and tested.
