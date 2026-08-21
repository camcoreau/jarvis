# Jarvis | CamCore AI

**Private AI operations for CamCore — Cameron Family Secure Network.**

Jarvis is CamCore's local-first AI assistant and operations interface. It is built on [OpenJarvis](https://github.com/open-jarvis/OpenJarvis) and keeps the upstream architecture intact wherever practical so security fixes and upstream improvements can continue to be merged without turning the fork into a rewrite.

> **Status:** private CamCore deployment. This repository is public source code; production credentials, private operational data and runtime secrets must never be committed here.

## What Jarvis does

Jarvis combines four deliberately separate kinds of information:

- **Documented state** — approved CamCore documentation fetched read-only from Outline.
- **Available capability** — a connector or tool attached to the current Operations session.
- **Live observation** — a successful current check against an approved operational source.
- **Approved action** — a modifying operation that has passed the relevant confirmation and audit controls.

Those categories are intentionally not interchangeable. Documentation is not proof that a service is healthy, and the presence of a tool is not proof that a backend is reachable.

## CamCore operating model

Jarvis is designed around these defaults:

- local inference first;
- least privilege;
- read before write;
- verify before change;
- explicit evidence labels;
- no credentials in model context, URLs, Git or browser bundles;
- separate member and administrator access planes;
- approval-gated modifying actions;
- auditable operational changes;
- public `camcore.au` and private `camcore.network` treated as distinct trust zones.

The production profile lives under [`deploy/camcore/`](deploy/camcore/).

## Access planes

### Member

The member surface is chat-only and does not inherit the Operations agent's tools or operational memory. It may receive approved read-only CamCore knowledge excerpts, but it cannot claim to have checked live infrastructure or performed a change.

The bundled Jarvis SPA is an administrator workspace. Member-facing clients use the dedicated `/v1/camcore/portal/*` API rather than the generic administrator `/v1` surface.

### Administrator / Operations

CamCore production can run in `trusted-proxy` mode. The reverse proxy still authenticates to Jarvis using `OPENJARVIS_API_KEY`, while a second proxy-only shared secret protects a trusted identity envelope containing the signed-in subject and CamCore role.

A `member` identity is restricted server-side to the member-safe portal routes. An `admin` identity can reach the explicitly protected Operations and upstream administrator APIs.

Browser-controlled role headers are not trusted. The authentication proxy must derive the role from its upstream SSO/access policy and add the identity headers only on the trusted proxy-to-Jarvis hop.

## Operations Centre

The CamCore UI separates **Operations** from **Runtime**:

- **Operations** shows approved infrastructure capabilities and current evidence from configured read-only sources, plus the existing confirmation-gated Docker control boundary.
- **Runtime** shows Jarvis inference telemetry, energy information, trace debugging and estimated local-vs-cloud cost comparison.

The capability inventory explicitly reports missing capabilities instead of pretending they are healthy. In particular, Portainer and Synology API discovery must never be used as evidence for Synology storage pools, SMART, RAID/SHR, filesystem capacity, NAS hardware or UPS state.

## Current CamCore integrations

### Outline — read-only knowledge

Jarvis discovers only the approved read tools used to search and fetch CamCore documentation. The Outline credential is supplied at runtime and is never committed.

### Portainer — Docker Operations

Jarvis can list Portainer environments, inspect allow-listed Docker state and health, read bounded/redacted logs and perform start/stop/restart only through confirmation-gated tooling. Portainer is not a NAS or host-storage monitor.

### Better Stack — uptime and incidents

Jarvis can read configured uptime monitor names/statuses and unresolved incident summaries. It deliberately omits request headers, response bodies and monitored URLs from the model-facing payload.

### YouTrack — read-only Operations work

Jarvis can read a bounded set of issues selected by a server-configured query. It returns issue IDs, summaries, project, resolution state and a small allow-list of operational custom fields. The tool has no issue-write method.

### Home Assistant — entity-scoped state

