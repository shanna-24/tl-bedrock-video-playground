/**
 * ComplianceResults Component
 * 
 * Displays compliance check results in a readable format with separate panels.
 */

import { useState } from 'react';
import type { ComplianceResult, ComplianceIssue, Video } from '../../types';

interface ComplianceResultsProps {
  result: ComplianceResult;
  video: Video;
  onClear: () => void;
  onPlayVideo: (video: Video, startTime?: number) => void;
}

export default function ComplianceResults({
  result,
  video,
  onClear,
  onPlayVideo
}: ComplianceResultsProps) {
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
        return 'bg-green-500/20 text-green-400 border-green-500/50';
      case 'REVIEW':
        return 'bg-orange-500/20 text-orange-400 border-orange-500/50';
      case 'BLOCK':
        return 'bg-red-500/20 text-red-400 border-red-500/50';
      default:
        return 'bg-gray-500/20 text-gray-400 border-gray-500/50';
    }
  };



  const getStatusIcon = (status?: string) => {
    switch (status?.toUpperCase()) {
      case 'APPROVE':
        return (
          <svg className="w-16 h-16 text-green-500" fill="currentColor" viewBox="0 0 24 24">
            <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
          </svg>
        );
      case 'REVIEW':
        return (
          <svg className="w-16 h-16 text-orange-500" fill="currentColor" viewBox="0 0 24 24">
            <path fillRule="evenodd" d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd" />
          </svg>
        );
      case 'BLOCK':
        return (
          <svg className="w-16 h-16 text-red-500" fill="currentColor" viewBox="0 0 24 24">
            <path fillRule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zm-1.72 6.97a.75.75 0 10-1.06 1.06L10.94 12l-1.72 1.72a.75.75 0 101.06 1.06L12 13.06l1.72 1.72a.75.75 0 101.06-1.06L13.06 12l1.72-1.72a.75.75 0 10-1.06-1.06L12 10.94l-1.72-1.72z" clipRule="evenodd" />
          </svg>
        );
      default:
        return (
          <svg className="w-16 h-16 text-gray-500" fill="currentColor" viewBox="0 0 24 24">
            <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm11.378-3.917c-.89-.777-2.366-.777-3.255 0a.75.75 0 01-.988-1.129c1.454-1.272 3.776-1.272 5.23 0 1.513 1.324 1.513 3.518 0 4.842a3.75 3.75 0 01-.837.552c-.676.328-1.028.774-1.028 1.152v.75a.75.75 0 01-1.5 0v-.75c0-1.279 1.06-2.107 1.875-2.502.182-.088.351-.199.503-.331.83-.727.83-1.857 0-2.584zM12 18a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd" />
          </svg>
        );
    }
  };

  const parseTimecode = (timecode?: string): number | undefined => {
    if (!timecode) return undefined;
    // Parse timecode like "00:15" or "00:15 - 00:20" to get start time in seconds
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

  const getStatusIconSmall = (status?: string) => {
    const colorClass = (() => {
      switch (status?.toUpperCase()) {
        case 'APPROVE': return 'text-green-500';
        case 'REVIEW': return 'text-orange-500';
        case 'BLOCK': return 'text-red-500';
        default: return 'text-gray-500';
      }
    })();
    
    switch (status?.toUpperCase()) {
      case 'APPROVE':
        return (
          <svg className={`w-6 h-6 ${colorClass}`} fill="currentColor" viewBox="0 0 24 24">
            <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
          </svg>
        );
      case 'REVIEW':
        return (
          <svg className={`w-6 h-6 ${colorClass}`} fill="currentColor" viewBox="0 0 24 24">
            <path fillRule="evenodd" d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd" />
          </svg>
        );
      case 'BLOCK':
        return (
          <svg className={`w-6 h-6 ${colorClass}`} fill="currentColor" viewBox="0 0 24 24">
            <path fillRule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zm-1.72 6.97a.75.75 0 10-1.06 1.06L10.94 12l-1.72 1.72a.75.75 0 101.06 1.06L12 13.06l1.72 1.72a.75.75 0 101.06-1.06L13.06 12l1.72-1.72a.75.75 0 10-1.06-1.06L12 10.94l-1.72-1.72z" clipRule="evenodd" />
          </svg>
        );
      default:
        return (
          <svg className={`w-6 h-6 ${colorClass}`} fill="currentColor" viewBox="0 0 24 24">
            <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm11.378-3.917c-.89-.777-2.366-.777-3.255 0a.75.75 0 01-.988-1.129c1.454-1.272 3.776-1.272 5.23 0 1.513 1.324 1.513 3.518 0 4.842a3.75 3.75 0 01-.837.552c-.676.328-1.028.774-1.028 1.152v.75a.75.75 0 01-1.5 0v-.75c0-1.279 1.06-2.107 1.875-2.502.182-.088.351-.199.503-.331.83-.727.83-1.857 0-2.584zM12 18a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd" />
          </svg>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-2">
            <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Compliance Check Results</h3>
            {getStatusIconSmall(result['Overall Status'])}
          </div>
          {result._metadata && (
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center">
              Checked on {formatDate(result._metadata.checked_at)}
            </p>
          )}
        </div>
        <button
          onClick={onClear}
          className="px-4 py-2 text-sm text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100
                   bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 rounded-lg
                   border border-gray-200 dark:border-gray-600
                   transition-all duration-200"
        >
          Clear
        </button>
      </div>

      {/* Video Info Panel */}
      <div className="bg-white dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600 p-6">
        <h4 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-4">
          Video Information
        </h4>
        <div className="flex items-start">
          {/* Status Icon on left */}
          <div className="flex flex-col items-center mr-6">
            {getStatusIcon(result['Overall Status'])}
            <span className={`text-sm font-bold mt-1 ${getStatusColor(result['Overall Status']).split(' ')[1]}`}>
              {result['Overall Status'] || 'Unknown'}
            </span>
          </div>
          <div className="space-y-2">
            <div className="flex">
              <span className="text-sm text-gray-500 dark:text-gray-400 w-20 flex-shrink-0 text-right pr-2">Filename:</span>
              <span className="text-sm text-gray-900 dark:text-gray-100 font-medium text-left break-all">
                {result.Filename || video.filename}
              </span>
            </div>
            <div className="flex">
              <span className="text-sm text-gray-500 dark:text-gray-400 w-20 flex-shrink-0 text-right pr-2">Title:</span>
              <span className="text-sm text-gray-900 dark:text-gray-100 font-medium text-left">
                {result.Title || 'N/A'}
              </span>
            </div>
            <div className="flex">
              <span className="text-sm text-gray-500 dark:text-gray-400 w-20 flex-shrink-0 text-right pr-2">Length:</span>
              <span className="text-sm text-gray-900 dark:text-gray-100 font-medium text-left">
                {result.Length || 'N/A'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Summary Panel */}
      <div className="bg-white dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600 p-6">
        <h4 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-4">
          Summary
        </h4>
        <p className="text-gray-700 dark:text-gray-200 leading-relaxed text-left">
          {result.Summary || 'No summary available.'}
        </p>
      </div>

      {/* Identified Issues Panel */}
      {sortedIssues.length > 0 && (
        <div className="bg-white dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600 p-6">
          <h4 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-4">
            Identified Issues ({sortedIssues.length})
          </h4>
          <div className="space-y-4">
            {sortedIssues.map((issue: ComplianceIssue, index: number) => (
              <div
                key={index}
                className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border border-gray-200 dark:border-gray-600"
              >
                <div className="flex items-start gap-4">
                  {/* Issue Details */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      {/* Timecode - matching SearchResults style */}
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
                          {issue.Timecode || 'N/A'}
                        </span>
                      </div>
                      {/* Status */}
                      {issue.Status && (
                        <span className={`text-sm font-semibold ${
                          issue.Status.toUpperCase() === 'BLOCK' ? 'text-red-500' :
                          issue.Status.toUpperCase() === 'REVIEW' ? 'text-orange-500' :
                          'text-gray-500'
                        }`}>
                          {issue.Status}
                        </span>
                      )}
                      {/* Category */}
                      <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        {issue.Category}
                        {issue.Subcategory && ` › ${issue.Subcategory}`}
                      </span>
                    </div>
                    {/* Description */}
                    <p className="text-gray-600 dark:text-gray-300 text-sm text-left">
                      {issue.Description}
                    </p>
                  </div>

                  {/* Thumbnail on right - use issue thumbnail if available, fallback to video thumbnail */}
                  <div 
                    className="flex-shrink-0 w-32 h-20 bg-gray-200 dark:bg-gray-700 rounded-lg overflow-hidden cursor-pointer relative group"
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
                        <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                      </div>
                    )}

                    {/* Play overlay - matching SearchResults style */}
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <svg
                        className="h-12 w-12 text-gray-200"
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
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No Issues Message */}
      {sortedIssues.length === 0 && result['Overall Status']?.toUpperCase() === 'APPROVE' && (
        <div className="bg-green-500/10 border border-green-500/50 rounded-lg p-6 text-center">
          <svg className="w-12 h-12 text-green-400 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-green-400 font-medium">No compliance issues identified</p>
        </div>
      )}

      {/* Raw Response (if parsing failed) */}
      {result.raw_response && (
        <div className="bg-white dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600 p-6">
          <h4 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-4">
            Raw Response
          </h4>
          <pre className="text-sm text-gray-700 dark:text-gray-200 whitespace-pre-wrap overflow-x-auto">
            {result.raw_response}
          </pre>
        </div>
      )}

      {/* Footer with Show Prompt option */}
      {result._metadata?.prompt && (
        <div className="text-center pt-4">
          <button
            onClick={() => setShowPrompt(true)}
            className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            Show prompt
          </button>
        </div>
      )}

      {/* Prompt Popup */}
      {showPrompt && result._metadata?.prompt && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[60vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Compliance Check Prompt
              </h3>
              <button
                onClick={() => setShowPrompt(false)}
                className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-4 overflow-y-auto flex-1">
              <pre className="text-sm text-gray-700 dark:text-gray-200 whitespace-pre-wrap font-mono text-left">
                {result._metadata.prompt}
              </pre>
            </div>
            <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
              <button
                onClick={() => setShowPrompt(false)}
                className="px-4 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-900 dark:text-gray-100 rounded-lg transition-colors"
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
