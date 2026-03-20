// Feature: obsidian-lens-frontend, Property 7: Video cards display required metadata
import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest';
import { render, cleanup, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import * as fc from 'fast-check';
import VideoGrid from '../VideoGrid';

vi.mock('../../../services/api', () => ({
  videoApi: {
    listVideos: vi.fn(),
    deleteVideo: vi.fn(),
  },
}));

import { videoApi } from '../../../services/api';

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
});

const videoArb = fc.record({
  id: fc.uuid(),
  index_id: fc.uuid(),
  filename: fc.string({ minLength: 1, maxLength: 30 }).filter(s => s.trim().length > 0),
  s3_uri: fc.constant('s3://bucket/key'),
  duration: fc.integer({ min: 1, max: 36000 }),
  uploaded_at: fc.date({ min: new Date('2020-01-01'), max: new Date('2030-01-01') }).map(d => d.toISOString()),
  embedding_ids: fc.constant([]),
  metadata: fc.constant({}),
});

const videosArb = fc.array(videoArb, { minLength: 1, maxLength: 5 });

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Validates: Requirements 7.3
 *
 * Property 7: For any video in the video list, the rendered VideoGrid card
 * should display the video's filename and formatted duration.
 */
describe('Property 7: Video cards display required metadata', () => {
  it('renders filename and duration for every video in any generated list', async () => {
    await fc.assert(
      fc.asyncProperty(videosArb, async (videos) => {
        vi.mocked(videoApi.listVideos).mockResolvedValue({ videos });

        const { container } = render(
          <VideoGrid indexId="test-index-id" />
        );

        // Wait for the videos to load (async fetch)
        await waitFor(() => {
          expect(container.textContent).toContain(videos[0].filename);
        });

        for (const video of videos) {
          // Assert filename appears in the rendered output
          expect(container.textContent).toContain(video.filename);

          // Assert formatted duration appears in the rendered output
          const expectedDuration = formatDuration(video.duration);
          expect(container.textContent).toContain(expectedDuration);
        }

        cleanup();
      }),
      { numRuns: 100 }
    );
  });
});
