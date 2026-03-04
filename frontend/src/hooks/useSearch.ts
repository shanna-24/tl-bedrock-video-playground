/**
 * useSearch Hook
 * 
 * Custom hook for managing search state and API calls.
 * Provides functions for searching videos with natural language queries and/or images.
 * 
 * Validates: Requirements 3.1, 3.2, 3.3, Multimodal Search Requirements 1.1, 3.1, 3.2, 3.3
 */

import { useState, useCallback } from 'react';
import { searchApi } from '../services/api';
import type { SearchResults, VideoClip } from '../types';

interface UseSearchReturn {
  searchResults: VideoClip[];
  query: string;
  searchTime: number;
  isSearching: boolean;
  error: string | null;
  search: (indexId: string, query: string, topK?: number, imageFile?: File, modalities?: string[], transcriptionMode?: string, videoId?: string) => Promise<void>;
  clearResults: () => void;
}

export function useSearch(): UseSearchReturn {
  const [searchResults, setSearchResults] = useState<VideoClip[]>([]);
  const [query, setQuery] = useState('');
  const [searchTime, setSearchTime] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(async (indexId: string, searchQuery: string, topK?: number, imageFile?: File, modalities?: string[], transcriptionMode?: string, videoId?: string) => {
    // Validate that at least one input is provided
    if (!searchQuery.trim() && !imageFile) {
      setError('At least one of query or image must be provided');
      return;
    }

    setIsSearching(true);
    setError(null);
    setQuery(searchQuery || '[image search]');

    try {
      const results: SearchResults = await searchApi.searchVideos(
        indexId, 
        searchQuery || undefined, 
        topK,
        imageFile,
        modalities,
        transcriptionMode,
        videoId
      );
      setSearchResults(results.clips);
      setSearchTime(results.search_time);
    } catch (err: any) {
      const errorMessage = err.detail || err.message || 'Search failed';
      setError(errorMessage);
      setSearchResults([]);
      setSearchTime(0);
    } finally {
      setIsSearching(false);
    }
  }, []);

  const clearResults = useCallback(() => {
    setSearchResults([]);
    setQuery('');
    setSearchTime(0);
    setError(null);
  }, []);

  return {
    searchResults,
    query,
    searchTime,
    isSearching,
    error,
    search,
    clearResults,
  };
}
