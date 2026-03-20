// Feature: obsidian-lens-frontend, Property 8: Search result clips display required information
import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import * as fc from 'fast-check';
import SearchResults from '../SearchResults';

vi.mock('../../../contexts/WebSocketContext', () => ({
  useThumbnailUpdates: vi.fn(),
}));

vi.mock('../../../services/api', () => ({
  videoReelApi: {
    generateReel: vi.fn(),
  },
}));

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
});

const videoClipArb = fc.record({
  video_id: fc.uuid(),
  start_timecode: fc.integer({ min: 0, max: 3600 }),
  end_timecode: fc.integer({ min: 1, max: 7200 }),
  relevance_score: fc.float({ min: Math.fround(0.01), max: Math.fround(1.0) }),
  screenshot_url: fc.constant(''),
  video_stream_url: fc.constant(''),
  metadata: fc.constant({}),
}).filter(c => c.end_timecode > c.start_timecode);

const clipsArb = fc.array(videoClipArb, { minLength: 1, maxLength: 5 });

function formatTimecode(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function formatRelevanceScore(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/**
 * Validates: Requirements 8.4, 8.5
 *
 * Property 8: For any clip in the search results, the rendered clip card
 * should display a relevance percentage and timecodes (start and end).
 */
describe('Property 8: Search result clips display required information', () => {
  it('renders relevance percentage and timecodes for every clip in any generated list', () => {
    fc.assert(
      fc.property(clipsArb, (clips) => {
        const { container } = render(
          <SearchResults
            results={clips}
            query="test query"
            searchTime={0.5}
            onClipSelect={() => {}}
            selectedClip={null}
            onReelGenerated={() => {}}
          />
        );

        const text = container.textContent || '';

        for (const clip of clips) {
          // Assert relevance percentage appears
          const expectedRelevance = formatRelevanceScore(clip.relevance_score);
          expect(text).toContain(expectedRelevance);

          // Assert start timecode appears
          const expectedStart = formatTimecode(clip.start_timecode);
          expect(text).toContain(expectedStart);

          // Assert end timecode appears
          const expectedEnd = formatTimecode(clip.end_timecode);
          expect(text).toContain(expectedEnd);
        }

        cleanup();
      }),
      { numRuns: 100 }
    );
  });
});
