# CamCore Portainer Operations connector

Jarvis Operations uses Portainer as the first live CamCore infrastructure control
plane. This connector is intentionally narrower than a generic HTTP, Docker
socket, or shell tool.

## Security model

- Portainer credentials are supplied only through the Jarvis container
  environment.
- The model cannot provide an arbitrary URL, HTTP header, or API key.
- Read tools return an allow-listed subset of Docker state. Container environment
  variables, Docker labels, raw mount source paths, and raw inspect payloads are
  not returned to the model.
- Container logs pass through the OpenJarvis secret and PII redactors before they
  are added to model context.
- `start`, `stop`, and `restart` are exposed through a separate tool with
  `requires_confirmation = true` and the `system:admin` capability.
- No delete, create, exec, image pull, stack redeploy, Docker socket, or arbitrary
  Portainer API operation is exposed in this phase.

## Runtime settings

Set these only in the Portainer stack environment:

```dotenv
CAMCORE_PORTAINER_URL=https://<final-internal-portainer-origin>
CAMCORE_PORTAINER_API_KEY=<portainer-access-token>
CAMCORE_PORTAINER_VERIFY_TLS=true
```

`CAMCORE_PORTAINER_URL` must point directly at the final Portainer API origin.
The connector deliberately rejects HTTP redirects so credentials are never
forwarded to a redirect target.

Use normal TLS verification whenever the internal Portainer certificate is
trusted by the Jarvis container. `CAMCORE_PORTAINER_VERIFY_TLS=false` exists only
for an explicitly accepted internal-certificate exception and should not be the
normal production setting.

## Model-visible tools

### `camcore_portainer_overview`

Reads Portainer environments and safe container summaries. It can include
stopped containers and reports Docker state/status plus health where Docker
provides a healthcheck.

### `camcore_portainer_container_status`

Reads one container's live Docker state and a filtered resource snapshot:

- run/stop/restart/paused/OOM/dead state
- Docker health status
- restart count
- network names (not per-container IP configuration)
- container mount destinations (not host source paths)
- CPU percentage
- memory usage/limit/percentage
- aggregate network RX/TX

The environment argument is optional when a container name is unique across the
Portainer estate.

### `camcore_portainer_container_logs`

Reads up to 500 recent stdout/stderr log lines. Secret and PII redaction is
applied before the text is returned to the model, and total returned log text is
bounded.

### `camcore_portainer_container_action`

Supports only:

- `start`
- `stop`
- `restart`

The tool is confirmation-gated. A normal read/diagnostic request must not invoke
this tool simply to inspect state.

## Initial validation

After setting the Portainer URL/token and redeploying Jarvis, use Administrator
Operations mode and test read access first:

> Show me the live Docker environments and containers you can currently see.

Then test a known container without changing it:

> Check the live status and resource usage of camcore-status.

Then test logs:

> Show the last 50 lines of camcore-status logs and tell me whether they contain
> an obvious error.

Do not use a real restart as the first validation. To validate action planning
without changing production, ask:

> If camcore-status needed a restart, which live checks would you perform first?

A later controlled test can exercise the confirmation-gated restart path on a
non-critical container when desired.
