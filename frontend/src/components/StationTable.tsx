import { Fragment, useState, useCallback, useRef } from 'react';
import { TrainFront, Train, Bus, TramFront, Ship, Accessibility, Ticket, ChevronRight, ChevronDown, Search, Clock, Footprints, ArrowRight } from 'lucide-react';

interface Facilities {
  ticket_halls?: string;
  toilets?: boolean;
  car_park?: boolean;
  wifi?: boolean;
  lifts?: number;
  escalators?: number;
  gates?: number;
}

interface JourneyLeg {
  mode: string;
  line?: string;
  summary: string;
  from?: string;
  to?: string;
  depart?: string;
  arrive?: string;
  duration: number;
  distance_m?: number;
}

interface Destination {
  dest_crs: string;
  dest_name: string;
  journey_min: number | null;
  trains_per_hour: number | null;
  pct_on_time: number | null;
  season_ticket_gbp: number | null;
  is_travelcard?: boolean;
  travelcard_zones?: string;
  journey_type?: 'direct' | 'multi_modal';
  num_changes?: number;
  modes?: string[];
  peak_fare_pence?: number | null;
  offpeak_fare_pence?: number | null;
  fare_zones?: string | null;
  legs?: JourneyLeg[];
  fare_caveats?: string[];
}

interface StationRow {
  name: string;
  type: string;
  category: string;
  atco_code: string;
  street?: string;
  indicator?: string;
  locality?: string;
  parent_locality?: string;
  suburb?: string;
  status?: string;
  distance_m?: number;
  crs_code?: string;
  lines?: string;
  operator?: string;
  zone?: string;
  step_free?: boolean;
  facilities?: Facilities;
  destinations?: Destination[];
}

interface Props {
  stations: StationRow[];
  modeCounts?: Record<string, number> | null;
  isArea?: boolean;
}

const CATEGORIES = [
  { key: 'rail',        label: 'National Rail',    icon: Train },
  { key: 'underground', label: 'Underground',      icon: TrainFront },
  { key: 'dlr',         label: 'DLR',              icon: TrainFront },
  { key: 'overground',  label: 'London Overground', icon: TrainFront },
  { key: 'tram',        label: 'Tram/Metro',       icon: TramFront },
  { key: 'bus',         label: 'Bus',              icon: Bus },
  { key: 'ferry',       label: 'Ferry',            icon: Ship },
] as const;

const MODE_ICONS: Record<string, { icon: typeof Train; label: string; color: string }> = {
  'national-rail': { icon: Train, label: 'Rail', color: 'text-red-600' },
  'tube':          { icon: TrainFront, label: 'Tube', color: 'text-blue-600' },
  'overground':    { icon: TrainFront, label: 'Overground', color: 'text-orange-500' },
  'dlr':           { icon: TrainFront, label: 'DLR', color: 'text-teal-600' },
  'elizabeth-line':{ icon: TrainFront, label: 'Elizabeth', color: 'text-purple-600' },
  'tram':          { icon: TramFront, label: 'Tram', color: 'text-green-600' },
  'bus':           { icon: Bus, label: 'Bus', color: 'text-red-500' },
  'walking':       { icon: Footprints, label: 'Walk', color: 'text-ink-faint' },
  'cycle':         { icon: Footprints, label: 'Cycle', color: 'text-ink-faint' },
  'ferry':         { icon: Ship, label: 'Ferry', color: 'text-blue-500' },
};

function ModeIcon({ mode, size = 'w-3 h-3' }: { mode: string; size?: string }) {
  const info = MODE_ICONS[mode] || { icon: Train, label: mode, color: 'text-ink-muted' };
  const Icon = info.icon;
  return <span title={info.label}><Icon className={`${size} ${info.color}`} /></span>;
}

