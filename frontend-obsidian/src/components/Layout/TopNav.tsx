import { useState, useRef, useEffect } from 'react';

interface VisibleTabs {
  search: boolean;
  analysis: boolean;
  compliance: boolean;
}

interface TopNavProps {
  onLogout: () => void;
  onMenuToggle?: () => void;
  visibleTabs?: VisibleTabs;
  onVisibleTabsChange?: (tabs: VisibleTabs) => void;
  showSettings?: boolean;
}

function TopNav({ onLogout, onMenuToggle, visibleTabs, onVisibleTabsChange, showSettings = false }: TopNavProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
        setSettingsOpen(false);
      }
    }
    if (settingsOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [settingsOpen]);

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 h-16 bg-surface border-b border-surface-container-highest/50 shadow-[0_0_32px_0_rgba(222,229,255,0.08)] flex items-center justify-between px-4 lg:px-6"
    >
      <div className="flex items-center gap-2">
        {onMenuToggle && (
          <button
            type="button"
            onClick={onMenuToggle}
            className="lg:hidden p-2 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors"
            aria-label="Toggle sidebar"
          >
            <span className="material-symbols-outlined">menu</span>
          </button>
        )}
        <span className="text-on-surface font-semibold text-lg">TwelveLabs</span>
      </div>

      <div className="flex items-center gap-1">
        {showSettings && visibleTabs && onVisibleTabsChange && (
          <div className="relative" ref={settingsRef}>
            <button
              type="button"
              onClick={() => setSettingsOpen(prev => !prev)}
              className="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors"
              aria-label="Tab settings"
            >
              <span className="material-symbols-outlined">settings</span>
            </button>
            {settingsOpen && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-surface-container-high rounded-lg shadow-lg py-2 z-50">
                {(['search', 'analysis', 'compliance'] as const).map((key) => (
                  <label
                    key={key}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-on-surface-variant hover:text-on-surface hover:bg-surface-container-highest/50 cursor-pointer transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={visibleTabs[key]}
                      onChange={() =>
                        onVisibleTabsChange({ ...visibleTabs, [key]: !visibleTabs[key] })
                      }
                      className="accent-primary"
                    />
                    <span className="capitalize">{key}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}
        <button
          type="button"
          onClick={onLogout}
          className="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors"
          aria-label="Logout"
        >
          <span className="material-symbols-outlined">logout</span>
        </button>
      </div>
    </header>
  );
}

export default TopNav;
