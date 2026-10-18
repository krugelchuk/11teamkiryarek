import { get, post } from './client';

export interface EnterpriseIntegration {
  id: string; title: string; caption: string; direction: string; status: 'not_connected'; mode: 'mock';
  description: string; fields: string[]; next_step: string; adapter: string;
}
export interface IntegrationCatalog { mode: 'mock'; external_calls: false; notice: string; items: EnterpriseIntegration[] }
export interface IntegrationPreview {
  provider: string; mode: 'mock'; external_calls: false; persisted: false; generated_at: string;
  notice: string; direction: string; request: Record<string, unknown>; response: Record<string, unknown>; steps: string[];
}
export const integrationApi = {
  list: () => get<IntegrationCatalog>('/api/admin/integrations'),
  preview: (provider: string) => post<IntegrationPreview>(`/api/admin/integrations/${encodeURIComponent(provider)}/preview`, {}),
};
