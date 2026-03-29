interface Props {
  floodLevel: string;
  riskScore: number;         // 0–100
  zone3Pct?: number | null;
  zone2Pct?: number | null;
  highRiskLsoaCount?: number | null;
  mediumRiskLsoaCount?: number | null;
  totalLsoas?: number | null;
  parentZone3Pct?: number | null;
}

const LEVEL_CONFIG: Record<string, { colour: string; trackColour: string; label: string; desc: string }> = {
  'Very Low':   { colour: '#22c55e', trackColour: '#dcfce7', label: 'Very Low',   desc: 'No flood zones within local LSOAs' },
  'Low':        { colour: '#84cc16', trackColour: '#ecfccb', label: 'Low',         desc: 'Minor Zone 2 presence (<10% of LSOAs)' },
  'Low-Medium': { colour: '#facc15', trackColour: '#fef9c3', label: 'Low-Medium',  desc: 'Some Zone 3 presence (<10% of LSOAs)' },
  'Medium':     { colour: '#fb923c', trackColour: '#ffedd5', label: 'Medium',      desc: 'Significant Zone 2 presence (≥10%)' },
  'High':       { colour: '#ef4444', trackColour: '#fee2e2', label: 'High',        desc: 'Significant Zone 3 presence (≥10%)' },
};

const DEFAULT_CONFIG = LEVEL_CONFIG['Very Low'];

