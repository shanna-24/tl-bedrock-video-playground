/**
 * VideoPlayerPopup Component
 * 
 * A popup/modal wrapper for the VideoPlayer component.
 * Displays the video player centered on screen with a backdrop.
 * Dismisses when clicking outside or pressing backspace.
 */

import { useEffect, useCallback } from 'react';
import VideoPlayer from './VideoPlayer';

interface VideoPlayerPopupProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  // VideoPlayer props
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
  // Handle backspace key to close popup
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Backspace') {
      // Prevent backspace from navigating back in browser
      e.preventDefault();
      onClose();
    }
  }, [onClose]);

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      // Prevent body scroll when popup is open
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
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div 
        className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-4xl mx-4 max-h-[90vh] overflow-hidden border border-gray-200 dark:border-gray-700"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 truncate pr-4">
            {title}
          </h3>
          <button
            onClick={onClose}
            className="flex-shrink-0 p-2 text-gray-400 hover:text-gray-600 dark:text-gray-300 dark:hover:text-gray-100 transition-colors rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
            aria-label="Close video player"
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
        
        {/* Video Player Content */}
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
