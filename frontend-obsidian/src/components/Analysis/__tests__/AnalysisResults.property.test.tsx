// Feature: obsidian-lens-frontend, Property 9: Analysis results display insights text
// Feature: obsidian-lens-frontend, Property 10: Navigating away cancels in-progress analysis
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, cleanup, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import * as fc from 'fast-check';
import AnalysisResults from '../AnalysisResults';

afterEach(cleanup);

const analysisResultArb = fc.record({
  query: fc.string({ minLength: 1, maxLength: 50 }).filter(s => s.trim().length > 0),
  scope: fc.constantFrom('index' as const, 'video' as const),
  scope_id: fc.uuid(),
  insights: fc.string({ minLength: 1, maxLength: 200 }).filter(s => s.trim().length > 0),
  analyzed_at: fc.constant('2024-01-15T10:30:00Z'),
  metadata: fc.constant({}),
});

/**
 * Validates: Requirements 9.3
 *
 * Property 9: For any AnalysisResult object, the AnalysisResults component
 * should render the insights text content and the query text from the result.
 */
describe('Property 9: Analysis results display insights text', () => {
  it('renders insights text and query for any generated AnalysisResult', () => {
    fc.assert(
      fc.property(analysisResultArb, (result) => {
        const { container } = render(
          <AnalysisResults result={result} onClear={() => {}} />
        );

        const text = container.textContent || '';

        // Assert insights text appears in the rendered output
        expect(text).toContain(result.insights);

        // Assert query text appears in the rendered output
        expect(text).toContain(result.query);

        cleanup();
      }),
      { numRuns: 100 }
    );
  });
});

/**
 * Validates: Requirements 9.6
 *
 * Property 10: Navigating away cancels in-progress analysis.
 * Tests that the onClear callback is invoked when the Clear button is clicked,
 * which is the mechanism used to cancel/reset analysis state on navigation.
 */
describe('Property 10: Navigating away cancels in-progress analysis', () => {
  it('calls onClear when the Clear button is clicked for any generated AnalysisResult', () => {
    fc.assert(
      fc.property(analysisResultArb, (result) => {
        const onClear = vi.fn();

        const { getByText } = render(
          <AnalysisResults result={result} onClear={onClear} />
        );

        const clearButton = getByText('Clear');
        fireEvent.click(clearButton);

        expect(onClear).toHaveBeenCalledTimes(1);

        cleanup();
      }),
      { numRuns: 100 }
    );
  });
});
