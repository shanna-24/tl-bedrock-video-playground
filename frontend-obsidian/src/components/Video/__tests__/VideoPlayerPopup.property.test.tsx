// Feature: obsidian-lens-frontend, Property 14: Video player popup supports all playback modes
import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import * as fc from 'fast-check';
import VideoPlayerPopup from '../VideoPlayerPopup';

afterEach(cleanup);

// Arbitrary for playback mode: video by ID
const videoIdArb = fc.record({
  type: fc.constant('videoId' as const),
  videoId: fc.uuid(),
  title: fc.string({ minLength: 1, maxLength: 30 }).filter(s => s.trim().length > 0),
});

// Arbitrary for playback mode: direct URL
const urlArb = fc.record({
  type: fc.constant('url' as const),
  videoUrl: fc.webUrl(),
  title: fc.string({ minLength: 1, maxLength: 30 }).filter(s => s.trim().length > 0),
});

// Arbitrary for playback mode: clip with start/end timecodes
const clipArb = fc.record({
  type: fc.constant('clip' as const),
  videoId: fc.uuid(),
  startTime: fc.integer({ min: 0, max: 3600 }),
  endTime: fc.integer({ min: 1, max: 7200 }),
  title: fc.string({ minLength: 1, maxLength: 30 }).filter(s => s.trim().length > 0),
}).filter(c => c.endTime > c.startTime);

const playbackModeArb = fc.oneof(videoIdArb, urlArb, clipArb);

/**
 * Validates: Requirements 11.3
 *
 * Property 14: For any of the three playback trigger types — (a) a Video object
 * with an ID, (b) a direct video URL string, (c) a VideoClip with start and end
 * timecodes — the VideoPlayerPopup should render content configured for the
 * correct playback mode.
 */
describe('Property 14: Video player popup supports all playback modes', () => {
  it('renders correct video source for any generated playback mode', () => {
    fc.assert(
      fc.property(playbackModeArb, (mode) => {
        const props = {
          isOpen: true,
          onClose: () => {},
          title: mode.title,
          ...(mode.type === 'videoId' ? { videoId: mode.videoId } : {}),
          ...(mode.type === 'url' ? { videoUrl: mode.videoUrl } : {}),
          ...(mode.type === 'clip'
            ? { videoId: mode.videoId, startTime: mode.startTime, endTime: mode.endTime }
            : {}),
        };

        const { container } = render(<VideoPlayerPopup {...props} />);
        const content = container.textContent || '';

        if (mode.type === 'videoId') {
          expect(content).toContain(mode.videoId);
        } else if (mode.type === 'url') {
          expect(content).toContain(mode.videoUrl);
        } else if (mode.type === 'clip') {
          expect(content).toContain(mode.videoId);
          expect(content).toContain(String(mode.startTime));
          expect(content).toContain(String(mode.endTime));
        }

        // Title should always be rendered
        expect(content).toContain(mode.title);

        cleanup();
      }),
      { numRuns: 100 }
    );
  });
});
