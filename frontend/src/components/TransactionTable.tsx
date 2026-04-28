import { useState, useRef, useEffect, Fragment } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { ArrowUp, ArrowDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { fetchTransactions, fetchPropertyHistory, SessionExpiredError } from '../api/client';
import type { Transaction, PropertyHistoryEntry } from '../api/client';
import { useResults } from '../context/ResultsContext';

const EPC_COLOURS: Record<string, string> = {
  A: '#008054', B: '#19b459', C: '#8dce46', D: '#ffd500',
  E: '#fcaa65', F: '#ef8023', G: '#e9153b',
};

const TYPE_LABELS: Record<string, string> = {
  D: 'Detached', S: 'Semi', T: 'Terraced', F: 'Flat',
};

const SORT_COLUMNS: ReadonlyArray<{ key: string; label: string; align: 'left' | 'right' | 'center'; sortable?: boolean; width: string }> = [
  { key: 'date', label: 'Date', align: 'left', width: '11%' },
  { key: 'address', label: 'Address', align: 'left', sortable: false, width: '25%' },
  { key: 'price', label: 'Price', align: 'right', width: '14%' },
  { key: 'type', label: 'Type', align: 'center', width: '10%' },
  { key: 'beds', label: 'Beds (est.)\u00B9', align: 'center', width: '10%' },
  { key: 'size', label: 'Size', align: 'right', width: '10%' },
  { key: 'tenure', label: 'Tenure', align: 'center', width: '9%' },
  { key: 'epc', label: 'EPC', align: 'center', width: '8%' },
];

const COL_COUNT = SORT_COLUMNS.length + 1; // +1 for expand +/− column

function pctChangeLabel(currentPrice: number, previousPrice: number): { text: string; positive: boolean } | null {
  if (!currentPrice || !previousPrice) return null;
  const pct = ((currentPrice - previousPrice) / previousPrice) * 100;
  return {
    text: `${pct >= 0 ? '+' : ''}${pct.toFixed(0)}%`,
    positive: pct >= 0,
  };
}

interface Props {
  sessionKey: string;
}

/* ------------------------------------------------------------------ */
/* Sub-row component — fetches & renders previous sales for a property */
/* ------------------------------------------------------------------ */

function PropertyHistorySubRows({
  sessionKey,
  txn,
  searchQuery,
  onHistoryLoaded,
}: {
  sessionKey: string;
  txn: Transaction;
  searchQuery: string;
  onHistoryLoaded: (mostRecentPreviousPrice: number | null) => void;
}) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['property-history', txn.transaction_id],
    queryFn: async () => {
      const result = await fetchPropertyHistory(
        sessionKey,
        txn.postcode,
        txn.paon,
        txn.saon,
        txn.street,
        txn.transaction_id,
        searchQuery || undefined,
      );
      // Notify parent of the most recent previous sale price
      onHistoryLoaded(result.history.length > 0 ? result.history[0].price : null);
      return result;
    },
    staleTime: 5 * 60_000,
    retry: 1,
  });

  if (isLoading) {
    return (
      <tr>
        <td colSpan={COL_COUNT} className="px-0 py-0">
          <div className="bg-brand-50/20 border-l-2 border-brand-300 ml-4">
            {[0, 1].map(i => (
              <div key={i} className="flex gap-3 px-4 py-2">
                <div className="h-3.5 w-16 bg-surface rounded animate-pulse" />
                <div className="h-3.5 w-24 bg-surface rounded animate-pulse" />
                <div className="h-3.5 w-16 bg-surface rounded animate-pulse" />
              </div>
            ))}
          </div>
        </td>
      </tr>
    );
  }

  if (isError) {
    return (
      <tr>
        <td colSpan={COL_COUNT} className="px-0 py-0">
          <div className="bg-red-50/30 border-l-2 border-red-300 ml-4 px-4 py-2.5 text-xs text-ink-faint">
            Failed to load property history
          </div>
        </td>
      </tr>
    );
  }

  if (!data || data.history.length === 0) {
    return (
      <tr>
        <td colSpan={COL_COUNT} className="px-0 py-0">
          <div className="bg-brand-50/20 border-l-2 border-brand-300 ml-4 px-4 py-2.5 text-xs text-ink-faint">
            No previous sales on record
          </div>
        </td>
      </tr>
    );
  }

  return (
    <>
      {data.history.map((h: PropertyHistoryEntry, idx: number) => {
        // % change relative to the PREVIOUS (older) sale below this one
        const olderSale = data.history[idx + 1];
        const change = olderSale ? pctChangeLabel(h.price, olderSale.price) : null;

        return (
          <tr key={`${h.date}-${h.price}`} className="bg-brand-50/20">
            {/* Expand column — connector line */}
            <td className="px-0 py-0 w-[3%]">
              <div className="border-l-2 border-brand-300 ml-4 h-full">&nbsp;</div>
            </td>
            <td className="px-3 py-1.5 text-ink-faint text-xs whitespace-nowrap">{h.date}</td>
            <td className="px-3 py-1.5 text-xs text-ink-faint italic">Previous sale</td>
            <td className="px-3 py-1.5 text-right whitespace-nowrap">
              <span className="text-ink-muted font-mono text-xs">
                £{h.price?.toLocaleString('en-GB') ?? '—'}
              </span>
              {change && (
                <span className={`ml-1.5 text-[10px] font-medium ${change.positive ? 'text-green-600' : 'text-red-500'}`}>
                  ({change.text})
                </span>
              )}
            </td>
            <td className="px-3 py-1.5 text-center">
              <span className="inline-block px-2 py-0.5 rounded text-[10px] font-medium bg-surface border border-divider">
                {TYPE_LABELS[h.property_type] || h.property_type_label}
              </span>
            </td>
            <td className="px-3 py-1.5 text-center text-ink-faint text-xs">{h.beds ?? '—'}</td>
            <td className="px-3 py-1.5 text-right text-ink-faint text-xs whitespace-nowrap">
              {h.size_sqm ? `${h.size_sqm} sqm` : '—'}
            </td>
            <td className="px-3 py-1.5 text-center text-ink-faint text-xs">{h.tenure_label || '—'}</td>
            <td className="px-3 py-1.5 text-center">
              {h.epc ? (
                <span
                  className="inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-bold text-white"
                  style={{ backgroundColor: EPC_COLOURS[h.epc] || '#888' }}
                >
                  {h.epc}
                </span>
              ) : (
                <span className="text-ink-faint text-xs">—</span>
              )}
            </td>
          </tr>
        );
      })}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Main TransactionTable component                                     */
/* ------------------------------------------------------------------ */

export default function TransactionTable({ sessionKey }: Props) {
  const [searchParams] = useSearchParams();
  const q = searchParams.get('q') ?? '';
  const queryClient = useQueryClient();
  const { mapFlyToRef, mapViewportRef, mapHighlightRef, clearMapHighlight } = useResults();
  // Save the map viewport before zooming to a property, so we can restore on collapse
  const preZoomViewportRef = useRef<{ center: [number, number]; zoom: number } | null>(null);

  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState('date');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set());
  const [yearFilter, setYearFilter] = useState<number | undefined>(undefined);
  const [expandedTxnId, setExpandedTxnId] = useState<string | null>(null);
  // Stores the most recent previous sale price for the expanded row (for main row % display)
  const [prevSalePrice, setPrevSalePrice] = useState<number | null>(null);

  const filterParam = typeFilter.size > 0 ? [...typeFilter].join(',') : 'D,S,T,F';

  const fetchParams = { page, sortBy, sortDir, propertyType: filterParam, year: yearFilter };

  const { data, isLoading, isFetching, isError, refetch } = useQuery({
    queryKey: ['transactions', sessionKey, page, sortBy, sortDir, filterParam, yearFilter],
    queryFn: () => fetchTransactions(sessionKey, fetchParams, q || undefined),
    enabled: !!sessionKey,
    placeholderData: (prev) => prev,
    staleTime: 60_000,
    retry: (failureCount, error) => {
      if (error instanceof SessionExpiredError) {
        queryClient.invalidateQueries({ queryKey: ['resolve', q] });
        return false;
      }
      return failureCount < 2;
    },
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

  const restoreMapViewport = () => {
    const saved = preZoomViewportRef.current;
    if (saved && mapFlyToRef.current) {
      mapFlyToRef.current(saved.center[0], saved.center[1], saved.zoom);
      preZoomViewportRef.current = null;
    }
  };

  // Restore map viewport + clear highlight when TransactionTable unmounts (metric card collapsed)
  useEffect(() => {
    return () => { restoreMapViewport(); clearMapHighlight(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleExpand = (txnId: string, txn: { lat: number | null; lon: number | null; price: number; property_type_label: string; tenure_label: string; beds: number | null; size_sqm: number | null; date: string; address: string; epc: string | null }) => {
    setExpandedTxnId(prev => {
      if (prev === txnId) {
        setPrevSalePrice(null);
        // Collapsing — restore map and remove highlight marker
        clearMapHighlight();
        restoreMapViewport();
        return null;
      }
      setPrevSalePrice(null);
      const { lat, lon } = txn;
      // Save current viewport before flying to property
      if (lat && lon && mapFlyToRef.current) {
        if (!preZoomViewportRef.current && mapViewportRef.current) {
          preZoomViewportRef.current = mapViewportRef.current;
        }
        mapFlyToRef.current(lon, lat);
        // Show temporary highlight marker at the property location
        mapHighlightRef.current?.(lon, lat, {
          name: txn.address,
          price: txn.price,
          property_type: txn.property_type_label,
          tenure: txn.tenure_label,
          bedrooms: txn.beds,
          floor_area_sqm: txn.size_sqm,
          date: txn.date,
          epc_rating: txn.epc,
        });
      }
      return txnId;
    });
  };

  const total = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 1;
  const from = total === 0 ? 0 : (page - 1) * (data?.page_size ?? 10) + 1;
  const to = Math.min(page * (data?.page_size ?? 10), total);

  return (
    <div className="mt-3">
      {/* Filters: type pills + year dropdown */}
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <div className="flex flex-wrap gap-1.5">
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
        <select
          value={yearFilter ?? ''}
          onChange={(e) => { setYearFilter(e.target.value ? Number(e.target.value) : undefined); setPage(1); }}
          className="px-2.5 py-1 rounded-lg text-[11px] font-medium border border-divider bg-surface text-ink-muted cursor-pointer hover:border-brand-300 transition-colors"
        >
          <option value="">Last 12 months</option>
          {(data?.available_years ?? []).map((yr) => (
            <option key={yr} value={yr}>{yr}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-divider">
        <table className="w-full text-sm table-fixed min-w-[640px]">
          <thead>
            <tr className="bg-surface">
              {/* Expand +/− column */}
              <th style={{ width: '3%' }} className="px-1 py-2.5" />
              {SORT_COLUMNS.map(col => {
                const sortable = col.sortable !== false && col.key !== 'address';
                const isActive = sortBy === col.key;
                return (
                  <th
                    key={col.key}
                    style={{ width: col.width }}
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
            {isError ? (
              <tr>
                <td colSpan={COL_COUNT} className="px-3 py-8 text-center text-ink-faint">
                  <span>Failed to load transactions. </span>
                  <button onClick={() => refetch()} className="text-brand-600 hover:underline">Retry</button>
                </td>
              </tr>
            ) : isLoading && !data ? (
              // Skeleton rows
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}>
                  <td className="px-1 py-2.5" />
                  {SORT_COLUMNS.map(col => (
                    <td key={col.key} className="px-3 py-2.5">
                      <div className="h-4 bg-surface rounded animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data && data.transactions.length > 0 ? (
              data.transactions.map((txn, i) => {
                const isExpanded = expandedTxnId === txn.transaction_id;
                // Show % change on main row price (from most recent previous sale)
                const mainRowChange = isExpanded && prevSalePrice
                  ? pctChangeLabel(txn.price, prevSalePrice)
                  : null;
                return (
                  <Fragment key={txn.transaction_id || i}>
                    <tr
                      className={`${isFetching ? 'opacity-60' : ''} ${i % 2 === 0 ? 'bg-white' : 'bg-surface-warm/20'} hover:bg-brand-50/30 transition-colors cursor-pointer`}
                      onClick={() => toggleExpand(txn.transaction_id, txn)}
                    >
                      {/* Expand +/− indicator */}
                      <td className="px-1 py-2 text-center w-[3%]">
                        <span className="text-xs text-ink-faint font-mono select-none">
                          {isExpanded ? '−' : '+'}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-ink-muted whitespace-nowrap">{txn.date}</td>
                      <td className="px-3 py-2 text-ink max-w-[200px] truncate" title={txn.address}>{txn.address || '—'}</td>
                      <td className="px-3 py-2 text-ink font-mono text-right whitespace-nowrap">
                        £{txn.price?.toLocaleString('en-GB') ?? '—'}
                        {mainRowChange && (
                          <span className={`ml-1.5 text-[10px] font-medium ${mainRowChange.positive ? 'text-green-600' : 'text-red-500'}`}>
                            ({mainRowChange.text})
                          </span>
                        )}
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
                    {isExpanded && (
                      <PropertyHistorySubRows
                        sessionKey={sessionKey}
                        txn={txn}
                        searchQuery={q}
                        onHistoryLoaded={setPrevSalePrice}
                      />
                    )}
                  </Fragment>
                );
              })
            ) : (
              <tr>
                <td colSpan={COL_COUNT} className="px-3 py-8 text-center text-ink-faint">
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
