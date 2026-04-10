import type { Metric } from '../types';

interface SectionSummary {
  headline: string;
  aboveCount: number;
  belowCount: number;
  equalCount: number;
  comparableCount: number;
  totalCount: number;
  priorityMetricIds: string[];
}

export function buildSectionSummary(metrics: Metric[], parentName: string): SectionSummary {
  let above = 0;
  let below = 0;
  let equal = 0;
  const priorityIds: string[] = [];

  for (const m of metrics) {
    if (m.comparison_status !== 'comparable' || m.comparison_flag === null) continue;
    if (m.comparison_flag === 'higher_than_parent') above++;
    else if (m.comparison_flag === 'lower_than_parent') below++;
    else equal++;
  }

  const comparable = above + below + equal;

  // Priority: metrics furthest from parent (either direction)
  const scored = metrics
    .filter((m) => m.comparison_status === 'comparable' && m.comparison_flag !== null)
    .map((m) => {
      const l = typeof m.local_value === 'number' ? m.local_value : 0;
      const p = typeof m.parent_value === 'number' ? m.parent_value : 0;
      const diff = p !== 0 ? Math.abs((l - p) / p) : 0;
      return { id: m.id, diff };
    })
    .sort((a, b) => b.diff - a.diff);
  for (const s of scored.slice(0, 3)) {
    priorityIds.push(s.id);
  }

  let headline: string;
  if (comparable === 0) {
    headline = `${metrics.length} metrics available`;
  } else {
    const parts: string[] = [];
    if (above > 0) parts.push(`${above} above`);
    if (below > 0) parts.push(`${below} below`);
    if (equal > 0) parts.push(`${equal} equal to`);
    headline = `${parts.join(', ')} ${parentName} average`;
  }

  return {
    headline,
    aboveCount: above,
    belowCount: below,
    equalCount: equal,
    comparableCount: comparable,
    totalCount: metrics.length,
    priorityMetricIds: priorityIds,
  };
}
