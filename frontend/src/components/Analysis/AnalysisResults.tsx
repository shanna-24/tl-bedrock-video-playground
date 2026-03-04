/**
 * AnalysisResults Component
 * 
 * Displays video analysis insights in a readable format.
 * Shows the query, scope, and AI-generated insights.
 * 
 * Validates: Requirements 4.4
 */

import type { AnalysisResult } from '../../types';

interface AnalysisResultsProps {
  result: AnalysisResult;
  onClear?: () => void;
}

export default function AnalysisResults({ result, onClear }: AnalysisResultsProps) {
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

  const getScopeIcon = (scope: string) => {
    if (scope === 'index') {
      return (
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
      );
    }
    return (
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
    );
  };

  const handleClear = () => {
    if (onClear) {
      onClear();
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-2">
            <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Analysis Results</h3>
            <div className="flex items-center space-x-1 px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded-lg">
              {getScopeIcon(result.scope)}
              <span className="text-xs text-gray-600 dark:text-gray-300 capitalize">{result.scope}</span>
            </div>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Analysed on {formatDate(result.analyzed_at)}
          </p>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={handleClear}
            className="px-4 py-2 text-sm text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100
                     bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 rounded-lg
                     border border-gray-200 dark:border-gray-600
                     transition-all duration-200"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Query */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg p-4">
        <div className="flex items-start space-x-3">
          <svg
            className="h-5 w-5 text-gray-500 dark:text-gray-400 mt-0.5 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div className="flex-1 text-left">
            <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Query</p>
            <p className="text-gray-900 dark:text-gray-100">{result.query}</p>
          </div>
        </div>
      </div>

      {/* Insights */}
      <div className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg p-6">
        <div className="flex items-start space-x-3 mb-4">
          <svg
            className="h-6 w-6 text-lime-500 dark:text-lime-400 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
            />
          </svg>
          <div className="flex-1">
            <h4 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Insights</h4>
            <div className="prose prose-invert max-w-none">
              <div className="text-gray-700 dark:text-gray-200 whitespace-pre-wrap leading-relaxed text-left">
                {result.insights}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Metadata */}
      {result.metadata && Object.keys(result.metadata).length > 0 && (
        <details className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg p-4">
          <summary className="cursor-pointer text-sm text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 transition-colors text-left">
            Additional Metadata
          </summary>
          <div className="mt-3 space-y-2">
            {Object.entries(result.metadata).map(([key, value]) => (
              <div key={key} className="flex items-start space-x-2 text-sm text-left">
                <span className="text-gray-500 dark:text-gray-400 min-w-[120px]">{key}:</span>
                <span className="text-gray-700 dark:text-gray-200 flex-1 break-all">{JSON.stringify(value)}</span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
