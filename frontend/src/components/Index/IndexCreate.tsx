/**
 * IndexCreate Component
 * 
 * Reusable component for creating new video indexes.
 * Handles index creation form and index limit validation.
 * 
 * Validates: Requirements 1.1, 1.2
 */

import { useState, useEffect } from 'react';
import { indexApi } from '../../services/api';
import type { Index } from '../../types';
import { useTheme } from '../../contexts/ThemeContext';

interface IndexCreateProps {
  /** Current number of indexes */
  currentIndexCount: number;
  /** Maximum number of indexes allowed */
  maxIndexes: number;
  /** Callback when index is successfully created */
  onIndexCreated?: (index: Index) => void;
  /** Callback when an error occurs */
  onError?: (error: string) => void;
}

export default function IndexCreate({
  currentIndexCount,
  maxIndexes,
  onIndexCreated,
  onError,
}: IndexCreateProps) {
  const [newIndexName, setNewIndexName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [isMessageFaded, setIsMessageFaded] = useState(false);
  const { mode } = useTheme();

  const canCreateIndex = currentIndexCount < maxIndexes;
  const isDark = mode === 'dark';

  // Timer to fade the max limit message after 5 seconds
  useEffect(() => {
    if (!canCreateIndex) {
      setIsMessageFaded(false);
      const timer = setTimeout(() => {
        setIsMessageFaded(true);
      }, 5000);

      return () => clearTimeout(timer);
    }
  }, [canCreateIndex]);

  const handleCreateIndex = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    // Clear previous errors
    setLocalError(null);
    
    // Validate index name
    if (!newIndexName.trim()) {
      const error = 'Index name cannot be empty';
      setLocalError(error);
      onError?.(error);
      return;
    }

    if (newIndexName.length < 3 || newIndexName.length > 50) {
      const error = 'Index name must be between 3 and 50 characters';
      setLocalError(error);
      onError?.(error);
      return;
    }

    try {
      setIsCreating(true);
      const newIndex = await indexApi.createIndex(newIndexName.trim());
      setNewIndexName('');
      setLocalError(null);
      
      // Notify parent component
      onIndexCreated?.(newIndex);
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Failed to create index';
      setLocalError(error);
      onError?.(error);
      console.error('Error creating index:', err);
    } finally {
      setIsCreating(false);
    }
  };

  // Show max limit message if limit reached
  if (!canCreateIndex) {
    const bgColor = isMessageFaded 
      ? 'transparent' 
      : (isDark ? 'rgb(113 63 18 / 0.3)' : 'rgb(254 249 195)');
    const borderColor = isMessageFaded
      ? (isDark ? 'rgb(75 85 99)' : 'rgb(209 213 219)')
      : (isDark ? 'rgb(202 138 4)' : 'rgb(250 204 21)');
    const textColor = isMessageFaded
      ? (isDark ? 'rgb(107 114 128)' : 'rgb(156 163 175)')
      : (isDark ? 'rgb(255 255 255)' : 'rgb(113 63 18)');
    
    return (
      <div 
        className="rounded-lg p-3 transition-all duration-500 border"
        style={{
          backgroundColor: bgColor,
          borderColor: borderColor
        }}
      >
        <p 
          className="text-sm font-medium transition-all duration-500"
          style={{ color: textColor }}
        >
          Maximum number of indexes ({maxIndexes}) reached. Delete an index to create a new one.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Local error message */}
      {localError && (
        <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-3">
          <p className="text-red-200 text-sm">{localError}</p>
        </div>
      )}

      {/* Create index form */}
      <form onSubmit={handleCreateIndex} className="bg-white rounded-lg p-4 border border-white/10">
        <div className="flex gap-3">
          <input
            type="text"
            value={newIndexName}
            onChange={(e) => setNewIndexName(e.target.value)}
            placeholder="Enter index name (3-50 characters)"
            disabled={isCreating}
            className="flex-1 px-4 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 shadow-sm rounded-lg 
                     text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500
                     focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-lime-400 focus:border-transparent
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transition-all duration-200"
            minLength={3}
            maxLength={50}
            aria-label="Index name"
          />
          <button
            type="submit"
            disabled={isCreating || !newIndexName.trim()}
            className="px-6 py-2 rounded-lg font-semibold text-white
                     bg-indigo-500
                     hover:bg-indigo-600
                     focus:outline-none focus:ring-2 focus:ring-indigo-400
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transform transition-all duration-200
                     hover:scale-[1.02] active:scale-[0.98]
                     shadow-lg hover:shadow-xl"
          >
            {isCreating ? (
              <span className="flex items-center">
                <svg 
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-gray-900" 
                  xmlns="http://www.w3.org/2000/svg" 
                  fill="none" 
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle 
                    className="opacity-25" 
                    cx="12" 
                    cy="12" 
                    r="10" 
                    stroke="currentColor" 
                    strokeWidth="4"
                  />
                  <path 
                    className="opacity-75" 
                    fill="currentColor" 
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Creating...
              </span>
            ) : (
              'Create Index'
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
