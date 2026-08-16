# Jarvis | CamCore AI — production deployment

This directory defines the private CamCore production deployment for Jarvis.
It is designed for a Portainer Git stack behind the existing Nginx Proxy
Manager (NPM) instance.

## Architecture

- `camcore-jarvis` serves the Jarvis web UI and API on container port `8000`.
- `camcore-jarvis-ollama` provides local inference and is not published to the
  Docker host.
- `camcore-jarvis-model-init` ensures the selected Ollama model is present before
  Jarvis starts.
- `camcore-jarvis-data` persists Jarvis databases, credentials, traces, skills,
  sessions and other runtime state.
- `camcore-jarvis-ollama-models` persists downloaded model data.
- Jarvis joins the Docker network shared with NPM. Ollama does not.
- No service in this stack publishes a host port.
- The CamCore production `config.toml` is baked into the immutable Jarvis image
  at `/etc/openjarvis/camcore-config.toml`. The Portainer stack does not rely on
  bind mounts from Portainer's temporary Git checkout.
- CamCore documentation is available to Jarvis through Outline's Streamable HTTP
  MCP endpoint over the shared `npm-backend` Docker network. The CamCore profile
  exposes only the read-only `list_documents` and `fetch` tools.

The deployment intentionally remains private. Do not create a public proxy host
or public DNS record for Jarvis during the foundation phase.

## 1. Confirm the NPM Docker network

On the Portainer host, identify the external Docker network already shared with
Nginx Proxy Manager:

```bash
docker network ls
```

Use that exact network name for `CAMCORE_PROXY_NETWORK`. The compose file will
fail closed if the value is missing instead of silently creating an isolated
network that NPM cannot reach.

## 2. Generate the Jarvis API key

Generate a strong key on the host:

```bash
python3 -c 'import secrets; print("oj_sk_" + secrets.token_urlsafe(32))'
```

Store the result in Portainer as `OPENJARVIS_API_KEY`. Do not commit it to Git.
The same key is also used in the NPM proxy configuration described below.

## 3. Create the Portainer Git stack

Use:

- Repository: `https://github.com/camcoreau/jarvis`
- Reference: `refs/heads/main`
- Compose path: `deploy/camcore/compose.yaml`
- Stack name: `camcore-jarvis`

Set these environment variables in Portainer:

```dotenv
CAMCORE_JARVIS_RELEASE=<published main commit SHA>
CAMCORE_JARVIS_MODEL=qwen3.5:4b
CAMCORE_PROXY_NETWORK=<existing NPM Docker network>
OPENJARVIS_API_KEY=<generated secret>
CAMCORE_OUTLINE_API_KEY=<read-only Outline API key>
CAMCORE_TZ=Australia/Melbourne
```

`CAMCORE_JARVIS_RELEASE` must be an immutable image tag published by the
CamCore image workflow. Do not use `latest`.

`CAMCORE_OUTLINE_API_KEY` is resolved only at runtime through the MCP server's
`token_env` setting. The real credential must exist only in Portainer (or another
runtime secret store) and must never be written into `config.toml`, this
repository, a URL, or client-side code.

The Outline credential should be limited to the `documents.list` and
`documents.info` scopes. Those scopes are sufficient for the configured MCP
`list_documents` search tool and `fetch` document reader. The Jarvis config also
applies an `include_tools` allowlist for those two tools so Outline write-capable
tools are not exposed to the CamCore agent.

The compose file intentionally contains no repository-file `configs:` mount.
This avoids Portainer Git-stack deployments failing when their temporary checkout
path is not available to the Docker daemon at container-create time.

On the first deployment, model download can take some time. Jarvis intentionally
waits for the model-init service to complete before starting.

## 4. Configure Nginx Proxy Manager

Create a private Proxy Host with:

- Domain: `jarvis.camcore.network`
- Scheme: `http`
- Forward hostname: `camcore-jarvis`
- Forward port: `8000`
- Websockets: enabled
- Block common exploits: enabled
- Main Proxy Host **Advanced** configuration: leave empty for Jarvis-specific
  authorization headers.

The browser UI loads without API authentication, but `/v1` and `/api` are
protected by `OPENJARVIS_API_KEY`. NPM must inject the key server-side so it is
not stored in every browser.

Create a **Custom Location** for `/` with the same upstream:

- Location: `/`
- Scheme: `http`
- Forward hostname: `camcore-jarvis`
- Forward port: `8000`

Add this to that custom location's **Advanced** configuration, replacing the
placeholder with the same secret stored in Portainer:

```nginx
proxy_set_header Authorization "Bearer <OPENJARVIS_API_KEY>";

# Jarvis chat uses Server-Sent Events. Do not buffer or cache the stream, and
# allow long local-model turns to remain connected.
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
```

The authorization directive belongs inside the custom location because NPM's
generated location block defines its own proxy headers. Putting the Jarvis
Authorization header only in the Proxy Host's top-level Advanced configuration
can leave the upstream request without the intended header.

