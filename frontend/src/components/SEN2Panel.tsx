/**
 * SEN2Panel — SEND EHCP Assessment details for a local authority.
 *
 * Shows timeliness gauge, refusal rate, tribunal data, placement breakdown,
 * and primary need breakdown with national averages for comparison.
 */

interface SEN2Details {
  la_name?: string;
  year?: string;
  quality?: 'good' | 'average' | 'poor' | null;
  // Timeliness
  pct_within_20wk?: number | null;
  nat_pct_within_20wk?: number | null;
  plans_issued_total?: number | null;
  plans_issued_within_20wk?: number | null;
  plans_issued_20wk_to_1yr?: number | null;
  plans_issued_over_1yr?: number | null;
  // Refusal
  requests_received?: number | null;
  requests_refused?: number | null;
  pct_refused?: number | null;
  nat_pct_refused?: number | null;
  // Tribunal
  tribunal_on_request?: number | null;
  tribunal_on_assessment?: number | null;
  tribunal_other?: number | null;
  mediation_on_request?: number | null;
  // Assessment outcomes
  pct_plan_issued?: number | null;
  nat_pct_plan_issued?: number | null;
  // Caseload
  total_ehcps?: number | null;
  mainstream_pct?: number | null;
  special_pct?: number | null;
  nat_mainstream_pct?: number | null;
  nat_special_pct?: number | null;
  // Primary need
  need_asd_pct?: number | null;
  need_slcn_pct?: number | null;
  need_semh_pct?: number | null;
  need_mld_pct?: number | null;
  need_sld_pct?: number | null;
  need_pmld_pct?: number | null;
  need_spld_pct?: number | null;
  need_pd_pct?: number | null;
  need_hi_pct?: number | null;
  need_vi_pct?: number | null;
  nat_need_asd_pct?: number | null;
  nat_need_slcn_pct?: number | null;
  nat_need_semh_pct?: number | null;
}

const QUALITY_COLOURS: Record<string, { bg: string; text: string; label: string }> = {
  good: { bg: 'bg-emerald-50', text: 'text-emerald-700', label: 'Above average' },
  average: { bg: 'bg-amber-50', text: 'text-amber-700', label: 'Around average' },
  poor: { bg: 'bg-red-50', text: 'text-red-700', label: 'Below average' },
};

function GaugeBar({ value, national, label, higherIsBetter = true }: {
  value: number | null | undefined;
  national: number | null | undefined;
  label: string;
  higherIsBetter?: boolean;
}) {
  if (value == null) return null;
  const pct = Math.min(100, Math.max(0, value));
  const isGood = higherIsBetter ? (national != null && value >= national) : (national != null && value <= national);
  const barColour = isGood ? 'bg-emerald-500' : 'bg-amber-500';

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-ink-muted">{label}</span>
        <span className="font-semibold text-ink">{value.toFixed(1)}%</span>
      </div>
      <div className="h-2 bg-ink-faint/20 rounded-full overflow-hidden relative">
        <div className={`h-full rounded-full ${barColour}`} style={{ width: `${pct}%` }} />
        {national != null && (
          <div
            className="absolute top-0 h-full w-0.5 bg-ink/60"
            style={{ left: `${Math.min(100, Math.max(0, national))}%` }}
            title={`National avg: ${national.toFixed(1)}%`}
          />
        )}
      </div>
      {national != null && (
        <div className="text-[10px] text-ink-faint">National avg: {national.toFixed(1)}%</div>
      )}
    </div>
  );
}

function NeedBar({ label, pct, national }: { label: string; pct: number | null | undefined; national?: number | null }) {
  if (pct == null) return null;
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 text-[11px] text-ink-muted truncate" title={label}>{label}</span>
      <div className="flex-1 h-1.5 bg-ink-faint/20 rounded-full overflow-hidden relative">
        <div className="h-full rounded-full bg-indigo-400" style={{ width: `${Math.min(100, pct)}%` }} />
        {national != null && (
          <div className="absolute top-0 h-full w-0.5 bg-ink/50" style={{ left: `${Math.min(100, national)}%` }} />
        )}
      </div>
      <span className="w-10 text-right text-[11px] font-medium text-ink">{pct.toFixed(1)}%</span>
    </div>
  );
}

