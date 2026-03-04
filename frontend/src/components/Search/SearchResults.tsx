/**
 * SearchResults Component
 * 
 * Displays search results with screenshots, timecodes, and relevance scores.
 * Allows users to select clips for playback.
 * Thumbnails update in real-time as they're generated.
 * Shows transcription text when available via popup.
 * 
 * Validates: Requirements 3.2, 3.3
 */

import { useState, useEffect, useCallback } from 'react';
import type { VideoClip } from '../../types';
import { useThumbnailUpdates } from '../../contexts/WebSocketContext';
import { videoReelApi } from '../../services/api';

interface SearchResultsProps {
  results: VideoClip[];
  query: string;
  searchTime?: number;
  onClipSelect?: (clip: VideoClip) => void;
  selectedClip?: VideoClip | null;
  onReelGenerated?: (reelUrl: string) => void;
}

export default function SearchResults({ 
  results, 
  query, 
  searchTime,
  onClipSelect,
  selectedClip,
  onReelGenerated
}: SearchResultsProps) {
  // Track thumbnail URLs that get updated via WebSocket
  const [thumbnailUrls, setThumbnailUrls] = useState<Record<string, string>>({});
  // Track which clip's transcription is being shown
  const [showTranscription, setShowTranscription] = useState<string | null>(null);
  // Track video reel generation state
  const [isGeneratingReel, setIsGeneratingReel] = useState(false);
  const [reelUrl, setReelUrl] = useState<string | null>(null);
  const [reelError, setReelError] = useState<string | null>(null);

  // Listen for thumbnail ready notifications
  const handleThumbnailReady = useCallback((data: { video_id: string; timecode: number; thumbnail_url: string }) => {
    const key = `${data.video_id}-${Math.round(data.timecode)}`;
    setThumbnailUrls(prev => ({
      ...prev,
      [key]: data.thumbnail_url
    }));
  }, []);

  useThumbnailUpdates(handleThumbnailReady);

  // Reset thumbnail URLs when results change
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

  const getScoreColor = (score: number): string => {
    if (score >= 0.8) return 'text-green-400';
    if (score >= 0.6) return 'text-yellow-400';
    return 'text-orange-400';
  };

  const handleGenerateReel = async () => {
    setIsGeneratingReel(true);
    setReelError(null);
    
    try {
      const response = await videoReelApi.generateReel(results);
      setReelUrl(response.stream_url);
      // Don't call onReelGenerated here - user must click "Play Video Reel" button
    } catch (error: any) {
      console.error('Failed to generate video reel:', error);
      setReelError(error.detail || error.message || 'Failed to generate video reel');
    } finally {
      setIsGeneratingReel(false);
    }
  };

  const handlePlayReel = () => {
    if (reelUrl && onReelGenerated) {
      onReelGenerated(reelUrl);
    }
  };

  if (results.length === 0) {
    return (
      <div className="text-center py-12">
        <svg
          className="mx-auto h-16 w-16 text-gray-500 dark:text-gray-300 mb-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <p className="text-gray-500 dark:text-gray-300 text-lg mb-2">No results found</p>
        <p className="text-gray-500 dark:text-gray-300 text-sm">
          Try a different search query or add more videos to your index
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Results header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Search Results
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-300 mt-1">
            Found {results.length} clip{results.length !== 1 ? 's' : ''} for "{query}"
            {searchTime && ` in ${searchTime.toFixed(2)}s`}
          </p>
        </div>
        
        {/* Video Reel Button */}
        <div>
          {!reelUrl ? (
            <button
              onClick={handleGenerateReel}
              disabled={isGeneratingReel || results.length === 0}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-500 to-indigo-600 dark:from-lime-500 dark:to-lime-600 text-white rounded-lg
                       hover:from-indigo-600 hover:to-indigo-500 dark:hover:from-lime-600 dark:hover:to-lime-500
                       focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-lime-400 focus:ring-offset-2
                       disabled:opacity-50 disabled:cursor-not-allowed
                       transition-all duration-200 shadow-md hover:shadow-lg"
            >
              {isGeneratingReel ? (
                <>
                  <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Generating...</span>
                </>
              ) : (
                <>
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  <span>Generate Video Reel</span>
                </>
              )}
            </button>
          ) : (
            <button
              onClick={handlePlayReel}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-500 to-indigo-600 dark:from-lime-500 dark:to-lime-600 text-white rounded-lg
                       hover:from-indigo-600 hover:to-indigo-500 dark:hover:from-lime-600 dark:hover:to-lime-500
                       focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-lime-400 focus:ring-offset-2
                       transition-all duration-200 shadow-md hover:shadow-lg"
            >
              <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
              <span>Play Video Reel</span>
            </button>
          )}
        </div>
      </div>

      {/* Error message */}
      {reelError && (
        <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg">
          <p className="text-red-400">{reelError}</p>
        </div>
      )}

      {/* Results grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {results.map((clip, index) => {
          const isSelected = selectedClip && 
            selectedClip.video_id === clip.video_id && 
            selectedClip.start_timecode === clip.start_timecode;
          
          return (
            <div
              key={`${clip.video_id}-${clip.start_timecode}-${index}`}
              onClick={() => onClipSelect && onClipSelect(clip)}
              style={{ animationDelay: `${index * 50}ms` }}
              className={`animate-slide-up frost-hover bg-white dark:bg-gray-700/50 rounded-lg overflow-hidden border transition-all duration-200 cursor-pointer
                ${isSelected
                  ? 'border-indigo-500 dark:border-lime-500 ring-2 ring-indigo-500/50 dark:ring-lime-500/50'
                  : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                }`}
            >
            {/* Screenshot */}
            <div className="relative aspect-video bg-gradient-to-br from-gray-800 to-gray-900 dark:from-gray-900 dark:to-black flex items-center justify-center overflow-hidden vignette group">
              {getThumbnailUrl(clip) ? (
                <img
                  src={getThumbnailUrl(clip)}
                  alt={`Clip at ${formatTimecode(clip.start_timecode)}`}
                  className="absolute inset-0 w-full h-full object-cover"
                  onError={(e) => {
                    // Fallback if screenshot fails to load
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

              {/* Relevance score badge */}
              <div className="absolute top-2 right-2">
                <div className={`px-2 py-1 rounded-lg bg-black/70 backdrop-blur-sm
                              text-xs font-semibold ${getScoreColor(clip.relevance_score)}`}>
                  {formatRelevanceScore(clip.relevance_score)}
                </div>
              </div>

              {/* Transcription icon */}
              {clip.metadata?.transcription && (
                <div className="absolute bottom-2 right-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      const key = `${clip.video_id}-${clip.start_timecode}`;
                      setShowTranscription(showTranscription === key ? null : key);
                    }}
                    className="p-2 rounded-lg bg-black/70 backdrop-blur-sm
                             hover:bg-black/90 transition-colors
                             text-white"
                    title="View transcription"
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
                        d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z"
                      />
                    </svg>
                  </button>
                </div>
              )}
            </div>

            {/* Clip info */}
            <div className="p-4 space-y-2">
              {/* Timecode */}
              <div className="flex items-center space-x-2 text-sm">
                <svg
                  className="h-4 w-4 text-gray-500 dark:text-gray-300"
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
                <span className="text-gray-900 dark:text-gray-100 font-medium">
                  {formatTimecode(clip.start_timecode)}
                </span>
                <span className="text-gray-500 dark:text-gray-300">-</span>
                <span className="text-gray-500 dark:text-gray-300">
                  {formatTimecode(clip.end_timecode)}
                </span>
              </div>

              {/* Duration */}
              <div className="text-xs text-gray-500 dark:text-gray-300">
                Duration: {formatTimecode(clip.end_timecode - clip.start_timecode)}
              </div>
            </div>
          </div>
        );
        })}
      </div>

      {/* Centered floating transcription popup */}
      {showTranscription && results.find(clip => 
        `${clip.video_id}-${clip.start_timecode}` === showTranscription
      ) && (
        <div 
          className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50"
          onClick={() => setShowTranscription(null)}
        >
          <div 
            className="bg-white dark:bg-gray-700/50 rounded-lg shadow-2xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-600">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Audio Transcript
              </h3>
              <button
                onClick={() => setShowTranscription(null)}
                className="text-gray-400 hover:text-gray-600 dark:text-gray-300 transition-colors"
              >
                <svg
                  className="h-6 w-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
            
            {/* Content */}
            <div className="px-6 py-4 overflow-y-auto max-h-[calc(80vh-80px)]">
              <p className="text-base text-gray-700 dark:text-gray-200 leading-relaxed whitespace-pre-wrap text-left">
                {results.find(clip => 
                  `${clip.video_id}-${clip.start_timecode}` === showTranscription
                )?.metadata?.transcription}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