// SVG semi-circle gauge — arc goes from 180° (left) to 0° (right)
// score 0–100 maps to 180°–0° on the upper semicircle
function polarToXY(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) };
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const s = polarToXY(cx, cy, r, startDeg);
  const e = polarToXY(cx, cy, r, endDeg);
  const large = Math.abs(endDeg - startDeg) > 180 ? 1 : 0;
  const sweep = startDeg > endDeg ? 0 : 1; // counter-clockwise
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} ${sweep} ${e.x} ${e.y}`;
}

export default function FloodRiskGauge({
  floodLevel, riskScore, zone3Pct, zone2Pct,
  highRiskLsoaCount: _highRiskLsoaCount, mediumRiskLsoaCount: _mediumRiskLsoaCount, totalLsoas: _totalLsoas, parentZone3Pct,
}: Props) {
  const cfg = LEVEL_CONFIG[floodLevel] ?? DEFAULT_CONFIG;

  // Gauge geometry
  const W = 220, H = 130;
  const cx = W / 2, cy = H - 10;
  const R_TRACK = 88, R_FILL = 88, STROKE = 18;

  // Angle: 180° = left (score 0), 0° = right (score 100)
  // needle tip at angleDeg = 180 - score * 1.8 (180° range)
  const clampedScore = Math.max(0, Math.min(100, riskScore));
  const needleAngle = 180 - clampedScore * 1.8;
  const needleTip = polarToXY(cx, cy, R_TRACK - 4, needleAngle);
  const needleBase1 = polarToXY(cx, cy, 8, needleAngle + 90);
  const needleBase2 = polarToXY(cx, cy, 8, needleAngle - 90);

  // Zone segments on the arc
  // 5 zones evenly spaced: 0-20-40-60-80-100
  const segColours = ['#22c55e', '#84cc16', '#facc15', '#fb923c', '#ef4444'];
  const segCount = 5;
  const degPerSeg = 180 / segCount; // 36° each

  return (
    <div className="bg-surface rounded-xl p-4 space-y-3 mt-2">
      {/* ─── SVG gauge ─── */}
      <div className="flex justify-center">
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
          {/* Coloured arc segments */}
          {segColours.map((col, i) => {
            const startDeg = 180 - i * degPerSeg;
            const endDeg = 180 - (i + 1) * degPerSeg;
            return (
              <path
                key={i}
                d={arcPath(cx, cy, R_TRACK, startDeg, endDeg)}
                fill="none"
                stroke={col}
                strokeWidth={STROKE}
                strokeLinecap="butt"
                opacity={0.25}
              />
            );
          })}

          {/* Active filled arc from 180° to needle angle */}
          <path
            d={arcPath(cx, cy, R_FILL, 180, needleAngle)}
            fill="none"
            stroke={cfg.colour}
            strokeWidth={STROKE}
            strokeLinecap="round"
            opacity={0.9}
          />

          {/* Tick marks */}
          {[0, 25, 50, 75, 100].map((v) => {
            const a = 180 - v * 1.8;
            const inner = polarToXY(cx, cy, R_TRACK - STROKE / 2 - 2, a);
            const outer = polarToXY(cx, cy, R_TRACK + STROKE / 2 + 2, a);
            return (
              <line
                key={v}
                x1={inner.x} y1={inner.y}
                x2={outer.x} y2={outer.y}
                stroke="#fff"
                strokeWidth={1.5}
              />
            );
          })}

          {/* Needle */}
          <polygon
            points={`${needleTip.x},${needleTip.y} ${needleBase1.x},${needleBase1.y} ${needleBase2.x},${needleBase2.y}`}
            fill="#1f2937"
            opacity={0.85}
          />
          <circle cx={cx} cy={cy} r={6} fill="#1f2937" opacity={0.85} />

          {/* Zone labels */}
          {['VL', 'L', 'M', 'H'].map((lbl, i) => {
            const a = 180 - (i + 0.5) * (180 / 4);
            const pt = polarToXY(cx, cy, R_TRACK + STROKE / 2 + 10, a);
            return (
              <text key={lbl} x={pt.x} y={pt.y} textAnchor="middle" dominantBaseline="middle"
                fontSize={8} fill="#9ca3af" fontWeight={600}>
                {lbl}
              </text>
            );
          })}

          {/* Centre level text */}
          <text x={cx} y={cy - 26} textAnchor="middle" fontSize={16} fontWeight={800}
            fill={cfg.colour}>
            {cfg.label}
          </text>
        </svg>
      </div>

      {/* ─── Description ─── */}
      <p className="text-xs text-ink-muted text-center">{cfg.desc}</p>

      {/* ─── Stats grid ─── */}
      <div className="grid grid-cols-2 gap-2">
        {zone3Pct != null && (
          <div className="p-2.5 rounded-xl bg-white border border-divider">
            <div className="text-[10px] text-ink-faint">Zone 3 (high risk)</div>
            <div className="text-lg font-bold" style={{ color: zone3Pct > 0 ? '#ef4444' : '#22c55e' }}>
              {zone3Pct.toFixed(1)}%
            </div>
            <div className="text-[10px] text-ink-faint">of local LSOAs</div>
          </div>
        )}
        {zone2Pct != null && (
          <div className="p-2.5 rounded-xl bg-white border border-divider">
            <div className="text-[10px] text-ink-faint">Zone 2 (medium risk)</div>
            <div className="text-lg font-bold" style={{ color: zone2Pct > 0 ? '#fb923c' : '#22c55e' }}>
              {zone2Pct.toFixed(1)}%
            </div>
            <div className="text-[10px] text-ink-faint">of local LSOAs</div>
          </div>
        )}
        {parentZone3Pct != null && (
          <div className="p-2.5 rounded-xl bg-white border border-divider col-span-2">
            <div className="text-[10px] text-ink-faint">Area avg Zone 3 exposure</div>
            <div className="text-sm font-semibold text-ink">{parentZone3Pct.toFixed(1)}%</div>
          </div>
        )}
      </div>

      <div className="flex items-start gap-2 p-2.5 rounded-xl bg-blue-50 border border-blue-100">
        <span className="text-blue-500 text-xs mt-0.5">🗺</span>
        <p className="text-[11px] text-blue-700 leading-snug">
          Flood Zone 2 &amp; 3 polygons are displayed on the map above — scroll up to view the exact boundaries in your area.
        </p>
      </div>

      <p className="text-[10px] text-ink-faint">
        Source: EA Flood Map for Planning. Zone 3 = &gt;1% annual probability. Zone 2 = 0.1–1%.
      </p>
    </div>
  );
}
