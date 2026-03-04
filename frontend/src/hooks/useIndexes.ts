/**
 * useIndexes Hook
 * 
 * Manages index state and provides CRUD operations for indexes.
 * Handles loading states, errors, and selected index management.
 * 
 * Validates: Requirements 1.1, 1.2, 1.3
 */

import { useState, useEffect, useCallback } from 'react';
import { indexApi, ApiError } from '../services/api';
import type { Index } from '../types';

interface IndexesState {
  indexes: Index[];
  selectedIndex: Index | null;
  isLoading: boolean;
  error: string | null;
  maxIndexes: number;
}

export interface UseIndexesReturn extends IndexesState {
  createIndex: (name: string) => Promise<Index>;
  deleteIndex: (indexId: string) => Promise<void>;
  selectIndex: (index: Index | null) => void;
  refreshIndexes: () => Promise<void>;
  clearError: () => void;
  canCreateIndex: boolean;
}

/**
 * Custom hook for managing index state and operations
 * 
 * @returns Index state and CRUD functions
 * 
 * @example
 * ```tsx
 * function IndexManager() {
 *   const {
 *     indexes,
 *     selectedIndex,
 *     isLoading,
 *     error,
 *     createIndex,
 *     deleteIndex,
 *     selectIndex,
 *     canCreateIndex
 *   } = useIndexes();
 *   
 *   if (isLoading) return <Spinner />;
 *   if (error) return <Error message={error} />;
 *   
 *   return (
 *     <div>
 *       <IndexList
 *         indexes={indexes}
 *         onSelect={selectIndex}
 *         onDelete={deleteIndex}
 *       />
 *       {canCreateIndex && (
 *         <CreateButton onClick={() => createIndex('New Index')} />
 *       )}
 *     </div>
 *   );
 * }
 * ```
 */
export function useIndexes(): UseIndexesReturn {
  const [state, setState] = useState<IndexesState>({
    indexes: [],
    selectedIndex: null,
    isLoading: true,
    error: null,
    maxIndexes: 3, // Default, will be updated from API
  });

  /**
   * Load indexes from API
   */
  const loadIndexes = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await indexApi.listIndexes();
      
      setState(prev => {
        // If there's a selected index, update it with the latest data
        let updatedSelectedIndex = prev.selectedIndex;
        if (prev.selectedIndex) {
          const updatedIndex = response.indexes.find(idx => idx.id === prev.selectedIndex!.id);
          if (updatedIndex) {
            updatedSelectedIndex = updatedIndex;
          }
        }
        
        return {
          ...prev,
          indexes: response.indexes,
          selectedIndex: updatedSelectedIndex,
          maxIndexes: response.max_indexes,
          isLoading: false,
          error: null,
        };
      });
    } catch (err) {
      let errorMessage = 'An unexpected error occurred. Please try again.';
      
      if (err instanceof ApiError) {
        errorMessage = err.detail || errorMessage;
      } else if (err instanceof Error) {
        errorMessage = err.message;
      }

      setState(prev => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
      }));
    }
  }, []);

  /**
   * Load indexes on mount
   */
  useEffect(() => {
    loadIndexes();
  }, [loadIndexes]);

  /**
   * Validate index name
   * 
   * @param name - Index name to validate
   * @throws Error if validation fails
   */
  const validateIndexName = (name: string): void => {
    const trimmedName = name.trim();
    
    if (trimmedName.length === 0) {
      throw new Error('Index name cannot be empty');
    }
    
    if (trimmedName.length < 3 || trimmedName.length > 50) {
      throw new Error('Index name must be between 3 and 50 characters');
    }
  };

  /**
   * Create a new index
   * 
   * @param name - Index name (will be trimmed)
   * @returns Created index
   * @throws Error if validation fails or API call fails
   */
  const createIndex = useCallback(async (name: string): Promise<Index> => {
    // Clear previous errors
    setState(prev => ({ ...prev, error: null }));

    try {
      // Trim whitespace
      const trimmedName = name.trim();
      
      // Validate name
      validateIndexName(trimmedName);
      
      // Check index limit
      if (state.indexes.length >= state.maxIndexes) {
        const error = `Maximum of ${state.maxIndexes} indexes allowed`;
        setState(prev => ({ ...prev, error }));
        throw new Error(error);
      }

      // Call API to create index
      const newIndex = await indexApi.createIndex(trimmedName);
      
      // Update state with new index and auto-select it
      setState(prev => ({
        ...prev,
        indexes: [...prev.indexes, newIndex],
        selectedIndex: newIndex,
        error: null,
      }));

      return newIndex;
    } catch (err) {
      let errorMessage = 'An unexpected error occurred. Please try again.';
      
      if (err instanceof ApiError) {
        errorMessage = err.detail || errorMessage;
      } else if (err instanceof Error) {
        errorMessage = err.message;
      }

      setState(prev => ({ ...prev, error: errorMessage }));
      throw err;
    }
  }, [state.indexes.length, state.maxIndexes]);

  /**
   * Delete an index
   * 
   * @param indexId - ID of the index to delete
   * @throws Error if API call fails
   */
  const deleteIndex = useCallback(async (indexId: string): Promise<void> => {
    // Clear previous errors
    setState(prev => ({ ...prev, error: null }));

    try {
      // Call API to delete index
      await indexApi.deleteIndex(indexId);
      
      // Update state - remove deleted index
      setState(prev => ({
        ...prev,
        indexes: prev.indexes.filter(idx => idx.id !== indexId),
        // Clear selection if deleted index was selected
        selectedIndex: prev.selectedIndex?.id === indexId ? null : prev.selectedIndex,
        error: null,
      }));
    } catch (err) {
      let errorMessage = 'An unexpected error occurred. Please try again.';
      
      if (err instanceof ApiError) {
        errorMessage = err.detail || errorMessage;
      } else if (err instanceof Error) {
        errorMessage = err.message;
      }

      setState(prev => ({ ...prev, error: errorMessage }));
      throw err;
    }
  }, []);

  /**
   * Select an index
   * 
   * @param index - Index to select, or null to clear selection
   */
  const selectIndex = useCallback((index: Index | null): void => {
    setState(prev => ({ ...prev, selectedIndex: index }));
  }, []);

  /**
   * Refresh indexes from API
   * 
   * @throws Error if API call fails
   */
  const refreshIndexes = useCallback(async (): Promise<void> => {
    await loadIndexes();
  }, [loadIndexes]);

  /**
   * Clear error state
   */
  const clearError = useCallback((): void => {
    setState(prev => ({ ...prev, error: null }));
  }, []);

  /**
   * Check if a new index can be created (under limit)
   */
  const canCreateIndex = state.indexes.length < state.maxIndexes;

  return {
    ...state,
    createIndex,
    deleteIndex,
    selectIndex,
    refreshIndexes,
    clearError,
    canCreateIndex,
  };
}
