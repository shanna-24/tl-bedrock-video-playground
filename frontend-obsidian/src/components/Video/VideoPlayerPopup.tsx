import { useEffect, useCallback } from 'react';
import VideoPlayer from './VideoPlayer';

interface VideoPlayerPopupProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  videoId?: string;
  videoUrl?: string;
  startTime?: number;
  endTime?: number;
  autoPlay?: boolean;
}

export default function VideoPlayerPopup({
  isOpen,
  onClose,
  title,
  videoId,
  videoUrl,
  startTime,
  endTime,
  autoPlay = true
}: VideoPlayerPopupProps) {
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Backspace') {
      e.preventDefault();
      onClose();
    }
  }, [onClose]);

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 glass-panel flex items-center justify-center"
      onClick={onClose}
    >
      <div
        className="bg-surface-container-high rounded-xl shadow-2xl w-full max-w-4xl mx-4 max-h-[90vh] overflow-hidden border border-outline-variant/20"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant/20">
          <h3 className="text-lg font-semibold text-on-surface truncate pr-4">{title}</h3>
          <button
            onClick={onClose}
            className="flex-shrink-0 p-2 text-on-surface-variant hover:text-on-surface transition-colors rounded-lg hover:bg-surface-container-highest"
            aria-label="Close video player"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>
        <div className="p-6">
          <VideoPlayer
            videoId={videoId}
            videoUrl={videoUrl}
            startTime={startTime}
            endTime={endTime}
            autoPlay={autoPlay}
          />
        </div>
      </div>
    </div>
  );
}
