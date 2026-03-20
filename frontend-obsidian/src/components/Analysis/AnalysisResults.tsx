/**
 * AnalysisResults Component
 *
 * Displays video analysis insights in a bento-grid layout with Obsidian Lens styling.
 * Left column: Query card + Metadata card. Right column: Glass_Panel insights.
 *
 * Validates: Requirements 9.3, 9.4, 9.5
 */

import type { AnalysisResult } from '../../types';

interface AnalysisResultsProps {
  result: AnalysisResult;
  onClear: () => void;
}

function AnalysisResults({ result, onClear }: AnalysisResultsProps) {
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

  const getScopeIcon = (scope: string): string => {
    return scope === 'index' ? 'inventory_2' : 'movie';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-on-surface text-xl font-semibold">Analysis Results</h3>
          <div className="bg-surface-container-highest rounded-lg px-2 py-1 flex items-center gap-1">
            <span className="material-symbols-outlined text-primary text-base">
              {getScopeIcon(result.scope)}
            </span>
            <span className="text-on-surface-variant text-xs capitalize">{result.scope}</span>
          </div>
        </div>
        <button
          onClick={onClear}
          className="text-primary hover:text-primary/80 text-sm font-medium transition-colors"
        >
          Clear
        </button>
      </div>

      {/* Bento Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left Column (4/12): Query + Metadata */}
        <div className="col-span-4 space-y-6">
          {/* Query Card */}
          <div className="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-5">
            <div className="flex items-start gap-3">
              <span className="material-symbols-outlined text-on-surface-variant text-xl mt-0.5 shrink-0">
                help_outline
              </span>
              <div className="flex-1 text-left">
                <p className="text-on-surface-variant text-xs uppercase tracking-wide mb-1">Query</p>
                <p className="text-on-surface">{result.query}</p>
              </div>
            </div>
            <p className="text-on-surface-variant text-sm mt-3">
              Analysed on {formatDate(result.analyzed_at)}
            </p>
          </div>

          {/* Metadata Card */}
          {result.metadata && Object.keys(result.metadata).length > 0 && (
            <details className="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-5">
              <summary className="cursor-pointer text-on-surface-variant text-sm hover:text-on-surface transition-colors text-left">
                Metadata Overview
              </summary>
              <div className="mt-3 space-y-2">
                {Object.entries(result.metadata).map(([key, value]) => (
                  <div key={key} className="flex items-start gap-2 text-sm text-left">
                    <span className="text-on-surface-variant min-w-[100px]">{key}:</span>
                    <span className="text-on-surface flex-1 break-all">
                      {typeof value === 'string' ? value : JSON.stringify(value)}
                    </span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>

        {/* Right Column (8/12): Glass_Panel Insights */}
        <div className="col-span-8">
          <div className="relative bg-surface-container-high/80 backdrop-blur-[12px] rounded-2xl border border-outline-variant/10 p-6 overflow-hidden">
            {/* Decorative blur circle */}
            <div className="absolute -top-20 -right-20 w-40 h-40 bg-primary/5 rounded-full blur-3xl pointer-events-none" />

            <div className="relative flex items-start gap-3 mb-4">
              <span className="material-symbols-outlined text-primary text-2xl shrink-0">
                lightbulb
              </span>
              <h4 className="text-on-surface text-lg font-semibold">Insights</h4>
            </div>

            <div className="relative bg-surface/40 rounded-xl p-4">
              <div className="text-on-surface whitespace-pre-wrap leading-relaxed text-left">
                {result.insights}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AnalysisResults;
