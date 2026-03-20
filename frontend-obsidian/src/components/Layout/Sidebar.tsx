interface SidebarProps {
  children: React.ReactNode;
  isOpen?: boolean;
  onClose?: () => void;
}

function Sidebar({ children, isOpen = false, onClose }: SidebarProps) {
  return (
    <>
      {/* Mobile overlay backdrop - visible below lg when sidebar is open */}
      {isOpen && (
        <div
          className="lg:hidden fixed inset-0 z-30 bg-black/50 backdrop-blur-sm"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar panel */}
      <aside
        className={`
          fixed z-40 bg-surface-container-low flex flex-col transition-transform duration-200 ease-in-out
          
          /* Mobile: slide-in from left, full height below topnav */
          top-16 left-0 w-64 h-[calc(100vh-64px)]
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
          
          /* Desktop: always visible, no transform */
          lg:translate-x-0
        `}
      >
        {/* Header */}
        <div className="px-4 pt-5 pb-3 flex items-center justify-between">
          <div>
            <h2 className="text-on-surface font-semibold text-sm">Indexes</h2>
            <p className="text-on-surface-variant text-xs mt-0.5">Active Collections</p>
          </div>
          {/* Close button on mobile */}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="lg:hidden p-2 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high transition-colors"
              aria-label="Close sidebar"
            >
              <span className="material-symbols-outlined text-[20px]">close</span>
            </button>
          )}
        </div>

        {/* Scrollable index list area */}
        <div className="flex-1 overflow-y-auto custom-scrollbar px-2">
          {children}
        </div>


      </aside>
    </>
  );
}

export default Sidebar;
