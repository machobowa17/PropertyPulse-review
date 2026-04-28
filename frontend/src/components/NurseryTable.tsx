import { Fragment, useState, useCallback, useMemo } from 'react';
import {
  ChevronRight, ChevronDown, MapPin,
  Baby, Users,
} from 'lucide-react';

export interface NurseryRow {
  urn: string;
  name: string;
  type?: string | null;
  postcode?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  la_name?: string | null;
  ofsted_rating?: string | null;
  last_inspection?: string | null;
  max_places?: number | null;
  distance_m?: number | null;
}

export interface NurserySummary {
  total?: number;
  outstanding?: number;
  good?: number;
  requires_improvement?: number;
  inadequate?: number;
  met?: number;
  not_inspected?: number;
}

interface Props {
  nurseries: NurseryRow[];
  summary?: NurserySummary | null;
}

const OFSTED_STYLES: Record<string, { bg: string; text: string }> = {
  Outstanding:             { bg: 'bg-emerald-100', text: 'text-emerald-800' },
  Good:                    { bg: 'bg-blue-100',    text: 'text-blue-800' },
  'Requires Improvement':  { bg: 'bg-amber-100',   text: 'text-amber-800' },
  Inadequate:              { bg: 'bg-red-100',      text: 'text-red-800' },
  Met:                     { bg: 'bg-sky-100',      text: 'text-sky-800' },
};

const TYPE_LABELS: Record<string, string> = {
  'childminder':                        'Childminder',
  'childcare on non-domestic premises':  'Nursery',
  'childcare on domestic premises':      'Home Nursery',
};

const SORT_OPTIONS = [
  { key: 'distance', label: 'Distance' },
  { key: 'ofsted', label: 'Ofsted Rating' },
  { key: 'places', label: 'Places' },
  { key: 'name', label: 'Name' },
] as const;

const TYPE_FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'childcare on non-domestic premises', label: 'Nursery' },
  { key: 'childminder', label: 'Childminder' },
  { key: 'childcare on domestic premises', label: 'Home' },
] as const;

const OFSTED_RANK: Record<string, number> = {
  Outstanding: 1,
  Good: 2,
  Met: 3,
  'Requires Improvement': 4,
  Inadequate: 5,
};

