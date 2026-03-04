/**
 * ComplianceForm Component
 * 
 * Form for submitting video compliance checks.
 * Allows users to select a video and run compliance checking against configured rules.
 */

import { useState, useEffect, type FormEvent } from 'react';
import type { Video, ComplianceParams } from '../../types';

interface ComplianceFormProps {
  indexId: string;
  videos: Video[];
  onCheck: (videoId: string) => void;
  isChecking?: boolean;
  progressMessage?: string;
  complianceParams?: ComplianceParams | null;
}

export default function ComplianceForm({ 
  indexId: _indexId, 
  videos, 
  onCheck, 
  isChecking = false,
  progressMessage: _progressMessage = '',
  complianceParams = null
}: ComplianceFormProps) {
  const [selectedVideoId, setSelectedVideoId] = useState(videos.length > 0 ? videos[0].id : '');

  // Update selected video when videos list changes
  useEffect(() => {
    if (videos.length > 0 && !videos.find(v => v.id === selectedVideoId)) {
      setSelectedVideoId(videos[0].id);
    }
  }, [videos, selectedVideoId]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (isChecking || !selectedVideoId) return;
    onCheck(selectedVideoId);
  };

  const canSubmit = !isChecking && selectedVideoId;

  // Generate guidance text from categories
  const getGuidanceText = () => {
    if (!complianceParams?.categories || complianceParams.categories.length === 0) {
      return 'Check video content.';
    }
    const categories = complianceParams.categories
      .map(cat => cat.toLowerCase().replace(' compliance', ''));
    
    if (categories.length === 1) {
      return `Check for ${categories[0]}.`;
    }
    
    const lastCategory = categories.pop();
    const categoryList = categories.join(', ') + ', and ' + lastCategory;
    return `Check for ${categoryList}.`;
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Compliance Info */}
      {complianceParams && (
        <div className="bg-indigo-500/10 dark:bg-lime-500/10 border border-indigo-500/30 dark:border-lime-500/30 rounded-lg p-4">
          <h4 className="text-sm font-semibold text-indigo-600 dark:text-lime-400 mb-2">
            Compliance Configuration
          </h4>
          <p className="text-sm text-gray-700 dark:text-gray-300 mb-2">
            <span className="font-medium">{complianceParams.product_line}</span> product line 
            from <span className="font-medium">{complianceParams.company}</span> ({complianceParams.category}).
          </p>
          <p className="text-sm text-gray-700 dark:text-gray-300">
            {getGuidanceText()}
          </p>
        </div>
      )}

      {/* Video selector */}
      <div>
        <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-3">
          Select a video from this index
        </label>
        {videos.length > 0 ? (
          <select
            value={selectedVideoId}
            onChange={(e) => setSelectedVideoId(e.target.value)}
            disabled={isChecking}
            className="w-full px-4 py-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg
                     text-gray-900 dark:text-gray-100
                     focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-lime-500 focus:border-transparent
                     disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {videos.map((video) => (
              <option key={video.id} value={video.id} className="bg-white dark:bg-gray-800">
                {video.filename}
              </option>
            ))}
          </select>
        ) : (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            No videos available. Upload videos to use compliance checking.
          </p>
        )}
      </div>

      {/* Submit button */}
      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full px-6 py-4 rounded-lg font-semibold text-white
                 bg-indigo-500 dark:bg-lime-500
                 hover:bg-indigo-600 dark:hover:bg-lime-600
                 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-lime-400
                 disabled:opacity-50 disabled:cursor-not-allowed
                 transform transition-all duration-200
                 hover:scale-[1.02] active:scale-[0.98]
                 shadow-lg"
      >
        {isChecking ? (
          <span className="flex items-center justify-center space-x-2">
            <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <span>Checking Compliance...</span>
          </span>
        ) : (
          'Check Compliance'
        )}
      </button>
    </form>
  );
}
