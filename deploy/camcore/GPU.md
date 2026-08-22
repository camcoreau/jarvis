# CamCore Ollama GPU acceleration

The CamCore production Ollama service uses the Intel integrated GPU passed through to the Ganymede VM.

## Host prerequisite

Before deploying the Jarvis stack, Ganymede must expose a DRM render node:

```bash
ls -la /dev/dri
```

The expected compute device is:

```text
/dev/dri/renderD128
```

The Jarvis compose file passes `/dev/dri` only to `camcore-jarvis-ollama`. No host GPU device is exposed to Jarvis itself or to the model-init container.

## Ollama settings

The standard `ollama/ollama` image bundles Vulkan support and enables Vulkan discovery by default when GPU devices are available. CamCore therefore does not force `OLLAMA_VULKAN`.

Intel UHD Graphics 630 is an integrated GPU. Ollama filters integrated Vulkan GPUs unless they are explicitly admitted, so the production service sets:

```text
OLLAMA_IGPU_ENABLE=1
```

The production image remains pinned to the approved Ollama version and digest.

## Deployment

Redeploy the `camcore-jarvis` Portainer Git stack from `refs/heads/main` after the GPU configuration is merged.

Docker will fail the Ollama container start if the configured `/dev/dri` host path is unavailable. Verify GPU passthrough to Ganymede before redeploying.

## Verification

After redeploy:

```bash
docker exec camcore-jarvis-ollama ls -la /dev/dri
```

Confirm `renderD128` is visible inside the container.

Check Ollama GPU discovery:

```bash
docker logs camcore-jarvis-ollama 2>&1 | grep -Ei 'vulkan|gpu|intel|integrated'
```

Run a short inference request, then inspect the active model:

```bash
docker exec camcore-jarvis-ollama ollama ps
```

The `PROCESSOR` column should show GPU use (or a CPU/GPU split) instead of `100% CPU` when Vulkan acceleration is active.

If Ollama still uses CPU only, keep the service available and inspect the discovery logs before forcing a specific Vulkan library or device. Do not remove the CPU fallback until GPU operation is verified stable.
