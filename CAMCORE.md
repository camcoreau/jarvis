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
- Prefer CamCore-specific agents, configs, connectors, skills and UI branding layers over invasive core rewrites.

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

## First CamCore agent

The initial `camcore_assistant` agent extends OpenJarvis's `orchestrator` instead of replacing it. This preserves upstream tool calling, event handling and execution behaviour while adding CamCore-specific operating rules.

Its default posture is:

- local-first;
- read-mostly;
- least privilege;
- verify before changing;
- protect credentials and private operational data;
- distinguish public `camcore.au` services from private `camcore.network` services;
- require clear user intent for destructive, security-sensitive or externally visible actions.

The starter profile is `configs/camcore/camcore-assistant.toml`.

## Secrets and configuration

Never commit production secrets, tokens, passwords, private keys or session material to this repository.

- Use environment variables or an external secret store for credentials.
- Keep the HTTP API bound to loopback by default.
- If Jarvis is later exposed to the LAN or through a reverse proxy, configure authentication before changing the bind address.
- Give each connector only the minimum permissions needed for its job.
- Prefer read-only credentials until a write workflow has explicit approval and audit controls.

## CamCore integration roadmap

1. Foundation agent, local profile and tests.
2. CamCore visual branding for desktop/web UI.
3. Read-only infrastructure context and health integrations.
4. Microsoft 365 and GitHub operational context.
5. YouTrack/support and documentation integrations.
6. Media stack and Home Assistant integrations.
7. Approval-gated write actions with audit logging.
8. Scheduled monitoring and proactive operational briefings.

## Upstream attribution

This repository remains a fork of OpenJarvis and retains its Apache 2.0 licensing and upstream attribution. CamCore-specific branding should not remove required copyright or licence notices.
