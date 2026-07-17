export interface User {
  id: string;
  email: string;
}

export interface DesktopStatus {
  provider_configured: boolean;
  resume_uploaded: boolean;
  onboarding_complete: boolean;
  provider?: string | null;
  active_model?: string | null;
  degraded?: boolean;
  message?: string | null;
}

export interface Profile {
  role_intent: string | null;
  min_salary: number | null;
  resume_text?: string | null;
  distilled_text?: string | null;
  target_roles?: string[] | null;
  target_companies?: string[] | null;
  preferred_locations?: string[] | null;
  config_overrides: ProfileConfig | null;
  onboarding_complete: boolean;
}

export interface ProfileConfig {
  profile_intent?: {
    roles?: string[];
    preset?: string;
  };
  scraping?: {
    locations?: string[];
  };
  location_scoring?: {
    preferred_locations?: string[];
    preferred_weight?: number;
  };
  company_preferences?: {
    tiers?: string[];
    filter_mode?: CompanyFilterMode;
    reputation_tiers?: CompanyReputationTier[];
    preferred_companies?: string[];
    excluded_companies?: string[];
  };
  title_blocklist?: string[];
  [key: string]: unknown;
}

export interface ProfileResponse {
  user_id: string;
  email: string;
  profile: Profile | null;
}

export interface Job {
  id: string;
  title: string;
  company: string;
  location: string | null;
  site: string | null;
  job_url: string;
  date_posted: string | null;
  description: string | null;
  final_score: number | null;
  semantic_score: number | null;
  skills_score: number | null;
  company_score: number | null;
  seniority_score: number | null;
  location_score: number | null;
  recency_score: number | null;
  company_tier: string | null;
  company_reputation_confidence?: number | null;
  company_reputation_rationale?: string | null;
  explanation?: JobExplanation | null;
  is_contract: boolean;
  feedback?: JobFeedback | null;
}

export type JobFeedbackValue = "relevant" | "not_relevant";
export type JobFeedbackReason = "wrong_role" | "wrong_seniority" | "wrong_location" | "other";

export interface JobFeedback {
  value: JobFeedbackValue;
  reason: JobFeedbackReason | null;
}

export interface JobExplanation {
  role_fit?: { lane?: string; title_similarity?: number };
  matched_skills?: string[];
  scores?: Record<string, number>;
  concerns?: string[];
  [key: string]: unknown;
}

export interface JobsResponse {
  jobs: Job[];
  total: number;
  page: number;
  limit: number;
  run_id?: string | null;
  completed_at?: string | null;
  strong_count?: number;
  source_counts?: Record<string, number>;
}

export interface JobListParams {
  page?: number;
  limit?: number;
  q?: string;
  min_score?: number;
  source?: string;
  sort?: "match" | "newest" | "company";
}

export type ApplicationStatus =
  | "interested"
  | "applied"
  | "phone_screen"
  | "interview"
  | "offer"
  | "rejected"
  | "archived";

export interface Application {
  id: string;
  job_id: string | null;
  company: string;
  title: string;
  status: ApplicationStatus;
  applied_at: string | null;
  notes: string | null;
  job_url?: string | null;
  source?: string | null;
  date_posted?: string | null;
}

export interface Run {
  run_id: string;
  status: "pending" | "running" | "success" | "partial" | "failed" | "cancelled";
  started_at: string | null;
  finished_at: string | null;
  job_count: number | null;
  stage?: string | null;
  progress?: number | null;
  message?: string | null;
  failure_reason?: string | null;
  error_summary?: string | null;
  cached?: boolean;
  stale?: boolean;
  source_counts?: Record<string, number>;
  source_stats?: SourceRunStat[];
  sources?: SourceRunStat[];
  attempt_count?: number;
}

export interface SourceRunStat {
  provider?: string;
  source?: string;
  status?: "success" | "failed" | "cached" | "skipped" | string;
  raw_count?: number | null;
  normalized_count?: number | null;
  deduped_count?: number | null;
  jobs_found?: number | null;
  jobs_persisted?: number | null;
  error?: string | null;
  error_summary?: string | null;
  cached?: boolean;
  query?: string | null;
  location?: string | null;
  duration_ms?: number | null;
}

export interface OnboardingStatus {
  onboarding_complete: boolean;
  has_resume: boolean;
  current_step?: "upload" | "questions";
  parse_status?: ResumeParseStatus;
  parse_confidence?: number | null;
  parse_error?: string | null;
  extracted?: ResumeExtraction | null;
  questions?: OnboardingQuestion[];
  draft?: OnboardingDraft | null;
}

export type CompanyFilterMode = "all" | "top_reputed" | "selected_tiers";

export type CompanyReputationTier = "S" | "A" | "B" | "C";

export type ResumeParseStatus =
  | "complete"
  | "partial"
  | "degraded"
  | "llm_unavailable"
  | "failed"
  | string;

export interface ResumeExtraction {
  skills?: string[];
  years_of_experience?: number | null;
  recent_titles?: string[];
  industries?: string[];
  location?: string | null;
  parse_status?: ResumeParseStatus;
  parse_confidence?: number | null;
  parse_source?: string | null;
  parser_model?: string | null;
  parse_error?: string | null;
  warnings?: string[];
}

export interface OnboardingQuestion {
  id: string;
  text: string;
  type: "text" | "multiselect" | "tags" | string;
  options?: string[];
}

export type OnboardingAnswer = string | string[];

export interface OnboardingDraft {
  current_step?: "upload" | "questions" | "complete" | string;
  answers?: Record<string, OnboardingAnswer>;
  questions?: OnboardingQuestion[];
  extracted?: ResumeExtraction | null;
  parse_status?: ResumeParseStatus;
  resume_filename?: string | null;
  parser_version?: string | null;
}

export interface OnboardingResumeResponse {
  extracted: ResumeExtraction;
  questions: OnboardingQuestion[];
  parse_status?: ResumeParseStatus;
  draft?: OnboardingDraft | null;
}
