/**
 * AnalysisForm Component
 * 
 * Form for submitting video analysis queries with scope selection.
 * Allows users to analyse entire indexes or individual videos.
 * 
 * Validates: Requirements 4.1, 4.2, 4.3
 */

import { useState, useEffect, type FormEvent } from 'react';
import type { Video } from '../../types';

interface AnalysisFormProps {
  indexId: string;
  videos: Video[];
  onAnalyze: (query: string, scope: 'index' | 'video', scopeId: string, verbosity: 'concise' | 'balanced' | 'extended', useJockey?: boolean) => void;
  isAnalyzing?: boolean;
  progressMessage?: string;
}

export default function AnalysisForm({ 
  indexId, 
  videos, 
  onAnalyze, 
  isAnalyzing = false,
  progressMessage 
}: AnalysisFormProps) {
  const [query, setQuery] = useState('');
  const [scope, setScope] = useState<'index' | 'video'>('index');
  const [selectedVideoId, setSelectedVideoId] = useState('');
  const [verbosity, setVerbosity] = useState<'concise' | 'balanced' | 'extended'>('balanced');
  const [useJockey, setUseJockey] = useState(false);
  const [shouldFlash, setShouldFlash] = useState(false);

  // Trigger pulse animation when progress message changes
  useEffect(() => {
    if (progressMessage && isAnalyzing) {
      setShouldFlash(true);
      const timer = setTimeout(() => setShouldFlash(false), 400);
      return () => clearTimeout(timer);
    }
  }, [progressMessage, isAnalyzing]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    
    if (!query.trim() || isAnalyzing) return;

    const scopeId = scope === 'index' ? indexId : selectedVideoId;
    if (!scopeId) return;

    onAnalyze(query.trim(), scope, scopeId, verbosity, scope === 'video' ? useJockey : undefined);
  };

  const handleScopeChange = (newScope: 'index' | 'video') => {
    setScope(newScope);
    if (newScope === 'video' && videos.length > 0 && !selectedVideoId) {
      setSelectedVideoId(videos[0].id);
    }
    // Reset useJockey when switching to index scope
    if (newScope === 'index') {
      setUseJockey(false);
    }
  };

  const canSubmit = query.trim() && !isAnalyzing && (scope === 'index' || selectedVideoId);

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Query input */}
      <div>
        <label htmlFor="analysis-query" className="block text-sm font-medium text-gray-600 dark:text-gray-300 dark:text-gray-300 mb-2">
          Analysis Query
        </label>
        <textarea
          id="analysis-query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a question about your video content (e.g., 'What are the main topics discussed?', 'Summarize the key points')"
          rows={4}
          disabled={isAnalyzing}
          className="w-full px-4 py-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg
                   text-gray-900 dark:text-gray-100 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 resize-none
                   focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-lime-500 focus:border-transparent
                   disabled:opacity-50 disabled:cursor-not-allowed
                   transition-all duration-200"
        />
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-300 dark:text-gray-300">
          Use natural language to ask questions or request analysis of your video content
        </p>
      </div>

      {/* Scope selector */}
      <div>
        <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 dark:text-gray-300 mb-3">
          Analysis Scope
        </label>
        <div className="space-y-3">
          {/* Index scope */}
          <label
            className={`
              frost-hover flex items-start p-4 rounded-lg border-2 cursor-pointer transition-all duration-200
              ${scope === 'index'
                ? 'border-indigo-500 dark:border-lime-500 bg-indigo-500/10 dark:bg-lime-500/20'
                : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700/50 hover:border-gray-300 dark:hover:border-gray-500'
              }
              ${isAnalyzing ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <input
              type="radio"
              name="scope"
              value="index"
              checked={scope === 'index'}
              onChange={() => handleScopeChange('index')}
              disabled={isAnalyzing}
              className="mt-1 h-4 w-4 text-indigo-500 dark:text-indigo-400 focus:ring-indigo-500 dark:focus:ring-indigo-400 focus:ring-offset-0"
            />
            <div className="ml-3 flex-1">
              <div className="flex items-center space-x-2">
                <svg
                  className="h-5 w-5 text-green-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                  />
                </svg>
                <span className="font-medium text-gray-900 dark:text-gray-100">Entire Index</span>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-300 mt-1">
                Analyse all videos in this index
              </p>
            </div>
          </label>

          {/* Video scope */}
          <label
            className={`
              frost-hover flex items-start p-4 rounded-lg border-2 cursor-pointer transition-all duration-200
              ${scope === 'video'
                ? 'border-indigo-500 dark:border-lime-500 bg-indigo-500/10 dark:bg-lime-500/20'
                : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700/50 hover:border-gray-300 dark:hover:border-gray-500'
              }
              ${isAnalyzing || videos.length === 0 ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <input
              type="radio"
              name="scope"
              value="video"
              checked={scope === 'video'}
              onChange={() => handleScopeChange('video')}
              disabled={isAnalyzing || videos.length === 0}
              className="mt-1 h-4 w-4 text-lime-500 focus:ring-indigo-500 focus:ring-offset-0"
            />
            <div className="ml-3 flex-1">
              <div className="flex items-center space-x-2">
                <svg
                  className="h-5 w-5 text-gray-600 dark:text-gray-300"
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
                <span className="font-medium text-gray-900 dark:text-gray-100">Single Video</span>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-300 mt-1">
                Analyse a specific video from this index
              </p>

              {/* Video selector */}
              {scope === 'video' && videos.length > 0 && (
                <select
                  value={selectedVideoId}
                  onChange={(e) => setSelectedVideoId(e.target.value)}
                  disabled={isAnalyzing}
                  className="mt-3 w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg
                           text-gray-900 dark:text-gray-100 text-sm
                           focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-lime-500 focus:border-transparent
                           disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={(e) => e.stopPropagation()}
                >
                  {videos.map((video) => (
                    <option key={video.id} value={video.id} className="bg-white dark:bg-gray-800">
                      {video.filename}
                    </option>
                  ))}
                </select>
              )}

              {videos.length === 0 && (
                <p className="text-xs text-gray-500 dark:text-gray-300 mt-2">
                  No videos available. Upload videos to use this option.
                </p>
              )}
            </div>
          </label>
        </div>
      </div>

      {/* Use Jockey option (only for Single Video) */}
      {scope === 'video' && videos.length > 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-3">
            Analysis Method
          </label>
          <label
            className={`
              flex items-start p-4 rounded-lg border-2 cursor-pointer transition-all duration-200
              ${useJockey
                ? 'border-indigo-500 dark:border-lime-500 bg-indigo-500/10 dark:bg-lime-500/20'
                : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700/50 hover:border-gray-300 dark:hover:border-gray-500 hover:bg-gray-50 dark:hover:bg-gray-700/70'
              }
              ${isAnalyzing ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <input
              type="checkbox"
              checked={useJockey}
              onChange={(e) => setUseJockey(e.target.checked)}
              disabled={isAnalyzing}
              className="mt-1 h-4 w-4 text-indigo-500 dark:text-indigo-400 focus:ring-indigo-500 dark:focus:ring-indigo-400 focus:ring-offset-0 rounded"
            />
            <div className="ml-3 flex-1">
              <div className="flex items-center space-x-2">
                <svg
                  className="h-5 w-5 text-purple-600 dark:text-purple-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                  />
                </svg>
                <span className="font-medium text-gray-900 dark:text-gray-100">Agent Framework</span>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-300 mt-1">
                Pegasus plus Claude for enhanced insights
              </p>
            </div>
          </label>
        </div>
      )}

      {/* Verbosity selector */}
      <div>
        <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-3">
          Response Verbosity
        </label>
        <div className="grid grid-cols-3 gap-3">
          {/* Concise option */}
          <label
            className={`
              frost-hover flex items-center justify-center p-4 rounded-lg border-2 cursor-pointer transition-all duration-200
              ${verbosity === 'concise'
                ? 'border-indigo-500 dark:border-lime-500 bg-indigo-500/10 dark:bg-lime-500/20'
                : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700/50 hover:border-gray-300 dark:hover:border-gray-500'
              }
              ${isAnalyzing ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <input
              type="radio"
              name="verbosity"
              value="concise"
              checked={verbosity === 'concise'}
              onChange={() => setVerbosity('concise')}
              disabled={isAnalyzing}
              className="sr-only"
            />
            <div className="text-center">
              <div className="flex items-center justify-center space-x-2 mb-1">
                <svg
                  className="h-5 w-5 text-indigo-500 dark:text-lime-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                  />
                </svg>
                <span className="font-semibold text-gray-900 dark:text-gray-100">Concise</span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-300">Brief, focused</p>
            </div>
          </label>

          {/* Balanced option */}
          <label
            className={`
              frost-hover flex items-center justify-center p-4 rounded-lg border-2 cursor-pointer transition-all duration-200
              ${verbosity === 'balanced'
                ? 'border-indigo-500 dark:border-lime-500 bg-indigo-500/10 dark:bg-lime-500/20'
                : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700/50 hover:border-gray-300 dark:hover:border-gray-500'
              }
              ${isAnalyzing ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <input
              type="radio"
              name="verbosity"
              value="balanced"
              checked={verbosity === 'balanced'}
              onChange={() => setVerbosity('balanced')}
              disabled={isAnalyzing}
              className="sr-only"
            />
            <div className="text-center">
              <div className="flex items-center justify-center space-x-2 mb-1">
                <svg
                  className="h-5 w-5 text-green-600 dark:text-green-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3"
                  />
                </svg>
                <span className="font-semibold text-gray-900 dark:text-gray-100">Balanced</span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-300">Well-rounded</p>
            </div>
          </label>

          {/* Extended option */}
          <label
            className={`
              frost-hover flex items-center justify-center p-4 rounded-lg border-2 cursor-pointer transition-all duration-200
              ${verbosity === 'extended'
                ? 'border-indigo-500 dark:border-lime-500 bg-indigo-500/10 dark:bg-lime-500/20'
                : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700/50 hover:border-gray-300 dark:hover:border-gray-500'
              }
              ${isAnalyzing ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <input
              type="radio"
              name="verbosity"
              value="extended"
              checked={verbosity === 'extended'}
              onChange={() => setVerbosity('extended')}
              disabled={isAnalyzing}
              className="sr-only"
            />
            <div className="text-center">
              <div className="flex items-center justify-center space-x-2 mb-1">
                <svg
                  className="h-5 w-5 text-purple-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <span className="font-semibold text-gray-900 dark:text-gray-100">Extended</span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-300">Comprehensive</p>
            </div>
          </label>
        </div>
      </div>

      {/* Submit button */}
      <div className="relative">
        <style>{`
          @keyframes button-pulse {
            0%, 100% {
              transform: scale(1);
            }
            50% {
              transform: scale(1.05);
            }
          }
          
          .pulse-animation {
            animation: button-pulse 0.4s ease-in-out;
          }
        `}</style>
        <button
          type="submit"
          disabled={!canSubmit}
          className={`w-full px-6 py-4 rounded-lg font-semibold text-white
                   bg-indigo-500 dark:bg-lime-500
                   hover:bg-indigo-600 dark:hover:bg-lime-600
                   focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-lime-400
                   disabled:opacity-50 disabled:cursor-not-allowed
                   transform transition-all duration-200
                   hover:scale-[1.02] active:scale-[0.98]
                   shadow-lg
                   ${shouldFlash ? 'pulse-animation' : ''}`}
        >
          {isAnalyzing ? (
            <span className="flex items-center justify-center space-x-2">
              <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
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
              {progressMessage && <span>{progressMessage}</span>}
            </span>
          ) : (
            'Analyse'
          )}
        </button>
      </div>
    </form>
  );
}
