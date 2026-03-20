import { useEffect, useRef, useState } from 'react';
import { videoApi } from '../../services/api';

interface VideoPlayerProps {
  videoId?: string;
  videoUrl?: string;
  startTime?: number;
  endTime?: number;
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
      if (endTime !== undefined && video.currentTime >= endTime) {
        video.pause();
        video.currentTime = startTime;
        setIsPlaying(false);
      }
    };

    const handleDurationChange = () => setDuration(video.duration);
    const handleLoadedMetadata = () => {
      setDuration(video.duration);
      if (startTime > 0) video.currentTime = startTime;
      if (autoPlay) video.play().catch(err => console.error('Autoplay failed:', err));
    };
    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleEnded = () => setIsPlaying(false);
    const handleSeeking = () => {
      if (endTime !== undefined) {
        if (video.currentTime < startTime) video.currentTime = startTime;
        else if (video.currentTime > endTime) video.currentTime = endTime;
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
    } catch (err: any) {
      setError(err.detail || err.message || 'Failed to load video');
    } finally {
      setIsLoading(false);
    }
  };

  const togglePlayPause = () => {
    if (!videoRef.current) return;
    if (isPlaying) videoRef.current.pause();
    else videoRef.current.play();
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    let time = parseFloat(e.target.value);
    if (endTime !== undefined) time = Math.max(startTime, Math.min(time, endTime));
    else time = Math.max(startTime, time);
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const vol = parseFloat(e.target.value);
    setVolume(vol);
    if (videoRef.current) videoRef.current.volume = vol;
    if (vol > 0 && isMuted) setIsMuted(false);
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
    if (hours > 0) return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  if (isLoading) {
    return (
      <div className="aspect-video bg-surface-container-low rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-on-surface-variant">Loading video...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="aspect-video bg-surface-container-low rounded-lg flex items-center justify-center">
        <div className="text-center p-8">
          <span className="material-symbols-outlined text-error text-5xl mb-4 block">error</span>
          <p className="text-error mb-2">Failed to load video</p>
          <p className="text-on-surface-variant text-sm">{error}</p>
          <button onClick={loadVideo} className="mt-4 px-4 py-2 bg-surface-container-high hover:bg-surface-container-highest text-on-surface rounded-lg transition-colors">
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full">
      <div className="relative aspect-video bg-black rounded-lg overflow-hidden">
        <video ref={videoRef} src={streamUrl || undefined} className="w-full h-full" onClick={togglePlayPause} />
      </div>
      <div className="mt-4 space-y-3">
        <div className="flex items-center space-x-3">
          <span className="text-sm text-on-surface-variant min-w-[3rem]">{formatTime(currentTime)}</span>
          <input type="range" min={startTime} max={endTime !== undefined ? endTime : (duration || 0)} value={currentTime} onChange={handleSeek}
            className="flex-1 h-2 bg-surface-container-highest rounded-lg appearance-none cursor-pointer
              [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
              [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:cursor-pointer
              [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:rounded-full
              [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer" />
          <span className="text-sm text-on-surface-variant min-w-[3rem]">{endTime !== undefined ? formatTime(endTime) : formatTime(duration)}</span>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button onClick={togglePlayPause} className="p-2 rounded-full bg-primary hover:bg-primary-dim focus:outline-none focus:ring-2 focus:ring-primary transition-all duration-200">
              <span className="material-symbols-outlined text-on-primary">{isPlaying ? 'pause' : 'play_arrow'}</span>
            </button>
            <div className="flex items-center space-x-2">
              <button onClick={toggleMute} className="p-2 text-on-surface-variant hover:text-on-surface transition-colors">
                <span className="material-symbols-outlined">{isMuted || volume === 0 ? 'volume_off' : 'volume_up'}</span>
              </button>
              <input type="range" min="0" max="1" step="0.1" value={isMuted ? 0 : volume} onChange={handleVolumeChange}
                className="w-20 h-2 bg-surface-container-highest rounded-lg appearance-none cursor-pointer
                  [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3
                  [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:cursor-pointer
                  [&::-moz-range-thumb]:w-3 [&::-moz-range-thumb]:h-3 [&::-moz-range-thumb]:rounded-full
                  [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
