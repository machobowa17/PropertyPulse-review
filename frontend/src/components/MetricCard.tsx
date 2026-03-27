import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronRight, TrendingUp, TrendingDown, Minus,
  PoundSterling, BarChart3, Activity, Scale, Building2, Home,
  Percent, Building, MapPin, Train, Zap, Wifi, Droplets, Wind,
  Cloud, Volume2, TreePine, Flame, Users, Clock, Heart, Key,
  LayoutGrid, GraduationCap, School, BarChart2, Stethoscope,
  Receipt, Landmark, Ruler, Wallet, Award, Sprout, Timer,
  TrainFront, Bike, Smartphone, Sparkles, Vote, Droplet,
  ShieldCheck, ShieldAlert, Coffee,
} from 'lucide-react';
import type { Metric, PersonaId } from '../types';
import { formatValue, METRIC_ICONS } from '../utils/tabs';
import { getTakeaway } from '../utils/personas';

const ICON_MAP: Record<string, React.ElementType> = {
  PoundSterling, BarChart3, Activity, Scale, Building2, Home,
  Percent, Building, MapPin, Train, Zap, Wifi, Droplets, Wind,
  Cloud, Volume2, TreePine, Flame, Users, Clock, Heart, Key,
  LayoutGrid, GraduationCap, School, BarChart2, Stethoscope,
  Receipt, Landmark, TrendingUp, TrendingDown, Ruler, Wallet,
  Award, Sprout, Timer, TrainFront, Bike, Smartphone, Sparkles,
  Vote, Droplet, ShieldCheck, ShieldAlert, Coffee,
};

export const COLOUR_STYLES = {
  green: { bg: 'bg-signal-green-bg', text: 'text-signal-green', border: 'border-signal-green/20' },
  amber: { bg: 'bg-signal-amber-bg', text: 'text-signal-amber', border: 'border-signal-amber/20' },
  red: { bg: 'bg-signal-red-bg', text: 'text-signal-red', border: 'border-signal-red/20' },
  neutral: { bg: 'bg-surface', text: 'text-ink-muted', border: 'border-divider' },
};

interface Props {
  metric: Metric;
  persona: PersonaId;
  parentName: string;
}

