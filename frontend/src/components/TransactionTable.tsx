import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowUp, ArrowDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { fetchTransactions } from '../api/client';

const EPC_COLOURS: Record<string, string> = {
  A: '#008054', B: '#19b459', C: '#8dce46', D: '#ffd500',
  E: '#fcaa65', F: '#ef8023', G: '#e9153b',
};

const TYPE_LABELS: Record<string, string> = {
  D: 'Detached', S: 'Semi', T: 'Terraced', F: 'Flat',
};

const SORT_COLUMNS: ReadonlyArray<{ key: string; label: string; align: 'left' | 'right' | 'center'; sortable?: boolean }> = [
  { key: 'date', label: 'Date', align: 'left' },
  { key: 'address', label: 'Address', align: 'left', sortable: false },
  { key: 'price', label: 'Price', align: 'right' },
  { key: 'type', label: 'Type', align: 'center' },
  { key: 'beds', label: 'Beds (est.)\u00B9', align: 'center' },
  { key: 'size', label: 'Size', align: 'right' },
  { key: 'tenure', label: 'Tenure', align: 'center' },
  { key: 'epc', label: 'EPC', align: 'center' },
];

interface Props {
  sessionKey: string;
}

export default function TransactionTable({ sessionKey }: Props) {
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState('date');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set());

  const filterParam = typeFilter.size > 0 ? [...typeFilter].join(',') : undefined;

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['transactions', sessionKey, page, sortBy, sortDir, filterParam],
    queryFn: () => fetchTransactions(sessionKey, {
      page,
      sortBy,
      sortDir,
      propertyType: filterParam,
    }),
    placeholderData: (prev) => prev,
    staleTime: 60_000,
  });

  const handleSort = (key: string) => {
    if (sortBy === key) {
      setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(key);
      setSortDir('desc');
    }
    setPage(1);
  };

  const toggleType = (code: string) => {
    setTypeFilter(prev => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
    setPage(1);
  };

  const total = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 1;
  const from = total === 0 ? 0 : (page - 1) * (data?.page_size ?? 10) + 1;
  const to = Math.min(page * (data?.page_size ?? 10), total);

  return (
    <div className="mt-3">
      {/* Type filter pills */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        <button
          onClick={() => { setTypeFilter(new Set()); setPage(1); }}
          className={`px-2.5 py-1 rounded-lg text-[11px] font-medium border transition-colors ${
            typeFilter.size === 0
              ? 'bg-brand-600 text-white border-brand-600'
              : 'bg-surface text-ink-muted border-divider hover:border-brand-300'
          }`}
        >
          All
        </button>
        {Object.entries(TYPE_LABELS).map(([code, label]) => (
          <button
            key={code}
            onClick={() => toggleType(code)}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-medium border transition-colors ${
              typeFilter.has(code)
                ? 'bg-brand-600 text-white border-brand-600'
                : 'bg-surface text-ink-muted border-divider hover:border-brand-300'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-divider">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface">
              {SORT_COLUMNS.map(col => {
                const sortable = col.sortable !== false && col.key !== 'address';
                const isActive = sortBy === col.key;
                return (
                  <th
                    key={col.key}
                    className={`px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-ink-faint whitespace-nowrap ${
                      col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'
                    } ${sortable ? 'cursor-pointer select-none hover:text-ink-muted' : ''}`}
                    onClick={sortable ? () => handleSort(col.key) : undefined}
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.label}
                      {sortable && isActive && (
                        sortDir === 'asc'
                          ? <ArrowUp className="w-3 h-3 text-brand-600" />
                          : <ArrowDown className="w-3 h-3 text-brand-600" />
                      )}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-divider/50">
            {isLoading && !data ? (
              // Skeleton rows
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}>
                  {SORT_COLUMNS.map(col => (
                    <td key={col.key} className="px-3 py-2.5">
                      <div className="h-4 bg-surface rounded animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data && data.transactions.length > 0 ? (
              data.transactions.map((txn, i) => (
                <tr
                  key={i}
                  className={`${isFetching ? 'opacity-60' : ''} ${i % 2 === 0 ? 'bg-white' : 'bg-surface-warm/20'} hover:bg-brand-50/30 transition-colors`}
                >
                  <td className="px-3 py-2 text-ink-muted whitespace-nowrap">{txn.date}</td>
                  <td className="px-3 py-2 text-ink max-w-[200px] truncate" title={txn.address}>{txn.address || '—'}</td>
                  <td className="px-3 py-2 text-ink font-mono text-right whitespace-nowrap">
                    £{txn.price?.toLocaleString('en-GB') ?? '—'}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span className="inline-block px-2 py-0.5 rounded text-[10px] font-medium bg-surface border border-divider">
                      {txn.property_type_label}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-center text-ink-muted">{txn.beds ?? '—'}</td>
                  <td className="px-3 py-2 text-right text-ink-muted whitespace-nowrap">
                    {txn.size_sqm ? `${txn.size_sqm} sqm` : '—'}
                  </td>
                  <td className="px-3 py-2 text-center text-ink-muted text-xs">{txn.tenure_label || '—'}</td>
                  <td className="px-3 py-2 text-center">
                    {txn.epc ? (
                      <span
                        className="inline-flex items-center justify-center w-6 h-6 rounded-md text-[11px] font-bold text-white"
                        style={{ backgroundColor: EPC_COLOURS[txn.epc] || '#888' }}
                      >
                        {txn.epc}
                      </span>
                    ) : (
                      <span className="text-ink-faint">—</span>
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={SORT_COLUMNS.length} className="px-3 py-8 text-center text-ink-faint">
                  No transactions found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 0 && (
        <div className="flex items-center justify-between mt-3">
          <span className="text-[11px] text-ink-faint">
            Showing {from}–{to} of {total.toLocaleString('en-GB')}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-lg border border-divider hover:bg-surface disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-3.5 h-3.5 text-ink-muted" />
            </button>
            <span className="text-xs text-ink-muted px-2">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1.5 rounded-lg border border-divider hover:bg-surface disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="w-3.5 h-3.5 text-ink-muted" />
            </button>
          </div>
        </div>
      )}

      {/* Footnote */}
      <p className="mt-2.5 text-[10px] text-ink-faint leading-relaxed">
        <sup>1</sup> Bedroom count is estimated from EPC habitable rooms (total rooms minus one for living space).
        This is an approximation — habitable rooms can include studies, dining rooms, and utility rooms.
        Not available for all properties. Do not rely on this figure for valuation purposes.
      </p>
    </div>
  );
}
