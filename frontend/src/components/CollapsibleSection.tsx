import { useState, useRef } from 'react';
import { ChevronDown } from 'lucide-react';

interface Props {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export default function CollapsibleSection({ title, defaultOpen = true, children }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const contentRef = useRef<HTMLDivElement>(null);

  return (
    <div className="rounded-2xl bg-white shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label={`${title} — ${open ? 'collapse' : 'expand'}`}
        className="w-full flex items-center justify-between px-5 py-3.5 text-left group hover:bg-surface transition-colors"
      >
        <span className="text-sm font-semibold text-ink">{title}</span>
        <ChevronDown
          aria-hidden="true"
          className={`w-4 h-4 text-ink-faint shrink-0 transition-transform duration-200 ${open ? 'rotate-180' : 'group-hover:text-ink-muted'}`}
        />
      </button>

      <div
        className="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
        style={{ gridTemplateRows: open ? '1fr' : '0fr', opacity: open ? 1 : 0 }}
      >
        <div ref={contentRef} className="overflow-hidden">
          <div className="px-4 pb-4 pt-1 border-t border-divider/50">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