export default function MetricCard({ metric, persona, parentName }: Props) {
  const [expanded, setExpanded] = useState(false);
  const takeaway = getTakeaway(metric, persona);
  const colours = COLOUR_STYLES[takeaway.colour];
  const iconName = METRIC_ICONS[metric.id] || 'BarChart3';
  const Icon = ICON_MAP[iconName] || BarChart3;
  const hasDetails = metric.details && Object.keys(metric.details).length > 0;

  const ComparisonIcon = metric.comparison_flag === 'higher_than_parent'
    ? TrendingUp
    : metric.comparison_flag === 'lower_than_parent'
    ? TrendingDown
    : Minus;

  return (
    <div
      className={`
        rounded-2xl bg-white border transition-all duration-200
        ${expanded ? 'shadow-md border-brand-200' : 'shadow-sm border-divider hover:shadow-md'}
      `}
    >
      {/* ═══ DESKTOP: Table Row (Bible 6.2.1: Metric | Local | Parent | So What | Watch Out) ═══ */}
      <button
        onClick={() => hasDetails && setExpanded(!expanded)}
        className="w-full text-left cursor-pointer group hidden lg:grid lg:grid-cols-[2fr_1fr_1fr_1fr_1fr_28px] lg:items-center lg:gap-4 lg:px-5 lg:py-3.5"
      >
        {/* Metric */}
        <div className="flex items-center gap-3 min-w-0">
          <div className={`shrink-0 w-9 h-9 rounded-lg flex items-center justify-center ${colours.bg}`}>
            <Icon className={`w-4.5 h-4.5 ${colours.text}`} />
          </div>
          <span className="text-sm font-semibold text-ink truncate">{metric.name}</span>
        </div>

        {/* Local */}
        <div className="text-base font-bold text-ink tracking-tight">
          {formatValue(metric.local_value, metric.unit)}
        </div>

        {/* Parent */}
        <div className="flex items-center gap-1.5 text-sm text-ink-faint">
          {metric.parent_value !== null ? (
            <>
              <ComparisonIcon className="w-3.5 h-3.5 shrink-0" />
              {formatValue(metric.parent_value, metric.unit)}
            </>
          ) : (
            <span className="text-ink-faint/50">&mdash;</span>
          )}
        </div>

        {/* So What */}
        <div>
          {takeaway.soWhat ? (
            <span className={`inline-block px-2.5 py-1 rounded-lg text-xs font-medium ${colours.bg} ${colours.text} border ${colours.border}`}>
              {takeaway.soWhat}
            </span>
          ) : (
            <span className="text-ink-faint/50">&mdash;</span>
          )}
        </div>

        {/* Watch Out */}
        <div>
          {takeaway.watchOut && takeaway.watchOut !== 'None' ? (
            <span className="inline-block px-2.5 py-1 rounded-lg text-xs font-medium bg-surface text-ink-muted border border-divider">
              {takeaway.watchOut}
            </span>
          ) : (
            <span className="text-xs text-ink-faint/50">&mdash;</span>
          )}
        </div>

        {/* Chevron */}
        {hasDetails ? (
          <ChevronRight
            className={`w-4 h-4 text-ink-faint shrink-0 transition-transform duration-200
                        ${expanded ? 'rotate-90' : 'group-hover:translate-x-0.5'}`}
          />
        ) : <div className="w-4" />}
      </button>

      {/* ═══ MOBILE: Card Layout ═══ */}
      <button
        onClick={() => hasDetails && setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-4 text-left cursor-pointer group lg:hidden"
      >
        <div className={`shrink-0 w-10 h-10 rounded-xl flex items-center justify-center ${colours.bg}`}>
          <Icon className={`w-5 h-5 ${colours.text}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-ink truncate">{metric.name}</div>
          <div className="flex items-baseline gap-2 mt-0.5">
            <span className="text-xl font-bold text-ink tracking-tight">
              {formatValue(metric.local_value, metric.unit)}
            </span>
            {metric.parent_value !== null && (
              <span className="flex items-center gap-1 text-xs text-ink-faint">
                <ComparisonIcon className="w-3 h-3" />
                {formatValue(metric.parent_value, metric.unit)}
                <span className="hidden sm:inline opacity-60">({parentName})</span>
              </span>
            )}
          </div>
        </div>
        {hasDetails && (
          <ChevronRight
            className={`w-4 h-4 text-ink-faint shrink-0 transition-transform duration-200
                        ${expanded ? 'rotate-90' : 'group-hover:translate-x-0.5'}`}
          />
        )}
      </button>

      {/* Mobile takeaway pills */}
      {takeaway.soWhat && (
        <div className="lg:hidden flex flex-wrap gap-2 px-4 pb-3 -mt-1">
          <div className={`px-3 py-1 rounded-lg text-xs font-medium ${colours.bg} ${colours.text} border ${colours.border}`}>
            {takeaway.soWhat}
          </div>
          {takeaway.watchOut && takeaway.watchOut !== 'None' && (
            <div className="px-3 py-1 rounded-lg text-xs font-medium bg-surface text-ink-muted border border-divider">
              {takeaway.watchOut}
            </div>
          )}
        </div>
      )}

      {/* ═══ Expanded details (shared) ═══ */}
      <AnimatePresence>
        {expanded && metric.details && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 lg:px-5 pb-4 pt-1 border-t border-divider">
              <DetailsRenderer details={metric.details} unit={metric.unit} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Render details object as sub-rows or list */
function DetailsRenderer({ details, unit }: { details: Record<string, unknown>; unit: string }) {
  if (Array.isArray(details.schools)) {
    return (
      <div className="space-y-2 mt-2">
        {(details.schools as Record<string, unknown>[]).map((s, i) => (
          <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl bg-surface">
            <div className="w-7 h-7 rounded-lg bg-brand-50 flex items-center justify-center text-xs font-bold text-brand-600">
              {i + 1}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-ink truncate">{String(s.name)}</div>
              <div className="flex flex-wrap gap-2 mt-0.5">
                {s.ofsted ? <span className="text-xs px-1.5 py-0.5 rounded bg-brand-50 text-brand-700">{String(s.ofsted)}</span> : null}
                {s.distance_m != null && <span className="text-xs text-ink-faint">{Number(s.distance_m).toLocaleString()}m</span>}
                {s.ks2_reading != null && <span className="text-xs text-ink-muted">Reading: {Number(s.ks2_reading).toFixed(1)}</span>}
                {s.ks2_maths != null && <span className="text-xs text-ink-muted">Maths: {Number(s.ks2_maths).toFixed(1)}</span>}
                {s.progress_8 != null && <span className="text-xs text-ink-muted">P8: {Number(s.progress_8).toFixed(2)}</span>}
                {s.attainment_8 != null && <span className="text-xs text-ink-muted">A8: {Number(s.attainment_8).toFixed(1)}</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (Array.isArray(details.stations)) {
    return (
      <div className="space-y-2 mt-2">
        {(details.stations as Record<string, unknown>[]).map((s, i) => (
          <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl bg-surface">
            <Train className="w-4 h-4 text-ink-faint shrink-0" />
            <span className="text-sm text-ink flex-1 truncate">{String(s.name)}</span>
            <span className="text-xs text-ink-muted shrink-0">{Number(s.distance_m).toLocaleString()}m</span>
          </div>
        ))}
        {details.bus_stops_500m != null && (
          <div className="text-xs text-ink-muted mt-1">Bus stops within 500m: {String(details.bus_stops_500m)}</div>
        )}
      </div>
    );
  }

  const entries = Object.entries(details).filter(([, v]) => v !== null && v !== undefined);
  if (entries.length === 0) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 mt-2">
      {entries.map(([key, value]) => {
        if (typeof value === 'object') return null;
        const label = key.replace(/_/g, ' ').replace(/pct /g, '% ').replace(/^(.)/, (c) => c.toUpperCase());
        const isGbp = unit === 'GBP' || unit === 'GBP/year' || unit === 'GBP/month';
        const display = typeof value === 'number'
          ? isGbp
            ? '£' + value.toLocaleString('en-GB', { maximumFractionDigits: 0 })
            : typeof value === 'number' && String(key).includes('pct')
            ? value.toFixed(1) + '%'
            : value.toLocaleString('en-GB', { maximumFractionDigits: 1 })
          : typeof value === 'boolean'
          ? value ? 'Yes' : 'No'
          : String(value);

        return (
          <div key={key} className="p-2.5 rounded-xl bg-surface">
            <div className="text-[11px] text-ink-faint uppercase tracking-wide font-medium">{label}</div>
            <div className="text-sm font-semibold text-ink mt-0.5">{display}</div>
          </div>
        );
      })}
    </div>
  );
}
