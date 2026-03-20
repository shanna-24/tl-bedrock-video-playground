import React from 'react';

type ActiveTab = 'videos' | 'search' | 'analysis' | 'compliance';

interface VisibleTabs {
  search: boolean;
  analysis: boolean;
  compliance: boolean;
}

interface TabNavProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  hasVideos: boolean;
  visibleTabs: VisibleTabs;
}

const TAB_ITEMS: { key: ActiveTab; label: string; alwaysEnabled?: boolean }[] = [
  { key: 'videos', label: 'Videos', alwaysEnabled: true },
  { key: 'search', label: 'Search' },
  { key: 'analysis', label: 'Analysis' },
  { key: 'compliance', label: 'Compliance' },
];

function TabNav({ activeTab, onTabChange, hasVideos, visibleTabs }: TabNavProps) {

  const visibleItems = TAB_ITEMS.filter(
    (tab) => tab.key === 'videos' || visibleTabs[tab.key as keyof VisibleTabs]
  );

  return (
    <div className="border-b border-surface-container-highest flex items-center">
      <nav className="flex" role="tablist">
        {visibleItems.map((tab) => {
          const isActive = activeTab === tab.key;
          const isDisabled = !tab.alwaysEnabled && !hasVideos;

          return (
            <button
              key={tab.key}
              role="tab"
              type="button"
              aria-selected={isActive}
              aria-disabled={isDisabled}
              disabled={isDisabled}
              onClick={() => !isDisabled && onTabChange(tab.key)}
              className={`px-6 py-3 font-medium text-sm transition-colors relative ${
                isDisabled
                  ? 'opacity-40 cursor-not-allowed text-on-surface-variant'
                  : isActive
                    ? 'text-primary'
                    : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              {tab.label}
              {isActive && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
              )}
            </button>
          );
        })}
      </nav>

    </div>
  );
}

export default TabNav;
