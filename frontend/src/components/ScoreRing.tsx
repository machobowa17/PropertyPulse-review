interface ScoreRingProps {
  score: number;
  max?: number;
  size?: number;
  label?: string;
  parentValue?: number;
  color?: string;
  className?: string;
}

/** 270-degree SVG arc gauge with gradient fill, glow aura, and optional parent marker. */
export default function ScoreRing({
  score,
  max = 100,
  size = 120,
  label,
  parentValue,
  color,
  className = '',
}: ScoreRingProps) {
  const clamped = Math.max(0, Math.min(max, score));
  const pct = clamped / max;

  // Derive color from score percentage if not provided
  const fillColor = color ?? (pct >= 0.7 ? '#059669' : pct >= 0.4 ? '#d97706' : '#dc2626');

  // Arc geometry: 270 degrees starting from bottom-left
  const cx = 50, cy = 55, r = 38, sw = 8;
  const startAngle = 135, endAngle = 405;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const arcPt = (a: number) => ({ x: cx + r * Math.cos(toRad(a)), y: cy + r * Math.sin(toRad(a)) });
  const describeArc = (s: number, e: number) => {
    const sp = arcPt(s), ep = arcPt(e);
    return `M${sp.x},${sp.y} A${r},${r} 0 ${e - s > 180 ? 1 : 0} 1 ${ep.x},${ep.y}`;
  };

  const valueAngle = startAngle + pct * (endAngle - startAngle);
  const parentAngle = parentValue != null
    ? startAngle + (Math.min(parentValue / max, 1)) * (endAngle - startAngle)
    : null;
  const parentPt = parentAngle != null ? arcPt(parentAngle) : null;

  // Unique gradient ID per instance (score+max combo is sufficient)
  const gradId = `sr-${Math.round(score)}-${max}`;

  return (
    <div className={`flex flex-col items-center ${className}`}>
      <svg width={size} height={size * 0.82} viewBox="0 0 100 82" style={{ overflow: 'visible' }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={fillColor} stopOpacity={0.5} />
            <stop offset="100%" stopColor={fillColor} />
          </linearGradient>
        </defs>

        {/* Glow aura rings */}
        <circle cx={cx} cy={cy} r={r + sw / 2 + 6} fill="none" stroke={fillColor} strokeWidth={1} opacity={0.06} />
        <circle cx={cx} cy={cy} r={r + sw / 2 + 3} fill="none" stroke={fillColor} strokeWidth={1} opacity={0.12} />

        {/* Track */}
        <path d={describeArc(startAngle, endAngle)} fill="none" stroke="currentColor" className="text-divider" strokeWidth={sw} strokeLinecap="round" />

        {/* Fill arc */}
        <path
          d={describeArc(startAngle, Math.max(valueAngle, startAngle + 0.5))}
          fill="none"
          stroke={`url(#${gradId})`}
          strokeWidth={sw}
          strokeLinecap="round"
          style={{
            filter: `drop-shadow(0 0 8px ${fillColor}44) drop-shadow(0 0 20px ${fillColor}18)`,
            transition: 'stroke-dasharray 0.7s cubic-bezier(0.4,0,0.2,1)',
          }}
        />

        {/* Parent marker dot */}
        {parentPt && (
          <circle cx={parentPt.x} cy={parentPt.y} r={3.5} fill="#6b7280" stroke="white" strokeWidth={1.5} />
        )}

        {/* Score number */}
        <text x={cx} y={cy - 2} textAnchor="middle" dominantBaseline="middle"
          className="fill-ink" style={{ fontSize: 20, fontWeight: 800, fontFamily: 'ui-monospace, monospace', letterSpacing: '-0.5px' }}>
          {Math.round(clamped)}
        </text>

        {/* "of max" label */}
        <text x={cx} y={cy + 12} textAnchor="middle"
          className="fill-ink-faint" style={{ fontSize: 8, fontFamily: 'system-ui, sans-serif' }}>
          of {max}
        </text>
      </svg>

      {/* Optional text label below */}
      {label && <span className="text-[10px] text-ink-faint font-medium tracking-wide uppercase mt-1">{label}</span>}
    </div>
  );
}
