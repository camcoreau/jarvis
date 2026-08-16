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
CAMCORE_TZ=Australia/Melbourne
```

`CAMCORE_JARVIS_RELEASE` must be an immutable image tag published by the
CamCore image workflow. Do not use `latest`.

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

The browser UI loads without API authentication, but `/v1` and `/api` are
protected by `OPENJARVIS_API_KEY`. To avoid placing that key in every browser,
add this to the Proxy Host **Advanced** configuration, replacing the placeholder
with the same secret stored in Portainer:

```nginx
proxy_set_header Authorization "Bearer <OPENJARVIS_API_KEY>";
```

NPM then supplies the credential to Jarvis server-side. The API key must never
be written into this repository or into a public-facing client bundle.

## 5. Internal DNS only

Create the internal DNS record for `jarvis.camcore.network` so CamCore clients
resolve it to the private reverse-proxy path. Do not publish the hostname as a
public internet service during the initial deployment.

## 6. Verify the deployment

After Portainer reports the stack healthy:

```bash
curl -I https://jarvis.camcore.network/
curl -s https://jarvis.camcore.network/v1/models
```

The first request should return the Jarvis UI. The second should return the
available model list through NPM's server-side authorization header.

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

The initial production profile is deliberately conservative:

- local Ollama inference;
- no public host ports;
- API-key enforcement;
- external analytics disabled;
- write/shell tools disabled;
- security profile set to `server` / `block`;
- audit logging enabled;
- explicit tool confirmation enabled;
- proactive actions and channels disabled.

Expand permissions only when the corresponding CamCore integration has a clear
read/write boundary, approval model and audit trail.
