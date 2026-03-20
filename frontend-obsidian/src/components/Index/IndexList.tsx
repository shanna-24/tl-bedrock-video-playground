/**
 * IndexList Component
 *
 * Displays a list of video indexes with create/delete functionality.
 * Shows index count and max limit indicator.
 * Styled with Obsidian Lens design tokens.
 *
 * Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5
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
  onRefresh,
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
        setIndexes(indexes.filter((idx) => idx.id !== indexId));
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
    <div className="space-y-2">
      {/* Error message */}
      {error && (
        <div className="bg-error/10 border border-error/30 rounded-lg p-3 mx-2">
          <p className="text-error text-sm font-medium">{error}</p>
        </div>
      )}

      {/* Create index form */}
      {canCreateIndex && (
        <form onSubmit={handleCreateIndex} className="px-2 pb-2">
          <div className="flex flex-col gap-2">
            <input
              type="text"
              value={newIndexName}
              onChange={(e) => setNewIndexName(e.target.value)}
              placeholder="New index name..."
              disabled={isCreating}
              className="w-full px-3 py-2 bg-surface-container-low text-on-surface ghost-border rounded-lg
                       placeholder-on-surface-variant/50
                       focus:outline-none focus:ring-1 focus:ring-primary/40
                       disabled:opacity-50 disabled:cursor-not-allowed
                       transition-all duration-200 text-sm"
              minLength={3}
              maxLength={30}
            />
            <button
              type="submit"
              disabled={isCreating || !newIndexName.trim()}
              className="w-full px-4 py-2 rounded-lg font-semibold text-sm
                       bg-gradient-to-r from-primary to-primary-container text-on-primary
                       hover:opacity-90
                       focus:outline-none focus:ring-2 focus:ring-primary/40
                       disabled:opacity-50 disabled:cursor-not-allowed
                       transition-all duration-200"
            >
              {isCreating ? (
                <span className="flex items-center justify-center">
                  <svg
                    className="animate-spin -ml-1 mr-2 h-4 w-4 text-on-primary"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
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
          className={`rounded-lg p-3 mx-2 transition-all duration-500 ${
            isMessageFaded
              ? 'bg-transparent border border-outline-variant/20'
              : 'bg-secondary/10 border border-secondary/30'
          }`}
        >
          <p
            className={`text-xs font-medium transition-all duration-500 ${
              isMessageFaded ? 'text-on-surface-variant/50' : 'text-secondary'
            }`}
          >
            Maximum indexes ({maxIndexes}) reached. Delete one to create a new one.
          </p>
        </div>
      )}

      {/* Index list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <svg
            className="animate-spin h-6 w-6 text-on-surface-variant"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            role="img"
            aria-label="Loading"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        </div>
      ) : indexes.length === 0 ? (
        <div className="text-center py-12 px-4">
          <span className="material-symbols-outlined text-4xl text-on-surface-variant/40 mb-2 block">
            inventory_2
          </span>
          <p className="text-on-surface-variant text-sm">No indexes yet</p>
          <p className="text-on-surface-variant/60 text-xs mt-1">Create your first index to get started</p>
        </div>
      ) : (
        <div className="flex flex-col">
          {indexes.map((index) => {
            const isActive = selectedIndexId === index.id;
            const isDeleting = deletingId === index.id;

            return (
              <div
                key={index.id}
                className={`relative group ${isDeleting ? 'opacity-50 pointer-events-none' : ''}`}
              >
                {/* Delete confirmation overlay */}
                {showDeleteConfirm === index.id && (
                  <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-20 rounded-lg">
                    <div className="bg-surface-container-high rounded-lg p-4 mx-2 shadow-xl">
                      <h3 className="text-on-surface font-semibold text-sm mb-1">Delete Index?</h3>
                      <p className="text-on-surface-variant text-xs mb-3">
                        This will permanently delete the index and all videos.
                      </p>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleDeleteConfirm(index.id)}
                          className="flex-1 px-3 py-1.5 bg-error hover:bg-error/80 text-on-error rounded-lg transition-colors text-xs font-medium"
                        >
                          Delete
                        </button>
                        <button
                          onClick={handleDeleteCancel}
                          className="flex-1 px-3 py-1.5 bg-surface-container-highest hover:bg-surface-bright text-on-surface rounded-lg transition-colors text-xs font-medium"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Index item */}
                <div
                  onClick={() => handleSelectIndex(index)}
                  className={`flex items-start gap-3 px-3 py-4 cursor-pointer transition-all duration-200 relative ${
                    isActive
                      ? 'bg-surface-container-high border-l-2 border-primary text-primary'
                      : 'text-on-surface-variant hover:bg-surface-variant hover:text-on-surface border-l-2 border-transparent'
                  }`}
                >
                  {/* Folder icon */}
                  <span
                    className={`material-symbols-outlined text-[20px] mt-0.5 shrink-0 ${
                      isActive ? 'text-primary' : 'text-on-surface-variant'
                    }`}
                  >
                    folder
                  </span>

                  {/* Index info */}
                  <div className="flex flex-col min-w-0 flex-1">
                    <span
                      className={`text-sm font-medium truncate ${
                        isActive ? 'text-primary' : 'text-on-surface'
                      }`}
                    >
                      {index.name}
                    </span>
                    <span className="text-on-surface-variant text-xs">
                      {index.video_count} {index.video_count === 1 ? 'video' : 'videos'}
                    </span>
                    <span className="text-on-surface-variant text-xs">
                      {new Date(index.created_at).toLocaleDateString()}
                    </span>
                  </div>

                  {/* Delete button - visible on hover */}
                  <button
                    onClick={(e) => handleDeleteClick(e, index.id)}
                    disabled={isDeleting}
                    className="absolute top-3 right-2 p-1 rounded-full
                             bg-error text-on-error
                             opacity-0 group-hover:opacity-100
                             focus:outline-none focus:ring-1 focus:ring-error
                             disabled:opacity-50 disabled:cursor-not-allowed
                             transition-all duration-200 hover:scale-110"
                    title="Delete index"
                  >
                    {isDeleting ? (
                      <svg
                        className="animate-spin h-3.5 w-3.5"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    ) : (
                      <span className="material-symbols-outlined text-[14px]">delete</span>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
