/**
 * IndexList Component
 * 
 * Displays a list of video indexes with create/delete functionality.
 * Shows index count and max limit indicator (3 indexes).
 * 
 * Validates: Requirements 1.1, 1.2, 1.3
 */

import { useState, useEffect } from 'react';
import { indexApi } from '../../services/api';
import type { Index } from '../../types';

interface IndexListProps {
  onIndexSelect?: (index: Index) => void;
  selectedIndexId?: string;
  indexes?: Index[];
  maxIndexes?: number;
  onRefresh?: () => void;
}

export default function IndexList({ 
  onIndexSelect, 
  selectedIndexId,
  indexes: propIndexes,
  maxIndexes: propMaxIndexes,
  onRefresh
}: IndexListProps) {
  const [indexes, setIndexes] = useState<Index[]>(propIndexes || []);
  const [isLoading, setIsLoading] = useState(!propIndexes);
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [newIndexName, setNewIndexName] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null);
  const [maxIndexes, setMaxIndexes] = useState(propMaxIndexes || 3);
  const [isMessageFaded, setIsMessageFaded] = useState(false);

  // Update local state when props change
  useEffect(() => {
    if (propIndexes) {
      setIndexes(propIndexes);
      setIsLoading(false);
    }
    if (propMaxIndexes !== undefined) {
      setMaxIndexes(propMaxIndexes);
    }
  }, [propIndexes, propMaxIndexes]);

  // Load indexes on mount only if not provided as props
  useEffect(() => {
    if (!propIndexes) {
      loadIndexes();
    }
  }, [propIndexes]);

  const loadIndexes = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await indexApi.listIndexes();
      setIndexes(response.indexes);
      setMaxIndexes(response.max_indexes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load indexes');
      console.error('Error loading indexes:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateIndex = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!newIndexName.trim()) {
      setError('Index name cannot be empty');
      return;
    }

    if (newIndexName.length < 3 || newIndexName.length > 30) {
      setError('Index name must be between 3 and 30 characters');
      return;
    }

    try {
      setIsCreating(true);
      setError(null);
      const newIndex = await indexApi.createIndex(newIndexName.trim());
      
      // If using props, notify parent to refresh
      if (propIndexes && onRefresh) {
        onRefresh();
      } else {
        setIndexes([...indexes, newIndex]);
      }
      
      setNewIndexName('');
      
      // Auto-select the newly created index
      if (onIndexSelect) {
        onIndexSelect(newIndex);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create index');
      console.error('Error creating index:', err);
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteClick = (e: React.MouseEvent, indexId: string) => {
    e.stopPropagation();
    setShowDeleteConfirm(indexId);
  };

  const handleDeleteConfirm = async (indexId: string) => {
    setDeletingId(indexId);
    setShowDeleteConfirm(null);

    try {
      setError(null);
      await indexApi.deleteIndex(indexId);
      
      // If using props, notify parent to refresh
      if (propIndexes && onRefresh) {
        onRefresh();
      } else {
        setIndexes(indexes.filter(idx => idx.id !== indexId));
      }
      
      // Clear selection if deleted index was selected
      if (selectedIndexId === indexId && onIndexSelect) {
        onIndexSelect(null as any);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete index');
      console.error('Error deleting index:', err);
    } finally {
      setDeletingId(null);
    }
  };

  const handleDeleteCancel = () => {
    setShowDeleteConfirm(null);
  };

  const handleSelectIndex = (index: Index) => {
    if (onIndexSelect) {
      onIndexSelect(index);
    }
  };

  const canCreateIndex = indexes.length < maxIndexes;

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

  return (
    <div className="space-y-6">
      {/* Header with count indicator */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Indexes</h2>
          <p className="text-gray-500 dark:text-gray-300 text-sm mt-1">
            {indexes.length} of {maxIndexes} indexes created
          </p>
        </div>
        
        {/* Index limit indicator */}
        <div className="flex items-center space-x-2">
          {[...Array(maxIndexes)].map((_, i) => (
            <div
              key={i}
              className={`w-3 h-3 rounded-full ${
                i < indexes.length
                  ? 'bg-indigo-500 dark:bg-lime-500'
                  : 'bg-gray-200 dark:bg-gray-700'
              }`}
              title={`Index ${i + 1}${i < indexes.length ? ' (created)' : ' (available)'}`}
            />
          ))}
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="bg-red-500/20 dark:bg-red-900/30 border border-red-500/50 dark:border-red-500/50 rounded-lg p-3">
          <p className="text-red-600 dark:text-red-400 text-sm font-medium">{error}</p>
        </div>
      )}

      {/* Create index form */}
      {canCreateIndex && (
        <form onSubmit={handleCreateIndex} className="bg-white dark:bg-gray-700/50 rounded-lg p-4 border border-gray-200 dark:border-gray-600">
          <div className="flex flex-col gap-3">
            <input
              type="text"
              value={newIndexName}
              onChange={(e) => setNewIndexName(e.target.value)}
              placeholder="Enter index name (30 chars max)"
              disabled={isCreating}
              className="w-full px-4 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 shadow-sm rounded-lg 
                       text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500
                       focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-lime-400 focus:border-transparent
                       disabled:opacity-50 disabled:cursor-not-allowed
                       transition-all duration-200"
              minLength={3}
              maxLength={30}
            />
            <button
              type="submit"
              disabled={isCreating || !newIndexName.trim()}
              className="w-full px-6 py-2 rounded-lg font-semibold text-white
                       bg-indigo-500 dark:bg-lime-500
                       hover:bg-indigo-600 dark:hover:bg-lime-600
                       focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-lime-400
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
      )}

      {/* Max limit reached message */}
      {!canCreateIndex && (
        <div 
          className={`rounded-lg p-3 transition-all duration-500 ${
            isMessageFaded 
              ? 'bg-transparent border border-gray-300' 
              : 'bg-yellow-500/20 border border-yellow-500/50'
          }`}
        >
          <p 
            className={`text-sm font-medium transition-all duration-500 ${
              isMessageFaded 
                ? 'text-gray-400 dark:text-gray-500' 
                : 'text-yellow-900 dark:text-white'
            }`}
          >
            Maximum number of indexes ({maxIndexes}) reached. Delete an index to create a new one.
          </p>
        </div>
      )}

      {/* Index list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <svg 
            className="animate-spin h-8 w-8 text-gray-200" 
            xmlns="http://www.w3.org/2000/svg" 
            fill="none" 
            viewBox="0 0 24 24"
            role="img"
            aria-label="Loading"
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
        </div>
      ) : indexes.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-gray-500 mb-2">
            <svg 
              className="mx-auto h-12 w-12 mb-4" 
              fill="none" 
              viewBox="0 0 24 24" 
              stroke="currentColor"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" 
              />
            </svg>
            <p className="text-lg">No indexes yet</p>
            <p className="text-sm mt-1">Create your first index to get started</p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {indexes.map((index, i) => (
            <div
              key={index.id}
              style={{ animationDelay: `${i * 50}ms` }}
              className={`animate-slide-up frost-hover bg-white dark:bg-gray-700/50 rounded-lg p-4 border transition-all duration-200 relative ${
                selectedIndexId === index.id
                  ? 'border-indigo-500 dark:border-lime-500 bg-indigo-500/10 dark:bg-lime-500/20'
                  : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
              } ${deletingId === index.id ? 'opacity-50 pointer-events-none' : ''}`}
            >
              {/* Small round delete button positioned in top-right */}
              <button
                onClick={(e) => handleDeleteClick(e, index.id)}
                disabled={deletingId === index.id}
                className="absolute top-3 right-3 p-1.5 rounded-full text-white
                         bg-red-400 hover:bg-red-500 dark:bg-red-500 dark:hover:bg-red-600
                         focus:outline-none focus:ring-2 focus:ring-red-400
                         disabled:opacity-50 disabled:cursor-not-allowed
                         transition-all duration-200 hover:scale-110
                         shadow-sm"
                title="Delete index"
              >
                {deletingId === index.id ? (
                  <svg 
                    className="animate-spin h-3.5 w-3.5" 
                    xmlns="http://www.w3.org/2000/svg" 
                    fill="none" 
                    viewBox="0 0 24 24"
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
                ) : (
                  <svg 
                    className="h-3.5 w-3.5" 
                    fill="none" 
                    viewBox="0 0 24 24" 
                    stroke="currentColor"
                  >
                    <path 
                      strokeLinecap="round" 
                      strokeLinejoin="round" 
                      strokeWidth={2} 
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" 
                    />
                  </svg>
                )}
              </button>

              {/* Confirmation dialog */}
              {showDeleteConfirm === index.id && (
                <div className="absolute inset-0 bg-black/50 dark:bg-black/70 flex items-center justify-center z-20 rounded-lg">
                  <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-xl max-w-sm mx-4">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
                      Delete Index?
                    </h3>
                    <p className="text-gray-600 dark:text-gray-300 mb-4">
                      This will permanently delete the index and all videos.
                    </p>
                    <div className="flex space-x-3">
                      <button
                        onClick={() => handleDeleteConfirm(index.id)}
                        className="flex-1 px-4 py-2 bg-red-500 hover:bg-red-600 dark:bg-red-600 dark:hover:bg-red-700 text-white rounded-lg transition-colors"
                      >
                        Delete
                      </button>
                      <button
                        onClick={handleDeleteCancel}
                        className="flex-1 px-4 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-900 dark:text-gray-100 rounded-lg transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <button
                onClick={() => handleSelectIndex(index)}
                className="w-full text-left pr-10"
              >
                <div className="flex items-start space-x-3">
                  <div className={`w-2 h-2 rounded-full mt-2 ${
                    selectedIndexId === index.id
                      ? 'bg-green-500 dark:bg-green-400'
                      : 'bg-gray-400 dark:bg-gray-600'
                  }`} />
                  <div className="flex flex-col">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{index.name}</h3>
                    <span className="text-sm text-gray-500 dark:text-gray-300">{index.video_count} {index.video_count === 1 ? 'video' : 'videos'}</span>
                    <span className="text-xs text-gray-400 dark:text-gray-500">Created {new Date(index.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
