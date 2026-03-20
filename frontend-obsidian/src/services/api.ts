/**
 * API service for TL-Video-Playground backend
 * 
 * This module provides functions for making HTTP requests to the backend API.
 * It handles authentication tokens and error responses.
 */

import type {
  LoginRequest,
  LoginResponse,
  LogoutResponse,
  ErrorResponse,
  Index,
} from '../types';
import { getBackendUrl } from './electron';

// API base URL - will be set dynamically
let API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Initialize API base URL (supports Electron)
(async () => {
  try {
    API_BASE_URL = await getBackendUrl();
  } catch (error) {
    console.warn('Failed to get backend URL from Electron, using default:', error);
  }
})();

/**
 * Custom error class for API errors
 */
export class ApiError extends Error {
  statusCode: number;
  detail?: string;

  constructor(
    message: string,
    statusCode: number,
    detail?: string
  ) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

/**
 * Get the authentication token from localStorage
 */
export function getAuthToken(): string | null {
  return localStorage.getItem('auth_token');
}

/**
 * Set the authentication token in localStorage
 */
export function setAuthToken(token: string): void {
  localStorage.setItem('auth_token', token);
}

/**
 * Remove the authentication token from localStorage
 */
export function removeAuthToken(): void {
  localStorage.removeItem('auth_token');
}

/**
 * Make an authenticated API request
 */
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
  signal?: AbortSignal
): Promise<T> {
  const token = getAuthToken();
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  // Add existing headers from options
  if (options.headers) {
    Object.assign(headers, options.headers);
  }

  // Add authorization header if token exists
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
    signal,
  });

  // Handle error responses
  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    
    try {
      const errorData: ErrorResponse = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch {
      // If response is not JSON, use default error message
    }

    throw new ApiError(
      errorDetail,
      response.status,
      errorDetail
    );
  }

  // Parse and return JSON response
  return response.json();
}

/**
 * Authentication API
 */
export const authApi = {
  /**
   * Login with password
   * 
   * @param password - User password
   * @returns Login response with JWT token
   * @throws ApiError if authentication fails
   */
  async login(password: string): Promise<LoginResponse> {
    const request: LoginRequest = { password };
    const response = await apiRequest<LoginResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(request),
    });
    
    // Store token in localStorage
    setAuthToken(response.token);
    
    return response;
  },

  /**
   * Logout current user
   * 
   * @returns Logout response
   * @throws ApiError if request fails
   */
  async logout(): Promise<LogoutResponse> {
    const response = await apiRequest<LogoutResponse>('/api/auth/logout', {
      method: 'POST',
    });
    
    // Remove token from localStorage
    removeAuthToken();
    
    return response;
  },
};

/**
 * Index API responses
 */
interface IndexListResponse {
  indexes: Index[];
  total: number;
  max_indexes: number;
}

interface DeleteResponse {
  message: string;
  deleted_id: string;
}

/**
 * Index Management API
 */
export const indexApi = {
  /**
   * List all indexes
   * 
   * @returns List of indexes with metadata
   * @throws ApiError if request fails
   */
  async listIndexes(): Promise<IndexListResponse> {
    return apiRequest<IndexListResponse>('/api/indexes');
  },

  /**
   * Create a new index
   * 
   * @param name - Index name (3-50 characters, alphanumeric)
   * @returns Created index information
   * @throws ApiError if creation fails or limit exceeded
   */
  async createIndex(name: string): Promise<Index> {
    return apiRequest<Index>('/api/indexes', {
      method: 'POST',
      body: JSON.stringify({ name }),
    });
  },

  /**
   * Delete an index
   * 
   * @param indexId - ID of the index to delete
   * @returns Deletion confirmation
   * @throws ApiError if deletion fails or index not found
   */
  async deleteIndex(indexId: string): Promise<DeleteResponse> {
    return apiRequest<DeleteResponse>(`/api/indexes/${indexId}`, {
      method: 'DELETE',
    });
  },
};


/**
 * Video API responses
 */
import type { Video, SearchResults, AnalysisResult } from '../types';

interface VideoListResponse {
  videos: Video[];
  total: number;
}

interface VideoStreamResponse {
  video_id: string;
  stream_url: string;
  start_time?: number;
}

/**
 * Video Management API
 */
