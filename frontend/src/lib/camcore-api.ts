import { apiFetch } from './api';

export type CamCoreRole = 'member' | 'admin' | 'legacy';
export type CamCoreEvidence =
  | 'live'
  | 'documented'
  | 'live-capable'
  | 'available'
  | 'unavailable';

export interface CamCoreIdentity {
  subject: string;
  role: CamCoreRole;
  email: string;
  display_name: string;
  auth_source: string;
}

export interface CamCoreCapability {
  id: string;
  label: string;
  available: boolean;
  source: string;
  scope: string;
  mode: 'read' | 'write';
  evidence: CamCoreEvidence;
  requires_confirmation: boolean;
}

export interface CamCoreCapabilityInventory {
  generated_at: string;
  capabilities: CamCoreCapability[];
}

export interface CamCorePortainerContainer {
  name: string;
  id: string;
  image: string;
  state: string;
  status: string;
  health?: string;
}

export interface CamCorePortainerEnvironment {
  id: number | string;
  name: string;
  portainer_status?: number;
  container_count?: number;
  running?: number;
  unhealthy?: number;
  containers?: CamCorePortainerContainer[];
  error?: string;
}

export interface CamCoreOperationsSource {
  state: 'live' | 'available' | 'unavailable' | 'error';
  evidence: CamCoreEvidence;
  source: string;
  observed_at?: string;
  detail?: string;
  data?: Record<string, unknown> & {
    source?: string;
    environment_count?: number;
    environments?: CamCorePortainerEnvironment[];
  };
}

export interface CamCoreOperationsOverview {
  generated_at: string;
  sources: Record<string, CamCoreOperationsSource> & {
    portainer: CamCoreOperationsSource;
  };
  capabilities: CamCoreCapability[];
}

export interface CamCoreProvider {
  id: 'auto' | 'local' | 'openai';
  label: string;
  available: boolean;
  model: string;
  privacy: string;
}

export interface CamCoreProviderStatus {
  default: string;
  autoResolved: 'local' | 'openai';
  fallbackLocal: boolean;
  providers: CamCoreProvider[];
}

async function readJson<T>(path: string): Promise<T> {
  const response = await apiFetch(path, { cache: 'no-store' });
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(detail || `CamCore request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchCamCoreIdentity(): Promise<CamCoreIdentity> {
  return readJson<CamCoreIdentity>('/v1/camcore/portal/identity');
}

export function fetchCamCoreCapabilities(): Promise<CamCoreCapabilityInventory> {
  return readJson<CamCoreCapabilityInventory>('/v1/camcore/operations/capabilities');
}

export function fetchCamCoreOperationsOverview(): Promise<CamCoreOperationsOverview> {
  return readJson<CamCoreOperationsOverview>('/v1/camcore/operations/overview');
}

export function fetchCamCoreProviderStatus(
  role: 'member' | 'admin' = 'admin',
): Promise<CamCoreProviderStatus> {
  return readJson<CamCoreProviderStatus>(
    `/v1/camcore/portal/providers?role=${encodeURIComponent(role)}`,
  );
}
