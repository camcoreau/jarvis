import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BookOpen,
  Boxes,
  CheckCircle2,
  CircleDashed,
  RefreshCw,
  Server,
  ShieldCheck,
} from 'lucide-react';
import {
  fetchCamCoreOperationsOverview,
  type CamCoreCapability,
  type CamCoreOperationsOverview,
} from '../lib/camcore-api';

function EvidenceBadge({ capability }: { capability: CamCoreCapability }) {
  const label = capability.available
    ? capability.evidence === 'documented'
      ? 'DOCUMENTED'
      : capability.evidence === 'live-capable'
        ? 'AVAILABLE'
        : capability.evidence.toUpperCase()
    : 'UNAVAILABLE';
  const good = capability.available;
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-bold tracking-[0.08em]"
      style={{
        border: `1px solid ${good ? 'color-mix(in srgb, var(--color-success) 28%, transparent)' : 'var(--color-border)'}`,
        background: good
          ? 'color-mix(in srgb, var(--color-success) 8%, transparent)'
          : 'rgba(255,255,255,.018)',
        color: good ? 'var(--color-success)' : 'var(--color-text-tertiary)',
      }}
    >
      {good ? <CheckCircle2 size={10} /> : <CircleDashed size={10} />}
      {label}
    </span>
  );
}

