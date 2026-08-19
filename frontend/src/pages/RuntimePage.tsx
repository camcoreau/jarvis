import { EnergyDashboard } from '../components/Dashboard/EnergyDashboard';
import { CostComparison } from '../components/Dashboard/CostComparison';
import { TraceDebugger } from '../components/Dashboard/TraceDebugger';

export function RuntimePage() {
  const now = new Date();
  const stamp = now.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';

  return (
    <div className="flex-1 overflow-y-auto px-6 py-10">
      <div className="max-w-5xl mx-auto">
        <header className="mb-7">
          <p className="camcore-hero-eyebrow">Jarvis runtime</p>
          <div className="flex items-end justify-between gap-4">
            <h1 className="text-2xl font-semibold tracking-tight" style={{ color: 'var(--color-text)' }}>
              Runtime <span className="camcore-gradient-text">Overview</span>
            </h1>
            <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              {stamp}
            </div>
          </div>
          <p className="text-sm mt-3 max-w-2xl leading-6" style={{ color: 'var(--color-text-secondary)' }}>
            Local Jarvis runtime telemetry — inference activity, power draw, token throughput and estimated cloud-cost comparison for suitable on-device workloads.
          </p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
          <EnergyDashboard />
          <CostComparison />
        </div>

        <TraceDebugger />
      </div>
    </div>
  );
}
