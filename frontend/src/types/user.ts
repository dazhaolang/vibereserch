export interface MembershipInfo {
  id: number;
  user_id: number;
  membership_type: string;
  monthly_literature_used: number;
  monthly_queries_used: number;
  total_projects?: number;
  subscription_start?: string | null;
  subscription_end?: string | null;
  auto_renewal?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface UserProfile {
  id: number;
  email: string;
  username: string;
  full_name?: string | null;
  institution?: string | null;
  research_field?: string | null;
  avatar_url?: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at?: string;
  updated_at?: string | null;
  last_login?: string | null;
  membership?: MembershipInfo | null;
}

export interface UsageStatisticsUsage {
  total_projects?: number;
  total_literature?: number;
  total_tasks?: number;
  completed_tasks?: number;
  monthly_literature_used?: number;
  monthly_queries_used?: number;
  [key: string]: number | undefined;
}

export interface UsageStatistics {
  membership_type: string;
  usage: UsageStatisticsUsage;
  limits: Record<string, number>;
  usage_percentage: Record<string, number>;
}
