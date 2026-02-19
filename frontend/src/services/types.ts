// ===== GOVERNMENT ENTITY TYPES =====

export interface GovernmentEntity {
  id: string;
  name: string;
  type: 'city' | 'county' | 'state' | 'federal';
  cached: boolean;
  last_searched?: string;
}

// ===== PROGRAM TYPES =====

export interface Program {
  id: string;
  program_name: string;
  agency: string;
  status_tag: 'ACTIVE' | 'EXPIRED' | 'NON-INCENTIVE';
  benefit_type: 'tax_credit' | 'wage_subsidy' | 'training_grant' | 'bonding' | 'unknown';
  jurisdiction: string;
  max_value?: string;
  target_populations: string[];
  description: string;
  official_source_url: string;
  government_level: 'city' | 'county' | 'state' | 'federal';
  confidence: 'high' | 'medium' | 'low';
}

// ===== DISCOVERY STATUS TYPES =====

export interface DiscoveryStatus {
  session_id: string;
  status: 'started' | 'routing' | 'discovering' | 'searching' | 'merging' | 'validating' | 'completed' | 'failed';
  current_step: string;
  government_levels: string[];
  programs_found: number;
  search_progress: {
    city: 'pending' | 'running' | 'completed';
    county: 'pending' | 'running' | 'completed';
    state: 'pending' | 'running' | 'completed';
    federal: 'pending' | 'running' | 'completed';
  };
}

export interface DiscoverResponse {
  session_id: string;
  status: string;
  message: string;
}

// ===== ROI TYPES =====

export interface ROIQuestion {
  id: string;
  program_id: string;
  program_name?: string;
  question: string;
  type: 'number' | 'text' | 'select';
  options?: string[];
  required: boolean;
}

export interface ROICalculation {
  program_name: string;
  roi_per_hire: number;
  number_of_hires: number;
  total_roi: number;
  input_values: Record<string, any>;
}

export interface ROIAnswersResponse {
  calculations: ROICalculation[];
  roi_spreadsheet_url: string;
}

// ===== SHORTLIST TYPES =====

export interface ShortlistRequest {
  program_ids: string[];
}

export interface ShortlistResponse {
  shortlisted: Program[];
}

// ===== ERROR TYPES =====

export interface ErrorResponse {
  error: string;
  message: string;
  details?: Record<string, string>;
}

// ===== WIZARD STATE =====

export interface WizardState {
  address: string;
  sessionId: string | null;
  selectedPrograms: string[];
}
