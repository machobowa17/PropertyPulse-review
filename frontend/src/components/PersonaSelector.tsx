import { useState, useRef, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import type { PersonaId } from '../types';
import { PERSONAS } from '../utils/personas';

interface Props {
  current: PersonaId;
  onChange: (id: PersonaId) => void;
}

export default function PersonaSelector({ current, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const currentPersona = PERSONAS.find((p) => p.id === current)!;

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface
                   hover:bg-brand-50 transition-all text-sm cursor-pointer"
        title="Select your persona for tailored insights"
      >
        <span className="text-base">{currentPersona.icon}</span>
        <span className="font-medium text-ink hidden md:inline">{currentPersona.label}</span>
        <ChevronDown className={`w-3.5 h-3.5 text-ink-faint transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 w-64 bg-white rounded-2xl shadow-2xl
                     overflow-hidden z-50 ring-1 ring-black/5 animate-dropdown-appear"
        >
          <div className="p-2 border-b border-divider">
            <p className="text-xs text-ink-muted font-medium px-2 py-1">I am a...</p>
          </div>
          <div className="p-1">
            {PERSONAS.map((p) => (
              <button
                key={p.id}
                onClick={() => { onChange(p.id); setOpen(false); }}
                className={`
                  w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all cursor-pointer
                  ${p.id === current ? 'bg-brand-50 text-brand-700' : 'hover:bg-surface text-ink'}
                `}
              >
                <span className="text-xl">{p.icon}</span>
                <div>
                  <div className="text-sm font-medium">{p.label}</div>
                  <div className="text-xs text-ink-muted">{p.description}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