export const videoApi = {
  /**
   * List videos in an index
   * 
   * @param indexId - ID of the index
   * @returns List of videos in the index
   * @throws ApiError if request fails
   */
  async listVideos(indexId: string): Promise<VideoListResponse> {
    return apiRequest<VideoListResponse>(`/api/indexes/${indexId}/videos`);
  },

  /**
   * Upload a video to an index
   * 
   * @param indexId - ID of the index
   * @param file - Video file to upload
   * @param onProgress - Optional callback for upload progress (0-100)
   * @returns Uploaded video information
   * @throws ApiError if upload fails
   */
  async uploadVideo(
    indexId: string,
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<Video> {
    const token = getAuthToken();
    const formData = new FormData();
    formData.append('file', file);

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      // Track upload progress
      if (onProgress) {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const progress = Math.round((e.loaded / e.total) * 100);
            onProgress(progress);
          }
        });
      }

      // Handle completion
      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            resolve(response);
          } catch (error) {
            reject(new ApiError('Invalid response format', xhr.status));
          }
        } else {
          try {
            const errorData = JSON.parse(xhr.responseText);
            reject(new ApiError(
              errorData.detail || `HTTP ${xhr.status}`,
              xhr.status,
              errorData.detail
            ));
          } catch {
            reject(new ApiError(`HTTP ${xhr.status}`, xhr.status));
          }
        }
      });

      // Handle errors
      xhr.addEventListener('error', () => {
        reject(new ApiError('Network error', 0));
      });

      xhr.addEventListener('abort', () => {
        reject(new ApiError('Upload cancelled', 0));
      });

      // Send request
      xhr.open('POST', `${API_BASE_URL}/api/indexes/${indexId}/videos`);
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      }
      xhr.send(formData);
    });
  },

  /**
   * Get video stream URL
   * 
   * @param videoId - ID of the video
   * @param startTime - Optional start time in seconds
   * @returns Video stream URL
   * @throws ApiError if request fails
   */
  async getStreamUrl(videoId: string, startTime?: number): Promise<VideoStreamResponse> {
    const params = startTime !== undefined ? `?start_time=${startTime}` : '';
    return apiRequest<VideoStreamResponse>(`/api/videos/${videoId}/stream${params}`);
  },

  /**
   * Backfill metadata for videos in an index
   * 
   * @param indexId - ID of the index
   * @returns Backfill results
   * @throws ApiError if request fails
   */
  async backfillMetadata(indexId: string): Promise<{ message: string; results: any }> {
    return apiRequest<{ message: string; results: any }>(
      `/api/indexes/${indexId}/videos/backfill-metadata`,
      { method: 'POST' }
    );
  },

  /**
   * Delete a video from its index
   * 
   * @param videoId - ID of the video to delete
   * @returns Deletion confirmation
   * @throws ApiError if deletion fails or video not found
   */
  async deleteVideo(videoId: string): Promise<DeleteResponse> {
    return apiRequest<DeleteResponse>(`/api/videos/${videoId}`, {
      method: 'DELETE',
    });
  },
};

/**
 * Search API
 */
export const searchApi = {
  /**
   * Search videos with natural language query and/or image
   *
   * Supports three search modes:
   * - Text-only: Provide only query parameter
   * - Image-only: Provide only imageFile parameter
   * - Multimodal: Provide both query and imageFile parameters
   *
   * @param indexId - ID of the index to search
   * @param query - Optional natural language search query
   * @param topK - Optional number of results to return (default: 10, range: 1-100)
   * @param imageFile - Optional image file for visual search
   * @param modalities - Optional array of modalities to search (visual, audio, transcription)
   * @param transcriptionMode - Optional transcription search mode (semantic, lexical, both)
   * @param videoId - Optional video ID to limit search to a single video
   * @returns Search results with video clips
   * @throws ApiError if search fails
   */
  async searchVideos(
    indexId: string,
    query?: string,
    topK?: number,
    imageFile?: File,
    modalities?: string[],
    transcriptionMode?: string,
    videoId?: string
  ): Promise<SearchResults> {
    const body: any = { index_id: indexId };

    // Add query if provided
    if (query) {
      body.query = query;
    }

    // Add topK if provided
    if (topK !== undefined) {
      body.top_k = topK;
    }

    // Add modalities if provided (and not all three selected)
    if (modalities && modalities.length > 0 && modalities.length < 3) {
      body.modalities = modalities;
    }

    // Add transcription_mode if specified and not default
    if (transcriptionMode && transcriptionMode !== 'both') {
      body.transcription_mode = transcriptionMode;
    }

    // Add video_id if specified (for single video search)
    if (videoId) {
      body.video_id = videoId;
    }

    // If image is provided, convert to base64 and add to body
    if (imageFile) {
      // Convert image to base64
      const base64Image = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          const result = reader.result as string;
          // Extract base64 data (remove data:image/...;base64, prefix)
          const base64Data = result.split(',')[1];
          resolve(base64Data);
        };
        reader.onerror = reject;
        reader.readAsDataURL(imageFile);
      });

      body.image = base64Image;

      // Determine image format from file type
      const imageFormat = imageFile.type.split('/')[1]; // e.g., 'image/jpeg' -> 'jpeg'
      body.image_format = imageFormat;
    }

    return apiRequest<SearchResults>('/api/search', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },
}

