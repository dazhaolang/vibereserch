import { apiClient } from './client';

export interface UsageStatsResponse {
  membership_type: string;
  usage: {
    total_projects: number;
    total_literature: number;
    total_tasks: number;
    completed_tasks: number;
    monthly_literature_used: number;
    monthly_queries_used: number;
  };
  limits: Record<string, number>;
  usage_percentage: Record<string, number>;
}

export async function fetchUsageStatistics(): Promise<UsageStatsResponse> {
  return (await apiClient.get<UsageStatsResponse>('/api/user/usage-statistics')) as unknown as UsageStatsResponse;
}