export function DashboardPage() {
  const [overview, setOverview] = useState<CamCoreOperationsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setOverview(await fetchCamCoreOperationsOverview());
    } catch (err) {
      setOverview(null);
      setError(err instanceof Error ? err.message : 'Operations data is unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = setInterval(() => void refresh(), 30_000);
    return () => clearInterval(interval);
  }, [refresh]);

  const portainer = overview?.sources.portainer;
  const environments = portainer?.data?.environments ?? [];
  const totals = useMemo(
    () => ({
      containers: environments.reduce((sum, item) => sum + (item.container_count ?? 0), 0),
      running: environments.reduce((sum, item) => sum + (item.running ?? 0), 0),
      unhealthy: environments.reduce((sum, item) => sum + (item.unhealthy ?? 0), 0),
      capabilities: overview?.capabilities.filter((item) => item.available).length ?? 0,
    }),
    [environments, overview],
  );

  return (
    <div className="flex-1 overflow-y-auto px-6 py-8">
      <div className="max-w-6xl mx-auto">
        <header className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="camcore-hero-eyebrow">CamCore Operations</p>
            <h1 className="text-2xl font-semibold tracking-tight" style={{ color: 'var(--color-text)' }}>
              Operational <span className="camcore-gradient-text">Evidence</span>
            </h1>
            <p className="text-sm mt-3 max-w-3xl leading-6" style={{ color: 'var(--color-text-secondary)' }}>
              Current observations are kept separate from documented state and merely available capabilities. Jarvis never treats documentation or an attached connector as proof that a system is healthy now.
            </p>
          </div>
          <button
            onClick={() => void refresh()}
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold cursor-pointer disabled:opacity-50"
            style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh evidence
          </button>
        </header>

        {error && (
          <div
            className="mb-5 flex items-start gap-3 rounded-xl px-4 py-3 text-sm"
            style={{
              border: '1px solid color-mix(in srgb, var(--color-error) 20%, transparent)',
              background: 'color-mix(in srgb, var(--color-error) 7%, transparent)',
              color: 'var(--color-text)',
            }}
          >
            <AlertTriangle size={17} style={{ color: 'var(--color-error)', flexShrink: 0 }} />
            <div>
              <strong className="block text-xs mb-1">Operations evidence unavailable</strong>
              <span style={{ color: 'var(--color-text-secondary)' }}>{error}</span>
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          {[
            ['Environments', environments.length, Server],
            ['Containers running', totals.running, Boxes],
            ['Unhealthy', totals.unhealthy, Activity],
            ['Capabilities available', totals.capabilities, ShieldCheck],
          ].map(([label, value, Icon]) => {
            const MetricIcon = Icon as typeof Server;
            return (
              <div key={String(label)} className="rounded-2xl p-4" style={{ border: '1px solid var(--color-border)', background: 'rgba(255,255,255,.018)' }}>
                <div className="flex items-center justify-between gap-3 mb-3">
                  <span className="text-[11px] font-semibold" style={{ color: 'var(--color-text-tertiary)' }}>{String(label)}</span>
                  <MetricIcon size={15} style={{ color: 'var(--color-accent)' }} />
                </div>
                <div className="text-2xl font-semibold" style={{ color: 'var(--color-text)' }}>{String(value)}</div>
              </div>
            );
          })}
        </div>

        <section className="mb-6 rounded-2xl overflow-hidden" style={{ border: '1px solid var(--color-border)', background: 'rgba(255,255,255,.015)' }}>
          <div className="flex items-center justify-between gap-3 px-5 py-4" style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                <Boxes size={16} style={{ color: 'var(--color-accent)' }} />
                Docker control plane
              </div>
              <p className="text-xs mt-1" style={{ color: 'var(--color-text-tertiary)' }}>
                Portainer evidence covers Docker only — never NAS disks, SMART, storage pools, RAID/SHR or UPS state.
              </p>
            </div>
            <span
              className="px-2.5 py-1 rounded-full text-[10px] font-bold tracking-[0.08em]"
              style={{
                color: portainer?.state === 'live' ? 'var(--color-success)' : 'var(--color-text-tertiary)',
                border: '1px solid var(--color-border)',
              }}
            >
              {portainer?.state === 'live' ? 'LIVE' : portainer?.state?.toUpperCase() ?? 'CHECKING'}
            </span>
          </div>

          {portainer?.state === 'live' ? (
            <div className="divide-y" style={{ borderColor: 'var(--color-border-subtle)' }}>
              {environments.map((environment) => (
                <div key={String(environment.id)} className="px-5 py-4 flex flex-col gap-3 lg:flex-row lg:items-center">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>{environment.name}</div>
                    <div className="text-xs mt-1" style={{ color: 'var(--color-text-tertiary)' }}>
                      {environment.container_count ?? 0} containers · {environment.running ?? 0} running · {environment.unhealthy ?? 0} unhealthy
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(environment.containers ?? []).filter((item) => item.state !== 'running' || item.health === 'unhealthy').slice(0, 6).map((item) => (
                      <span key={item.id} className="px-2 py-1 rounded-lg text-[10px]" style={{ border: '1px solid var(--color-border)', color: item.health === 'unhealthy' ? 'var(--color-error)' : 'var(--color-warning)' }}>
                        {item.name}: {item.health ?? item.state}
                      </span>
                    ))}
                    {(environment.unhealthy ?? 0) === 0 && (environment.container_count ?? 0) === (environment.running ?? 0) && (
                      <span className="px-2 py-1 rounded-lg text-[10px]" style={{ color: 'var(--color-success)' }}>
                        No Docker exceptions observed
                      </span>
                    )}
                  </div>
                </div>
              ))}
              {environments.length === 0 && (
                <div className="px-5 py-6 text-sm" style={{ color: 'var(--color-text-tertiary)' }}>No Portainer environments were returned.</div>
              )}
            </div>
          ) : (
            <div className="px-5 py-6 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              {portainer?.detail ?? 'No live Portainer observation has completed.'}
            </div>
          )}
        </section>

        <section>
          <div className="flex items-center gap-2 mb-3">
            <BookOpen size={15} style={{ color: 'var(--color-accent)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>Capability inventory</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {(overview?.capabilities ?? []).map((capability) => (
              <article key={capability.id} className="rounded-2xl p-4" style={{ border: '1px solid var(--color-border)', background: 'rgba(255,255,255,.014)' }}>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>{capability.label}</h3>
                    <div className="text-[11px] mt-1" style={{ color: 'var(--color-text-tertiary)' }}>{capability.source}</div>
                  </div>
                  <EvidenceBadge capability={capability} />
                </div>
                <p className="text-xs leading-5" style={{ color: 'var(--color-text-secondary)' }}>{capability.scope}</p>
                {capability.requires_confirmation && (
                  <div className="mt-3 text-[10px] font-semibold" style={{ color: 'var(--color-warning)' }}>Explicit approval required for writes</div>
                )}
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
