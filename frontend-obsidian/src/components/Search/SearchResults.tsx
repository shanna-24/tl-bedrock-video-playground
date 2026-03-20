/**
 * SearchResults Component
 *
 * Displays search results as clip cards with thumbnails, timecodes, and relevance scores.
 * Supports video reel generation, transcription popups, and real-time thumbnail updates.
 *
 * Validates: Requirements 8.4, 8.5, 8.6, 8.7, 8.8
 */

import { useState, useEffect, useCallback } from 'react';
import type { VideoClip } from '../../types';
import { useThumbnailUpdates } from '../../contexts/WebSocketContext';
import { videoReelApi } from '../../services/api';

interface SearchResultsProps {
  results: VideoClip[];
  query: string;
  searchTime: number;
  onClipSelect: (clip: VideoClip) => void;
  selectedClip: VideoClip | null;
  onReelGenerated: (url: string) => void;
}

function SearchResults({
  results,
  query,
  searchTime,
  onClipSelect,
  selectedClip,
  onReelGenerated,
}: SearchResultsProps) {
  const [thumbnailUrls, setThumbnailUrls] = useState<Record<string, string>>({});
  const [showTranscription, setShowTranscription] = useState<string | null>(null);
  const [isGeneratingReel, setIsGeneratingReel] = useState(false);
  const [reelUrl, setReelUrl] = useState<string | null>(null);
  const [reelError, setReelError] = useState<string | null>(null);

  // Listen for thumbnail ready notifications via WebSocket
  const handleThumbnailReady = useCallback(
    (data: { video_id: string; timecode: number; thumbnail_url: string }) => {
      const key = `${data.video_id}-${Math.round(data.timecode)}`;
      setThumbnailUrls((prev) => ({ ...prev, [key]: data.thumbnail_url }));
    },
    [],
  );

  useThumbnailUpdates(handleThumbnailReady);

  // Reset state when results change
  useEffect(() => {
    setThumbnailUrls({});
    setShowTranscription(null);
    setReelUrl(null);
    setReelError(null);
  }, [results]);

  const getThumbnailUrl = (clip: VideoClip): string => {
    const key = `${clip.video_id}-${Math.round(clip.start_timecode)}`;
    return thumbnailUrls[key] || clip.screenshot_url;
  };

  const formatTimecode = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  const formatRelevanceScore = (score: number): string => {
    return `${Math.round(score * 100)}%`;
  };

  const handleGenerateReel = async () => {
    setIsGeneratingReel(true);
    setReelError(null);
    try {
      const response = await videoReelApi.generateReel(results);
      setReelUrl(response.stream_url);
    } catch (error: any) {
      console.error('Failed to generate video reel:', error);
      setReelError(error.detail || error.message || 'Failed to generate video reel');
    } finally {
      setIsGeneratingReel(false);
    }
  };

  const handlePlayReel = () => {
    if (reelUrl) {
      onReelGenerated(reelUrl);
    }
  };

  // Empty state
  if (results.length === 0) {
    return (
      <div className="text-center py-16">
        <span className="material-symbols-outlined text-5xl text-on-surface-variant mb-4 block">
          search_off
        </span>
        <p className="text-on-surface-variant text-lg mb-2">No results found</p>
        <p className="text-on-surface-variant/60 text-sm">
          Try a different search query or add more videos to your index
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Results header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-on-surface">Search Results</h3>
          <p className="text-sm text-on-surface-variant mt-1">
            Found {results.length} clip{results.length !== 1 ? 's' : ''} for &ldquo;{query}&rdquo;
            {searchTime !== undefined && ` in ${searchTime.toFixed(2)}s`}
          </p>
        </div>

        {/* Video Reel Buttons */}
        <div>
          {!reelUrl ? (
            <button
              onClick={handleGenerateReel}
              disabled={isGeneratingReel || results.length === 0}
              className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-primary to-primary-container text-on-primary rounded-xl
                         hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:ring-offset-2 focus:ring-offset-background
                         disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-md hover:shadow-lg font-medium"
            >
              {isGeneratingReel ? (
                <>
                  <span className="material-symbols-outlined animate-spin text-xl">progress_activity</span>
                  <span>Generating…</span>
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-xl">movie</span>
                  <span>Generate Video Reel</span>
                </>
              )}
            </button>
          ) : (
            <button
              onClick={handlePlayReel}
              className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-primary to-primary-container text-on-primary rounded-xl
                         hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:ring-offset-2 focus:ring-offset-background
                         transition-all duration-200 shadow-md hover:shadow-lg font-medium"
            >
              <span className="material-symbols-outlined text-xl">play_circle</span>
              <span>Play Video Reel</span>
            </button>
          )}
        </div>
      </div>

      {/* Reel error */}
      {reelError && (
        <div className="p-4 bg-error-container/10 border border-error/30 rounded-xl">
          <p className="text-error">{reelError}</p>
        </div>
      )}

      {/* Results grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {results.map((clip, index) => {
          const isSelected =
            selectedClip &&
            selectedClip.video_id === clip.video_id &&
            selectedClip.start_timecode === clip.start_timecode;

          return (
            <div
              key={`${clip.video_id}-${clip.start_timecode}-${index}`}
              onClick={() => onClipSelect(clip)}
              style={{ animationDelay: `${index * 50}ms` }}
              className={`bg-surface-container-low rounded-2xl overflow-hidden border transition-all duration-200 cursor-pointer
                ${
                  isSelected
                    ? 'border-primary ring-2 ring-primary/30'
                    : 'border-outline-variant/10 hover:border-primary/30'
                }`}
            >
              {/* Thumbnail */}
              <div className="relative aspect-video bg-surface-container-high flex items-center justify-center overflow-hidden group">
                {getThumbnailUrl(clip) ? (
                  <img
                    src={getThumbnailUrl(clip)}
                    alt={`Clip at ${formatTimecode(clip.start_timecode)}`}
                    className="absolute inset-0 w-full h-full object-cover"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                    }}
                  />
                ) : null}

                {/* Gradient overlay on hover */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

                {/* Play overlay on hover */}
                <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center z-10 pointer-events-none">
                  <span className="material-symbols-outlined text-6xl text-on-surface/80">
                    play_circle
                  </span>
                </div>

                {/* Relevance score badge (top-right) */}
                <div className="absolute top-2 right-2 z-10">
                  <div className="px-2.5 py-1 rounded-lg bg-black/60 backdrop-blur-md text-xs font-semibold text-primary">
                    {formatRelevanceScore(clip.relevance_score)}
                  </div>
                </div>

                {/* Transcription button (bottom-right) */}
                {clip.metadata?.transcription && (
                  <div className="absolute bottom-2 right-2 z-10">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        const key = `${clip.video_id}-${clip.start_timecode}`;
                        setShowTranscription(showTranscription === key ? null : key);
                      }}
                      className="p-2 rounded-lg bg-black/60 backdrop-blur-md hover:bg-black/80 transition-colors text-on-surface"
                      title="View transcription"
                    >
                      <span className="material-symbols-outlined text-lg">closed_caption</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Clip info */}
              <div className="p-4 space-y-2">
                {/* Timecode */}
                <div className="flex items-center space-x-2 text-sm">
                  <span className="material-symbols-outlined text-base text-on-surface-variant">
                    schedule
                  </span>
                  <span className="text-on-surface font-medium">
                    {formatTimecode(clip.start_timecode)}
                  </span>
                  <span className="text-on-surface-variant">–</span>
                  <span className="text-on-surface-variant">
                    {formatTimecode(clip.end_timecode)}
                  </span>
                </div>

                {/* Duration */}
                <div className="text-xs text-on-surface-variant">
                  Duration: {formatTimecode(clip.end_timecode - clip.start_timecode)}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Transcription popup (Glass_Panel) */}
      {showTranscription &&
        results.find(
          (clip) => `${clip.video_id}-${clip.start_timecode}` === showTranscription,
        ) && (
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50"
            onClick={() => setShowTranscription(null)}
          >
            <div
              className="bg-surface-container-high/80 backdrop-blur-[12px] rounded-2xl shadow-2xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden border border-outline-variant/10"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant/10">
                <h3 className="text-lg font-semibold text-on-surface">Audio Transcript</h3>
                <button
                  onClick={() => setShowTranscription(null)}
                  className="text-on-surface-variant hover:text-on-surface transition-colors"
                >
                  <span className="material-symbols-outlined">close</span>
                </button>
              </div>

              {/* Content */}
              <div className="px-6 py-4 overflow-y-auto max-h-[calc(80vh-80px)] custom-scrollbar">
                <p className="text-base text-on-surface leading-relaxed whitespace-pre-wrap text-left">
                  {
                    results.find(
                      (clip) =>
                        `${clip.video_id}-${clip.start_timecode}` === showTranscription,
                    )?.metadata?.transcription
                  }
                </p>
              </div>
            </div>
          </div>
        )}
    </div>
  );
}

export default SearchResults;