export default function SEN2Panel({ details }: { details: SEN2Details }) {
  const d = details;
  const q = d.quality ? QUALITY_COLOURS[d.quality] : null;

  const totalTribunals = (d.tribunal_on_request ?? 0) + (d.tribunal_on_assessment ?? 0) + (d.tribunal_other ?? 0);

  return (
    <div className="space-y-4 mt-2">
      {/* Quality badge */}
      {q && (
        <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${q.bg} ${q.text}`}>
          {d.quality === 'good' ? '●' : d.quality === 'poor' ? '●' : '●'} {q.label} for EHCP timeliness
        </div>
      )}

      {/* Timeliness gauge */}
      <GaugeBar
        value={d.pct_within_20wk}
        national={d.nat_pct_within_20wk}
        label="Plans issued within 20 weeks"
        higherIsBetter={true}
      />

      {/* Timeliness breakdown */}
      {d.plans_issued_total != null && (
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="p-2 rounded-lg bg-emerald-50/50">
            <div className="text-sm font-bold text-emerald-700">{d.plans_issued_within_20wk?.toLocaleString() ?? '—'}</div>
            <div className="text-[10px] text-emerald-600">Within 20 wks</div>
          </div>
          <div className="p-2 rounded-lg bg-amber-50/50">
            <div className="text-sm font-bold text-amber-700">{d.plans_issued_20wk_to_1yr?.toLocaleString() ?? '—'}</div>
            <div className="text-[10px] text-amber-600">20 wks – 1 yr</div>
          </div>
          <div className="p-2 rounded-lg bg-red-50/50">
            <div className="text-sm font-bold text-red-700">{d.plans_issued_over_1yr?.toLocaleString() ?? '—'}</div>
            <div className="text-[10px] text-red-600">Over 1 year</div>
          </div>
        </div>
      )}

      {/* Refusal rate */}
      <GaugeBar
        value={d.pct_refused}
        national={d.nat_pct_refused}
        label="Assessment requests refused"
        higherIsBetter={false}
      />

      {/* Key stats row */}
      <div className="grid grid-cols-2 gap-3">
        {d.total_ehcps != null && (
          <div className="p-2 rounded-lg bg-surface border border-ink-faint/10">
            <div className="text-lg font-bold text-ink">{d.total_ehcps.toLocaleString()}</div>
            <div className="text-[10px] text-ink-muted">Active EHCPs</div>
          </div>
        )}
        {totalTribunals > 0 && (
          <div className="p-2 rounded-lg bg-surface border border-ink-faint/10">
            <div className="text-lg font-bold text-ink">{totalTribunals}</div>
            <div className="text-[10px] text-ink-muted">Tribunal appeals ({d.year})</div>
          </div>
        )}
        {d.pct_plan_issued != null && (
          <div className="p-2 rounded-lg bg-surface border border-ink-faint/10">
            <div className="text-lg font-bold text-ink">{d.pct_plan_issued.toFixed(1)}%</div>
            <div className="text-[10px] text-ink-muted">
              Assessments → plan issued
              {d.nat_pct_plan_issued != null && <span className="text-ink-faint"> (nat: {d.nat_pct_plan_issued.toFixed(1)}%)</span>}
            </div>
          </div>
        )}
        {d.mediation_on_request != null && d.mediation_on_request > 0 && (
          <div className="p-2 rounded-lg bg-surface border border-ink-faint/10">
            <div className="text-lg font-bold text-ink">{d.mediation_on_request}</div>
            <div className="text-[10px] text-ink-muted">Mediations ({d.year})</div>
          </div>
        )}
      </div>

      {/* Placement breakdown */}
      {(d.mainstream_pct != null || d.special_pct != null) && (
        <div>
          <div className="text-xs font-semibold text-ink-muted mb-1.5">Placement type</div>
          <div className="flex h-5 rounded-full overflow-hidden">
            {d.mainstream_pct != null && <div className="bg-blue-400" style={{ width: `${d.mainstream_pct}%` }} title={`Mainstream: ${d.mainstream_pct}%`} />}
            {d.special_pct != null && <div className="bg-purple-400" style={{ width: `${d.special_pct}%` }} title={`Special: ${d.special_pct}%`} />}
            {d.mainstream_pct != null && d.special_pct != null && (
              <div className="bg-ink-faint/30 flex-1" title="Other (AP, FE, EHE, etc.)" />
            )}
          </div>
          <div className="flex justify-between mt-1 text-[10px] text-ink-muted">
            <span>
              <span className="inline-block w-2 h-2 rounded-full bg-blue-400 mr-1" />
              Mainstream {d.mainstream_pct?.toFixed(0)}%
              {d.nat_mainstream_pct != null && <span className="text-ink-faint"> (nat: {d.nat_mainstream_pct.toFixed(0)}%)</span>}
            </span>
            <span>
              <span className="inline-block w-2 h-2 rounded-full bg-purple-400 mr-1" />
              Special {d.special_pct?.toFixed(0)}%
              {d.nat_special_pct != null && <span className="text-ink-faint"> (nat: {d.nat_special_pct.toFixed(0)}%)</span>}
            </span>
          </div>
        </div>
      )}

      {/* Primary need breakdown */}
      {d.need_asd_pct != null && (
        <div>
          <div className="text-xs font-semibold text-ink-muted mb-1.5">Primary need</div>
          <div className="space-y-1">
            <NeedBar label="ASD" pct={d.need_asd_pct} national={d.nat_need_asd_pct} />
            <NeedBar label="SLCN" pct={d.need_slcn_pct} national={d.nat_need_slcn_pct} />
            <NeedBar label="SEMH" pct={d.need_semh_pct} national={d.nat_need_semh_pct} />
            <NeedBar label="MLD" pct={d.need_mld_pct} />
            <NeedBar label="SLD" pct={d.need_sld_pct} />
            <NeedBar label="PMLD" pct={d.need_pmld_pct} />
            <NeedBar label="SpLD" pct={d.need_spld_pct} />
            <NeedBar label="PD" pct={d.need_pd_pct} />
            <NeedBar label="HI" pct={d.need_hi_pct} />
            <NeedBar label="VI" pct={d.need_vi_pct} />
          </div>
        </div>
      )}

      {/* Source note */}
      <div className="text-[10px] text-ink-faint pt-1 border-t border-ink-faint/10">
        Source: DfE SEN2 returns ({d.year}). Covers {d.la_name ?? 'this LA'}. National averages shown as markers on bars.
      </div>
    </div>
  );
}
