/**
 * useVideos Hook
 * 
 * Custom hook for managing video state and API calls.
 * Provides functions for listing videos in an index.
 * 
 * Validates: Requirements 1.5
 */

import { useState, useEffect } from 'react';
import { videoApi } from '../services/api';
import type { Video } from '../types';

interface UseVideosReturn {
  videos: Video[];
  isLoading: boolean;
  error: string | null;
  refreshVideos: () => Promise<void>;
}

export function useVideos(indexId: string | null): UseVideosReturn {
  const [videos, setVideos] = useState<Video[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadVideos = async () => {
    if (!indexId) {
      setVideos([]);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await videoApi.listVideos(indexId);
      setVideos(response.videos);
    } catch (err: any) {
      const errorMessage = err.detail || err.message || 'Failed to load videos';
      setError(errorMessage);
      setVideos([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadVideos();
  }, [indexId]);

  return {
    videos,
    isLoading,
    error,
    refreshVideos: loadVideos,
  };
}