/**
 * Analysis API
 */
export const analysisApi = {
  /**
   * Analyze entire index
   * 
   * @param indexId - ID of the index to analyze
   * @param query - Natural language analysis query
   * @param verbosity - Response verbosity level ('concise' or 'extended')
   * @param correlationId - Optional correlation ID for progress tracking
   * @param signal - Optional AbortSignal for cancellation
   * @returns Analysis results
   * @throws ApiError if analysis fails
   */
  async analyzeIndex(
    indexId: string, 
    query: string, 
    verbosity: 'concise' | 'balanced' | 'extended' = 'balanced',
    correlationId?: string,
    signal?: AbortSignal
  ): Promise<AnalysisResult> {
    return apiRequest<AnalysisResult>('/api/analyze/index', {
      method: 'POST',
      body: JSON.stringify({ 
        index_id: indexId, 
        query, 
        verbosity,
        correlation_id: correlationId
      }),
    }, signal);
  },

  /**
   * Analyze single video
   * 
   * @param videoId - ID of the video to analyze
   * @param query - Natural language analysis query
   * @param verbosity - Response verbosity level ('concise' or 'extended')
   * @param useJockey - Whether to use Jockey orchestration for enhanced analysis
   * @param correlationId - Optional correlation ID for progress tracking
   * @param signal - Optional AbortSignal for cancellation
   * @returns Analysis results
   * @throws ApiError if analysis fails
   */
  async analyzeVideo(
    videoId: string, 
    query: string, 
    verbosity: 'concise' | 'balanced' | 'extended' = 'balanced', 
    useJockey: boolean = false,
    correlationId?: string,
    signal?: AbortSignal
  ): Promise<AnalysisResult> {
    return apiRequest<AnalysisResult>('/api/analyze/video', {
      method: 'POST',
      body: JSON.stringify({ 
        video_id: videoId, 
        query, 
        verbosity, 
        use_jockey: useJockey,
        correlation_id: correlationId
      }),
    }, signal);
  },

  /**
   * Cancel an ongoing analysis
   * 
   * @param correlationId - Correlation ID of the analysis to cancel
   * @returns Whether the cancellation was successful
   * @throws ApiError if request fails
   */
  async cancelAnalysis(correlationId: string): Promise<{ cancelled: boolean; correlation_id: string }> {
    return apiRequest<{ cancelled: boolean; correlation_id: string }>('/api/analyze/cancel', {
      method: 'POST',
      body: JSON.stringify({ correlation_id: correlationId }),
    });
  },
};

/**
 * Video Reel API
 */
import type { VideoClip } from '../types';

interface VideoReelResponse {
  reel_id: string;
  s3_key: string;
  stream_url: string;
  clip_count: number;
}

export const videoReelApi = {
  /**
   * Generate a video reel from search result clips
   * 
   * @param clips - List of video clips to concatenate
   * @returns Generated reel information with streaming URL
   * @throws ApiError if generation fails
   */
  async generateReel(clips: VideoClip[]): Promise<VideoReelResponse> {
    return apiRequest<VideoReelResponse>('/api/video-reel/generate', {
      method: 'POST',
      body: JSON.stringify({ clips }),
    });
  },
};

/**
 * Compliance API
 */
import type { ComplianceCheckResponse, ComplianceParams } from '../types';

export const complianceApi = {
  /**
   * Check video compliance
   * 
   * @param videoId - ID of the video to check
   * @param correlationId - Optional correlation ID for progress tracking
   * @param signal - Optional AbortSignal for cancellation
   * @returns Compliance check results
   * @throws ApiError if check fails
   */
  async checkCompliance(
    videoId: string,
    correlationId?: string,
    signal?: AbortSignal
  ): Promise<ComplianceCheckResponse> {
    return apiRequest<ComplianceCheckResponse>('/api/compliance/check', {
      method: 'POST',
      body: JSON.stringify({
        video_id: videoId,
        correlation_id: correlationId
      }),
    }, signal);
  },

  /**
   * Get compliance parameters
   * 
   * @returns Current compliance parameters (company, category, product_line)
   * @throws ApiError if request fails
   */
  async getParams(): Promise<ComplianceParams> {
    return apiRequest<ComplianceParams>('/api/compliance/params');
  },
};

