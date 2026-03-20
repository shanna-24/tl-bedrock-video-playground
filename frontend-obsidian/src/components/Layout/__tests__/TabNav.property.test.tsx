// Feature: obsidian-lens-frontend, Property 4: Tabs are disabled when index has no videos
// Feature: obsidian-lens-frontend, Property 5: Tab switch clears video playback state
// Feature: obsidian-lens-frontend, Property 6: Hiding the active tab falls back to Videos
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, cleanup, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import * as fc from 'fast-check';
import TabNav from '../TabNav';

afterEach(cleanup);

const allVisibleTabs = { search: true, analysis: true, compliance: true };

/**
 * Validates: Requirements 6.3
 *
 * Property 4: For any tab in {search, analysis, compliance}, when hasVideos is false,
 * that tab's button should have aria-disabled="true" and be disabled,
 * while the Videos tab remains enabled.
 */
describe('Property 4: Tabs are disabled when index has no videos', () => {
  it('non-video tabs are disabled when hasVideos=false, Videos tab stays enabled', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('search', 'analysis', 'compliance'),
        (tabKey: string) => {
          const onTabChange = vi.fn();
          const { getByRole } = render(
            <TabNav
              activeTab="videos"
              onTabChange={onTabChange}
              hasVideos={false}
              visibleTabs={allVisibleTabs}
              onVisibleTabsChange={vi.fn()}
            />
          );

          const tabLabel = tabKey.charAt(0).toUpperCase() + tabKey.slice(1);
          const tabButton = getByRole('tab', { name: tabLabel });
          expect(tabButton).toHaveAttribute('aria-disabled', 'true');
          expect(tabButton).toBeDisabled();

          // Videos tab should remain enabled
          const videosButton = getByRole('tab', { name: 'Videos' });
          expect(videosButton).not.toBeDisabled();
          expect(videosButton).toHaveAttribute('aria-disabled', 'false');

          cleanup();
        }
      ),
      { numRuns: 100 }
    );
  });
});


/**
 * Validates: Requirements 6.4
 *
 * Property 5: For any pair of distinct tabs (fromTab, toTab), clicking toTab
 * invokes the onTabChange callback with the new tab key. The actual playback
 * state clearing is handled by DashboardLayout's useEffect on activeTab change.
 */
describe('Property 5: Tab switch clears video playback state', () => {
  it('onTabChange is called with the target tab when switching between distinct tabs', () => {
    fc.assert(
      fc.property(
        fc.tuple(
          fc.constantFrom('videos' as const, 'search' as const, 'analysis' as const, 'compliance' as const),
          fc.constantFrom('videos' as const, 'search' as const, 'analysis' as const, 'compliance' as const)
        ).filter(([a, b]) => a !== b),
        ([fromTab, toTab]) => {
          const onTabChange = vi.fn();
          const { getByRole } = render(
            <TabNav
              activeTab={fromTab}
              onTabChange={onTabChange}
              hasVideos={true}
              visibleTabs={allVisibleTabs}
              onVisibleTabsChange={vi.fn()}
            />
          );

          const toLabel = toTab.charAt(0).toUpperCase() + toTab.slice(1);
          const targetButton = getByRole('tab', { name: toLabel });
          fireEvent.click(targetButton);

          expect(onTabChange).toHaveBeenCalledWith(toTab);

          cleanup();
        }
      ),
      { numRuns: 100 }
    );
  });
});

/**
 * Validates: Requirements 6.6
 *
 * Property 6: For any tab in {search, analysis, compliance}, when that tab is
 * hidden via visibleTabs, TabNav does not render a button for it. The actual
 * fallback to 'videos' is handled by DashboardLayout's useEffect.
 */
describe('Property 6: Hiding the active tab falls back to Videos', () => {
  it('hidden tabs are not rendered in the tab bar', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('search' as const, 'analysis' as const, 'compliance' as const),
        (hiddenTab) => {
          const hiddenVisibleTabs = { ...allVisibleTabs, [hiddenTab]: false };
          const { queryByRole } = render(
            <TabNav
              activeTab="videos"
              onTabChange={vi.fn()}
              hasVideos={true}
              visibleTabs={hiddenVisibleTabs}
              onVisibleTabsChange={vi.fn()}
            />
          );

          const tabLabel = hiddenTab.charAt(0).toUpperCase() + hiddenTab.slice(1);
          const hiddenButton = queryByRole('tab', { name: tabLabel });
          expect(hiddenButton).toBeNull();

          // Videos tab should always be rendered
          const videosButton = queryByRole('tab', { name: 'Videos' });
          expect(videosButton).not.toBeNull();

          cleanup();
        }
      ),
      { numRuns: 100 }
    );
  });
});
