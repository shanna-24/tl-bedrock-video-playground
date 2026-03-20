/**
 * AnalysisForm Component
 *
 * Form for submitting video analysis queries with scope selection,
 * verbosity control, and optional Jockey agent framework toggle.
 *
 * Validates: Requirements 9.1, 9.2
 */

import { useState, useEffect, type FormEvent } from 'react';
import type { Video } from '../../types';

interface AnalysisFormProps {
  indexId: string;
  videos: Video[];
  onAnalyze: (query: string, scope: 'index' | 'video', scopeId: string, verbosity: 'concise' | 'balanced' | 'extended', useJockey?: boolean) => void;
  isAnalyzing: boolean;
  progressMessage: string;
}

function AnalysisForm({
  indexId,
  videos,
  onAnalyze,
  isAnalyzing,
  progressMessage,
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

  // Default video selection when videos change
  useEffect(() => {
    if (videos.length > 0 && !selectedVideoId) {
      setSelectedVideoId(videos[0].id);
    }
  }, [videos, selectedVideoId]);

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
    if (newScope === 'index') {
      setUseJockey(false);
    }
  };

  const canSubmit = query.trim() && !isAnalyzing && (scope === 'index' || selectedVideoId);

  const verbosityOptions: { value: 'concise' | 'balanced' | 'extended'; label: string; icon: string; desc: string }[] = [
    { value: 'concise', label: 'Concise', icon: 'bolt', desc: 'Brief, focused' },
    { value: 'balanced', label: 'Balanced', icon: 'balance', desc: 'Well-rounded' },
    { value: 'extended', label: 'Extended', icon: 'description', desc: 'Comprehensive' },
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Query textarea */}
      <div>
        <label htmlFor="analysis-query" className="block text-sm font-medium text-on-surface-variant mb-2">
          Analysis Query
        </label>
        <textarea
          id="analysis-query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a question about your video content (e.g., 'What are the main topics discussed?', 'Summarize the key points')"
          rows={4}
          disabled={isAnalyzing}
          className="w-full px-4 py-3 bg-surface-container-low rounded-xl ghost-border text-on-surface placeholder-on-surface-variant/50
                     resize-none focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-transparent
                     disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
        />
        <p className="mt-2 text-xs text-on-surface-variant/60">
          Use natural language to ask questions or request analysis of your video content
        </p>
      </div>

      {/* Scope selector - radio cards */}
      <div>
        <label className="block text-sm font-medium text-on-surface-variant mb-3">
          Analysis Scope
        </label>
        <div className="space-y-3">
          {/* Index scope card */}
          <label
            className={`flex items-start p-4 rounded-xl cursor-pointer transition-all duration-200
              ${scope === 'index'
                ? 'border border-primary/30 bg-primary-container/10'
                : 'bg-surface-container-low border border-outline-variant/10 hover:border-outline-variant/30'
              }
              ${isAnalyzing ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <input
              type="radio"
              name="scope"
              value="index"
              checked={scope === 'index'}
              onChange={() => handleScopeChange('index')}
              disabled={isAnalyzing}
              className="sr-only"
            />
            <div className="flex items-center gap-3 flex-1">
              <span className={`material-symbols-outlined text-xl ${scope === 'index' ? 'text-primary' : 'text-on-surface-variant'}`}>
                inventory_2
              </span>
              <div className="flex-1">
                <span className={`font-medium ${scope === 'index' ? 'text-on-surface' : 'text-on-surface-variant'}`}>
                  Entire Index
                </span>
                <p className="text-xs text-on-surface-variant/60 mt-0.5">
                  Analyse all videos in this index
                </p>
              </div>
              {scope === 'index' && (
                <span className="material-symbols-outlined text-primary text-lg">check_circle</span>
              )}
            </div>
          </label>

          {/* Video scope card */}
          <label
            className={`flex items-start p-4 rounded-xl cursor-pointer transition-all duration-200
              ${scope === 'video'
                ? 'border border-primary/30 bg-primary-container/10'
                : 'bg-surface-container-low border border-outline-variant/10 hover:border-outline-variant/30'
              }
              ${isAnalyzing || videos.length === 0 ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <input
              type="radio"
              name="scope"
              value="video"
              checked={scope === 'video'}
              onChange={() => handleScopeChange('video')}
              disabled={isAnalyzing || videos.length === 0}
              className="sr-only"
            />
            <div className="flex items-center gap-3 flex-1">
              <span className={`material-symbols-outlined text-xl ${scope === 'video' ? 'text-primary' : 'text-on-surface-variant'}`}>
                movie
              </span>
              <div className="flex-1">
                <span className={`font-medium ${scope === 'video' ? 'text-on-surface' : 'text-on-surface-variant'}`}>
                  Single Video
                </span>
                <p className="text-xs text-on-surface-variant/60 mt-0.5">
                  Analyse a specific video from this index
                </p>
                {videos.length === 0 && (
                  <p className="text-xs text-on-surface-variant/40 mt-1">
                    No videos available. Upload videos to use this option.
                  </p>
                )}
              </div>
              {scope === 'video' && (
                <span className="material-symbols-outlined text-primary text-lg">check_circle</span>
              )}
            </div>
          </label>

          {/* Video selector dropdown */}
          {scope === 'video' && videos.length > 0 && (
            <select
              value={selectedVideoId}
              onChange={(e) => setSelectedVideoId(e.target.value)}
              disabled={isAnalyzing}
              className="w-full px-3 py-2.5 bg-surface-container-high rounded-lg ghost-border text-on-surface text-sm
                         focus:outline-none focus:ring-2 focus:ring-primary/40
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {videos.map((video) => (
                <option key={video.id} value={video.id} className="bg-surface-container-high">
                  {video.filename}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Use Jockey option (only for Single Video scope) */}
      {scope === 'video' && videos.length > 0 && (
        <div>
          <label className="block text-sm font-medium text-on-surface-variant mb-3">
            Analysis Method
          </label>
          <label
            className={`flex items-center gap-3 p-4 rounded-xl cursor-pointer transition-all duration-200
              ${useJockey
                ? 'border border-primary/30 bg-primary-container/10'
                : 'bg-surface-container-low border border-outline-variant/10 hover:border-outline-variant/30'
              }
              ${isAnalyzing ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <input
              type="checkbox"
              checked={useJockey}
              onChange={(e) => setUseJockey(e.target.checked)}
              disabled={isAnalyzing}
              className="sr-only"
            />
            <span className={`material-symbols-outlined text-xl ${useJockey ? 'text-primary' : 'text-on-surface-variant'}`}>
              flash_on
            </span>
            <div className="flex-1">
              <span className={`font-medium ${useJockey ? 'text-on-surface' : 'text-on-surface-variant'}`}>
                Agent Framework
              </span>
              <p className="text-xs text-on-surface-variant/60 mt-0.5">
                Pegasus plus Claude for enhanced insights
              </p>
            </div>
            {useJockey && (
              <span className="material-symbols-outlined text-primary text-lg">check_circle</span>
            )}
          </label>
        </div>
      )}

      {/* Verbosity segmented control */}
      <div>
        <label className="block text-sm font-medium text-on-surface-variant mb-3">
          Response Verbosity
        </label>
        <div className="bg-surface-container-highest rounded-xl p-1">
          <div className="grid grid-cols-3 gap-1">
            {verbosityOptions.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => !isAnalyzing && setVerbosity(opt.value)}
                disabled={isAnalyzing}
                className={`flex flex-col items-center gap-1 py-3 px-2 rounded-lg transition-all duration-200
                  ${verbosity === opt.value
                    ? 'bg-primary-container text-on-primary-container shadow-sm'
                    : 'text-on-surface-variant hover:text-on-surface'
                  }
                  disabled:cursor-not-allowed`}
              >
                <span className="material-symbols-outlined text-lg">{opt.icon}</span>
                <span className="text-sm font-medium">{opt.label}</span>
                <span className={`text-xs ${verbosity === opt.value ? 'text-on-primary-container/70' : 'text-on-surface-variant/60'}`}>
                  {opt.desc}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Submit button + progress */}
      <div className="relative">
        <button
          type="submit"
          disabled={!canSubmit}
          className={`w-full px-6 py-4 rounded-xl font-semibold
                     bg-gradient-to-r from-primary to-primary-container text-on-primary
                     hover:shadow-lg hover:shadow-primary/20
                     focus:outline-none focus:ring-2 focus:ring-primary/40
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transform transition-all duration-200
                     hover:scale-[1.01] active:scale-[0.99]
                     ${shouldFlash ? 'animate-pulse' : ''}`}
        >
          {isAnalyzing ? (
            <span className="flex items-center justify-center gap-3">
              <span className="material-symbols-outlined animate-spin text-xl">progress_activity</span>
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

export default AnalysisForm;
