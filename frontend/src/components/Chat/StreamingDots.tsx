interface Props {
  phase: string;
}

function displayPhase(phase: string): string {
  if (phase === 'Generating...' || phase === 'Agent thinking...') {
    return 'Jarvis is thinking...';
  }
  return phase;
}

export function StreamingDots({ phase }: Props) {
  const label = displayPhase(phase);
  return (
    <div className="flex items-center gap-2 py-2" aria-live="polite">
      <div className="flex gap-1" aria-hidden="true">
        <span
          className="w-1.5 h-1.5 rounded-full animate-bounce"
          style={{ background: 'var(--color-text-tertiary)', animationDelay: '0ms' }}
        />
        <span
          className="w-1.5 h-1.5 rounded-full animate-bounce"
          style={{ background: 'var(--color-text-tertiary)', animationDelay: '150ms' }}
        />
        <span
          className="w-1.5 h-1.5 rounded-full animate-bounce"
          style={{ background: 'var(--color-text-tertiary)', animationDelay: '300ms' }}
        />
      </div>
      {label && (
        <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
          {label}
        </span>
      )}
    </div>
  );
}
