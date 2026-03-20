/**
 * ComplianceResults Component
 *
 * Displays compliance check results with overall status, video info, summary, and issues list.
 * Uses Obsidian Lens design tokens: tonal nesting, Material Symbols icons, error/primary color coding.
 *
 * Validates: Requirements 10.3, 10.4, 10.5, 10.6, 10.7
 */

import { useState } from 'react';
import type { ComplianceResult, ComplianceIssue, Video } from '../../types';

interface ComplianceResultsProps {
  result: ComplianceResult;
  video: Video;
  onClear: () => void;
  onPlayVideo: (video: Video, startTime?: number) => void;
}

function ComplianceResults({ result, video, onClear, onPlayVideo }: ComplianceResultsProps) {
  const [showPrompt, setShowPrompt] = useState(false);

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusColor = (status?: string) => {
    switch (status?.toUpperCase()) {
      case 'APPROVE':
        return 'text-primary';
      case 'REVIEW':
        return 'text-tertiary';
      case 'BLOCK':
        return 'text-error';
      default:
        return 'text-on-surface-variant';
    }
  };

  const getStatusIcon = (status?: string): string => {
    switch (status?.toUpperCase()) {
      case 'APPROVE':
        return 'check_circle';
      case 'REVIEW':
        return 'warning';
      case 'BLOCK':
        return 'cancel';
      default:
        return 'help';
    }
  };

  const getBadgeClasses = (status?: string) => {
    switch (status?.toUpperCase()) {
      case 'BLOCK':
        return 'bg-error/20 text-error';
      case 'REVIEW':
        return 'bg-tertiary/20 text-tertiary';
      case 'APPROVE':
        return 'bg-primary/20 text-primary';
      default:
        return 'bg-on-surface-variant/20 text-on-surface-variant';
    }
  };

  const parseTimecode = (timecode?: string): number | undefined => {
    if (!timecode) return undefined;
    const match = timecode.match(/(\d+):(\d+)/);
    if (match) {
      return parseInt(match[1]) * 60 + parseInt(match[2]);
    }
    return undefined;
  };

  // Sort issues by Status: BLOCK > REVIEW > APPROVE
  const sortedIssues = [...(result['Identified Issues'] || [])].sort((a, b) => {
    const statusOrder: Record<string, number> = { 'BLOCK': 0, 'REVIEW': 1, 'APPROVE': 2 };
    const aOrder = statusOrder[a.Status?.toUpperCase() || ''] ?? 4;
    const bOrder = statusOrder[b.Status?.toUpperCase() || ''] ?? 4;
    return aOrder - bOrder;
  });

  const overallStatus = result['Overall Status']?.toUpperCase();
  const isPass = overallStatus === 'APPROVE';

  return (
    <div className="space-y-6">
      {/* Status Bar */}
      <div
        data-testid="compliance-status-bar"
        className={`rounded-xl p-4 border-l-2 ${
          isPass
            ? 'bg-primary-container/10 border-primary'
            : 'bg-error-container/10 border-error'
        }`}
      >
        <div className="flex items-center gap-3">
          <span
            className={`material-symbols-outlined text-3xl ${
              isPass ? 'text-primary' : 'text-error'
            }`}
          >
            {getStatusIcon(result['Overall Status'])}
          </span>
          <div>
            <p className={`font-semibold ${isPass ? 'text-primary' : 'text-error'}`}>
              {result['Overall Status'] || 'Unknown'}
            </p>
            {result._metadata && (
              <p className="text-on-surface-variant text-xs">
                Checked on {formatDate(result._metadata.checked_at)}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Header with Clear */}
      <div className="flex items-center justify-between">
        <h3 className="text-on-surface text-xl font-semibold">Compliance Check Results</h3>
        <button
          onClick={onClear}
          className="text-primary hover:text-primary/80 text-sm font-medium transition-colors"
        >
          Clear
        </button>
      </div>

      {/* Video Info Card */}
      <div className="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-6">
        <h4 className="text-on-surface-variant text-xs uppercase tracking-wider mb-4">
          Video Information
        </h4>
        <div className="flex items-start gap-4">
          {/* Large status icon */}
          <div className="flex flex-col items-center shrink-0">
            <span className={`material-symbols-outlined text-5xl ${getStatusColor(result['Overall Status'])}`}>
              {getStatusIcon(result['Overall Status'])}
            </span>
            <span className={`text-xs font-semibold mt-1 ${getStatusColor(result['Overall Status'])}`}>
              {result['Overall Status'] || 'Unknown'}
            </span>
          </div>
          <div className="space-y-2 text-left">
            <div className="flex">
              <span className="text-on-surface-variant text-sm w-20 shrink-0 text-right pr-2">Filename:</span>
              <span className="text-on-surface text-sm font-medium break-all">
                {result.Filename || video.filename}
              </span>
            </div>
            <div className="flex">
              <span className="text-on-surface-variant text-sm w-20 shrink-0 text-right pr-2">Title:</span>
              <span className="text-on-surface text-sm font-medium">
                {result.Title || 'N/A'}
              </span>
            </div>
            <div className="flex">
              <span className="text-on-surface-variant text-sm w-20 shrink-0 text-right pr-2">Length:</span>
              <span className="text-on-surface text-sm font-medium">
                {result.Length || 'N/A'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Summary Card */}
      <div className="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-6">
        <h4 className="text-on-surface-variant text-xs uppercase tracking-wider mb-4">
          Summary
        </h4>
        <p className="text-on-surface leading-relaxed text-left">
          {result.Summary || 'No summary available.'}
        </p>
      </div>

      {/* Identified Issues */}
      {sortedIssues.length > 0 && (
        <div className="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-6">
          <h4 className="text-on-surface-variant text-xs uppercase tracking-wider mb-4">
            Identified Issues ({sortedIssues.length})
          </h4>
          <div className="space-y-4">
            {sortedIssues.map((issue: ComplianceIssue, index: number) => (
              <div
                key={index}
                className="bg-surface-container-high/50 rounded-xl p-4 border border-outline-variant/10"
              >
                <div className="flex items-start gap-4">
                  {/* Issue Details */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2 flex-wrap">
                      {/* Timecode */}
                      <button
                        onClick={() => onPlayVideo(video, parseTimecode(issue.Timecode))}
                        className="flex items-center gap-1 text-sm text-on-surface font-medium hover:text-primary transition-colors"
                        title="Jump to timecode"
                      >
                        <span className="material-symbols-outlined text-base">schedule</span>
                        <span>{issue.Timecode || 'N/A'}</span>
                      </button>
                      {/* Status badge */}
                      {issue.Status && (
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${getBadgeClasses(issue.Status)}`}>
                          {issue.Status}
                        </span>
                      )}
                      {/* Category / Subcategory */}
                      <span className="text-on-surface-variant text-sm">
                        {issue.Category}
                        {issue.Subcategory && ` › ${issue.Subcategory}`}
                      </span>
                    </div>
                    {/* Description */}
                    <p className="text-on-surface-variant text-sm text-left">
                      {issue.Description}
                    </p>
                  </div>

                  {/* Thumbnail */}
                  <div
                    className="shrink-0 w-32 h-20 bg-surface-container-high rounded-lg overflow-hidden cursor-pointer relative group"
                    onClick={() => onPlayVideo(video, parseTimecode(issue.Timecode))}
                  >
                    {(issue.thumbnail_url || video.thumbnail_url) ? (
                      <img
                        src={issue.thumbnail_url || video.thumbnail_url}
                        alt="Issue thumbnail"
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <span className="material-symbols-outlined text-on-surface-variant text-2xl">
                          videocam
                        </span>
                      </div>
                    )}
                    {/* Play overlay on hover */}
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <span className="material-symbols-outlined text-on-surface text-3xl">
                        play_circle
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No Issues Message */}
      {sortedIssues.length === 0 && isPass && (
        <div className="bg-primary-container/10 border border-primary/30 rounded-xl p-6 text-center">
          <span className="material-symbols-outlined text-primary text-4xl mb-3 block">
            check_circle
          </span>
          <p className="text-primary font-medium">No compliance issues identified</p>
        </div>
      )}

      {/* Raw Response (fallback) */}
      {result.raw_response && (
        <div className="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-6">
          <h4 className="text-on-surface-variant text-xs uppercase tracking-wider mb-4">
            Raw Response
          </h4>
          <pre className="text-on-surface text-sm whitespace-pre-wrap overflow-x-auto">
            {result.raw_response}
          </pre>
        </div>
      )}

      {/* Show Prompt link */}
      {result._metadata?.prompt && (
        <div className="text-center pt-4">
          <button
            onClick={() => setShowPrompt(true)}
            className="text-xs text-on-surface-variant hover:text-on-surface transition-colors"
          >
            Show prompt
          </button>
        </div>
      )}

      {/* Prompt Popup (Glass_Panel) */}
      {showPrompt && result._metadata?.prompt && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-surface-container-high/80 backdrop-blur-[12px] rounded-2xl shadow-xl max-w-4xl w-full max-h-[60vh] flex flex-col border border-outline-variant/10">
            <div className="flex items-center justify-between p-4 border-b border-outline-variant/10">
              <h3 className="text-on-surface text-lg font-semibold">
                Compliance Check Prompt
              </h3>
              <button
                onClick={() => setShowPrompt(false)}
                className="p-2 text-on-surface-variant hover:text-on-surface transition-colors"
              >
                <span className="material-symbols-outlined text-xl">close</span>
              </button>
            </div>
            <div className="p-4 overflow-y-auto flex-1 custom-scrollbar">
              <pre className="text-on-surface text-sm whitespace-pre-wrap font-mono text-left">
                {result._metadata.prompt}
              </pre>
            </div>
            <div className="p-4 border-t border-outline-variant/10 flex justify-end">
              <button
                onClick={() => setShowPrompt(false)}
                className="px-4 py-2 bg-surface-container-highest hover:bg-surface-bright text-on-surface rounded-lg transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ComplianceResults;
