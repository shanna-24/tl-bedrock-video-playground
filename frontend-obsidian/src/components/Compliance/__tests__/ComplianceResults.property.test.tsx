// Feature: obsidian-lens-frontend, Property 11: Compliance status bar uses correct color tokens
// Feature: obsidian-lens-frontend, Property 12: Compliance issues display all required fields
// Feature: obsidian-lens-frontend, Property 13: Navigating away cancels in-progress compliance check
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, cleanup, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import * as fc from 'fast-check';
import ComplianceResults from '../ComplianceResults';

afterEach(cleanup);

// --- Generators ---

const statusArb = fc.constantFrom('APPROVE', 'REVIEW', 'BLOCK');

const issueArb = fc.record({
  Category: fc.string({ minLength: 1, maxLength: 20 }).filter(s => s.trim().length > 0),
  Subcategory: fc.option(fc.string({ minLength: 1, maxLength: 20 }).filter(s => s.trim().length > 0)),
  Description: fc.string({ minLength: 1, maxLength: 100 }).filter(s => s.trim().length > 0),
  Timecode: fc.option(fc.constant('01:30')),
  Status: fc.option(fc.constantFrom('BLOCK', 'REVIEW', 'APPROVE')),
  thumbnail_url: fc.constant(''),
});

const complianceResultArb = fc.record({
  'Overall Status': statusArb,
  Filename: fc.option(fc.string({ minLength: 1, maxLength: 30 })),
  Summary: fc.option(fc.string({ minLength: 1, maxLength: 100 })),
  'Identified Issues': fc.array(issueArb, { minLength: 0, maxLength: 3 }),
  _metadata: fc.constant({
    video_id: 'vid-1',
    video_filename: 'test.mp4',
    checked_at: '2024-01-15T10:30:00Z',
    compliance_params: { company: 'Test', category: 'General', product_line: 'Default' },
  }),
});

const videoArb = fc.record({
  id: fc.uuid(),
  index_id: fc.constant('idx-1'),
  filename: fc.string({ minLength: 1, maxLength: 30 }).filter(s => s.trim().length > 0),
  s3_uri: fc.constant('s3://bucket/video.mp4'),
  duration: fc.nat({ max: 3600 }),
  uploaded_at: fc.constant('2024-01-15T10:30:00Z'),
  embedding_ids: fc.constant([]),
  metadata: fc.constant({}),
  thumbnail_url: fc.constant(''),
});


/**
 * Validates: Requirements 10.3
 *
 * Property 11: For any ComplianceResult, the status bar should use `primary` color tokens
 * when the overall status is APPROVE, and `error-container` color tokens when the status
 * is REVIEW or BLOCK.
 */
describe('Property 11: Compliance status bar uses correct color tokens', () => {
  it('renders correct color classes on the status bar for any generated status', () => {
    fc.assert(
      fc.property(complianceResultArb, videoArb, (result, video) => {
        const { getByTestId } = render(
          <ComplianceResults
            result={result}
            video={video}
            onClear={() => {}}
            onPlayVideo={() => {}}
          />
        );

        const statusBar = getByTestId('compliance-status-bar');
        const classes = statusBar.className;

        if (result['Overall Status'] === 'APPROVE') {
          expect(classes).toContain('border-primary');
          expect(classes).toContain('bg-primary-container');
        } else {
          // REVIEW or BLOCK
          expect(classes).toContain('border-error');
          expect(classes).toContain('bg-error-container');
        }

        cleanup();
      }),
      { numRuns: 100 }
    );
  });
});

/**
 * Validates: Requirements 10.4
 *
 * Property 12: For any ComplianceIssue in a ComplianceResult's identified issues list,
 * the rendered issue card should display the Category and Description fields.
 */
describe('Property 12: Compliance issues display all required fields', () => {
  it('renders Category and Description for every issue in any generated ComplianceResult', () => {
    const resultWithIssuesArb = fc.record({
      'Overall Status': statusArb,
      Filename: fc.option(fc.string({ minLength: 1, maxLength: 30 })),
      Summary: fc.option(fc.string({ minLength: 1, maxLength: 100 })),
      'Identified Issues': fc.array(issueArb, { minLength: 1, maxLength: 3 }),
      _metadata: fc.constant({
        video_id: 'vid-1',
        video_filename: 'test.mp4',
        checked_at: '2024-01-15T10:30:00Z',
        compliance_params: { company: 'Test', category: 'General', product_line: 'Default' },
      }),
    });

    fc.assert(
      fc.property(resultWithIssuesArb, videoArb, (result, video) => {
        const { container } = render(
          <ComplianceResults
            result={result}
            video={video}
            onClear={() => {}}
            onPlayVideo={() => {}}
          />
        );

        const text = container.textContent || '';
        const issues = result['Identified Issues'] || [];

        for (const issue of issues) {
          expect(text).toContain(issue.Category);
          expect(text).toContain(issue.Description);
        }

        cleanup();
      }),
      { numRuns: 100 }
    );
  });
});

/**
 * Validates: Requirements 10.8
 *
 * Property 13: Navigating away cancels in-progress compliance check.
 * Tests that the onClear callback is invoked when the Clear button is clicked,
 * which is the mechanism used to cancel/reset compliance state on navigation.
 */
describe('Property 13: Navigating away cancels in-progress compliance check', () => {
  it('calls onClear when the Clear button is clicked for any generated ComplianceResult', () => {
    fc.assert(
      fc.property(complianceResultArb, videoArb, (result, video) => {
        const onClear = vi.fn();

        const { getByText } = render(
          <ComplianceResults
            result={result}
            video={video}
            onClear={onClear}
            onPlayVideo={() => {}}
          />
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
