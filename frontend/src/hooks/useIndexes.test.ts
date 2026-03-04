/**
 * Unit tests for useIndexes hook
 * 
 * Tests index state management, CRUD operations, and error handling.
 * 
 * Note: These tests require Vitest and @testing-library/react to be installed.
 * Run: npm install -D vitest @testing-library/react @testing-library/react-hooks jsdom
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useIndexes } from './useIndexes';
import * as api from '../services/api';
import type { Index } from '../types';

// Mock the API module
vi.mock('../services/api', () => ({
  indexApi: {
    listIndexes: vi.fn(),
    createIndex: vi.fn(),
    deleteIndex: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    statusCode: number;
    detail?: string;
    constructor(message: string, statusCode: number, detail?: string) {
      super(message);
      this.name = 'ApiError';
      this.statusCode = statusCode;
      this.detail = detail;
    }
  },
}));

describe('useIndexes', () => {
  const mockIndexes: Index[] = [
    {
      id: 'index-1',
      name: 'Test Index 1',
      created_at: '2024-01-01T00:00:00Z',
      video_count: 5,
      s3_vectors_collection_id: 'collection-1',
      metadata: {},
    },
    {
      id: 'index-2',
      name: 'Test Index 2',
      created_at: '2024-01-02T00:00:00Z',
      video_count: 3,
      s3_vectors_collection_id: 'collection-2',
      metadata: {},
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('should initialize with loading state', () => {
      vi.mocked(api.indexApi.listIndexes).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      const { result } = renderHook(() => useIndexes());

      expect(result.current.isLoading).toBe(true);
      expect(result.current.indexes).toEqual([]);
      expect(result.current.selectedIndex).toBe(null);
      expect(result.current.error).toBe(null);
    });

    it('should load indexes on mount', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: mockIndexes,
        total: 2,
        max_indexes: 3,
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.indexes).toEqual(mockIndexes);
      expect(result.current.maxIndexes).toBe(3);
      expect(result.current.error).toBe(null);
    });

    it('should handle loading error', async () => {
      vi.mocked(api.indexApi.listIndexes).mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.indexes).toEqual([]);
      expect(result.current.error).toBe('Network error');
    });

    it('should handle API error with detail', async () => {
      vi.mocked(api.indexApi.listIndexes).mockRejectedValue(
        new api.ApiError('Failed to load', 500, 'Server error')
      );

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBe('Server error');
    });
  });

  describe('createIndex', () => {
    it('should successfully create an index', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [],
        total: 0,
        max_indexes: 3,
      });

      const newIndex: Index = {
        id: 'index-3',
        name: 'New Index',
        created_at: '2024-01-03T00:00:00Z',
        video_count: 0,
        s3_vectors_collection_id: 'collection-3',
        metadata: {},
      };

      vi.mocked(api.indexApi.createIndex).mockResolvedValue(newIndex);

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      let createdIndex: Index | undefined;
      await act(async () => {
        createdIndex = await result.current.createIndex('New Index');
      });

      expect(api.indexApi.createIndex).toHaveBeenCalledWith('New Index');
      expect(createdIndex).toEqual(newIndex);
      expect(result.current.indexes).toContainEqual(newIndex);
      expect(result.current.selectedIndex).toEqual(newIndex); // Auto-selected
      expect(result.current.error).toBe(null);
    });

    it('should trim whitespace from index name', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [],
        total: 0,
        max_indexes: 3,
      });

      const newIndex: Index = {
        id: 'index-1',
        name: 'Test Index',
        created_at: '2024-01-01T00:00:00Z',
        video_count: 0,
        s3_vectors_collection_id: 'collection-1',
        metadata: {},
      };

      vi.mocked(api.indexApi.createIndex).mockResolvedValue(newIndex);

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.createIndex('  Test Index  ');
      });

      expect(api.indexApi.createIndex).toHaveBeenCalledWith('Test Index');
    });

    it('should validate empty index name', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [],
        total: 0,
        max_indexes: 3,
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        try {
          await result.current.createIndex('   ');
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('Index name cannot be empty');
      expect(api.indexApi.createIndex).not.toHaveBeenCalled();
    });

    it('should validate index name too short', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [],
        total: 0,
        max_indexes: 3,
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        try {
          await result.current.createIndex('ab');
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('Index name must be between 3 and 50 characters');
      expect(api.indexApi.createIndex).not.toHaveBeenCalled();
    });

    it('should validate index name too long', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [],
        total: 0,
        max_indexes: 3,
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const longName = 'a'.repeat(51);

      await act(async () => {
        try {
          await result.current.createIndex(longName);
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('Index name must be between 3 and 50 characters');
      expect(api.indexApi.createIndex).not.toHaveBeenCalled();
    });

    it('should accept index name at minimum length (3 characters)', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [],
        total: 0,
        max_indexes: 3,
      });

      const newIndex: Index = {
        id: 'index-1',
        name: 'abc',
        created_at: '2024-01-01T00:00:00Z',
        video_count: 0,
        s3_vectors_collection_id: 'collection-1',
        metadata: {},
      };

      vi.mocked(api.indexApi.createIndex).mockResolvedValue(newIndex);

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.createIndex('abc');
      });

      expect(api.indexApi.createIndex).toHaveBeenCalledWith('abc');
      expect(result.current.error).toBe(null);
    });

    it('should accept index name at maximum length (50 characters)', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [],
        total: 0,
        max_indexes: 3,
      });

      const maxLengthName = 'a'.repeat(50);
      const newIndex: Index = {
        id: 'index-1',
        name: maxLengthName,
        created_at: '2024-01-01T00:00:00Z',
        video_count: 0,
        s3_vectors_collection_id: 'collection-1',
        metadata: {},
      };

      vi.mocked(api.indexApi.createIndex).mockResolvedValue(newIndex);

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.createIndex(maxLengthName);
      });

      expect(api.indexApi.createIndex).toHaveBeenCalledWith(maxLengthName);
      expect(result.current.error).toBe(null);
    });

    it('should enforce index limit', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [mockIndexes[0], mockIndexes[1], { ...mockIndexes[0], id: 'index-3' }],
        total: 3,
        max_indexes: 3,
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.indexes).toHaveLength(3);

      await act(async () => {
        try {
          await result.current.createIndex('Fourth Index');
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('Maximum of 3 indexes allowed');
      expect(api.indexApi.createIndex).not.toHaveBeenCalled();
    });

    it('should handle API error during creation', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [],
        total: 0,
        max_indexes: 3,
      });

      vi.mocked(api.indexApi.createIndex).mockRejectedValue(
        new api.ApiError('Creation failed', 400, 'Invalid index name')
      );

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        try {
          await result.current.createIndex('Test Index');
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('Invalid index name');
      expect(result.current.indexes).toHaveLength(0);
    });

    it('should clear previous errors on new creation attempt', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [],
        total: 0,
        max_indexes: 3,
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // First attempt - validation error
      await act(async () => {
        try {
          await result.current.createIndex('ab');
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('Index name must be between 3 and 50 characters');

      // Second attempt - should clear error
      const newIndex: Index = {
        id: 'index-1',
        name: 'Valid Index',
        created_at: '2024-01-01T00:00:00Z',
        video_count: 0,
        s3_vectors_collection_id: 'collection-1',
        metadata: {},
      };

      vi.mocked(api.indexApi.createIndex).mockResolvedValue(newIndex);

      await act(async () => {
        await result.current.createIndex('Valid Index');
      });

      expect(result.current.error).toBe(null);
    });
  });

  describe('deleteIndex', () => {
    it('should successfully delete an index', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: mockIndexes,
        total: 2,
        max_indexes: 3,
      });

      vi.mocked(api.indexApi.deleteIndex).mockResolvedValue({
        message: 'Index deleted successfully',
        deleted_id: 'index-1',
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.indexes).toHaveLength(2);

      await act(async () => {
        await result.current.deleteIndex('index-1');
      });

      expect(api.indexApi.deleteIndex).toHaveBeenCalledWith('index-1');
      expect(result.current.indexes).toHaveLength(1);
      expect(result.current.indexes[0].id).toBe('index-2');
      expect(result.current.error).toBe(null);
    });

    it('should clear selection if deleted index was selected', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: mockIndexes,
        total: 2,
        max_indexes: 3,
      });

      vi.mocked(api.indexApi.deleteIndex).mockResolvedValue({
        message: 'Index deleted successfully',
        deleted_id: 'index-1',
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Select the first index
      act(() => {
        result.current.selectIndex(mockIndexes[0]);
      });

      expect(result.current.selectedIndex).toEqual(mockIndexes[0]);

      // Delete the selected index
      await act(async () => {
        await result.current.deleteIndex('index-1');
      });

      expect(result.current.selectedIndex).toBe(null);
    });

    it('should keep selection if deleted index was not selected', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: mockIndexes,
        total: 2,
        max_indexes: 3,
      });

      vi.mocked(api.indexApi.deleteIndex).mockResolvedValue({
        message: 'Index deleted successfully',
        deleted_id: 'index-1',
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Select the second index
      act(() => {
        result.current.selectIndex(mockIndexes[1]);
      });

      expect(result.current.selectedIndex).toEqual(mockIndexes[1]);

      // Delete the first index
      await act(async () => {
        await result.current.deleteIndex('index-1');
      });

      // Selection should remain on the second index
      expect(result.current.selectedIndex).toEqual(mockIndexes[1]);
    });

    it('should handle API error during deletion', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: mockIndexes,
        total: 2,
        max_indexes: 3,
      });

      vi.mocked(api.indexApi.deleteIndex).mockRejectedValue(
        new api.ApiError('Deletion failed', 404, 'Index not found')
      );

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        try {
          await result.current.deleteIndex('index-1');
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('Index not found');
      expect(result.current.indexes).toHaveLength(2); // No change
    });
  });

  describe('selectIndex', () => {
    it('should select an index', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: mockIndexes,
        total: 2,
        max_indexes: 3,
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.selectedIndex).toBe(null);

      act(() => {
        result.current.selectIndex(mockIndexes[0]);
      });

      expect(result.current.selectedIndex).toEqual(mockIndexes[0]);
    });

    it('should clear selection when null is passed', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: mockIndexes,
        total: 2,
        max_indexes: 3,
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Select an index
      act(() => {
        result.current.selectIndex(mockIndexes[0]);
      });

      expect(result.current.selectedIndex).toEqual(mockIndexes[0]);

      // Clear selection
      act(() => {
        result.current.selectIndex(null);
      });

      expect(result.current.selectedIndex).toBe(null);
    });

    it('should allow switching between indexes', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: mockIndexes,
        total: 2,
        max_indexes: 3,
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Select first index
      act(() => {
        result.current.selectIndex(mockIndexes[0]);
      });

      expect(result.current.selectedIndex).toEqual(mockIndexes[0]);

      // Switch to second index
      act(() => {
        result.current.selectIndex(mockIndexes[1]);
      });

      expect(result.current.selectedIndex).toEqual(mockIndexes[1]);
    });
  });

  describe('refreshIndexes', () => {
    it('should reload indexes from API', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [mockIndexes[0]],
        total: 1,
        max_indexes: 3,
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.indexes).toHaveLength(1);

      // Update mock to return more indexes
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: mockIndexes,
        total: 2,
        max_indexes: 3,
      });

      await act(async () => {
        await result.current.refreshIndexes();
      });

      expect(result.current.indexes).toHaveLength(2);
    });

    it('should handle errors during refresh', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: mockIndexes,
        total: 2,
        max_indexes: 3,
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Update mock to return error
      vi.mocked(api.indexApi.listIndexes).mockRejectedValue(
        new Error('Network error')
      );

      await act(async () => {
        await result.current.refreshIndexes();
      });

      expect(result.current.error).toBe('Network error');
    });
  });

  describe('clearError', () => {
    it('should clear error state', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [],
        total: 0,
        max_indexes: 3,
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Create an error
      await act(async () => {
        try {
          await result.current.createIndex('ab');
        } catch (err) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('Index name must be between 3 and 50 characters');

      // Clear error
      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBe(null);
    });
  });

  describe('canCreateIndex', () => {
    it('should return true when under index limit', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [mockIndexes[0]],
        total: 1,
        max_indexes: 3,
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.canCreateIndex).toBe(true);
    });

    it('should return false when at index limit', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [mockIndexes[0], mockIndexes[1], { ...mockIndexes[0], id: 'index-3' }],
        total: 3,
        max_indexes: 3,
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.canCreateIndex).toBe(false);
    });

    it('should update after creating an index', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [mockIndexes[0], mockIndexes[1]],
        total: 2,
        max_indexes: 3,
      });

      const newIndex: Index = {
        id: 'index-3',
        name: 'New Index',
        created_at: '2024-01-03T00:00:00Z',
        video_count: 0,
        s3_vectors_collection_id: 'collection-3',
        metadata: {},
      };

      vi.mocked(api.indexApi.createIndex).mockResolvedValue(newIndex);

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.canCreateIndex).toBe(true);

      await act(async () => {
        await result.current.createIndex('New Index');
      });

      expect(result.current.canCreateIndex).toBe(false);
    });

    it('should update after deleting an index', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: [mockIndexes[0], mockIndexes[1], { ...mockIndexes[0], id: 'index-3' }],
        total: 3,
        max_indexes: 3,
      });

      vi.mocked(api.indexApi.deleteIndex).mockResolvedValue({
        message: 'Index deleted successfully',
        deleted_id: 'index-1',
      });

      const { result } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.canCreateIndex).toBe(false);

      await act(async () => {
        await result.current.deleteIndex('index-1');
      });

      expect(result.current.canCreateIndex).toBe(true);
    });
  });

  describe('state persistence', () => {
    it('should maintain state across hook re-renders', async () => {
      vi.mocked(api.indexApi.listIndexes).mockResolvedValue({
        indexes: mockIndexes,
        total: 2,
        max_indexes: 3,
      });

      const { result, rerender } = renderHook(() => useIndexes());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.indexes).toEqual(mockIndexes);

      // Select an index
      act(() => {
        result.current.selectIndex(mockIndexes[0]);
      });

      // Re-render the hook
      rerender();

      // State should be maintained
      expect(result.current.indexes).toEqual(mockIndexes);
      expect(result.current.selectedIndex).toEqual(mockIndexes[0]);
    });
  });
});
