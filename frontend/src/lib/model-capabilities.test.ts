import { describe, expect, it } from 'vitest';

import {
  cloudProvider,
  inferenceProviderLabel,
  isCloudModel,
  isEmbedOnlyModel,
} from './model-capabilities';

describe('isEmbedOnlyModel', () => {
  it.each([
    'nomic-embed-text',
    'mxbai-embed-large',
    'text-embedding-3-small',
    'all-minilm:latest',
    'hf.co/BAAI/bge-m3:latest',
  ])('classifies %s as embedding-only', (modelId) => {
    expect(isEmbedOnlyModel(modelId)).toBe(true);
  });

  it.each(['qwen3.5:4b', 'codegemma:7b'])('keeps %s available for chat', (modelId) => {
    expect(isEmbedOnlyModel(modelId)).toBe(false);
  });
});

describe('inference provider labels', () => {
  it.each([
    ['gpt-5.6', 'OpenAI'],
    ['o3', 'OpenAI'],
    ['claude-sonnet-4-6', 'Anthropic'],
    ['gemini-2.5-pro', 'Google'],
    ['openrouter/example', 'OpenRouter'],
  ])('identifies %s as cloud provider %s', (modelId, provider) => {
    expect(cloudProvider(modelId)).toBe(provider);
    expect(isCloudModel(modelId)).toBe(true);
    expect(inferenceProviderLabel(modelId)).toBe(`Cloud · ${provider}`);
  });

  it.each(['qwen3.5:4b', 'llama3.2:latest', ''])('labels %s as CamCore local', (modelId) => {
    expect(isCloudModel(modelId)).toBe(false);
    expect(inferenceProviderLabel(modelId)).toBe('Local · CamCore');
  });
});
