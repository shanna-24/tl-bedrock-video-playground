/**
 * Type definitions for TL-Video-Playground frontend
 */

// Authentication types
export interface LoginRequest {
  password: string;
}

export interface LoginResponse {
  token: string;
  message: string;
}

export interface LogoutResponse {
  message: string;
}

export interface ErrorResponse {
  detail: string;
}

// Index types
export interface Index {
  id: string;
  name: string;
  created_at: string;
  video_count: number;
  s3_vectors_collection_id: string;
  metadata: Record<string, any>;
}

// Video types
export interface Video {
  id: string;
  index_id: string;
  filename: string;
  s3_uri: string;
  duration: number;
  uploaded_at: string;
  embedding_ids: string[];
  metadata: Record<string, any>;
  thumbnail_url?: string;
}

// Search types
export interface VideoClip {
  video_id: string;
  start_timecode: number;
  end_timecode: number;
  relevance_score: number;
  screenshot_url: string;
  video_stream_url: string;
  metadata: Record<string, any>;
  transcription?: string;  // Optional transcription text
}

export interface SearchResults {
  query: string;
  clips: VideoClip[];
  total_results: number;
  search_time: number;
}

// Analysis types
export interface AnalysisResult {
  query: string;
  scope: 'index' | 'video';
  scope_id: string;
  insights: string;
  analyzed_at: string;
  metadata: Record<string, any>;
}

// Compliance types
export interface ComplianceIssue {
  Timecode?: string;
  Category?: string;
  Subcategory?: string;
  Description?: string;
  Status?: string;
  thumbnail_url?: string;
}

export interface ComplianceResult {
  Filename?: string;
  Title?: string;
  Length?: string;
  Summary?: string;
  'Overall Status'?: string;
  'Identified Issues'?: ComplianceIssue[];
  raw_response?: string;
  _metadata?: {
    video_id: string;
    video_filename: string;
    checked_at: string;
    compliance_params: {
      company: string;
      category: string;
      product_line: string;
    };
    prompt?: string;
  };
}

export interface ComplianceCheckResponse {
  result: ComplianceResult;
  s3_key: string;
  s3_uri: string;
}

export interface ComplianceParams {
  company: string;
  category: string;
  product_line: string;
  categories: string[];
}
