// Feature: obsidian-lens-frontend, Property 3: Index list renders all available indexes
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import * as fc from 'fast-check';
import IndexList from '../IndexList';

afterEach(cleanup);

const indexArb = fc.record({
  id: fc.uuid(),
  name: fc.string({ minLength: 1, maxLength: 20 }).filter(s => s.trim().length > 0),
  created_at: fc.date({ min: new Date('2020-01-01'), max: new Date('2030-01-01') }).map(d => d.toISOString()),
  video_count: fc.nat({ max: 100 }),
  s3_vectors_collection_id: fc.uuid(),
  metadata: fc.constant({}),
});

const indexesArb = fc.array(indexArb, { minLength: 1, maxLength: 10 });

/**
 * Validates: Requirements 5.1
 *
 * Property 3: For any list of indexes, the IndexList component should render
 * exactly one item per index, and each item should display the index name
 * and video count.
 */
describe('Property 3: Index list renders all available indexes', () => {
  it('renders each index name and video count for any generated list of indexes', () => {
    fc.assert(
      fc.property(indexesArb, (indexes) => {
        const { container } = render(
          <IndexList indexes={indexes} onIndexSelect={vi.fn()} />
        );

        for (const index of indexes) {
          // Assert the index name appears in the rendered output
          const nameElements = container.querySelectorAll('.text-sm.font-medium.truncate');
          const nameTexts = Array.from(nameElements).map(el => el.textContent);
          expect(nameTexts).toContain(index.name);

          // Assert the video count appears in the rendered output
          const expectedCountText = `${index.video_count} ${index.video_count === 1 ? 'video' : 'videos'}`;
          expect(container.textContent).toContain(expectedCountText);
        }

        // Assert the correct number of index items rendered
        const indexItems = container.querySelectorAll('.text-sm.font-medium.truncate');
        expect(indexItems.length).toBe(indexes.length);

        cleanup();
      }),
      { numRuns: 100 }
    );
  });
});
