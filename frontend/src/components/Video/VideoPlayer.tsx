/**
 * VideoPlayer Component
 * 
 * HTML5 video player with custom controls and timecode support.
 * Supports playback from specific start times.
 * 
 * Validates: Requirements 2.1, 2.2, 2.3
 */

import { useEffect, useRef, useState } from 'react';
import { videoApi } from '../../services/api';

interface VideoPlayerProps {
  videoId?: string;
  videoUrl?: string; // Direct video URL (for search clips)
  startTime?: number; // Start time in seconds
  endTime?: number; // End time in seconds (for clip playback)
  autoPlay?: boolean;
}

export default function VideoPlayer({ 
  videoId, 
  videoUrl,
  startTime = 0, 
  endTime,
  autoPlay = false 
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);

  useEffect(() => {
    // Load video from API if videoId is provided, otherwise use direct URL
    if (videoId) {
      loadVideo();
    } else if (videoUrl) {
      setStreamUrl(videoUrl);
      setIsLoading(false);
    }
  }, [videoId, videoUrl, startTime]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !streamUrl) return;

    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime);
      
      // Enforce end time for clip playback
      if (endTime !== undefined && video.currentTime >= endTime) {
        video.pause();
        video.currentTime = startTime; // Reset to start of clip
        setIsPlaying(false);
      }
    };
    
    const handleDurationChange = () => setDuration(video.duration);
    const handleLoadedMetadata = () => {
      setDuration(video.duration);
      if (startTime > 0) {
        video.currentTime = startTime;
      }
      if (autoPlay) {
        video.play().catch(err => console.error('Autoplay failed:', err));
      }
    };
    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleEnded = () => setIsPlaying(false);
    
    // Prevent seeking outside clip boundaries
    const handleSeeking = () => {
      if (endTime !== undefined) {
        if (video.currentTime < startTime) {
          video.currentTime = startTime;
        } else if (video.currentTime > endTime) {
          video.currentTime = endTime;
        }
      } else if (video.currentTime < startTime) {
        video.currentTime = startTime;
      }
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('durationchange', handleDurationChange);
    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);
    video.addEventListener('ended', handleEnded);
    video.addEventListener('seeking', handleSeeking);

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('durationchange', handleDurationChange);
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('pause', handlePause);
      video.removeEventListener('ended', handleEnded);
      video.removeEventListener('seeking', handleSeeking);
    };
  }, [streamUrl, startTime, endTime, autoPlay]);

  const loadVideo = async () => {
    if (!videoId) return;
    
    setIsLoading(true);
    setError(null);

    try {
      const response = await videoApi.getStreamUrl(videoId, startTime);
      setStreamUrl(response.stream_url);
      
      // Wait for video to load metadata before seeking
      if (videoRef.current) {
        videoRef.current.onloadedmetadata = () => {
          if (videoRef.current && startTime > 0) {
            videoRef.current.currentTime = startTime;
          }
          if (autoPlay && videoRef.current) {
            videoRef.current.play();
          }
        };
      }
    } catch (err: any) {
      const errorMessage = err.detail || err.message || 'Failed to load video';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const togglePlayPause = () => {
    if (!videoRef.current) return;

    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    let time = parseFloat(e.target.value);
    
    // Constrain seeking to clip boundaries if endTime is set
    if (endTime !== undefined) {
      time = Math.max(startTime, Math.min(time, endTime));
    } else {
      time = Math.max(startTime, time);
    }
    
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const vol = parseFloat(e.target.value);
    setVolume(vol);
    if (videoRef.current) {
      videoRef.current.volume = vol;
    }
    if (vol > 0 && isMuted) {
      setIsMuted(false);
    }
  };

  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  const formatTime = (seconds: number): string => {
    if (isNaN(seconds)) return '0:00';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  if (isLoading) {
    return (
      <div className="aspect-video bg-gray-900 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500 mx-auto mb-4"></div>
          <p className="text-gray-500">Loading video...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="aspect-video bg-gray-900 rounded-lg flex items-center justify-center">
        <div className="text-center p-8">
          <svg
            className="mx-auto h-12 w-12 text-red-400 mb-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <p className="text-red-400 mb-2">Failed to load video</p>
          <p className="text-gray-500 text-sm">{error}</p>
          <button
            onClick={loadVideo}
            className="mt-4 px-4 py-2 bg-gray-50 hover:bg-white/20 text-gray-900 rounded-lg transition-colors"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full">
      {/* Video element */}
      <div className="relative aspect-video bg-black rounded-lg overflow-hidden">
        <video
          ref={videoRef}
          src={streamUrl || undefined}
          className="w-full h-full"
          onClick={togglePlayPause}
        />
      </div>

      {/* Custom controls */}
      <div className="mt-4 space-y-3">
        {/* Progress bar */}
        <div className="flex items-center space-x-3">
          <span className="text-sm text-gray-500 min-w-[3rem]">
            {formatTime(currentTime)}
          </span>
          <input
            type="range"
            min={startTime}
            max={endTime !== undefined ? endTime : (duration || 0)}
            value={currentTime}
            onChange={handleSeek}
            className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer
                     [&::-webkit-slider-thumb]:appearance-none
                     [&::-webkit-slider-thumb]:w-4
                     [&::-webkit-slider-thumb]:h-4
                     [&::-webkit-slider-thumb]:rounded-full
                     [&::-webkit-slider-thumb]:bg-indigo-500
                     dark:[&::-webkit-slider-thumb]:bg-lime-500
                     [&::-webkit-slider-thumb]:cursor-pointer
                     [&::-moz-range-thumb]:w-4
                     [&::-moz-range-thumb]:h-4
                     [&::-moz-range-thumb]:rounded-full
                     [&::-moz-range-thumb]:bg-indigo-500
                     dark:[&::-moz-range-thumb]:bg-lime-500
                     [&::-moz-range-thumb]:border-0
                     [&::-moz-range-thumb]:cursor-pointer"
          />
          <span className="text-sm text-gray-500 min-w-[3rem]">
            {endTime !== undefined ? formatTime(endTime) : formatTime(duration)}
          </span>
        </div>

        {/* Control buttons */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            {/* Play/Pause button */}
            <button
              onClick={togglePlayPause}
              className="p-2 rounded-full bg-indigo-500 dark:bg-lime-500
                       hover:bg-indigo-600 dark:hover:bg-lime-600
                       focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-lime-400
                       transition-all duration-200"
            >
              {isPlaying ? (
                <svg className="h-6 w-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                </svg>
              ) : (
                <svg className="h-6 w-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
              )}
            </button>

            {/* Volume controls */}
            <div className="flex items-center space-x-2">
              <button
                onClick={toggleMute}
                className="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
              >
                {isMuted || volume === 0 ? (
                  <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" />
                  </svg>
                ) : (
                  <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z" />
                  </svg>
                )}
              </button>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={isMuted ? 0 : volume}
                onChange={handleVolumeChange}
                className="w-20 h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer
                         [&::-webkit-slider-thumb]:appearance-none
                         [&::-webkit-slider-thumb]:w-3
                         [&::-webkit-slider-thumb]:h-3
                         [&::-webkit-slider-thumb]:rounded-full
                         [&::-webkit-slider-thumb]:bg-indigo-500
                         dark:[&::-webkit-slider-thumb]:bg-lime-500
                         [&::-webkit-slider-thumb]:cursor-pointer
                         [&::-moz-range-thumb]:w-3
                         [&::-moz-range-thumb]:h-3
                         [&::-moz-range-thumb]:rounded-full
                         [&::-moz-range-thumb]:bg-indigo-500
                         dark:[&::-moz-range-thumb]:bg-lime-500
                         [&::-moz-range-thumb]:border-0
                         [&::-moz-range-thumb]:cursor-pointer"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
