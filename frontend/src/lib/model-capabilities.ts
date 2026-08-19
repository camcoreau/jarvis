const EMBEDDING_MODEL_PREFIXES = [
  'all-minilm',
  'bge-',
  'bge_',
  'e5-',
  'e5_',
  'gte-',
  'gte_',
  'jina-embeddings',
  'nomic-bert',
  'sentence-transformers',
];

const CLOUD_PROVIDERS: Array<[RegExp, string]> = [
  [/^(gpt-|chatgpt-|o1(?:-|$)|o3(?:-|$)|o4(?:-|$))/i, 'OpenAI'],
  [/^claude-/i, 'Anthropic'],
  [/^gemini-/i, 'Google'],
  [/^openrouter\//i, 'OpenRouter'],
];

function modelLeaf(modelId: string | null | undefined): string {
  const name = (modelId ?? '').trim().toLowerCase();
  return name.slice(name.lastIndexOf('/') + 1).split(':')[0];
}

export function isEmbedOnlyModel(modelId: string | null | undefined): boolean {
  const leaf = modelLeaf(modelId);
  return (
    leaf.includes('embed') ||
    leaf.includes('minilm') ||
    EMBEDDING_MODEL_PREFIXES.some((prefix) => leaf.startsWith(prefix))
  );
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
