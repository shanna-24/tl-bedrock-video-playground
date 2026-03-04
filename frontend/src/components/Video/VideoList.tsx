/**
 * VideoList Component
 * 
 * Displays a list of videos in an index with thumbnails and metadata.
 * Allows users to select videos for playback.
 * 
 * Validates: Requirements 1.5
 */

import { useEffect, useState } from 'react';
import { videoApi } from '../../services/api';
import type { Video } from '../../types';

interface VideoListProps {
  indexId: string;
  onVideoSelect?: (video: Video) => void;
  onVideoDeleted?: () => void;
  selectedVideoId?: string;
  refreshTrigger?: number; // Used to trigger refresh after upload
}

export default function VideoList({ 
  indexId, 
  onVideoSelect,
  onVideoDeleted,
  selectedVideoId,
  refreshTrigger 
}: VideoListProps) {
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
    e.stopPropagation(); // Prevent video selection
    setShowDeleteConfirm(videoId);
  };

  const handleDeleteConfirm = async (videoId: string) => {
    setDeletingVideoId(videoId);
    setShowDeleteConfirm(null);

    try {
      await videoApi.deleteVideo(videoId);
      // Refresh the video list after successful deletion
      await loadVideos();
      // Notify parent component to refresh indexes
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg">
        <p className="text-red-400">{error}</p>
        <button
          onClick={loadVideos}
          className="mt-2 text-sm text-red-300 hover:text-red-200 underline"
        >
          Try again
        </button>
      </div>
    );
  }

  if (videos.length === 0) {
    return (
      <div className="text-center py-12">
        <svg
          className="mx-auto h-12 w-12 text-gray-500 dark:text-gray-400 mb-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"
          />
        </svg>
        <p className="text-gray-500 dark:text-gray-400 text-lg">No videos in this index</p>
        <p className="text-gray-500 dark:text-gray-400 text-sm mt-2">Upload a video to get started</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          Videos ({videos.length})
        </h3>
        <button
          onClick={loadVideos}
          className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
          title="Refresh"
        >
          <svg
            className="h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {videos.map((video, i) => (
          <div
            key={video.id}
            style={{ animationDelay: `${i * 50}ms` }}
            className={`
              animate-slide-up frost-hover bg-white dark:bg-gray-700/50 rounded-lg overflow-hidden border transition-all duration-200 relative
              ${selectedVideoId === video.id
                ? 'border-indigo-500 dark:border-lime-500 ring-2 ring-indigo-500/50 dark:ring-lime-500/50'
                : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
              }
              ${onVideoSelect ? 'cursor-pointer' : ''}
              ${deletingVideoId === video.id ? 'opacity-50 pointer-events-none' : ''}
            `}
          >
            {/* Delete button */}
            <button
              onClick={(e) => handleDeleteClick(e, video.id)}
              disabled={deletingVideoId === video.id}
              className="absolute top-2 right-2 z-20 p-2 bg-red-400/90 hover:bg-red-500 dark:bg-red-500/90 dark:hover:bg-red-600 text-white rounded-full transition-colors shadow-lg"
              title="Delete video"
            >
              <svg
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
            </button>

            {/* Confirmation dialog */}
            {showDeleteConfirm === video.id && (
              <div className="absolute inset-0 bg-black/50 dark:bg-black/70 flex items-center justify-center z-20 rounded-lg">
                <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-xl max-w-sm mx-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
                    Delete Video?
                  </h3>
                  <p className="text-gray-600 dark:text-gray-300 mb-4">
                    This will permanently delete the video and all related data.
                  </p>
                  <div className="flex space-x-3">
                    <button
                      onClick={() => handleDeleteConfirm(video.id)}
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

            {/* Video card content */}
            <div onClick={() => onVideoSelect && onVideoSelect(video)}>
              {/* Thumbnail */}
              <div className="aspect-video bg-gradient-to-br from-gray-800 to-gray-900 dark:from-gray-900 dark:to-black flex items-center justify-center relative overflow-hidden vignette group">
                {video.thumbnail_url ? (
                  <img
                    className="absolute inset-0 w-full h-full object-cover"
                    src={video.thumbnail_url}
                    alt={video.filename}
                    onError={(e) => {
                      // Hide image on error and show placeholder
                      e.currentTarget.style.display = 'none';
                    }}
                  />
                ) : null}
                
                {/* Play overlay - show on hover */}
                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center z-10 pointer-events-none">
                  <svg
                    className="h-16 w-16 text-gray-200"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                </div>
              </div>

              {/* Video info */}
              <div className="p-4">
                <h4 className="text-gray-900 dark:text-gray-100 font-medium truncate mb-2" title={video.filename}>
                  {video.filename}
                </h4>
                <div className="space-y-1 text-sm text-gray-500 dark:text-gray-300">
                  <div className="flex items-center space-x-2">
                    <svg
                      className="h-4 w-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    <span>{formatDuration(video.duration)}</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <svg
                      className="h-4 w-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                      />
                    </svg>
                    <span>{formatDate(video.uploaded_at)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
