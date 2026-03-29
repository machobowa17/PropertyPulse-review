import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';

interface Props {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export default function CollapsibleSection({ title, defaultOpen = true, children }: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-2xl bg-white border border-divider shadow-sm overflow-hidden">
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

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 pt-1 border-t border-divider">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
