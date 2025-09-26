import { apiClient } from './client';
import type { InteractionSelectionResponse, InteractionTimeoutResponse } from '@/types';

export interface ClarificationOption {
  option_id: string;
  title: string;
  description: string;
  estimated_time?: string;
  estimated_results?: string;
  is_recommended?: boolean;
}

export interface ClarificationCard {
  session_id: string;
  stage: string;
  question: string;
  options: ClarificationOption[];
  timeout_seconds: number;
  custom_input_allowed: boolean;
  recommended_option_id?: string;
}

export interface StartInteractionResponse {
  success: boolean;
  session_id: string;
  requires_clarification: boolean;
  clarification_card?: ClarificationCard;
  direct_result?: unknown;
  error?: string;
  error_code?: string;
}

export async function startInteraction(payload: {
  project_id: number;
  context_type: string;
  user_input: string;
  additional_context?: Record<string, unknown>;
}): Promise<StartInteractionResponse> {
  return (await apiClient.post<StartInteractionResponse>('/api/interaction/start', payload)) as unknown as StartInteractionResponse;
}

export async function submitInteractionSelection(sessionId: string, optionId: string) {
  return (await apiClient.post<InteractionSelectionResponse>(`/api/interaction/${sessionId}/select`, {
    option_id: optionId,
    selection_data: {}
  })) as unknown as InteractionSelectionResponse;
}

export async function submitInteractionCustomInput(sessionId: string, customInput: string) {
  return (await apiClient.post<InteractionSelectionResponse>(`/api/interaction/${sessionId}/custom`, {
    custom_input: customInput,
    context: {},
    client_timestamp: new Date().toISOString(),
  })) as unknown as InteractionSelectionResponse;
}

export async function submitInteractionTimeout(sessionId: string) {
  return (await apiClient.post<InteractionTimeoutResponse>(`/api/interaction/${sessionId}/timeout`, {})) as unknown as InteractionTimeoutResponse;
}
