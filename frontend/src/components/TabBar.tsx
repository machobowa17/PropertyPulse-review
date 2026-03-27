import { useRef, useEffect, useState } from 'react';
import { TrendingUp, Coffee, Leaf, Users, Landmark } from 'lucide-react';
import type { TabName } from '../types';
import { TABS } from '../utils/tabs';

const ICONS: Record<string, React.ElementType> = {
  TrendingUp, Coffee, Leaf, Users, Landmark,
};

interface Props {
  active: TabName;
  onChange: (tab: TabName) => void;
}

export default function TabBar({ active, onChange }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 0 });

  useEffect(() => {
    const el = ref.current?.querySelector(`[data-tab="${active}"]`) as HTMLElement | null;
    if (el) {
      setIndicatorStyle({ left: el.offsetLeft, width: el.offsetWidth });
    }
  }, [active]);

  return (
    <div className="relative" ref={ref}>
      <div className="flex overflow-x-auto gap-1 py-2 scrollbar-none -mx-1 px-1">
        {TABS.map((tab) => {
          const Icon = ICONS[tab.icon] || TrendingUp;
          const isActive = active === tab.name;
          return (
            <button
              key={tab.name}
              data-tab={tab.name}
              onClick={() => onChange(tab.name)}
              className={`
                flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium whitespace-nowrap
                transition-all duration-200 cursor-pointer shrink-0
                ${isActive
                  ? 'text-brand-700 bg-brand-50'
                  : 'text-ink-muted hover:text-ink hover:bg-surface'
                }
              `}
            >
              <Icon className="w-4 h-4" />
              <span className="hidden sm:inline">{tab.name}</span>
              <span className="sm:hidden">{tab.shortName}</span>
            </button>
          );
        })}
      </div>
      {/* Active indicator line */}
      <div
        className="absolute bottom-0 h-0.5 bg-brand-600 rounded-full transition-all duration-300"
        style={{ left: indicatorStyle.left, width: indicatorStyle.width }}
      />
    </div>
  );
}
