# Jarvis | CamCore AI

This fork adds a CamCore-specific operations layer to OpenJarvis while keeping the upstream architecture intact wherever practical.

## Product identity

**Jarvis | CamCore AI** is the private AI operations assistant for CamCore — Cameron Family Secure Network.

The design goal is local-first operation with controlled access to CamCore infrastructure, documentation and connected services. Cloud inference or external APIs should only be used when they are intentionally configured or required for a task.

## Fork strategy

Keep CamCore changes narrow and separated from upstream code so future OpenJarvis updates remain practical to merge.

- `main` is the CamCore release branch.
- Feature work is developed on `agent/*` branches and merged through pull requests.
- Upstream source is `open-jarvis/OpenJarvis`.
- Avoid broad renames of Python packages, CLI commands or internal OpenJarvis primitives unless there is a strong technical reason.
- Prefer CamCore-specific agents, configs, routes, tools and UI overlay layers over invasive core rewrites.

### Recommended upstream remote

```bash
git remote add upstream https://github.com/open-jarvis/OpenJarvis.git
git fetch upstream
```

### Recommended upstream sync flow

```bash
git checkout main
git pull origin main
git checkout -b agent/sync-openjarvis-YYYYMMDD
git fetch upstream
git merge --no-ff upstream/main
```

Resolve conflicts on the sync branch, run the full relevant test suite, then merge through a pull request. Do not force-update `main` to match upstream.

## Main branch protection target

`main` should be protected before CamCore-specific development is merged. Target controls:

- Require a pull request before merging.
- Require at least one approval when another reviewer is available.
- Require status checks to pass.
- Require conversation resolution before merging.
- Block force pushes and branch deletion.
- Prefer squash merging for CamCore feature branches.

The repository's branch/ruleset settings are a GitHub control-plane responsibility; source code cannot substitute for these rules.

## CamCore agent

`camcore_assistant` extends OpenJarvis's `orchestrator` instead of replacing it. This preserves upstream tool calling, event handling and execution behaviour while adding CamCore-specific operating rules.

Its default posture is:

- local-first;
- read-mostly;
- least privilege;
- verify before changing;
- protect credentials and private operational data;
- distinguish public `camcore.au` services from private `camcore.network` services;
- distinguish documented state, available capability and successful live observation;
- require clear user intent for destructive, security-sensitive or externally visible actions.

The starter profile is `configs/camcore/camcore-assistant.toml`; the hardened production profile is `deploy/camcore/config.toml`.

## Access boundary

CamCore production uses `trusted-proxy` mode in addition to the normal OpenJarvis API key.

- `OPENJARVIS_API_KEY` authenticates the reverse proxy to Jarvis.
- `CAMCORE_PROXY_IDENTITY_SECRET` authenticates the proxy's human identity envelope.
- The proxy asserts a stable subject and a `member` or `admin` role derived from its trusted authentication/SSO policy.
- Member identities are restricted server-side to the member-safe portal API.
- Administrator identities can reach the private Operations surface.
- Browser/query-controlled role input is not authorization.

`legacy` mode remains available for ordinary local/upstream OpenJarvis compatibility and does not manufacture a CamCore identity.

The bundled Jarvis SPA is an administrator workspace: it uses the generic Operations agent routes. Member-facing clients must use the dedicated `/v1/camcore/portal/*` member API and must not inherit the administrator SPA's generic `/v1` surface.

## Capability truthfulness

Every CamCore integration must preserve four distinct states:

1. **Documented** — information retrieved from approved documentation.
2. **Available** — an approved tool is attached to this session and can be attempted.
3. **Live** — a successful current provider request produced an observation.
4. **Approved action** — a modifying operation passed the required confirmation/audit boundary.

Never promote documented or merely available state into a live health claim.

## Secrets and configuration

Never commit production secrets, tokens, passwords, private keys or session material to this repository.

- Use environment variables or an external secret store for credentials.
- Keep provider URLs and credentials server-side; the model may select only bounded logical parameters.
- Give each integration only the minimum permissions needed for its job.
- Prefer read-only credentials until a write workflow has explicit approval and audit controls.
- Do not expose raw provider payloads when an allow-listed summary can answer the operational question.
- Do not put proxy/API/provider credentials into browser localStorage or client bundles.

## Current CamCore integration boundary

Implemented read-first integrations:

- Outline — read-only documentation search/fetch.
- Portainer — Docker state/resources/logs plus confirmation-gated start/stop/restart.
- Better Stack — monitor state and unresolved incidents.
- YouTrack — bounded read-only issue/work context.
- Home Assistant — state for server allow-listed entities only.
- Microsoft Graph — Microsoft 365 service health/issues only.
- GitHub — bounded issue/Actions state for server allow-listed repositories.
- Tautulli — aggregate current CamCore Media activity only; no viewer identity, IPs, titles, paths or individual viewing details.
- Synology DSM — `SYNO.API.Info` capability discovery only.

Explicitly **not** implemented as live truth yet:

- Synology physical disk/SMART/storage-pool/RAID/SHR/filesystem/hardware/UPS health;
- unrestricted Home Assistant entity access or service calls;
- Microsoft 365 mailbox/user/device/configuration writes;
- YouTrack writes;
- GitHub writes;
- media control or individual viewing-history access.

## Integration roadmap

1. ~~Foundation agent, local profile and tests.~~
2. ~~CamCore visual branding for desktop/web UI.~~
3. ~~Read-only monitoring/context foundation and evidence-labelled Operations Centre.~~
4. ~~Microsoft 365 service-health and GitHub read context.~~
5. ~~YouTrack/support read context and Outline documentation.~~
6. ~~Home Assistant allow-listed read state and aggregate CamCore Media activity.~~
7. Portainer container control is the first approval-gated write boundary; other providers remain read-only.
8. Scheduled monitoring and proactive operational briefings remain deliberately disabled until the access/audit model is proven in production.
9. Add a documented/supportable Synology or host-monitoring source for storage/SMART/UPS health before exposing those facts as live observations.

## Upstream attribution

This repository remains a fork of OpenJarvis and retains its Apache 2.0 licensing and upstream attribution. CamCore-specific branding should not remove required copyright or licence notices.
