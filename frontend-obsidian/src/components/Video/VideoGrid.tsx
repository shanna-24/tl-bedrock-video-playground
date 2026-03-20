/**
 * VideoGrid Component
 *
 * Displays a responsive grid of video cards with thumbnails and metadata.
 * Allows users to select videos for playback and delete videos.
 * Reimplemented from VideoList with Obsidian Lens design tokens.
 *
 * Validates: Requirements 7.3, 7.4, 7.5, 7.6, 7.7, 13.3
 */

import { useEffect, useState } from 'react';
import { videoApi } from '../../services/api';
import type { Video } from '../../types';

interface VideoGridProps {
  indexId: string;
  onVideoSelect?: (video: Video) => void;
  onVideoDeleted?: () => void;
  selectedVideoId?: string;
  refreshTrigger?: number;
}

export default function VideoGrid({
  indexId,
  onVideoSelect,
  onVideoDeleted,
  selectedVideoId,
  refreshTrigger,
}: VideoGridProps) {
  const [videos, setVideos] = useState<Video[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingVideoId, setDeletingVideoId] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null);

  useEffect(() => {
    loadVideos();
  }, [indexId, refreshTrigger]);

  const loadVideos = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await videoApi.listVideos(indexId);
      setVideos(response.videos);
    } catch (err: any) {
      const errorMessage = err.detail || err.message || 'Failed to load videos';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteClick = (e: React.MouseEvent, videoId: string) => {
    e.stopPropagation();
    setShowDeleteConfirm(videoId);
  };

  const handleDeleteConfirm = async (videoId: string) => {
    setDeletingVideoId(videoId);
    setShowDeleteConfirm(null);

    try {
      await videoApi.deleteVideo(videoId);
      await loadVideos();
      if (onVideoDeleted) {
        onVideoDeleted();
      }
    } catch (err: any) {
      const errorMessage = err.detail || err.message || 'Failed to delete video';
      setError(errorMessage);
    } finally {
      setDeletingVideoId(null);
    }
  };

  const handleDeleteCancel = () => {
    setShowDeleteConfirm(null);
  };

  const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-on-surface-variant" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="p-4 bg-error/10 border border-error/30 rounded-lg">
        <p className="text-error">{error}</p>
        <button
          onClick={loadVideos}
          className="mt-2 text-sm text-error hover:text-on-error-container underline"
        >
          Try again
        </button>
      </div>
    );
  }

  // Empty state
  if (videos.length === 0) {
    return (
      <div className="text-center py-12">
        <span className="material-symbols-outlined text-5xl text-on-surface-variant mb-4 block">
          videocam_off
        </span>
        <p className="text-on-surface-variant text-lg">No videos in this index</p>
        <p className="text-on-surface-variant text-sm mt-2">Upload a video to get started</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-on-surface">
          Videos ({videos.length})
        </h3>
        <button
          onClick={loadVideos}
          className="text-on-surface-variant hover:text-on-surface transition-colors p-1"
          title="Refresh"
        >
          <span className="material-symbols-outlined text-xl">refresh</span>
        </button>
      </div>

      {/* Responsive grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {videos.map((video) => (
          <div
            key={video.id}
            className={`
              group relative bg-surface-container-high rounded-xl overflow-hidden border transition-all duration-200
              ${selectedVideoId === video.id
                ? 'border-primary ring-1 ring-primary/30'
                : 'border-outline-variant/10 hover:border-primary/20'
              }
              ${onVideoSelect ? 'cursor-pointer' : ''}
              ${deletingVideoId === video.id ? 'opacity-50 pointer-events-none' : ''}
            `}
          >
            {/* Delete button - visible on hover */}
            <button
              onClick={(e) => handleDeleteClick(e, video.id)}
              disabled={deletingVideoId === video.id}
              className="absolute top-2 right-2 z-20 p-1.5 bg-error text-on-error rounded-full opacity-0 group-hover:opacity-100 transition-opacity shadow-lg"
              title="Delete video"
            >
              <span className="material-symbols-outlined text-base">delete</span>
            </button>

            {/* Delete confirmation dialog */}
            {showDeleteConfirm === video.id && (
              <div className="absolute inset-0 bg-black/70 flex items-center justify-center z-20 rounded-xl">
                <div className="bg-surface-container-high rounded-lg p-6 shadow-xl max-w-sm mx-4">
                  <h3 className="text-lg font-semibold text-on-surface mb-2">
                    Delete Video?
                  </h3>
                  <p className="text-on-surface-variant mb-4">
                    This will permanently delete the video and all related data.
                  </p>
                  <div className="flex space-x-3">
                    <button
                      onClick={() => handleDeleteConfirm(video.id)}
                      className="flex-1 px-4 py-2 bg-error hover:bg-error-dim text-on-error rounded-lg transition-colors"
                    >
                      Delete
                    </button>
                    <button
                      onClick={handleDeleteCancel}
                      className="flex-1 px-4 py-2 bg-surface-container-highest hover:bg-surface-bright text-on-surface rounded-lg transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Video card content */}
            <div onClick={() => onVideoSelect && onVideoSelect(video)}>
              {/* Thumbnail */}
              <div className="aspect-video bg-surface-container-low relative overflow-hidden">
                {video.thumbnail_url ? (
                  <img
                    className="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    src={video.thumbnail_url}
                    alt={video.filename}
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                    }}
                  />
                ) : null}

                {/* Play overlay on hover */}
                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center z-10 pointer-events-none">
                  <span className="material-symbols-outlined text-6xl text-on-surface">
                    play_circle
                  </span>
                </div>

                {/* Duration badge */}
                <span className="absolute bottom-2 right-2 bg-black/70 text-on-surface text-xs px-2 py-0.5 rounded">
                  {formatDuration(video.duration)}
                </span>
              </div>

              {/* Video info */}
              <div className="p-4">
                <h4
                  className="text-on-surface font-medium truncate mb-1"
                  title={video.filename}
                >
                  {video.filename}
                </h4>
                <p className="text-on-surface-variant text-xs">
                  {formatDate(video.uploaded_at)}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
