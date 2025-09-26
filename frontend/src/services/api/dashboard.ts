import { apiClient } from './client';

export interface DashboardSnapshot {
  projectCount: number;
  literatureCount: number;
  runningTasks: number;
  recentInsights: Array<{ id: string; title: string; summary: string; created_at: string }>;
}

export async function fetchDashboardSnapshot(): Promise<DashboardSnapshot> {
  return (await apiClient.get<DashboardSnapshot>('/api/performance/dashboard')) as unknown as DashboardSnapshot;
}
