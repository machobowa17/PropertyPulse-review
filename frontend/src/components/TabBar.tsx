import { useRef, useEffect, useState, useCallback } from 'react';
import { Home, Coffee, TreePine, Users, Landmark } from 'lucide-react';
import type { TabName } from '../types';
import { TABS } from '../utils/tabs';

const ICONS: Record<string, React.ElementType> = {
  Home, Coffee, TreePine, Users, Landmark,
};

interface Props {
  active: TabName;
  onChange: (tab: TabName) => void;
}

export default function TabBar({ active, onChange }: Props) {
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
        {/* Sliding pill background */}
        <div
          className="absolute top-2 h-[calc(100%-16px)] bg-brand-50 rounded-xl transition-all duration-300 ease-out"
          style={{ left: pillStyle.left, width: pillStyle.width }}
        />
        {TABS.map((tab) => {
          const Icon = ICONS[tab.icon] || Home;
          const isActive = active === tab.name;
          return (
            <button
              key={tab.name}
              role="tab"
              aria-selected={isActive}
              data-tab={tab.name}
              onClick={() => onChange(tab.name)}
              className={`
                relative z-10 flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium whitespace-nowrap
                transition-colors duration-200 cursor-pointer shrink-0
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
      </div>
    </div>
  );
}
