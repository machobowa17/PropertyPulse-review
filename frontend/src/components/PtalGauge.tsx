interface Props {
  band: string;
  ptaiScore?: number | null;
  parentAvgPtai?: number | null;
  busStops640m?: number | null;
  heavyStops960m?: number | null;
  tflData?: boolean;
}

const BANDS = [
  { id: '0',  label: '0',   desc: 'No service',    colour: '#e5e7eb' },
  { id: '1a', label: '1a',  desc: 'Very poor',     colour: '#fca5a5' },
  { id: '1b', label: '1b',  desc: 'Poor',          colour: '#fb923c' },
  { id: '2',  label: '2',   desc: 'Low',           colour: '#fbbf24' },
  { id: '3',  label: '3',   desc: 'Moderate',      colour: '#a3e635' },
  { id: '4',  label: '4',   desc: 'Good',          colour: '#4ade80' },
  { id: '5',  label: '5',   desc: 'Very good',     colour: '#22c55e' },
  { id: '6a', label: '6a',  desc: 'Excellent',     colour: '#059669' },
  { id: '6b', label: '6b',  desc: 'Exceptional',   colour: '#065f46' },
];

function bandDescription(band: string): string {
  return BANDS.find((b) => b.id === band)?.desc ?? 'Unknown';
}

function bandColour(band: string): string {
  return BANDS.find((b) => b.id === band)?.colour ?? '#9ca3af';
}

export default function PtalGauge({ band, ptaiScore, parentAvgPtai, busStops640m, heavyStops960m, tflData }: Props) {
  const activeBand = band ?? '0';

  return (
    <div className="bg-surface rounded-xl p-4 space-y-4 mt-2">
      {/* ─── Score header ─── */}
      <div className="flex items-center gap-4">
        <div
          className="w-16 h-16 rounded-2xl flex flex-col items-center justify-center shrink-0"
          style={{ backgroundColor: bandColour(activeBand) }}
        >
          <span className="text-2xl font-black text-white leading-none">{activeBand}</span>
          <span className="text-[9px] text-white/80 font-medium uppercase tracking-wide mt-0.5">PTAL</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-base font-bold text-ink">{bandDescription(activeBand)}</div>
          {ptaiScore != null && (
            <div className="text-xs text-ink-faint mt-0.5">
              PTAI score: <span className="font-semibold text-ink">{ptaiScore.toFixed(1)}</span>
              {parentAvgPtai != null && (
                <span className="ml-2 opacity-70">area avg {parentAvgPtai.toFixed(1)}</span>
              )}
            </div>
          )}
          {tflData && (
            <div className="text-[10px] text-ink-faint mt-1">Source: TfL official data</div>
          )}
        </div>
      </div>

      {/* ─── Band scale ─── */}
      <div>
        <div className="text-[11px] text-ink-faint uppercase tracking-wide font-medium mb-2">Accessibility scale</div>
        <div className="flex gap-1">
          {BANDS.map((b) => {
            const isActive = b.id === activeBand;
            return (
              <div key={b.id} className="flex-1 flex flex-col items-center gap-1">
                <div
                  className={`w-full rounded transition-all ${isActive ? 'h-8 shadow-md ring-2 ring-offset-1 ring-gray-400' : 'h-5 opacity-50'}`}
                  style={{ backgroundColor: b.colour }}
                />
                <span className={`text-[9px] font-medium ${isActive ? 'text-ink' : 'text-ink-faint'}`}>
                  {b.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* ─── Stop counts ─── */}
      {(busStops640m != null || heavyStops960m != null) && (
        <div className="grid grid-cols-2 gap-2">
          {busStops640m != null && (
            <div className="p-2.5 rounded-xl bg-white border border-divider">
              <div className="text-[10px] text-ink-faint">Bus stops (640m)</div>
              <div className="text-lg font-bold text-ink">{busStops640m}</div>
            </div>
          )}
          {heavyStops960m != null && (
            <div className="p-2.5 rounded-xl bg-white border border-divider">
              <div className="text-[10px] text-ink-faint">Rail/Metro/Tram (960m)</div>
              <div className="text-lg font-bold text-ink">{heavyStops960m}</div>
            </div>
          )}
        </div>
      )}

      <p className="text-[10px] text-ink-faint">
        PTAL 1a (very poor) → 6b (exceptional). {!tflData && 'Derived from NaPTAN stop counts.'}
      </p>
    </div>
  );
}
