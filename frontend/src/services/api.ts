import axios from 'axios';
import type {
  DiscoverResponse,
  DiscoveryStatus,
  Program,
  ROIQuestion,
  ROIAnswersResponse,
  ShortlistResponse,
} from './types';

// Use proxy in development (vite.config.ts), direct URL in production
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Check if demo mode is active via VITE_DEMO_MODE env var or ?demo=true URL param
 */
const isDemoMode = (): boolean => {
  if (import.meta.env.VITE_DEMO_MODE === 'true') return true;
  if (typeof window !== 'undefined') {
    return new URLSearchParams(window.location.search).get('demo') === 'true';
  }
  return false;
};

/**
 * Discover incentive programs for an address
 */
export const discoverIncentives = async (
  address: string,
  legalEntityType: string = 'Unknown',
  industryCode?: string
): Promise<DiscoverResponse> => {
  const params = isDemoMode() ? '?demo=true' : '';
  const response = await api.post<DiscoverResponse>(`/incentives/discover${params}`, {
    address,
    legal_entity_type: legalEntityType,
    industry_code: industryCode,
  });
  return response.data;
};

/**
 * Get the discovery status
 */
export const getDiscoveryStatus = async (sessionId: string): Promise<DiscoveryStatus> => {
  const response = await api.get<DiscoveryStatus>(`/incentives/${sessionId}/status`);
  return response.data;
};

/**
 * Get discovered programs
 */
export const getPrograms = async (sessionId: string): Promise<{ programs: Program[] }> => {
  const response = await api.get<{ programs: Program[] }>(`/incentives/${sessionId}/programs`);
  return response.data;
};

/**
 * Submit shortlisted programs
 */
export const submitShortlist = async (
  sessionId: string,
  programIds: string[]
): Promise<ShortlistResponse> => {
  const response = await api.post<ShortlistResponse>(`/incentives/${sessionId}/shortlist`, {
    program_ids: programIds,
  });
  return response.data;
};

/**
 * Get ROI questions for shortlisted programs
 */
export const getROIQuestions = async (sessionId: string): Promise<{ questions: ROIQuestion[] }> => {
  const response = await api.get<{ questions: ROIQuestion[] }>(
    `/incentives/${sessionId}/roi-questions`
  );
  return response.data;
};

/**
 * Submit ROI answers and get calculations
 */
export const submitROIAnswers = async (
  sessionId: string,
  answers: Record<string, any>
): Promise<ROIAnswersResponse> => {
  const response = await api.post<ROIAnswersResponse>(`/incentives/${sessionId}/roi-answers`, {
    answers,
  });
  return response.data;
};

/**
 * Download ROI spreadsheet
 */
export const downloadROISpreadsheet = async (sessionId: string): Promise<Blob> => {
  const response = await api.get(`/incentives/${sessionId}/roi-spreadsheet`, {
    responseType: 'blob',
  });
  return response.data;
};

/**
 * Address autocomplete (mock for demo)
 */
export const addressAutocomplete = async (query: string): Promise<string[]> => {
  if (!query || query.length < 2) return [];
  const response = await api.get<{ suggestions: string[] }>(
    `/incentives/address-autocomplete`,
    { params: { q: query } }
  );
  return response.data.suggestions;
};

/**
 * Health check endpoint
 */
export const healthCheck = async (): Promise<{
  status: string;
  version: string;
  timestamp: string;
}> => {
  const response = await api.get('/health');
  return response.data;
};
