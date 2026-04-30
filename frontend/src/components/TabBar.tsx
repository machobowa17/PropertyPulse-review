import { useRef, useEffect, useState, useCallback } from 'react';
import { Home, Coffee, TreePine, Users, Landmark, LayoutDashboard, MapPin, X } from 'lucide-react';
import type { TabName } from '../types';
import { TABS } from '../utils/tabs';

const ICONS: Record<string, React.ElementType> = {
  LayoutDashboard, Home, Coffee, TreePine, Users, Landmark, MapPin,
};

interface Props {
  active: TabName;
  onChange: (tab: TabName) => void;
  /** When true, show a "Property" pseudo-tab at the end */
  showPropertyTab?: boolean;
  /** Whether the Property tab is currently active */
  propertyActive?: boolean;
  /** Callback when Property tab is clicked */
  onPropertyClick?: () => void;
  /** Callback to dismiss the Property tab */
  onPropertyDismiss?: () => void;
}

export default function TabBar({ active, onChange, showPropertyTab, propertyActive, onPropertyClick, onPropertyDismiss }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [pillStyle, setPillStyle] = useState({ left: 0, width: 0 });
  const [canScrollRight, setCanScrollRight] = useState(false);
  const [canScrollLeft, setCanScrollLeft] = useState(false);

  const checkScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  useEffect(() => {
    const update = () => {
      const el = ref.current?.querySelector(`[data-tab="${active}"]`) as HTMLElement | null;
      if (el) {
        setPillStyle({ left: el.offsetLeft, width: el.offsetWidth });
      }
      checkScroll();
    };
    update();
    window.addEventListener('resize', update);
    const scrollEl = scrollRef.current;
    scrollEl?.addEventListener('scroll', checkScroll, { passive: true });
    return () => {
      window.removeEventListener('resize', update);
      scrollEl?.removeEventListener('scroll', checkScroll);
    };
  }, [active, checkScroll]);

  return (
    <div className="relative" ref={ref}>
      {/* Scroll fade indicators (mobile) */}
      {canScrollLeft && (
        <div className="absolute left-0 top-0 bottom-0 w-6 bg-gradient-to-r from-white to-transparent z-20 pointer-events-none lg:hidden" />
      )}
      {canScrollRight && (
        <div className="absolute right-0 top-0 bottom-0 w-6 bg-gradient-to-l from-white to-transparent z-20 pointer-events-none lg:hidden" />
      )}
      <div ref={scrollRef} role="tablist" aria-label="Data tabs" className="flex overflow-x-auto gap-1 py-2 scrollbar-none -mx-1 px-1 relative">
        {/* Sliding pill background — hidden when Property pseudo-tab is active */}
        <div
          className="absolute top-2 h-[calc(100%-16px)] bg-brand-50 rounded-xl transition-all duration-300 ease-out"
          style={{
            left: pillStyle.left,
            width: propertyActive ? 0 : pillStyle.width,
            opacity: propertyActive ? 0 : 1,
          }}
        />
        {TABS.map((tab) => {
          const Icon = ICONS[tab.icon] || Home;
          const isActive = active === tab.name && !propertyActive;
          return (
            <button
              key={tab.name}
              role="tab"
              aria-selected={isActive}
              data-tab={tab.name}
              onClick={() => onChange(tab.name)}
              className={`
                relative z-10 flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium whitespace-nowrap
                transition-colors duration-200 active:scale-95 cursor-pointer shrink-0
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
                ${isActive
                  ? 'text-brand-700'
                  : 'text-ink-muted hover:text-ink'
                }
              `}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-brand-600' : ''}`} />
              <span className="hidden sm:inline">{tab.name}</span>
              <span className="sm:hidden">{tab.shortName}</span>
            </button>
          );
        })}
        {/* Dynamic Property tab — appears when a property is selected */}
        {showPropertyTab && (
          <button
            role="tab"
            aria-selected={propertyActive}
            data-tab="Property"
            onClick={onPropertyClick}
            className={`
              relative z-10 flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-medium whitespace-nowrap
              transition-colors duration-200 active:scale-95 cursor-pointer shrink-0
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
              ${propertyActive
                ? 'text-blue-700 bg-blue-50'
                : 'text-ink-muted hover:text-ink'
              }
            `}
          >
            <MapPin className={`w-4 h-4 ${propertyActive ? 'text-blue-600' : ''}`} />
            <span>Property</span>
            {onPropertyDismiss && (
              <span
                role="button"
                aria-label="Close property view"
                onClick={(e) => { e.stopPropagation(); onPropertyDismiss(); }}
                className="ml-1 p-0.5 rounded hover:bg-blue-100 transition"
              >
                <X className="w-3 h-3" />
              </span>
            )}
          </button>
        )}
      </div>
    </div>
  );
}
