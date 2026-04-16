import { useEffect, useRef, useState } from 'react';
import { Home, KeyRound, LineChart, ChevronDown } from 'lucide-react';

export type DecisionMode = 'buy' | 'rent' | 'invest';

export const DECISION_MODES: Array<{
  id: DecisionMode;
  label: string;
  shortLabel: string;
  description: string;
  icon: typeof Home;
}> = [
  {
    id: 'buy',
    label: 'Buying',
    shortLabel: 'Buy',
    description: 'Home fit, affordability, and long-term confidence',
    icon: Home,
  },
  {
    id: 'rent',
    label: 'Renting',
    shortLabel: 'Rent',
    description: 'Practicality, transport, and monthly reality',
    icon: KeyRound,
  },
  {
    id: 'invest',
    label: 'Investing',
    shortLabel: 'Invest',
    description: 'Yield, demand, and downside discipline',
    icon: LineChart,
  },
];

interface Props {
  current: DecisionMode;
  onChange: (mode: DecisionMode) => void;
  variant?: 'segmented' | 'dropdown';
  className?: string;
}

export default function DecisionModeSelector({ current, onChange, variant = 'segmented', className = '' }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const currentMode = DECISION_MODES.find((mode) => mode.id === current) ?? DECISION_MODES[0];

  useEffect(() => {
    if (variant !== 'dropdown') return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [variant]);

  if (variant === 'dropdown') {
    const CurrentIcon = currentMode.icon;
    return (
      <div ref={ref} className={`relative ${className}`}>
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface hover:bg-brand-50 transition-all text-sm cursor-pointer"
          title="Select your decision mode"
        >
          <CurrentIcon className="w-4 h-4 text-brand-600" />
          <span className="font-medium text-ink hidden md:inline">{currentMode.label}</span>
          <ChevronDown className={`w-3.5 h-3.5 text-ink-faint transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>

        {open && (
          <div className="absolute right-0 top-full mt-2 w-72 bg-white rounded-2xl shadow-2xl overflow-hidden z-50 ring-1 ring-black/5 animate-dropdown-appear">

              <div className="p-2 border-b border-divider">
                <p className="text-xs text-ink-muted font-medium px-2 py-1">I am deciding where to...</p>
              </div>
              <div className="p-1">
                {DECISION_MODES.map((mode) => {
                  const Icon = mode.icon;
                  return (
                    <button
                      key={mode.id}
                      onClick={() => {
                        onChange(mode.id);
                        setOpen(false);
                      }}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all cursor-pointer ${mode.id === current ? 'bg-brand-50 text-brand-700' : 'hover:bg-surface text-ink'}`}
                    >
                      <div className="w-9 h-9 rounded-xl bg-white shadow-sm border border-divider flex items-center justify-center shrink-0">
                        <Icon className="w-4 h-4 text-brand-600" />
                      </div>
                      <div>
                        <div className="text-sm font-medium">{mode.label}</div>
                        <div className="text-xs text-ink-muted">{mode.description}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={`inline-flex items-center gap-1 rounded-2xl border border-divider bg-white/90 p-1 shadow-sm ${className}`}>
      {DECISION_MODES.map((mode) => {
        const Icon = mode.icon;
        const active = mode.id === current;
        return (
          <button
            key={mode.id}
            type="button"
            onClick={() => onChange(mode.id)}
            className={`inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-semibold transition-all cursor-pointer ${active ? 'bg-brand-600 text-white shadow-sm' : 'text-ink-muted hover:bg-surface hover:text-ink'}`}
            aria-pressed={active}
          >
            <Icon className="w-4 h-4" />
            <span>{mode.shortLabel}</span>
          </button>
        );
      })}
    </div>
  );
}
