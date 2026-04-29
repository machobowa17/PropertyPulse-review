import { Flame, Zap, Droplet, Building2, Wind, Sun, Fuel } from 'lucide-react';

interface Props {
  avgCo2?: number | null;
  avgEnergyKwh?: number | null;
  avgHeatingCost?: number | null;
  avgHotwaterCost?: number | null;
  avgLightingCost?: number | null;
  heatGasPct?: number | null;
  heatElectricPct?: number | null;
  heatOilPct?: number | null;
  heatDistrictPct?: number | null;
  heatOtherPct?: number | null;
  heatNonePct?: number | null;
  pctMainsGas?: number | null;
  pctSolar?: number | null;
  agePre1900Pct?: number | null;
  age1900_1929Pct?: number | null;
  age1930_1949Pct?: number | null;
  age1950_1966Pct?: number | null;
  age1967_1982Pct?: number | null;
  age1983_2002Pct?: number | null;
  agePost2002Pct?: number | null;
  // D21: Glazing & insulation
  windowsGoodPct?: number | null;
  windowsVpoorPct?: number | null;
  windowsPoorPct?: number | null;
  windowsAvgPct?: number | null;
  wallsGoodPct?: number | null;
  wallsVpoorPct?: number | null;
  roofGoodPct?: number | null;
  roofVpoorPct?: number | null;
  glazeSinglePct?: number | null;
  glazeDoublePct?: number | null;
  glazeTriplePct?: number | null;
  avgMultiGlazePct?: number | null;
  // D22: Built form
  formDetachedPct?: number | null;
  formSemiPct?: number | null;
  formTerracePct?: number | null;
  formEndTerracePct?: number | null;
  enhanced?: boolean;
}

const HEAT_ITEMS = [
  { key: 'gas', label: 'Gas', icon: Flame, colour: '#2563eb' },
  { key: 'electric', label: 'Electric', icon: Zap, colour: '#7c3aed' },
  { key: 'oil', label: 'Oil', icon: Droplet, colour: '#ea580c' },
  { key: 'district', label: 'District', icon: Building2, colour: '#0891b2' },
  { key: 'other', label: 'Other', icon: Wind, colour: '#6b7280' },
] as const;

const AGE_BANDS = [
  { key: 'pre1900', label: 'Pre-1900', colour: '#7c2d12' },
  { key: '1900_1929', label: '1900–29', colour: '#9a3412' },
  { key: '1930_1949', label: '1930–49', colour: '#c2410c' },
  { key: '1950_1966', label: '1950–66', colour: '#ea580c' },
  { key: '1967_1982', label: '1967–82', colour: '#f59e0b' },
  { key: '1983_2002', label: '1983–02', colour: '#84cc16' },
  { key: 'post2002', label: 'Post-2002', colour: '#22c55e' },
] as const;

const FABRIC_ITEMS = [
  { label: 'Windows', goodKey: 'windows' as const, colour: '#3b82f6' },
  { label: 'Walls', goodKey: 'walls' as const, colour: '#8b5cf6' },
  { label: 'Roof', goodKey: 'roof' as const, colour: '#f59e0b' },
] as const;

function fmt(v: number | null | undefined): string {
  if (v == null) return '—';
  return v.toLocaleString('en-GB', { maximumFractionDigits: 1 });
}

function fmtGbp(v: number | null | undefined): string {
  if (v == null) return '—';
  return `£${Math.round(v).toLocaleString('en-GB')}`;
}

