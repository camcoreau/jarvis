import { useState, useEffect, useCallback, useRef } from 'react';
import { Loader2, CheckCircle2, XCircle, Cpu, Server, Database, ShieldCheck } from 'lucide-react';
import {
  getSetupStatus,
  fetchModels,
  fetchRecommendedModel,
  type SetupStatus,
} from '../lib/api';
import { useAppStore } from '../lib/store';
import { isEmbedOnlyModel } from '../lib/model-capabilities';

const STEPS = [
  { key: 'ollama_ready', label: 'Inference Engine', icon: Cpu, detail: 'Starting Ollama...' },
  { key: 'model_ready', label: 'AI Model', icon: Database, detail: 'Loading model...' },
  { key: 'server_ready', label: 'Jarvis Core', icon: Server, detail: 'Starting local services...' },
] as const;

type StepKey = (typeof STEPS)[number]['key'];

function StepRow({
  icon: Icon,
  label,
  done,
  active,
  detail,
}: {
  icon: typeof Cpu;
  label: string;
  done: boolean;
  active: boolean;
  detail: string;
}) {
  return (
    <div
      className="flex items-center gap-4 px-5 py-4 rounded-xl transition-all"
      style={{
        background: done
          ? 'var(--color-accent-subtle)'
          : active
            ? 'var(--color-surface)'
            : 'transparent',
        border: active ? '1px solid var(--color-border)' : '1px solid transparent',
      }}
    >
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
        style={{
          background: done ? 'var(--color-accent-subtle)' : 'var(--color-bg-tertiary)',
          border: done ? '1px solid rgba(79,207,243,.2)' : '1px solid transparent',
          color: done ? 'var(--color-accent)' : 'var(--color-text-tertiary)',
        }}
      >
        <Icon size={18} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
          {label}
        </div>
        <div className="text-xs truncate" style={{ color: 'var(--color-text-tertiary)', maxWidth: '280px' }}>
          {done ? 'Ready' : active ? detail : 'Waiting...'}
        </div>
      </div>
      <div className="shrink-0">
        {done ? (
          <CheckCircle2 size={18} style={{ color: 'var(--color-success)' }} />
        ) : active ? (
          <Loader2 size={18} className="animate-spin" style={{ color: 'var(--color-accent)' }} />
        ) : (
          <div
            className="w-4 h-4 rounded-full"
            style={{ border: '2px solid var(--color-border)' }}
          />
        )}
      </div>
    </div>
  );
}

export function SetupScreen({ onReady }: { onReady: () => void }) {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const handedOffRef = useRef(false);
  const poll = useCallback(async () => {
    const s = await getSetupStatus();
    if (s) setStatus(s);
    if (s?.phase === 'ready' && !handedOffRef.current) {
      handedOffRef.current = true;
      try {
        const [models, rec] = await Promise.all([
          fetchModels().catch(() => []),
          fetchRecommendedModel().catch(() => ({ model: '', reason: '' })),
        ]);
        const store = useAppStore.getState();
        const hadSelection = !!store.selectedModel;
        store.setModels(models);
        store.setModelsLoading(false);
        const chatModels = models.filter((m) => !isEmbedOnlyModel(m.id));
        const recommended = rec.model && chatModels.some((m) => m.id === rec.model)
          ? rec.model
          : chatModels[0]?.id || '';
        if (recommended && !hadSelection) {
          store.setSelectedModel(recommended);
        }
      } catch {
        // Non-fatal: the main app can select a model after startup.
      }
      setTimeout(() => onReady(), 600);
    }
  }, [onReady]);

  useEffect(() => {
    poll();
    const interval = setInterval(poll, 800);
    return () => clearInterval(interval);
  }, [poll]);

  const activeStep: StepKey | null =
    status && !status.ollama_ready
      ? 'ollama_ready'
      : status && !status.model_ready
        ? 'model_ready'
        : status && !status.server_ready
          ? 'server_ready'
          : null;

  return (
    <div className="camcore-setup-shell fixed inset-0 flex items-center justify-center">
      <div className="w-full max-w-lg px-5">
        <section className="camcore-setup-card" aria-labelledby="jarvis-setup-title">
          <div className="mb-8">
            <div className="camcore-brand-mark mb-5" aria-hidden="true">
              <ShieldCheck size={20} />
            </div>
            <p className="camcore-hero-eyebrow">CamCore secure services</p>
            <h1 id="jarvis-setup-title" className="camcore-setup-brand">
              Jarvis <span className="camcore-gradient-text">CamCore AI</span>
            </h1>
            <p className="text-sm leading-6" style={{ color: 'var(--color-text-secondary)' }}>
              Preparing your private local-first operations assistant.
            </p>
          </div>

          <div className="flex flex-col gap-2 mb-7">
            {(status?.source === 'custom'
              ? [
                  { key: 'ollama_ready' as const, label: 'Inference Engine', icon: Cpu, detail: 'Connecting to your server...' },
                  { key: 'model_ready' as const, label: 'Model Endpoint', icon: Database, detail: 'Checking endpoint...' },
                  { key: 'server_ready' as const, label: 'Jarvis Core', icon: Server, detail: 'Starting local services...' },
                ]
              : STEPS
            ).map((step) => (
              <StepRow
                key={step.key}
                icon={step.icon}
                label={step.label}
                done={status?.[step.key] ?? false}
                active={activeStep === step.key}
                detail={activeStep === step.key && status?.detail ? status.detail : step.detail}
              />
            ))}
          </div>

          {status?.error && (
            <div
              className="flex items-start gap-3 px-4 py-3 rounded-xl text-sm"
              style={{
                background: 'color-mix(in srgb, var(--color-error) 10%, transparent)',
                border: '1px solid color-mix(in srgb, var(--color-error) 20%, transparent)',
                color: 'var(--color-error)',
              }}
            >
              <XCircle size={16} className="shrink-0 mt-0.5" />
              <span style={{ wordBreak: 'break-word', overflowWrap: 'anywhere' }}>{status.error}</span>
            </div>
          )}

          {!status?.error && (
            <div
              className="h-1 rounded-full overflow-hidden"
              style={{ background: 'var(--color-bg-tertiary)' }}
              aria-label="Jarvis startup progress"
            >
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  background: 'linear-gradient(90deg, #419eea, var(--color-accent), #bcecf4)',
                  width: `${
                    ((status?.ollama_ready ? 1 : 0) +
                      (status?.model_ready ? 1 : 0) +
                      (status?.server_ready ? 1 : 0)) *
                    33.33
                  }%`,
                }}
              />
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
