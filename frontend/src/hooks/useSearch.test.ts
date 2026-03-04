/**
 * useSearch Hook Tests
 * 
 * Tests for search state management and API integration.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useSearch } from './useSearch';
import * as api from '../services/api';

// Mock the API
vi.mock('../services/api', () => ({
  searchApi: {
    searchVideos: vi.fn(),
  },
}));

describe('useSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initializes with empty state', () => {
    const { result } = renderHook(() => useSearch());

    expect(result.current.searchResults).toEqual([]);
    expect(result.current.query).toBe('');
    expect(result.current.searchTime).toBe(0);
    expect(result.current.isSearching).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('performs search and updates state', async () => {
    const mockResults = {
      query: 'people talking',
      clips: [
        {
          video_id: 'video-1',
          start_timecode: 10,
          end_timecode: 20,
          relevance_score: 0.95,
          screenshot_url: 'https://example.com/screenshot.jpg',
          video_stream_url: 'https://example.com/video',
          metadata: {},
        },
      ],
      total_results: 1,
      search_time: 1.5,
    };

    vi.mocked(api.searchApi.searchVideos).mockResolvedValue(mockResults);

    const { result } = renderHook(() => useSearch());

    act(() => {
      result.current.search('index-123', 'people talking');
    });

    expect(result.current.isSearching).toBe(true);

    await waitFor(() => {
      expect(result.current.isSearching).toBe(false);
    });

    expect(result.current.searchResults).toEqual(mockResults.clips);
    expect(result.current.query).toBe('people talking');
    expect(result.current.searchTime).toBe(1.5);
    expect(result.current.error).toBeNull();
  });

  it('handles search errors', async () => {
    vi.mocked(api.searchApi.searchVideos).mockRejectedValue({
      detail: 'Search failed',
    });

    const { result } = renderHook(() => useSearch());

    act(() => {
      result.current.search('index-123', 'test query');
    });

    await waitFor(() => {
      expect(result.current.isSearching).toBe(false);
    });

    expect(result.current.error).toBe('Search failed');
    expect(result.current.searchResults).toEqual([]);
  });

  it('rejects empty queries', async () => {
    const { result } = renderHook(() => useSearch());

    await act(async () => {
      await result.current.search('index-123', '   ');
    });

    expect(result.current.error).toBe('At least one of query or image must be provided');
    expect(api.searchApi.searchVideos).not.toHaveBeenCalled();
  });

  it('clears results', () => {
    const { result } = renderHook(() => useSearch());

    // Set some state first
    act(() => {
      result.current.search('index-123', 'test');
    });

    act(() => {
      result.current.clearResults();
    });

    expect(result.current.searchResults).toEqual([]);
    expect(result.current.query).toBe('');
    expect(result.current.searchTime).toBe(0);
    expect(result.current.error).toBeNull();
  });
});
