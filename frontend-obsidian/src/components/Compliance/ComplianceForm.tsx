/**
 * ComplianceForm Component
 *
 * Form for submitting video compliance checks.
 * Allows users to select a video and run compliance checking against configured rules.
 * Styled with the Obsidian Lens design system.
 */

import { useState, useEffect, type FormEvent } from 'react';
import type { Video, ComplianceParams } from '../../types';

interface ComplianceFormProps {
  indexId: string;
  videos: Video[];
  onCheck: (videoId: string) => void;
  isChecking: boolean;
  progressMessage: string;
  complianceParams: ComplianceParams | null;
}

export default function ComplianceForm({
  indexId: _indexId,
  videos,
  onCheck,
  isChecking,
  progressMessage,
  complianceParams,
}: ComplianceFormProps) {
  const [selectedVideoId, setSelectedVideoId] = useState(
    videos.length > 0 ? videos[0].id : ''
  );

  // Update selected video when videos list changes
  useEffect(() => {
    if (videos.length > 0 && !videos.find((v) => v.id === selectedVideoId)) {
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
    if (
      !complianceParams?.categories ||
      complianceParams.categories.length === 0
    ) {
      return 'Check video content.';
    }
    const categories = complianceParams.categories.map((cat) =>
      cat.toLowerCase().replace(' compliance', '')
    );

    if (categories.length === 1) {
      return `Check for ${categories[0]}.`;
    }

    const lastCategory = categories.pop();
    const categoryList = categories.join(', ') + ', and ' + lastCategory;
    return `Check for ${categoryList}.`;
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Compliance Configuration Info Card */}
      {complianceParams && (
        <div className="bg-primary-container/10 border border-primary/30 rounded-xl p-4">
          <h4 className="text-primary text-sm font-semibold mb-2">
            Compliance Configuration
          </h4>
          <p className="text-on-surface-variant text-sm mb-2">
            <span className="font-medium">{complianceParams.product_line}</span>{' '}
            product line from{' '}
            <span className="font-medium">{complianceParams.company}</span> (
            {complianceParams.category}).
          </p>
          <p className="text-on-surface-variant text-sm">{getGuidanceText()}</p>
        </div>
      )}

      {/* Video selector */}
      <div>
        <label className="block text-on-surface-variant text-sm font-medium mb-3">
          Select a video from this index
        </label>
        {videos.length > 0 ? (
          <select
            value={selectedVideoId}
            onChange={(e) => setSelectedVideoId(e.target.value)}
            disabled={isChecking}
            className="w-full px-4 py-3 bg-surface-container-low rounded-xl ghost-border text-on-surface
                       focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-transparent
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {videos.map((video) => (
              <option
                key={video.id}
                value={video.id}
                className="bg-surface-container-low"
              >
                {video.filename}
              </option>
            ))}
          </select>
        ) : (
          <p className="text-on-surface-variant/60 text-sm">
            No videos available. Upload videos to use compliance checking.
          </p>
        )}
      </div>

      {/* Submit button */}
      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full px-6 py-4 rounded-xl font-semibold
                   bg-gradient-to-r from-primary to-primary-container text-on-primary
                   hover:brightness-110
                   focus:outline-none focus:ring-2 focus:ring-primary/50
                   disabled:opacity-50 disabled:cursor-not-allowed
                   transform transition-all duration-200
                   hover:scale-[1.02] active:scale-[0.98]"
      >
        {isChecking ? (
          <span className="flex items-center justify-center gap-2">
            <span className="material-symbols-outlined animate-spin text-xl">
              progress_activity
            </span>
            <span>
              {progressMessage ? progressMessage : 'Checking Compliance...'}
            </span>
          </span>
        ) : (
          'Check Compliance'
        )}
      </button>
    </form>
  );
}