function PunctualityBadge({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-ink-faint text-xs">—</span>;
  const color = pct >= 80 ? 'text-green-700 bg-green-50 border-green-200'
    : pct >= 60 ? 'text-amber-700 bg-amber-50 border-amber-200'
    : 'text-red-700 bg-red-50 border-red-200';
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold border ${color}`}>
      {pct.toFixed(0)}%
    </span>
  );
}

function formatPence(pence: number): string {
  return `£${(pence / 100).toFixed(2)}`;
}

/* ── Journey card for a single destination ─────────────────────────────── */
function JourneyCard({ d, expanded, onToggle }: {
  d: Destination;
  expanded: boolean;
  onToggle: () => void;
}) {
  const isMultiModal = d.journey_type === 'multi_modal' && d.legs && d.legs.length > 0;
  const hasChanges = (d.num_changes ?? 0) > 0;

  return (
    <div className="border border-divider/40 rounded-lg bg-white hover:border-brand-300 transition-colors">
      {/* Summary row — always visible */}
      <button
        onClick={isMultiModal ? onToggle : undefined}
        className={`w-full text-left px-3 py-2.5 ${isMultiModal ? 'cursor-pointer' : ''}`}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm text-ink">{d.dest_name}</span>
              <span className="text-[10px] text-ink-faint font-mono">({d.dest_crs})</span>
            </div>
            {/* Mode chain */}
            {isMultiModal && d.modes && d.modes.length > 0 && (
              <div className="flex items-center gap-1 mt-1">
                {d.modes.filter(m => m !== 'walking').map((mode, i) => (
                  <Fragment key={mode}>
                    {i > 0 && <ArrowRight className="w-2.5 h-2.5 text-ink-faint" />}
                    <ModeIcon mode={mode} />
                    <span className="text-[10px] text-ink-muted">
                      {MODE_ICONS[mode]?.label || mode}
                    </span>
                  </Fragment>
                ))}
              </div>
            )}
            {/* Fares line */}
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-1 text-[11px] text-ink-muted">
              {d.peak_fare_pence != null && (
                <span>Peak {formatPence(d.peak_fare_pence)}</span>
              )}
              {d.offpeak_fare_pence != null && (
                <span>Off-peak {formatPence(d.offpeak_fare_pence)}</span>
              )}
              {d.season_ticket_gbp != null && (
                <span className="font-medium text-ink">
                  ~£{d.season_ticket_gbp.toLocaleString()}/yr
                  {d.travelcard_zones && (
                    <span className="text-ink-faint ml-0.5 text-[10px]">
                      Zones {d.travelcard_zones}
                    </span>
                  )}
                </span>
              )}
              {d.fare_zones && !d.travelcard_zones && (
                <span className="text-[10px] text-ink-faint">Zones {d.fare_zones}</span>
              )}
            </div>
          </div>
          {/* Right side: duration + changes */}
          <div className="flex-shrink-0 text-right">
            <div className="text-sm font-semibold text-ink tabular-nums">
              {d.journey_min != null ? `${d.journey_min} min` : '—'}
            </div>
            {hasChanges ? (
              <div className="text-[10px] text-ink-muted mt-0.5">
                {d.num_changes} {d.num_changes === 1 ? 'change' : 'changes'}
              </div>
            ) : d.trains_per_hour != null ? (
              <div className="text-[10px] text-ink-faint mt-0.5">
                {d.trains_per_hour.toFixed(1)}/hr
              </div>
            ) : null}
            {isMultiModal && (
              <div className="mt-1">
                {expanded
                  ? <ChevronDown className="w-3 h-3 text-brand-500 inline" />
                  : <ChevronRight className="w-3 h-3 text-ink-faint inline" />
                }
              </div>
            )}
          </div>
        </div>
      </button>

      {/* Expanded leg-by-leg detail */}
      {expanded && isMultiModal && d.legs && (
        <div className="border-t border-divider/30 px-3 py-2 bg-surface-warm/20">
          <div className="space-y-0">
            {d.legs.map((leg, i) => (
              <div key={i} className="flex items-start gap-2 py-1.5">
                <div className="flex-shrink-0 w-10 text-right text-[10px] text-ink-muted tabular-nums mt-0.5">
                  {leg.depart || ''}
                </div>
                <div className="flex-shrink-0 mt-0.5">
                  <ModeIcon mode={leg.mode} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-ink">
                    {leg.mode === 'walking' ? (
                      <span className="text-ink-muted">
                        Walk{leg.distance_m ? ` (${leg.distance_m}m)` : ''} · {leg.duration} min
                      </span>
                    ) : (
                      <>
                        {leg.from && leg.to ? (
                          <>{leg.from} → {leg.to}</>
                        ) : (
                          leg.summary
                        )}
                        <span className="text-ink-faint ml-1.5">{leg.duration} min</span>
                      </>
                    )}
                  </div>
                  {leg.line && leg.mode !== 'walking' && (
                    <div className="text-[10px] text-ink-faint">{leg.line}</div>
                  )}
                </div>
                <div className="flex-shrink-0 text-[10px] text-ink-faint tabular-nums">
                  {leg.arrive || ''}
                </div>
              </div>
            ))}
          </div>
          {/* Fare caveats */}
          {d.fare_caveats && d.fare_caveats.length > 0 && (
            <div className="mt-2 pt-1.5 border-t border-divider/20">
              {d.fare_caveats.map((c, i) => (
                <div key={i} className="text-[10px] text-ink-faint leading-tight">{c}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Direct route row (flat, for non-TfL-enriched destinations) ────────── */
function DirectRow({ d, hasOnTime, hasPrice }: {
  d: Destination;
  hasOnTime: boolean;
  hasPrice: boolean;
}) {
  return (
    <tr className="hover:bg-white/50">
      <td className="py-1.5 pr-3 font-medium text-ink">{d.dest_name}</td>
      <td className="py-1.5 px-2 text-right text-ink-muted tabular-nums">
        {d.journey_min != null ? `${d.journey_min} min` : '—'}
      </td>
      <td className="py-1.5 px-2 text-right text-ink-muted tabular-nums">
        {d.trains_per_hour != null ? d.trains_per_hour.toFixed(1) : '—'}
      </td>
      {hasOnTime && (
        <td className="py-1.5 px-2 text-center">
          <PunctualityBadge pct={d.pct_on_time} />
        </td>
      )}
      {hasPrice && (
        <td className="py-1.5 pl-2 text-right text-ink-muted tabular-nums">
          {d.season_ticket_gbp != null ? (
            <>{`£${d.season_ticket_gbp.toLocaleString()}/yr`}{d.travelcard_zones && <span className="text-ink-faint ml-1 text-[9px]">Zones {d.travelcard_zones}</span>}</>
          ) : '—'}
        </td>
      )}
    </tr>
  );
}

/* ── Destination sub-panel (replaces old DestinationSubTable) ──────────── */
function DestinationSubTable({ station }: { station: StationRow }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Array<{
    station_id: string; crs_code?: string; name: string;
    stop_type: string; lat: number; lon: number;
  }>>([]);
  const [customDest, setCustomDest] = useState<Destination | null>(null);
  const [searching, setSearching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [expandedLegs, setExpandedLegs] = useState<Set<string>>(new Set());
  const [departTime, setDepartTime] = useState('08:00');
  const [liveResults, setLiveResults] = useState<Record<string, Destination>>({});
  const [loadingLive, setLoadingLive] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const doSearch = useCallback((q: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (q.length < 2) { setSearchResults([]); setFetchError(null); return; }
    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      setFetchError(null);
      try {
        const resp = await fetch(`/api/v1/commute/stations?q=${encodeURIComponent(q)}`);
        if (resp.ok) setSearchResults(await resp.json());
        else setFetchError('Search failed');
      } catch { setFetchError('Network error'); }
      setSearching(false);
    }, 300);
  }, []);

  const selectDestination = useCallback(async (
    result: { station_id: string; crs_code?: string; name: string; stop_type: string; lat: number; lon: number }
  ) => {
    setSearchResults([]);
    setSearchQuery(result.name);
    setFetchError(null);
    try {
      const timeStr = departTime.replace(':', '');
      let journeyUrl = `/api/v1/commute/journey?origin_crs=${station.crs_code}&time=${timeStr}`;
      if (result.crs_code) {
        journeyUrl += `&dest_crs=${result.crs_code}`;
      } else {
        journeyUrl += `&dest_lat=${result.lat}&dest_lon=${result.lon}`;
      }
      const resp = await fetch(journeyUrl);
      if (resp.ok) {
        const data = await resp.json();
        if (!data.error) {
          setCustomDest({ ...data, dest_crs: result.crs_code || result.station_id, dest_name: result.name });
        } else if (result.crs_code) {
          const resp2 = await fetch(
            `/api/v1/commute/station-pair?origin_crs=${station.crs_code}&dest_crs=${result.crs_code}`
          );
          if (resp2.ok) setCustomDest(await resp2.json());
          else setFetchError('No route found');
        } else {
          setFetchError('No route found');
        }
      } else {
        setFetchError('Journey lookup failed');
      }
    } catch { setFetchError('Network error'); }
  }, [station.crs_code, departTime]);

  const updateDepartTime = useCallback(async () => {
    if (!station.destinations || !station.crs_code) return;
    setLoadingLive(true);
    setFetchError(null);
    const timeStr = departTime.replace(':', '');
    const results: Record<string, Destination> = {};
    let errors = 0;

    for (const d of station.destinations) {
      try {
        const resp = await fetch(
          `/api/v1/commute/journey?origin_crs=${station.crs_code}&dest_crs=${d.dest_crs}&time=${timeStr}`
        );
        if (resp.ok) {
          const data = await resp.json();
          if (!data.error) {
            results[d.dest_crs] = { ...d, ...data, dest_name: d.dest_name };
          }
        } else {
          errors++;
        }
      } catch { errors++; }
    }
    setLiveResults(results);
    if (errors > 0 && Object.keys(results).length === 0) {
      setFetchError('Could not fetch live journeys');
    }
    setLoadingLive(false);
  }, [station.destinations, station.crs_code, departTime]);

  const destinations = station.destinations || [];
  const hasMultiModal = destinations.some(d => d.journey_type === 'multi_modal');
  const directOnly = destinations.filter(d => d.journey_type !== 'multi_modal');
  const hasOnTime = directOnly.some(d => d.pct_on_time != null);
  const hasPrice = directOnly.some(d => d.season_ticket_gbp != null);

  const toggleLeg = (crs: string) => {
    setExpandedLegs(prev => {
      const next = new Set(prev);
      if (next.has(crs)) next.delete(crs);
      else next.add(crs);
      return next;
    });
  };

  return (
    <div className="px-4 py-3 bg-surface-warm/30">
      {/* Header with departure time selector */}
      <div className="flex items-center justify-between mb-2">
        <div className="text-[11px] font-semibold text-ink-muted uppercase tracking-wider">
          Top destinations from {station.name}
        </div>
        {hasMultiModal && (
          <div className="flex items-center gap-1.5">
            <Clock className="w-3 h-3 text-ink-faint" />
            <input
              type="time"
              value={departTime}
              onChange={e => setDepartTime(e.target.value)}
              className="text-[11px] px-1.5 py-0.5 rounded border border-divider bg-white focus:border-brand-400 focus:outline-none tabular-nums"
            />
            <button
              onClick={updateDepartTime}
              disabled={loadingLive}
              className="text-[10px] px-2 py-0.5 rounded bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50 transition-colors"
            >
              {loadingLive ? '...' : 'Update'}
            </button>
          </div>
        )}
      </div>

      {/* Journey cards (multi-modal destinations) */}
      {hasMultiModal && (
        <div className="space-y-1.5 mb-3">
          {destinations
            .filter(d => d.journey_type === 'multi_modal')
            .map(d => {
              const live = liveResults[d.dest_crs];
              const display = live || d;
              return (
                <JourneyCard
                  key={d.dest_crs}
                  d={display}
                  expanded={expandedLegs.has(d.dest_crs)}
                  onToggle={() => toggleLeg(d.dest_crs)}
                />
              );
            })}
        </div>
      )}

      {/* Direct-only table (fallback for non-TfL-enriched destinations) */}
      {directOnly.length > 0 && (
        <table className="w-full text-xs mb-2">
          <thead>
            <tr className="text-[10px] uppercase tracking-wider text-ink-faint">
              <th className="text-left py-1 pr-3">Destination</th>
              <th className="text-right py-1 px-2">Journey</th>
              <th className="text-right py-1 px-2">Trains/hr</th>
              {hasOnTime && <th className="text-center py-1 px-2">On time</th>}
              {hasPrice && <th className="text-right py-1 pl-2">Season ticket</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-divider/30">
            {directOnly.map(d => (
              <DirectRow key={d.dest_crs} d={d} hasOnTime={hasOnTime} hasPrice={hasPrice} />
            ))}
          </tbody>
        </table>
      )}

      {/* Custom destination (if selected via search) */}
      {customDest && customDest.journey_type === 'multi_modal' && customDest.legs ? (
        <div className="mb-2">
          <JourneyCard
            d={customDest}
            expanded={expandedLegs.has('custom')}
            onToggle={() => toggleLeg('custom')}
          />
        </div>
      ) : customDest && (
        <div className="mb-2 text-xs bg-brand-50/30 rounded px-3 py-2 border border-brand-200/30">
          <span className="font-medium text-brand-700">{customDest.dest_name || searchQuery}</span>
          <span className="ml-3 text-ink-muted tabular-nums">
            {customDest.journey_min != null ? `${customDest.journey_min} min` : '—'}
          </span>
          {customDest.season_ticket_gbp != null && (
            <span className="ml-3 text-ink-muted tabular-nums">
              ~£{customDest.season_ticket_gbp.toLocaleString()}/yr
            </span>
          )}
        </div>
      )}

      {/* Custom destination search */}
      <div className="relative max-w-[260px]">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-ink-faint" />
        <input
          type="text"
          placeholder="Search another destination..."
          value={searchQuery}
          onChange={e => {
            setSearchQuery(e.target.value);
            doSearch(e.target.value);
          }}
          className="w-full pl-7 pr-2 py-1 text-xs rounded border border-divider bg-white focus:border-brand-400 focus:outline-none"
        />
        {searchResults.length > 0 && (
          <div className="absolute z-10 top-full left-0 mt-1 w-full bg-white border border-divider rounded shadow-lg max-h-[150px] overflow-y-auto">
            {searchResults.map(r => (
              <button
                key={r.station_id}
                onClick={() => selectDestination(r)}
                className="w-full text-left px-2 py-1.5 text-xs hover:bg-brand-50 border-b border-divider/30 last:border-0"
              >
                {r.name} <span className="text-ink-faint">({r.crs_code || r.stop_type})</span>
              </button>
            ))}
          </div>
        )}
        {searching && (
          <div className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-ink-faint">...</div>
        )}
      </div>
      {fetchError && (
        <div className="mt-1.5 text-[11px] text-red-600 bg-red-50 px-2 py-1 rounded border border-red-200 max-w-[260px]">
          {fetchError}
        </div>
      )}
    </div>
  );
}

/* ── Main StationTable ─────────────────────────────────────────────────── */
export default function StationTable({ stations, modeCounts, isArea }: Props) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const availableCategories = CATEGORIES.filter(c => {
    const count = modeCounts?.[c.key] ?? stations.filter(s => s.category === c.key).length;
    return count > 0;
  });

  const bestDefault = availableCategories.find(c =>
    stations.some(s => s.category === c.key && (s.lines || s.operator))
  )?.key ?? availableCategories[0]?.key ?? 'rail';

  const [activeCategory, setActiveCategory] = useState<string>(bestDefault);

  const filtered = stations.filter(s => s.category === activeCategory);
  const hasDistance = !isArea && filtered.some(s => s.distance_m != null);
  const hasLines = filtered.some(s => s.lines);
  const hasOperator = filtered.some(s => s.operator);
  const hasZone = filtered.some(s => s.zone);
  const hasInfo = filtered.some(s => s.step_free || s.facilities);
  const hasExpandable = activeCategory === 'rail' && filtered.some(s => s.destinations?.length);

  const toggleRow = (key: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  let colCount = 2;
  if (hasExpandable) colCount++;
  if (hasLines) colCount++;
  if (hasOperator) colCount++;
  if (hasZone) colCount++;
  if (hasDistance) colCount++;
  if (hasInfo) colCount++;

  return (
    <div className="mt-3 space-y-3">
      {/* Category toggle pills */}
      <div className="flex flex-wrap gap-1.5">
        {availableCategories.map(cat => {
          const count = modeCounts?.[cat.key] ?? stations.filter(s => s.category === cat.key).length;
          const isActive = activeCategory === cat.key;
          const Icon = cat.icon;
          return (
            <button
              key={cat.key}
              onClick={() => setActiveCategory(cat.key)}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium border transition-colors ${
                isActive
                  ? 'bg-brand-600 text-white border-brand-600'
                  : 'bg-surface text-ink-muted border-divider hover:border-brand-300'
              }`}
            >
              <Icon className="w-3 h-3" />
              {cat.label}
              {count > 0 && (
                <span className={`text-[10px] ${isActive ? 'text-white/80' : 'text-ink-faint'}`}>
                  ({count})
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Table */}
      {filtered.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-divider">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface">
                {hasExpandable && (
                  <th className="w-8 px-1 py-2.5" />
                )}
                <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-faint whitespace-nowrap">
                  Name
                </th>
                {hasLines && (
                  <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-faint whitespace-nowrap">
                    Lines
                  </th>
                )}
                {hasOperator && (
                  <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-faint whitespace-nowrap">
                    Operator
                  </th>
                )}
                {hasZone && (
                  <th className="px-3 py-2.5 text-center text-[11px] font-semibold uppercase tracking-wider text-ink-faint whitespace-nowrap">
                    Zone
                  </th>
                )}
                <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-faint whitespace-nowrap">
                  Location
                </th>
                {hasDistance && (
                  <th className="px-3 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wider text-ink-faint whitespace-nowrap">
                    Distance
                  </th>
                )}
                {hasInfo && (
                  <th className="px-3 py-2.5 text-center text-[11px] font-semibold uppercase tracking-wider text-ink-faint whitespace-nowrap">
                    Info
                  </th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-divider/50">
              {filtered.map((s, i) => {
                const facilityBadges: string[] = [];
                if (s.step_free) facilityBadges.push('Step-free');
                if (s.facilities?.toilets) facilityBadges.push('Toilets');
                if (s.facilities?.car_park) facilityBadges.push('Car park');
                if (s.facilities?.wifi) facilityBadges.push('WiFi');
                if (s.facilities?.ticket_halls) facilityBadges.push('Ticket hall');

                const rowKey = s.atco_code || `${s.name}-${i}`;
                const isExpanded = expandedRows.has(rowKey);
                const canExpand = hasExpandable && s.destinations && s.destinations.length > 0 &&
                  s.destinations.some(d => d.journey_min != null || d.trains_per_hour != null);

                return (
                  <Fragment key={rowKey}>
                    <tr
                      className={`${i % 2 === 0 ? 'bg-white' : 'bg-surface-warm/20'} hover:bg-brand-50/30 transition-colors ${canExpand ? 'cursor-pointer' : ''}`}
                      onClick={canExpand ? () => toggleRow(rowKey) : undefined}
                    >
                      {hasExpandable && (
                        <td className="w-8 px-1 py-2 text-center">
                          {canExpand && (
                            isExpanded
                              ? <ChevronDown className="w-3.5 h-3.5 text-brand-500 inline" />
                              : <ChevronRight className="w-3.5 h-3.5 text-ink-faint inline" />
                          )}
                        </td>
                      )}
                      <td className="px-3 py-2 text-ink font-medium whitespace-nowrap">
                        {s.name}
                        {s.crs_code && (
                          <span className="ml-1.5 text-[10px] text-ink-faint font-mono">({s.crs_code})</span>
                        )}
                      </td>
                      {hasLines && (
                        <td className="px-3 py-2 max-w-[200px]">
                          {s.lines ? (
                            <div className="flex flex-wrap gap-1">
                              {s.lines.split(', ').map(line => (
                                <span key={line} className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium bg-brand-50 text-brand-700 border border-brand-200">
                                  {line}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-ink-faint text-xs">—</span>
                          )}
                        </td>
                      )}
                      {hasOperator && (
                        <td className="px-3 py-2 text-ink-muted text-xs whitespace-nowrap">
                          {s.operator || '—'}
                        </td>
                      )}
                      {hasZone && (
                        <td className="px-3 py-2 text-center">
                          {s.zone ? (
                            <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-surface border border-divider text-ink">
                              {s.zone}
                            </span>
                          ) : (
                            <span className="text-ink-faint text-xs">—</span>
                          )}
                        </td>
                      )}
                      <td className="px-3 py-2 text-ink-muted text-xs">
                        {s.street || s.locality || s.suburb || '—'}
                        {s.parent_locality && s.parent_locality !== s.locality && (
                          <span className="text-ink-faint">, {s.parent_locality}</span>
                        )}
                      </td>
                      {hasDistance && (
                        <td className="px-3 py-2 text-right text-ink-muted tabular-nums whitespace-nowrap">
                          {s.distance_m != null ? `${s.distance_m.toLocaleString()}m` : '—'}
                        </td>
                      )}
                      {hasInfo && (
                        <td className="px-3 py-2">
                          <div className="flex items-center justify-center gap-1.5">
                            {s.step_free && (
                              <span title="Step-free access" className="text-green-600">
                                <Accessibility className="w-3.5 h-3.5" />
                              </span>
                            )}
                            {s.facilities?.ticket_halls && (
                              <span title="Ticket hall" className="text-brand-500">
                                <Ticket className="w-3.5 h-3.5" />
                              </span>
                            )}
                            {facilityBadges.length > 0 && !s.step_free && !s.facilities?.ticket_halls && (
                              <span className="text-[10px] text-ink-faint">{facilityBadges.join(', ')}</span>
                            )}
                            {facilityBadges.length === 0 && !s.step_free && (
                              <span className="text-ink-faint text-xs">—</span>
                            )}
                          </div>
                        </td>
                      )}
                    </tr>
                    {/* Expanded destination sub-panel */}
                    {isExpanded && canExpand && (
                      <tr className={i % 2 === 0 ? 'bg-white' : 'bg-surface-warm/20'}>
                        <td colSpan={colCount} className="p-0 border-t border-divider/30">
                          <DestinationSubTable station={s} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-6 text-ink-faint text-sm">
          No {CATEGORIES.find(c => c.key === activeCategory)?.label.toLowerCase() ?? 'transport'} stops found nearby
        </div>
      )}
    </div>
  );
}