NPM then supplies the credential to Jarvis server-side. The API key must never
be written into this repository or into a public-facing client bundle.

## 5. Outline knowledge access

Jarvis and Outline are both attached to `npm-backend`, so Jarvis connects to the
Outline container directly instead of resolving `docs.camcore.network` to NPM's
LAN/macvlan address:

```text
http://outline:3000/mcp
```

Outline still needs the request context associated with its canonical internal
hostname. The MCP transport therefore sends these static, non-secret routing
headers:

```text
Host: docs.camcore.network
X-Forwarded-Host: docs.camcore.network
X-Forwarded-Proto: https
```

This route was verified live from `camcore-jarvis` against Outline 1.9.2: the
MCP `initialize` request returned HTTP 200 with `text/event-stream` and reported
server name `outline`, version `1.9.2`.

The bearer credential remains separate in `CAMCORE_OUTLINE_API_KEY`; the static
header feature rejects `Authorization`, `Content-Type`, `Accept`, and
`Mcp-Session-Id` overrides so secrets and protocol state cannot be moved into
repository configuration.

Outline's MCP route filters available tools by the scopes attached to the
authenticated token. The CamCore profile additionally filters discovery to:

- `list_documents` — full-text search/listing of accessible documents.
- `fetch` — retrieve the selected document's full content.

Jarvis is instructed to consult this source for documented CamCore architecture,
server roles, services, policies, standards, procedures and configuration. It
must not treat documentation as proof that a host or service is currently online.
Live health should come from a monitoring integration when one is added.

If the Outline MCP integration cannot authenticate, Jarvis should continue to
run without those tools and log the discovery failure. The Docker stack itself
requires `CAMCORE_OUTLINE_API_KEY`, preventing an accidental deployment that
omits the configured credential entirely.

## 6. Internal DNS only

Create the internal DNS record for `jarvis.camcore.network` so CamCore clients
resolve it to the private reverse-proxy path. Do not publish the hostname as a
public internet service during the initial deployment.

## 7. Verify the deployment

After Portainer reports the stack healthy, test from a CamCore client that can
reach the private NPM endpoint:

```bash
curl -I https://jarvis.camcore.network/
curl -s https://jarvis.camcore.network/v1/models
```

The first request should return the Jarvis UI. The second should return the
available model list through NPM's server-side authorization header.

Verify the SSE chat path separately with a streaming client. A healthy request
returns an OpenAI-compatible sequence and finishes with `data: [DONE]`:

```bash
curl -N \
  -H 'Content-Type: application/json' \
  --data-binary @jarvis-test.json \
  https://jarvis.camcore.network/v1/chat/completions
```

Example `jarvis-test.json`:

```json
{"model":"qwen3.5:4b","messages":[{"role":"user","content":"Reply with exactly OK"}],"stream":true}
```

In the Jarvis startup logs, verify that Outline discovery succeeds and reports
two tools from `camcore-outline`, for example:

```text
Discovered 2 MCP tools from server 'camcore-outline'
```

Then use a knowledge-grounding test such as:

> Who or what are Earth, Jupiter, Ganymede, Saturn, Mars, Venus and Europa in
> CamCore? Search the CamCore knowledge base before answering. Tell me which
> documentation you used and do not guess.

In Portainer, confirm:

- `camcore-jarvis` is healthy.
- `camcore-jarvis-ollama` is healthy.
- `camcore-jarvis-model-init` exited successfully.
- `camcore-jarvis-data-init` exited successfully.
- Neither Jarvis nor Ollama has a published host port.

## Model changes

Change `CAMCORE_JARVIS_MODEL` in Portainer and redeploy. The model-init service
will ask Ollama to pull the selected model before Jarvis starts with it.

Start conservatively. Increase model size only after checking memory pressure,
CPU load and response latency on the host.

## Rollback

Rollback is intentionally simple:

1. Set `CAMCORE_JARVIS_RELEASE` to the previous known-good published commit SHA.
2. Redeploy the stack.
3. Leave the persistent data and Ollama model volumes in place.

The immutable image tag makes application rollback independent of the persistent
Jarvis state.

## Backups

Back up these Docker volumes as part of the normal CamCore backup process:

- `camcore-jarvis-data`
- `camcore-jarvis-ollama-models` (optional if model re-download time is acceptable)

The Jarvis data volume is the important one. It can contain credentials, memory,
audit data, traces, skills and session state and should be treated as sensitive.

## Security posture

The production profile is deliberately conservative:

- local Ollama inference;
- no public host ports;
- API-key enforcement;
- external analytics disabled;
- public savings/leaderboard sharing disabled in the CamCore frontend;
- Outline MCP credentials supplied only at runtime;
- Outline MCP traffic kept on the shared internal Docker bridge;
- Outline MCP discovery restricted to `list_documents` and `fetch`;
- write/shell tools disabled;
- security profile set to `server` / `block`;
- audit logging enabled;
- explicit tool confirmation enabled;
- proactive actions and channels disabled.

Expand permissions only when the corresponding CamCore integration has a clear
read/write boundary, approval model and audit trail.
