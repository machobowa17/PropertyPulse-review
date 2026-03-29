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
  const [pillStyle, setPillStyle] = useState({ left: 0, width: 0 });

  useEffect(() => {
    const el = ref.current?.querySelector(`[data-tab="${active}"]`) as HTMLElement | null;
    if (el) {
      setPillStyle({ left: el.offsetLeft, width: el.offsetWidth });
    }
  }, [active]);

  return (
    <div className="relative" ref={ref}>
      <div className="flex overflow-x-auto gap-1 py-2 scrollbar-none -mx-1 px-1 relative">
        {/* Sliding pill background */}
        <div
          className="absolute top-2 h-[calc(100%-16px)] bg-brand-50 rounded-xl transition-all duration-300 ease-out"
          style={{ left: pillStyle.left, width: pillStyle.width }}
        />
        {TABS.map((tab) => {
          const Icon = ICONS[tab.icon] || TrendingUp;
          const isActive = active === tab.name;
          return (
            <button
              key={tab.name}
              data-tab={tab.name}
              onClick={() => onChange(tab.name)}
              className={`
                relative z-10 flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium whitespace-nowrap
                transition-colors duration-200 cursor-pointer shrink-0
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