export default function BuildingProfileChart({
  avgCo2, avgEnergyKwh,
  avgHeatingCost, avgHotwaterCost, avgLightingCost,
  heatGasPct, heatElectricPct, heatOilPct, heatDistrictPct, heatOtherPct, heatNonePct,
  pctMainsGas, pctSolar,
  agePre1900Pct, age1900_1929Pct, age1930_1949Pct, age1950_1966Pct,
  age1967_1982Pct, age1983_2002Pct, agePost2002Pct,
  windowsGoodPct, windowsVpoorPct,
  wallsGoodPct, wallsVpoorPct,
  roofGoodPct, roofVpoorPct,
  glazeSinglePct, glazeDoublePct, glazeTriplePct, avgMultiGlazePct,
  formDetachedPct, formSemiPct, formTerracePct, formEndTerracePct,
  enhanced,
}: Props) {
  const heatMap: Record<string, number | null | undefined> = {
    gas: heatGasPct, electric: heatElectricPct, oil: heatOilPct,
    district: heatDistrictPct, other: heatOtherPct,
  };
  const hasHeating = heatGasPct != null || heatElectricPct != null;

  const ageMap: Record<string, number | null | undefined> = {
    pre1900: agePre1900Pct, '1900_1929': age1900_1929Pct, '1930_1949': age1930_1949Pct,
    '1950_1966': age1950_1966Pct, '1967_1982': age1967_1982Pct,
    '1983_2002': age1983_2002Pct, post2002: agePost2002Pct,
  };
  const hasAge = Object.values(ageMap).some(v => v != null && v > 0);
  const maxAge = Math.max(...Object.values(ageMap).map(v => v ?? 0));

  const totalCost = [avgHeatingCost, avgHotwaterCost, avgLightingCost]
    .filter((v): v is number => v != null)
    .reduce((a, b) => a + b, 0);
  const hasCosts = avgHeatingCost != null;

  // D22: Built form
  const hasForm = formDetachedPct != null || formSemiPct != null || formTerracePct != null;
  const formItems = [
    { label: 'Detached', pct: formDetachedPct, colour: '#2563eb' },
    { label: 'Semi-detached', pct: formSemiPct, colour: '#7c3aed' },
    { label: 'Terraced', pct: formTerracePct, colour: '#ea580c' },
  ].filter(f => f.pct != null && f.pct >= 0.5) as { label: string; pct: number; colour: string }[];

  // D21: Fabric quality
  const fabricGoodMap: Record<string, number | null | undefined> = {
    windows: windowsGoodPct, walls: wallsGoodPct, roof: roofGoodPct,
  };
  const fabricVpoorMap: Record<string, number | null | undefined> = {
    windows: windowsVpoorPct, walls: wallsVpoorPct, roof: roofVpoorPct,
  };
  const hasFabric = windowsGoodPct != null || wallsGoodPct != null || roofGoodPct != null;
  const hasGlazing = glazeDoublePct != null || glazeSinglePct != null;

  return (
    <div className="bg-surface rounded-xl p-4 space-y-4 mt-2">
      {/* ─── Energy & Emissions ─── */}
      <div>
        <h4 className="text-xs font-semibold text-ink-muted mb-2">Energy & Emissions</h4>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {avgCo2 != null && (
            <div className="bg-white border border-divider rounded-lg p-3">
              <div className="text-[10px] text-ink-faint uppercase tracking-wide">CO2 / property</div>
              <div className="text-lg font-bold text-ink mt-0.5">{fmt(avgCo2)}</div>
              <div className="text-[10px] text-ink-faint">tonnes CO2/yr</div>
            </div>
          )}
          {avgEnergyKwh != null && (
            <div className="bg-white border border-divider rounded-lg p-3">
              <div className="text-[10px] text-ink-faint uppercase tracking-wide">Energy use</div>
              <div className="text-lg font-bold text-ink mt-0.5">{fmt(avgEnergyKwh)}</div>
              <div className="text-[10px] text-ink-faint">kWh/m²/yr</div>
            </div>
          )}
          {hasCosts && (
            <div className="bg-white border border-divider rounded-lg p-3">
              <div className="text-[10px] text-ink-faint uppercase tracking-wide">Running costs</div>
              <div className="text-lg font-bold text-ink mt-0.5">{fmtGbp(totalCost)}<span className="text-xs font-normal text-ink-faint">/yr</span></div>
              <div className="text-[10px] text-ink-faint">
                Heating {fmtGbp(avgHeatingCost)} · Water {fmtGbp(avgHotwaterCost)} · Light {fmtGbp(avgLightingCost)}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ─── Built Form Distribution (D22) ─── */}
      {hasForm && (
        <div>
          <h4 className="text-xs font-semibold text-ink-muted mb-2">Built Form</h4>
          {/* Stacked bar */}
          <div className="h-6 rounded-full overflow-hidden flex bg-divider">
            {formItems.map(({ label, pct, colour }) => (
              <div
                key={label}
                className="h-full flex items-center justify-center text-[10px] font-semibold text-white"
                style={{ width: `${pct}%`, backgroundColor: colour, minWidth: pct >= 3 ? undefined : 0 }}
                title={`${label}: ${pct.toFixed(1)}%`}
              >
                {pct >= 8 ? `${pct.toFixed(0)}%` : ''}
              </div>
            ))}
          </div>
          {/* Legend */}
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5">
            {formItems.map(({ label, pct, colour }) => (
              <div key={label} className="flex items-center gap-1.5 text-xs text-ink-muted">
                <div className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: colour }} />
                <span>{label} <span className="font-semibold text-ink">{pct.toFixed(1)}%</span></span>
              </div>
            ))}
            {formEndTerracePct != null && formEndTerracePct >= 0.5 && (
              <div className="text-[10px] text-ink-faint ml-auto">
                incl. end-terrace {formEndTerracePct.toFixed(1)}%
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── Heating Fuel Breakdown ─── */}
      {hasHeating && (
        <div>
          <h4 className="text-xs font-semibold text-ink-muted mb-2">Heating Fuel</h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {HEAT_ITEMS.map(({ key, label, icon: Icon, colour }) => {
              const pct = heatMap[key];
              if (pct == null || pct < 0.5) return null;
              return (
                <div key={key} className="flex items-center gap-2 p-2 bg-white rounded-lg border border-divider">
                  <Icon className="w-4 h-4 shrink-0" style={{ color: colour }} />
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] text-ink-faint">{label}</div>
                    <div className="text-sm font-semibold text-ink">{pct.toFixed(1)}%</div>
                  </div>
                </div>
              );
            })}
            {heatNonePct != null && heatNonePct >= 0.5 && (
              <div className="flex items-center gap-2 p-2 bg-white rounded-lg border border-divider">
                <div className="w-4 h-4 shrink-0 rounded-full bg-divider" />
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] text-ink-faint">No heating</div>
                  <div className="text-sm font-semibold text-ink">{heatNonePct.toFixed(1)}%</div>
                </div>
              </div>
            )}
          </div>
          <div className="flex gap-4 mt-2">
            {pctMainsGas != null && (
              <div className="flex items-center gap-1.5 text-xs text-ink-muted">
                <Fuel className="w-3.5 h-3.5 text-amber-600" />
                <span>Mains gas: <span className="font-semibold text-ink">{pctMainsGas.toFixed(1)}%</span></span>
              </div>
            )}
            {pctSolar != null && pctSolar >= 0.5 && (
              <div className="flex items-center gap-1.5 text-xs text-ink-muted">
                <Sun className="w-3.5 h-3.5 text-amber-500" />
                <span>Solar: <span className="font-semibold text-ink">{pctSolar.toFixed(1)}%</span></span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── Fabric & Insulation Quality (D21) ─── */}
      {hasFabric && (
        <div>
          <h4 className="text-xs font-semibold text-ink-muted mb-2">Fabric & Insulation</h4>
          <div className="space-y-2">
            {FABRIC_ITEMS.map(({ label, goodKey, colour }) => {
              const good = fabricGoodMap[goodKey];
              const vpoor = fabricVpoorMap[goodKey];
              if (good == null) return null;
              return (
                <div key={goodKey}>
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-[11px] text-ink-muted">{label}</span>
                    <div className="flex gap-3 text-[11px]">
                      <span className="text-emerald-600 font-semibold">{good.toFixed(0)}% good+</span>
                      {vpoor != null && vpoor >= 0.5 && (
                        <span className="text-red-500 font-semibold">{vpoor.toFixed(0)}% v.poor</span>
                      )}
                    </div>
                  </div>
                  <div className="h-3 rounded-full overflow-hidden flex bg-divider">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${good}%`,
                        backgroundColor: colour,
                        opacity: 0.8,
                        animation: enhanced ? 'enhanced-bar-fill 0.7s ease-out both' : undefined,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          {/* Glazing breakdown */}
          {hasGlazing && (
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
              {glazeDoublePct != null && glazeDoublePct >= 0.5 && (
                <div className="text-xs text-ink-muted">
                  Double glazed: <span className="font-semibold text-ink">{glazeDoublePct.toFixed(1)}%</span>
                </div>
              )}
              {glazeTriplePct != null && glazeTriplePct >= 0.5 && (
                <div className="text-xs text-ink-muted">
                  Triple glazed: <span className="font-semibold text-ink">{glazeTriplePct.toFixed(1)}%</span>
                </div>
              )}
              {glazeSinglePct != null && glazeSinglePct >= 0.5 && (
                <div className="text-xs text-ink-muted">
                  Single glazed: <span className="font-semibold text-ink">{glazeSinglePct.toFixed(1)}%</span>
                </div>
              )}
              {avgMultiGlazePct != null && (
                <div className="text-xs text-ink-muted">
                  Avg multi-glaze: <span className="font-semibold text-ink">{avgMultiGlazePct.toFixed(0)}%</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ─── Construction Age Profile ─── */}
      {hasAge && (
        <div>
          <h4 className="text-xs font-semibold text-ink-muted mb-2">Construction Period</h4>
          <div className="space-y-1">
            {AGE_BANDS.map(({ key, label, colour }) => {
              const pct = ageMap[key] ?? 0;
              if (pct < 0.5) return null;
              return (
                <div key={key} className="flex items-center gap-2">
                  <div className="w-16 text-[11px] text-ink-muted text-right shrink-0">{label}</div>
                  <div className="flex-1 relative h-5 bg-divider rounded-full overflow-hidden">
                    <div
                      className="absolute left-0 top-0 h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${maxAge > 0 ? (pct / maxAge) * 100 : 0}%`,
                        backgroundColor: colour,
                        opacity: 0.85,
                        animation: enhanced ? 'enhanced-bar-fill 0.7s ease-out both' : undefined,
                      }}
                    />
                  </div>
                  <div className="w-12 text-right text-xs font-medium text-ink tabular-nums shrink-0">
                    {pct.toFixed(1)}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <p className="text-[10px] text-ink-faint">
        Source: MHCLG EPC Register. Averages across all EPC certificates lodged in this area.
        Running costs reflect EPC assessment values, not current energy prices.
      </p>
    </div>
  );
}