function OfstedBadge({ rating }: { rating: string | null | undefined }) {
  if (!rating) return <span className="text-xs text-ink-faint">Not rated</span>;
  const style = OFSTED_STYLES[rating];
  if (!style) return <span className="text-xs text-ink-faint">{rating}</span>;
  return (
    <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium ${style.bg} ${style.text}`}>
      {rating}
    </span>
  );
}

function NurseryDetail({ nursery }: { nursery: NurseryRow }) {
  return (
    <div className="p-3 bg-surface-secondary/50 border-t border-border-base space-y-2">
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-ink-faint">Type</span>
          <p className="font-medium text-ink-base">
            {TYPE_LABELS[(nursery.type ?? '').toLowerCase()] ?? nursery.type ?? 'Unknown'}
          </p>
        </div>
        {nursery.ofsted_rating && (
          <div>
            <span className="text-ink-faint">Ofsted</span>
            <p><OfstedBadge rating={nursery.ofsted_rating} /></p>
          </div>
        )}
        {nursery.max_places != null && (
          <div>
            <span className="text-ink-faint">Max Places</span>
            <p className="font-medium text-ink-base">{nursery.max_places}</p>
          </div>
        )}
        {nursery.last_inspection && (
          <div>
            <span className="text-ink-faint">Last Inspection</span>
            <p className="font-medium text-ink-base">
              {new Date(nursery.last_inspection).toLocaleDateString('en-GB', {
                day: 'numeric', month: 'short', year: 'numeric',
              })}
            </p>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-2 pt-1 border-t border-border-base/50">
        {nursery.postcode && (
          <span className="inline-flex items-center gap-1 text-xs text-ink-muted">
            <MapPin className="w-3 h-3" /> {nursery.postcode}
          </span>
        )}
        {nursery.la_name && (
          <span className="inline-flex items-center gap-1 text-xs text-ink-muted">
            {nursery.la_name}
          </span>
        )}
      </div>
    </div>
  );
}

export default function NurseryTable({ nurseries, summary }: Props) {
  const [selectedType, setSelectedType] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('distance');
  const [expandedUrn, setExpandedUrn] = useState<string | null>(null);

  const filtered = useMemo(() => {
    let result = nurseries;
    if (selectedType !== 'all') {
      result = result.filter(n => (n.type ?? '').toLowerCase() === selectedType);
    }
    return [...result].sort((a, b) => {
      switch (sortBy) {
        case 'distance':
          return (a.distance_m ?? 99999) - (b.distance_m ?? 99999);
        case 'ofsted': {
          const ra = OFSTED_RANK[a.ofsted_rating ?? ''] ?? 9;
          const rb = OFSTED_RANK[b.ofsted_rating ?? ''] ?? 9;
          return ra - rb;
        }
        case 'places':
          return (b.max_places ?? 0) - (a.max_places ?? 0);
        case 'name':
          return a.name.localeCompare(b.name);
        default:
          return 0;
      }
    });
  }, [nurseries, selectedType, sortBy]);

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = { all: nurseries.length };
    for (const n of nurseries) {
      const t = (n.type ?? 'other').toLowerCase();
      counts[t] = (counts[t] || 0) + 1;
    }
    return counts;
  }, [nurseries]);

  const toggleExpand = useCallback((urn: string) => {
    setExpandedUrn(prev => prev === urn ? null : urn);
  }, []);

  if (!nurseries.length) {
    return (
      <div className="text-center py-6 text-sm text-ink-faint">
        No nurseries found in this area
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Summary Bar */}
      {summary && (
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="font-medium text-ink-base">{summary.total} providers</span>
          {(summary.outstanding ?? 0) > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">
              {summary.outstanding} Outstanding
            </span>
          )}
          {(summary.good ?? 0) > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-800">
              {summary.good} Good
            </span>
          )}
          {(summary.met ?? 0) > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-sky-100 text-sky-800">
              {summary.met} Met
            </span>
          )}
          {(summary.requires_improvement ?? 0) > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">
              {summary.requires_improvement} RI
            </span>
          )}
          {(summary.inadequate ?? 0) > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-800">
              {summary.inadequate} Inadequate
            </span>
          )}
        </div>
      )}

      {/* Type Filter Pills */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {TYPE_FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setSelectedType(f.key)}
            className={`shrink-0 px-2 py-1 rounded-full text-xs font-medium transition-colors ${
              selectedType === f.key
                ? 'bg-brand-primary text-white'
                : 'bg-surface-secondary text-ink-muted hover:bg-surface-tertiary'
            }`}
          >
            {f.label}
            {typeCounts[f.key] ? ` (${typeCounts[f.key]})` : ''}
          </button>
        ))}
      </div>

      {/* Sort */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-ink-faint">Sort:</span>
        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value)}
          className="text-xs bg-surface-secondary border border-border-base rounded px-1.5 py-0.5"
        >
          {SORT_OPTIONS.map(o => (
            <option key={o.key} value={o.key}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Nursery List */}
      <div className="max-h-[400px] overflow-y-auto space-y-0.5">
        {filtered.map((nursery, idx) => {
          const isExpanded = expandedUrn === nursery.urn;
          const isChildminder = (nursery.type ?? '').toLowerCase() === 'childminder';

          return (
            <Fragment key={nursery.urn}>
              <button
                onClick={() => toggleExpand(nursery.urn)}
                className={`w-full text-left px-2 py-1.5 rounded transition-colors ${
                  isExpanded ? 'bg-surface-secondary' : 'hover:bg-surface-secondary/50'
                }`}
              >
                <div className="flex items-center gap-2">
                  {/* Rank */}
                  <span className="text-xs text-ink-faint w-5 text-right shrink-0">
                    {idx + 1}
                  </span>

                  {/* Icon */}
                  <span className="shrink-0">
                    {isChildminder ? (
                      <Users className="w-3.5 h-3.5 text-pink-500" />
                    ) : (
                      <Baby className="w-3.5 h-3.5 text-teal-500" />
                    )}
                  </span>

                  {/* Name + type */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-ink-base truncate">
                      {nursery.name}
                    </p>
                    <div className="flex items-center gap-1.5 text-xs text-ink-muted">
                      <span>{TYPE_LABELS[(nursery.type ?? '').toLowerCase()] ?? nursery.type}</span>
                      {nursery.max_places != null && (
                        <span className="text-ink-faint">{nursery.max_places} places</span>
                      )}
                    </div>
                  </div>

                  {/* Ofsted Badge */}
                  <div className="shrink-0">
                    <OfstedBadge rating={nursery.ofsted_rating} />
                  </div>

                  {/* Distance */}
                  {nursery.distance_m != null && (
                    <span className="shrink-0 text-xs text-ink-faint w-12 text-right">
                      {nursery.distance_m < 1000
                        ? `${nursery.distance_m}m`
                        : `${(nursery.distance_m / 1000).toFixed(1)}km`}
                    </span>
                  )}

                  {/* Expand chevron */}
                  <span className="shrink-0 text-ink-faint">
                    {isExpanded ? (
                      <ChevronDown className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5" />
                    )}
                  </span>
                </div>
              </button>

              {isExpanded && <NurseryDetail nursery={nursery} />}
            </Fragment>
          );
        })}
      </div>

      {/* Footer */}
      <div className="text-xs text-ink-faint pt-1 border-t border-border-base">
        Showing {filtered.length} of {nurseries.length} providers
      </div>
    </div>
  );
}
