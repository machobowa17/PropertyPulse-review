import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Building2, Bus, Clock3, MapPin, Train, Wifi } from 'lucide-react';
import { fetchAreaTab } from '../api/client';
import type { AreaResponse, Metric } from '../types';

interface Props {
  sessionKey: string;
  originLabel: string;
}

type LoadState = 'idle' | 'loading' | 'ready' | 'error';

function getMetric(metrics: Metric[], id: string): Metric | undefined {
  return metrics.find((metric) => metric.id === id);
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function formatDistanceMetres(distanceM: number | null): string {
  if (distanceM === null) return 'Not available';
  if (distanceM < 1000) return `${Math.round(distanceM)} m`;
  return `${(distanceM / 1000).toFixed(1)} km`;
}

function formatPercent(value: number | null): string {
  return value === null ? 'Not available' : `${value.toFixed(1)}%`;
}

function formatScore(value: number | null): string {
  return value === null ? 'Not available' : `${value.toFixed(1)}/100`;
}

function formatSignedScoreDelta(value: number | null): string {
  if (value === null) return 'Not available';
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}`;
}

function pickStrongestSignal(items: Array<{ label: string; value: number | null }>): { label: string; value: number } | null {
  const valid = items.filter((item): item is { label: string; value: number } => item.value !== null);
  if (!valid.length) return null;
  return valid.reduce((best, current) => (current.value > best.value ? current : best));
}

function pickWeakestSignal(items: Array<{ label: string; value: number | null }>): { label: string; value: number } | null {
  const valid = items.filter((item): item is { label: string; value: number } => item.value !== null);
  if (!valid.length) return null;
  return valid.reduce((worst, current) => (current.value < worst.value ? current : worst));
}

function formatComparisonFlag(flag: string | null): string {
  if (!flag) return 'In line with the comparison area';
  if (flag === 'higher_than_parent') return 'Above the comparison area';
  if (flag === 'lower_than_parent') return 'Below the comparison area';
  return 'In line with the comparison area';
}

function formatComparisonGap(localValue: number | null, parentValue: number | null): string {
  if (localValue === null || parentValue === null) return 'Comparison not available';
  return `${formatSignedScoreDelta(localValue - parentValue)} versus comparison area`;
}

function formatStationType(code: string | null): string {
  const lookup: Record<string, string> = {
    RSE: 'rail',
    RLY: 'rail',
    RPL: 'rail',
    MET: 'Underground / metro',
    PLT: 'Underground / metro',
    TMU: 'tram',
    STR: 'tram',
  };
  if (!code) return 'station';
  return lookup[code] || 'station';
}

function buildModeSummary(modeCounts: Record<string, unknown> | null | undefined): string {
  if (!modeCounts) return 'Mode mix not available yet';
  const ordered = ['rail', 'metro', 'tram', 'bus', 'ferry']
    .map((key) => {
      const count = asNumber(modeCounts[key]);
      if (count === null || count <= 0) return null;
      return `${Math.round(count)} ${key}${count === 1 ? '' : 's'}`;
    })
    .filter(Boolean);
  return ordered.length ? ordered.join(' • ') : 'Mode mix not available yet';
}

function buildAccessSummary(metrics: Metric[]): { title: string; body: string } {
  const nearestStation = getMetric(metrics, 'nearest_station');
  const stationsInArea = getMetric(metrics, 'stations_in_area');
  const ptal = getMetric(metrics, 'ptal_score');

  if (nearestStation) {
    const details = nearestStation.details ?? {};
    const stations = Array.isArray(details.stations) ? details.stations as Array<Record<string, unknown>> : [];
    const firstStation = stations[0] ?? null;
    const stationName = asString(firstStation?.name) || 'nearest higher-capacity stop';
    const stationType = formatStationType(asString(firstStation?.type));
    const distance = getMetricHeadlineNumber(nearestStation);
    const busStops = asNumber(details.bus_stops_500m);
    const ptalBand = getMetricHeadlineString(ptal);

    return {
      title: 'Access to higher-capacity transport',
      body: `${originLabelSummaryPrefix(metrics)} ${stationName} (${stationType}) is about ${formatDistanceMetres(distance)} away. ${busStops !== null ? `${Math.round(busStops)} bus stop${busStops === 1 ? '' : 's'} fall within roughly 500 m. ` : ''}${ptalBand ? `PTAL band ${ptalBand} is available for nearby public-transport context.` : 'This phase focuses on source-backed stop access rather than modelled door-to-door journey times.'}`.trim(),
    };
  }

  if (stationsInArea) {
    const details = stationsInArea.details ?? {};
    const stationCount = getMetricHeadlineNumber(stationsInArea);
    const busStops = asNumber(details.bus_stops);
    const ptalBand = getMetricHeadlineString(ptal);
    return {
      title: 'Area-wide network access',
      body: `${originLabelSummaryPrefix(metrics)} the wider search area contains ${stationCount !== null ? Math.round(stationCount) : 'an unreported number of'} rail, metro, or tram stops. ${busStops !== null ? `${Math.round(busStops)} bus stop${busStops === 1 ? '' : 's'} are mapped inside the analysed area. ` : ''}${ptalBand ? `Where PTAL is available, the strongest local band is ${ptalBand}.` : 'For area searches, this view shows network presence across the place rather than implying a single exact origin point.'}`.trim(),
    };
  }

  return {
    title: 'Network access',
    body: 'Source-backed station and stop access data is not yet available for this search result.',
  };
}

function originLabelSummaryPrefix(metrics: Metric[]): string {
  const isArea = Boolean(getMetric(metrics, 'stations_in_area'));
  return isArea ? 'Across the analysed area,' : 'From the resolved location,';
}

function getMetricHeadlineNumber(metric: Metric | null | undefined): number | null {
  return asNumber(metric?.local_value);
}

function getMetricHeadlineString(metric: Metric | null | undefined): string | null {
  return asString(metric?.local_value);
}

function getMetricComparisonFlag(metric: Metric | null | undefined): string | null {
  return asString(metric?.comparison_flag);
}

function getMetricComparisonNumber(metric: Metric | null | undefined): number | null {
  return asNumber(metric?.parent_value);
}

export default function CommuteEstimator({ sessionKey, originLabel }: Props) {
  const [state, setState] = useState<LoadState>('idle');
  const [metrics, setMetrics] = useState<Metric[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setState('loading');
      try {
        const response: AreaResponse = await fetchAreaTab(sessionKey, 'Lifestyle & Connectivity');
        if (cancelled) return;
        setMetrics(response.metrics || []);
        setState('ready');
      } catch {
        if (cancelled) return;
        setMetrics([]);
        setState('error');
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [sessionKey]);

  const accessMetric = useMemo(() => getMetric(metrics, 'nearest_station') || getMetric(metrics, 'stations_in_area'), [metrics]);
  const ptalMetric = useMemo(() => getMetric(metrics, 'ptal_score'), [metrics]);
  const broadbandMetric = useMemo(() => getMetric(metrics, 'broadband'), [metrics]);
  const commutePatternMetric = useMemo(() => getMetric(metrics, 'commute_distance'), [metrics]);
  const commuterConnectivityMetric = useMemo(() => getMetric(metrics, 'commuter_connectivity'), [metrics]);

  const accessSummary = useMemo(() => buildAccessSummary(metrics), [metrics]);

  const modeMix = useMemo(() => {
    if (!accessMetric?.details || typeof accessMetric.details !== 'object') return 'Mode mix not available yet';
    return buildModeSummary((accessMetric.details as Record<string, unknown>).mode_counts as Record<string, unknown> | undefined);
  }, [accessMetric]);

  const stationNames = useMemo(() => {
    if (!accessMetric?.details || typeof accessMetric.details !== 'object') return [] as string[];
    const stations = (accessMetric.details as Record<string, unknown>).stations;
    if (!Array.isArray(stations)) return [] as string[];
    return stations
      .map((item) => (item && typeof item === 'object' ? asString((item as Record<string, unknown>).name) : null))
      .filter((value): value is string => Boolean(value))
      .slice(0, 4);
  }, [accessMetric]);

  const ptalSummary = useMemo(() => {
    if (!ptalMetric) {
      return 'PTAL is not available for this search geography, so the panel falls back to stop and station access signals.';
    }
    const details = ptalMetric.details ?? {};
    const band = getMetricHeadlineString(ptalMetric);
    const ptai = asNumber(details.ptai_score);
    const busStops640 = asNumber(details.bus_stops_640m);
    const heavyStops960 = asNumber(details.heavy_stops_960m);
    const fragments = [
      band ? `PTAL band ${band}` : null,
      ptai !== null ? `PTAI ${ptai.toFixed(1)}` : null,
      busStops640 !== null ? `${Math.round(busStops640)} bus stops within 640 m` : null,
      heavyStops960 !== null ? `${Math.round(heavyStops960)} heavier-capacity stops within 960 m` : null,
    ].filter(Boolean);
    return fragments.length ? fragments.join(' • ') : 'PTAL is available but detailed components are not populated for this area.';
  }, [ptalMetric]);

  const commutePatternSummary = useMemo(() => {
    if (!commutePatternMetric) {
      return 'Census commute-pattern context is not available for this search result.';
    }
    const details = commutePatternMetric.details ?? {};
    const wfh = asNumber(details.pct_wfh) ?? getMetricHeadlineNumber(commutePatternMetric);
    const shortTrips = asNumber(details.pct_lt2km);
    const mediumTrips = asNumber(details.pct_2_10km);
    const longerTrips = asNumber(details.pct_10_30km);
    const longTrips = asNumber(details.pct_30plus);
    const parts = [
      wfh !== null ? `${formatPercent(wfh)} mainly work from home` : null,
      shortTrips !== null ? `${formatPercent(shortTrips)} commute under 2 km` : null,
      mediumTrips !== null ? `${formatPercent(mediumTrips)} commute 2–10 km` : null,
      longerTrips !== null ? `${formatPercent(longerTrips)} commute 10–30 km` : null,
      longTrips !== null ? `${formatPercent(longTrips)} commute 30 km+` : null,
    ].filter(Boolean);
    return parts.length ? parts.join(' • ') : 'Commute-pattern detail is not populated yet.';
  }, [commutePatternMetric]);

  const commuterConnectivitySummary = useMemo(() => {
    if (!commuterConnectivityMetric) {
      return 'Official DfT destination-reach context is not available for this search result yet.';
    }
    const details = commuterConnectivityMetric.details ?? {};
    const overall = getMetricHeadlineNumber(commuterConnectivityMetric);
    const publicTransport = asNumber(details.overall_public_transport);
    const walking = asNumber(details.overall_walking);
    const cycling = asNumber(details.overall_cycling);
    const driving = asNumber(details.overall_driving);
    const employment = asNumber(details.employment_overall);
    const education = asNumber(details.education_overall);
    const healthcare = asNumber(details.healthcare_overall);

    const strongestMode = pickStrongestSignal([
      { label: 'public transport', value: publicTransport },
      { label: 'walking', value: walking },
      { label: 'cycling', value: cycling },
      { label: 'driving', value: driving },
    ]);
    const weakestMode = pickWeakestSignal([
      { label: 'public transport', value: publicTransport },
      { label: 'walking', value: walking },
      { label: 'cycling', value: cycling },
      { label: 'driving', value: driving },
    ]);
    const strongestDestination = pickStrongestSignal([
      { label: 'employment', value: employment },
      { label: 'education', value: education },
      { label: 'healthcare', value: healthcare },
    ]);

    const parts = [
      overall !== null ? `Overall official DfT connectivity is ${formatScore(overall)}.` : null,
      strongestMode ? `The strongest mode in this area is ${strongestMode.label} at ${strongestMode.value.toFixed(1)}.` : null,
      weakestMode ? `The weakest mode is ${weakestMode.label} at ${weakestMode.value.toFixed(1)}.` : null,
      strongestDestination ? `Destination reach is strongest for ${strongestDestination.label} at ${strongestDestination.value.toFixed(1)}.` : null,
    ].filter(Boolean);

    return parts.length ? parts.join(' ') : 'Official DfT destination-reach context is available but detailed components are not populated yet.';
  }, [commuterConnectivityMetric]);

  const commuterConnectivityMeta = useMemo(() => {
    if (!commuterConnectivityMetric) return [] as string[];
    const details = commuterConnectivityMetric.details ?? {};
    const sourceRelease = asString(details.source_release);
    const comparisonFlag = getMetricComparisonFlag(commuterConnectivityMetric);
    const localValue = getMetricHeadlineNumber(commuterConnectivityMetric);
    const parentValue = getMetricComparisonNumber(commuterConnectivityMetric);
    return [
      sourceRelease ? sourceRelease : null,
      comparisonFlag ? formatComparisonFlag(comparisonFlag) : null,
      localValue !== null && parentValue !== null ? formatComparisonGap(localValue, parentValue) : null,
    ].filter((item): item is string => Boolean(item));
  }, [commuterConnectivityMetric]);

  const broadbandSummary = useMemo(() => {
    if (!broadbandMetric) {
      return 'Broadband context not available.';
    }
    const details = broadbandMetric.details ?? {};
    const gigabit = asNumber(details.gigabit_pct) ?? getMetricHeadlineNumber(broadbandMetric);
    const fullFibre = asNumber(details.full_fibre_pct);
    const superfast = asNumber(details.superfast_pct);
    const parts = [
      gigabit !== null ? `${formatPercent(gigabit)} gigabit-capable` : null,
      fullFibre !== null ? `${formatPercent(fullFibre)} full fibre` : null,
      superfast !== null ? `${formatPercent(superfast)} superfast` : null,
    ].filter(Boolean);
    return parts.length ? parts.join(' • ') : 'Broadband context not available.';
  }, [broadbandMetric]);

  if (state === 'loading' || state === 'idle') {
    return (
      <div className="bg-surface rounded-xl p-4 space-y-3 mt-2">
        <div className="text-sm font-semibold text-ink">Commuter Connectivity</div>
        <div className="text-xs text-ink-muted">Loading source-backed movement evidence for {originLabel}…</div>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div className="bg-surface rounded-xl p-4 space-y-3 mt-2">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 rounded-full bg-amber-100 p-2 text-amber-700">
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div className="space-y-1">
            <h4 className="text-sm font-semibold text-ink">Commuter connectivity unavailable</h4>
            <p className="text-xs text-ink-muted">
              The source-backed movement panel could not load for <span className="font-semibold text-ink">{originLabel}</span>.
            </p>
            <p className="text-xs text-ink-muted">
              Use the wider Lifestyle rows as the primary transport evidence for now while this supporting panel reloads.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface rounded-xl p-4 space-y-4 mt-2">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-ink">Commuter Connectivity</h4>
          <p className="mt-1 text-xs text-ink-muted">
            Use this panel to judge how easy everyday movement is around <span className="font-semibold text-ink">{originLabel}</span>. It brings together source-backed network access,
            PTAL where available, observed commute patterns, broadband fallback, and official DfT destination-reach context. It does <span className="font-semibold text-ink">not</span>{' '}
            claim a bespoke door-to-door journey time for a specific person or employer.
          </p>
        </div>
        <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-700">
          Official DfT context
        </span>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-divider bg-white p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-faint">
            <MapPin className="h-4 w-4 text-brand-600" />
            Joining the transport network
          </div>
          <div className="mt-2 text-sm font-semibold text-ink">{accessSummary.title}</div>
          <p className="mt-1 text-xs leading-relaxed text-ink-muted">{accessSummary.body}</p>
          {stationNames.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {stationNames.map((name) => (
                <span key={name} className="inline-flex items-center rounded-full border border-divider bg-surface px-2.5 py-1 text-[11px] text-ink-muted">
                  {name}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-divider bg-white p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-faint">
            <Train className="h-4 w-4 text-brand-600" />
            Modes available nearby
          </div>
          <div className="mt-2 text-sm font-semibold text-ink">Local transport mix</div>
          <p className="mt-1 text-xs leading-relaxed text-ink-muted">{modeMix}</p>
          <div className="mt-3 rounded-lg bg-surface px-3 py-2 text-[11px] text-ink-muted">
            Read this as a network-readiness check: it shows whether daily movement starts from a thin or well-supported local transport base before any future destination-specific layer is considered.
          </div>
        </div>

        <div className="rounded-xl border border-divider bg-white p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-faint">
            <Bus className="h-4 w-4 text-brand-600" />
            Public-transport context
          </div>
          <div className="mt-2 text-sm font-semibold text-ink">Accessibility context</div>
          <p className="mt-1 text-xs leading-relaxed text-ink-muted">{ptalSummary}</p>
          <div className="mt-3 text-[11px] text-ink-faint">
            Where PTAL exists, it gives a stronger public-transport accessibility signal. Outside those areas, the panel leans more heavily on station, stop, and mode-presence evidence.
          </div>
        </div>

        <div className="rounded-xl border border-divider bg-white p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-faint">
            <Clock3 className="h-4 w-4 text-brand-600" />
            Existing travel patterns
          </div>
          <div className="mt-2 text-sm font-semibold text-ink">Observed commute mix</div>
          <p className="mt-1 text-xs leading-relaxed text-ink-muted">{commutePatternSummary}</p>
          <div className="mt-3 flex items-start gap-2 rounded-lg bg-surface px-3 py-2 text-[11px] text-ink-muted">
            <Building2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" />
            <span>
              This is contextual evidence about how residents in the area tend to travel or work from home. It helps frame likely movement habits, but it is not a personalised route planner.
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-divider bg-white p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-faint">
            <Building2 className="h-4 w-4 text-brand-600" />
            Official destination reach
          </div>
          <div className="mt-2 text-sm font-semibold text-ink">Official DfT structural connectivity</div>
          <p className="mt-1 text-xs leading-relaxed text-ink-muted">{commuterConnectivitySummary}</p>
          {commuterConnectivityMeta.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {commuterConnectivityMeta.map((item) => (
                <span key={item} className="inline-flex items-center rounded-full border border-divider bg-surface px-2.5 py-1 text-[11px] text-ink-muted">
                  {item}
                </span>
              ))}
            </div>
          )}
          <div className="mt-3 rounded-lg bg-surface px-3 py-2 text-[11px] text-ink-muted">
            Use this as structural evidence about how well the area connects to employment and everyday destinations overall. It complements the local stop-and-station picture without implying a guaranteed trip time to a named destination.
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-divider bg-white p-3">
        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-faint">
          <Wifi className="h-4 w-4 text-brand-600" />
          Remote-work fallback
        </div>
        <p className="mt-2 text-xs leading-relaxed text-ink-muted">
          {broadbandSummary} This matters because everyday practicality is not only about travel; strong digital coverage can soften commuting pressure when hybrid or remote working is realistic.
        </p>
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-3 text-[11px] leading-relaxed text-amber-900">
        <div className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            A later phase can still add structured reach to named commuter hubs if a defensible source is verified. For now, this panel stays inside source-backed evidence only: local network access, observed commute patterns, and official DfT area-level destination reach rather than guessed personal trip times.
          </span>
        </div>
      </div>
    </div>
  );
}
