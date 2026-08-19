import { useEffect, useState } from 'react';
import { Outlet, useNavigate } from 'react-router';
import { ApprovalBell } from './ApprovalBell';
import { Sidebar } from './Sidebar/Sidebar';
import { SystemPulse } from './SystemPulse';
import { useAppStore } from '../lib/store';
import { checkHealth } from '../lib/api';
import { fetchCamCoreIdentity, type CamCoreIdentity } from '../lib/camcore-api';

export function Layout() {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const [apiReachable, setApiReachable] = useState<boolean | null>(null);
  const [identity, setIdentity] = useState<CamCoreIdentity | null>(null);

  useEffect(() => {
    const check = () => checkHealth().then(setApiReachable);
    check();
    const interval = setInterval(check, 30000);
    const onFocus = () => check();
    window.addEventListener('focus', onFocus);
    return () => {
      clearInterval(interval);
      window.removeEventListener('focus', onFocus);
    };
  }, []);

  useEffect(() => {
    fetchCamCoreIdentity().then(setIdentity).catch(() => setIdentity(null));
  }, []);

  const navigate = useNavigate();
  const backendLabel = apiReachable === false ? 'Backend unavailable' : apiReachable === null ? 'Checking backend' : 'Systems connected';
  const sessionLabel = identity?.display_name || identity?.email || (identity?.role === 'admin' ? 'Administrator' : 'CamCore session');

  return (
    <div className="camcore-shell flex h-full w-full overflow-hidden relative">
      <div className="hud-backdrop" aria-hidden="true" />
      <SystemPulse apiReachable={apiReachable} />
      <ApprovalBell />

      <Sidebar />
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/45 md:hidden"
          onClick={() => useAppStore.getState().setSidebarOpen(false)}
        />
      )}

      <main className="camcore-workspace flex-1 flex flex-col min-w-0 h-full relative z-10">
        <div className="camcore-status-strip shrink-0" aria-label="Jarvis system status">
          <span className="camcore-status-product">Jarvis</span>
          <span className="camcore-status-divider" aria-hidden="true" />
          <span className="camcore-status-context">CamCore AI</span>
          <span className="camcore-status-divider" aria-hidden="true" />
          <span className="camcore-status-context">{sessionLabel}</span>
          {identity?.role === 'admin' && (
            <span className="camcore-status-context" style={{ color: 'var(--color-accent)' }}>ADMIN</span>
          )}
          <span className="camcore-status-spacer" />
          <span className="camcore-status-context">Local-first</span>
          <span className="camcore-status-pill">
            <span className="camcore-status-dot" aria-hidden="true" />
            {backendLabel}
          </span>
        </div>

        {apiReachable === false && (
          <div
            className="flex items-center gap-3 px-4 py-2 text-sm shrink-0"
            style={{
              background: 'color-mix(in srgb, var(--color-error) 8%, transparent)',
              borderBottom: '1px solid color-mix(in srgb, var(--color-error) 15%, transparent)',
              color: 'var(--color-text)',
            }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full shrink-0"
              style={{ background: 'var(--color-error)' }}
            />
            <span>Jarvis cannot reach its local backend.</span>
            <button
              onClick={() => navigate('/settings')}
              className="text-sm underline cursor-pointer ml-auto shrink-0"
              style={{ color: 'var(--color-accent)' }}
            >
              Check connection
            </button>
          </div>
        )}

        <div className="flex-1 flex flex-col min-w-0 min-h-0 relative z-[2]">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