Jarvis can read current state only for entity IDs explicitly listed in `CAMCORE_HOMEASSISTANT_ENTITIES`. It does not enumerate all household state and drops location/arbitrary attributes from returned state objects.

### Microsoft 365 — service health

Jarvis can use a dedicated Microsoft Graph application with `ServiceHealth.Read.All` to read subscribed service health and current service issues. This integration does not grant mailbox, user, device or configuration write access.

### GitHub — allow-listed repository status

Jarvis can read bounded issue and Actions state only for repositories listed in `CAMCORE_GITHUB_REPOSITORIES`. No repository target can be supplied by the model, and the tool contains no write operation.

### CamCore Media — aggregate Tautulli activity

Jarvis can read current Tautulli activity as an aggregate operational summary: total streams, transcode/direct-play/direct-stream counts, LAN/WAN counts, media-type totals, session-state totals and aggregate bandwidth. It never returns usernames, IP addresses, media titles, file paths, player identities or individual viewing history to the model.

### Synology DSM — capability discovery only

Jarvis can call the documented `SYNO.API.Info` endpoint to discover API names and supported versions advertised by the configured DSM. This does **not** expose or claim physical disk, SMART, storage-pool, RAID/SHR, filesystem, hardware or UPS health.

## Remaining read-first integrations

The main remaining capability gaps are:

1. A documented and supportable Synology/host source for volume, storage-pool, SMART, hardware and UPS health.
2. Deeper host telemetry where Better Stack uptime checks are insufficient.
3. Optional Microsoft 365 licensing/device/security readers, each with its own least-privilege permission boundary.

Any write expansion requires a separately defined approval boundary, rollback path and audit behaviour.

## Production deployment

Jarvis is deployed as a private Portainer Git stack behind the CamCore reverse proxy. The stack:

- publishes no host port;
- keeps Ollama off the proxy network;
- exposes Ollama to the separately managed AI frontend only through the explicit private `camcore-ai-backend` Docker network;
- uses immutable GHCR commit-SHA image tags;
- runs Jarvis with a read-only root filesystem;
- drops all Linux capabilities;
- enables secret/PII scanning, SSRF protection, rate limits, confirmation enforcement and audit logging;
- disables external OpenJarvis analytics in the CamCore production profile.

See [`deploy/camcore/README.md`](deploy/camcore/README.md) for deployment and rollback instructions.

## Development

The internal Python package, CLI command and many compatibility identifiers deliberately remain `openjarvis`. Do not broadly rename them for branding purposes; keeping those internals stable materially reduces upstream merge conflicts.

Typical contributor setup follows upstream OpenJarvis:

```bash
git clone https://github.com/camcoreau/jarvis.git
cd jarvis
git remote add upstream https://github.com/open-jarvis/OpenJarvis.git
uv sync --extra dev
uv run pre-commit install
uv run pytest tests/ -v
```

CamCore work should be developed on `agent/*` branches and merged through pull requests after the relevant Python, Rust, frontend and deployment checks pass.

## Upstream sync

Do not force-reset CamCore `main` to upstream. Sync on a dedicated branch:

```bash
git checkout main
git pull origin main
git checkout -b agent/sync-openjarvis-YYYYMMDD
git fetch upstream
git merge --no-ff upstream/main
```

Resolve conflicts, validate the CamCore boundaries and merge the sync through a pull request.

More fork-maintenance guidance is in [`CAMCORE.md`](CAMCORE.md).

## Upstream OpenJarvis

Jarvis remains derived from OpenJarvis, a local-first personal AI framework developed as part of the Intelligence Per Watt research initiative. Upstream documentation, research material and community resources remain available from the original project:

- OpenJarvis source: `open-jarvis/OpenJarvis`
- OpenJarvis documentation: `open-jarvis.github.io/OpenJarvis`
- OpenJarvis project: `openjarvis.stanford.edu`
- Paper: arXiv `2605.17172`

Upstream copyright, attribution and Apache 2.0 licensing are retained.

## Licence

[Apache License 2.0](LICENSE)
