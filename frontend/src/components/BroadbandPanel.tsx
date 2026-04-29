interface Props {
  fullFibrePct: number | null;
  superfastPct: number | null;
  gigabitPct: number | null;
  parentFullFibrePct: number | null;
  parentSuperfastPct: number | null;
  parentGigabitPct: number | null;
}

function CoverageBar({ label, value, parentValue, colour }: {
  label: string;
  value: number | null;
  parentValue: number | null;
  colour: string;
}) {
  if (value == null) return null;
  const diff = parentValue != null ? value - parentValue : null;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-ink-muted">{label}</span>
        <div className="flex items-center gap-2">
          <span className="font-semibold text-ink">{value.toFixed(1)}%</span>
          {diff != null && (
            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
              diff >= 0 ? 'bg-signal-green/15 text-signal-green' : 'bg-signal-red/15 text-signal-red'
            }`}>
              {diff >= 0 ? '+' : ''}{diff.toFixed(1)}%
            </span>
          )}
        </div>
      </div>
      <div className="relative h-2.5 bg-surface rounded-full overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-all"
          style={{ width: `${value}%`, backgroundColor: colour }}
        />
        {parentValue != null && (
          <div
            className="absolute inset-y-0 w-0.5 bg-ink/30"
            style={{ left: `${parentValue}%` }}
          />
        )}
      </div>
    </div>
  );
}

export default function BroadbandPanel({
  fullFibrePct, superfastPct, gigabitPct,
  parentFullFibrePct, parentSuperfastPct, parentGigabitPct,
}: Props) {
  return (
    <div className="space-y-4 mt-1">
      <div className="space-y-2.5">
        <CoverageBar
          label="Ultrafast / Full Fibre (≥300 Mbps)"
          value={fullFibrePct}
          parentValue={parentFullFibrePct}
          colour="#7c3aed"
        />
        <CoverageBar
          label="Superfast (≥30 Mbps)"
          value={superfastPct}
          parentValue={parentSuperfastPct}
          colour="#2563eb"
        />
        <CoverageBar
          label="Gigabit-capable (≥1000 Mbps)"
          value={gigabitPct}
          parentValue={parentGigabitPct}
          colour="#059669"
        />
      </div>
      <p className="text-[10px] text-ink-faint">
        Source: Ofcom Connected Nations Jul 2024. Vertical tick = area average.
      </p>
    </div>
  );
}
