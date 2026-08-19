const EMBED_ONLY_PATTERNS = [
  /embed/i,
  /embedding/i,
  /nomic-embed/i,
  /bge-[a-z0-9-]*-?embedding/i,
  /e5-[a-z0-9-]*-?embedding/i,
];

const CLOUD_PROVIDERS: Array<[RegExp, string]> = [
  [/^(gpt-|o1-|o3-|o4-)/i, 'OpenAI'],
  [/^claude-/i, 'Anthropic'],
  [/^gemini-/i, 'Google'],
  [/^openrouter\//i, 'OpenRouter'],
];

export function isEmbedOnlyModel(modelId: string | null | undefined): boolean {
  const value = (modelId ?? '').trim();
  return value.length > 0 && EMBED_ONLY_PATTERNS.some((pattern) => pattern.test(value));
}

export function cloudProvider(modelId: string | null | undefined): string | null {
  const value = (modelId ?? '').trim();
  if (!value) return null;
  for (const [pattern, provider] of CLOUD_PROVIDERS) {
    if (pattern.test(value)) return provider;
  }
  return null;
}

export function isCloudModel(modelId: string | null | undefined): boolean {
  return cloudProvider(modelId) !== null;
}

export function inferenceProviderLabel(modelId: string | null | undefined): string {
  const provider = cloudProvider(modelId);
  return provider ? `Cloud · ${provider}` : 'Local · CamCore';
}
