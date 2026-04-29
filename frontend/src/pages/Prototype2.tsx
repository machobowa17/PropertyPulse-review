/**
 * Prototype 2 — BurbScore-inspired FULL design refresh mockup.
 *
 * Standalone page at /prototype2 with STATIC MOCK DATA. Demonstrates:
 * - Warm earth-tone palette (cream, burnt orange, sage green)
 * - 3-font system (Fraunces serif display + Plus Jakarta Sans body + JetBrains Mono data)
 * - Generous whitespace and narrower max-width (820px content)
 * - Micro-interactions (staggered reveals, hover elevations, animated underlines)
 * - Full sub-charts: price trend, crime bars, air quality gauge, demographic donut, noise scale
 * - Full tables: transactions with expand rows, schools with filter pills + detail tabs
 * - Real MapView integration (lazy loaded)
 * - Thematically consistent detail renderers throughout
 *
 * Does NOT touch any existing components or pages.
 */
import { useState } from 'react';
import {
  Search, Leaf, TrendingUp, TrendingDown, Shield, Users,
  Building2, Home, Coffee, TreePine, Landmark, ArrowRight, ArrowUpRight,
  ArrowDownRight, Minus, ChevronDown, ChevronUp,
  GraduationCap, Train, Wind, Wifi, PoundSterling,
  Scale, FileDown, Bookmark,
  LayoutDashboard, Volume2,
} from 'lucide-react';

/* ══════════════════════════════════════════════════════════════════════
   DESIGN TOKENS
   ══════════════════════════════════════════════════════════════════════ */
const T = {
  pageBg:      '#FAF8F5',
  cardBg:      '#FFFFFF',
  warmBg:      '#F5F0EB',
  heroBg:      '#1C1917',
  heroGrad:    'linear-gradient(135deg, #1C1917 0%, #292524 50%, #1C1917 100%)',
  accent:      '#C2410C',
  accentLight: '#FFF7ED',
  accentMid:   '#EA580C',
  accentHover: '#9A3412',
  accentBg:    '#FED7AA',
  sage:        '#15803D',
  sageBg:      '#F0FDF4',
  sageLight:   '#DCFCE7',
  ink:         '#1C1917',
  inkMuted:    '#57534E',
  inkFaint:    '#A8A29E',
  divider:     '#E7E5E4',
  dividerSoft: '#F5F5F4',
  good:        '#059669',
  goodBg:      '#ECFDF5',
  caution:     '#D97706',
  cautionBg:   '#FFFBEB',
  bad:         '#DC2626',
  badBg:       '#FEF2F2',
  serif:       "'Fraunces', 'Playfair Display', Georgia, serif",
  sans:        "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  mono:        "'JetBrains Mono', 'IBM Plex Mono', ui-monospace, monospace",
} as const;

/* ══════════════════════════════════════════════════════════════════════
   MOCK DATA
   ══════════════════════════════════════════════════════════════════════ */
const AREA = { name: 'Coulsdon', parent: 'Croydon', county: 'Greater London', type: 'Ward', lsoaCount: 7 };

const ReceiptIcon = Building2;

const HEADLINE_METRICS = [
  { id: 'avg_price', label: 'Avg Price', value: '£485,200', parent: '£412,800', direction: 'higher_is_neutral' as const, icon: PoundSterling, trend: '+3.2%' },
  { id: 'council_tax', label: 'Council Tax', value: '£1,891', parent: '£1,724', direction: 'lower_is_better' as const, icon: ReceiptIcon, trend: '+4.1%' },
  { id: 'nearest_station', label: 'Nearest Station', value: '0.6 mi', parent: '1.2 mi', direction: 'lower_is_better' as const, icon: Train, trend: null },
  { id: 'crime_rate', label: 'Crime Rate', value: '62.4', parent: '89.1', direction: 'lower_is_better' as const, icon: Shield, unit: 'per 1k', trend: '-8.3%' },
  { id: 'air_quality', label: 'Air Quality', value: '10.2', parent: '11.8', direction: 'lower_is_better' as const, icon: Wind, unit: 'µg/m³', trend: '-1.1%' },
  { id: 'median_age', label: 'Median Age', value: '38', parent: '35', direction: 'higher_is_neutral' as const, icon: Users, trend: null },
  { id: 'deprivation', label: 'IMD Decile', value: '7', parent: '5', direction: 'higher_is_better' as const, icon: Scale, trend: null },
  { id: 'school_quality', label: 'Good+ Schools', value: '82%', parent: '71%', direction: 'higher_is_better' as const, icon: GraduationCap, trend: null },
  { id: 'broadband', label: 'Avg Broadband', value: '72 Mbps', parent: '64 Mbps', direction: 'higher_is_better' as const, icon: Wifi, trend: null },
  { id: 'amenities', label: 'Amenities', value: '47', parent: '38', direction: 'higher_is_better' as const, icon: Coffee, unit: 'within 1km', trend: null },
];

const TAB_SCORES = [
  { tab: 'Property & Market', icon: Home, score: 72, colour: '#C2410C' },
  { tab: 'Lifestyle & Connectivity', icon: Coffee, score: 81, colour: '#7C3AED' },
  { tab: 'Environment & Safety', icon: TreePine, score: 68, colour: '#059669' },
  { tab: 'Community & Education', icon: Users, score: 77, colour: '#EA580C' },
  { tab: 'Local Governance', icon: Landmark, score: 54, colour: '#0891B2' },
];

const COMPARABLE_AREAS = [
  { name: 'Purley', parent: 'Croydon', match: 87, avgPrice: '£462,100', crimeRate: '58.2' },
  { name: 'Sanderstead', parent: 'Croydon', match: 83, avgPrice: '£521,400', crimeRate: '41.7' },
  { name: 'Kenley', parent: 'Croydon', match: 79, avgPrice: '£445,800', crimeRate: '52.9' },
];

const PRICE_TREND = [
  { period: 'Apr 23', median: 448000 },
  { period: 'Jul 23', median: 455000 },
  { period: 'Oct 23', median: 442000 },
  { period: 'Jan 24', median: 451000 },
  { period: 'Apr 24', median: 460000 },
  { period: 'Jul 24', median: 472000 },
  { period: 'Oct 24', median: 468000 },
  { period: 'Jan 25', median: 478000 },
  { period: 'Apr 25', median: 485000 },
];

const CRIME_TREND = [
  { year: '2019', rate: 74.2 },
  { year: '2020', rate: 65.1 },
  { year: '2021', rate: 68.9 },
  { year: '2022', rate: 71.3 },
  { year: '2023', rate: 67.8 },
  { year: '2024', rate: 62.4 },
];

const CRIME_BREAKDOWN = [
  { type: 'Violence & Sexual', count: 312, pct: 28.1 },
  { type: 'Anti-social Behaviour', count: 224, pct: 20.2 },
  { type: 'Vehicle Crime', count: 187, pct: 16.8 },
  { type: 'Burglary', count: 134, pct: 12.1 },
  { type: 'Shoplifting', count: 98, pct: 8.8 },
  { type: 'Other', count: 155, pct: 14.0 },
];

const TRANSACTIONS = [
  { date: '2025-03-14', address: '42 Marlpit Lane', price: 485000, type: 'S', beds: 3, sqft: 1120, tenure: 'Freehold', epc: 'C', prevPrice: 385000, prevDate: '2018-06-22' },
  { date: '2025-02-28', address: '7 The Grove', price: 612000, type: 'D', beds: 4, sqft: 1540, tenure: 'Freehold', epc: 'B', prevPrice: null, prevDate: null },
  { date: '2025-02-15', address: 'Flat 3, Avalon Court', price: 265000, type: 'F', beds: 2, sqft: 680, tenure: 'Leasehold', epc: 'D', prevPrice: 228000, prevDate: '2019-11-08' },
  { date: '2025-01-30', address: '18 Woodcote Grove Rd', price: 725000, type: 'D', beds: 5, sqft: 1920, tenure: 'Freehold', epc: 'C', prevPrice: 615000, prevDate: '2016-03-11' },
  { date: '2025-01-22', address: '91 Brighton Road', price: 348000, type: 'T', beds: 2, sqft: 840, tenure: 'Freehold', epc: 'E', prevPrice: 295000, prevDate: '2017-09-04' },
  { date: '2024-12-18', address: 'Flat 12, Cane Hill Park', price: 310000, type: 'F', beds: 2, sqft: 720, tenure: 'Leasehold', epc: 'B', prevPrice: null, prevDate: null },
];

const SCHOOLS = [
  { name: 'Woodcote Primary', phase: 'Primary', ofsted: 'Outstanding' as const, distance: '0.3 mi', ks2: 72, fsm: 8.2, pupils: 420, lastInspection: 'Mar 2023', p8: undefined as number | undefined },
  { name: 'Coulsdon C of E Primary', phase: 'Primary', ofsted: 'Good' as const, distance: '0.4 mi', ks2: 65, fsm: 14.1, pupils: 315, lastInspection: 'Nov 2022', p8: undefined as number | undefined },
  { name: 'Smitham Primary', phase: 'Primary', ofsted: 'Good' as const, distance: '0.6 mi', ks2: 68, fsm: 11.3, pupils: 380, lastInspection: 'Jun 2024', p8: undefined as number | undefined },
  { name: 'Oasis Academy Coulsdon', phase: 'Secondary', ofsted: 'Good' as const, distance: '0.5 mi', ks2: undefined as number | undefined, fsm: 22.4, pupils: 1120, lastInspection: 'Feb 2024', p8: 0.21 },
  { name: 'Woodcote High School', phase: 'Secondary', ofsted: 'Requires Improvement' as const, distance: '0.8 mi', ks2: undefined as number | undefined, fsm: 18.7, pupils: 980, lastInspection: 'Sep 2023', p8: -0.15 },
];

const NOISE_LEVELS = [
  { source: 'Road Traffic (Day)', db: 52.3, category: 'Moderate' },
  { source: 'Road Traffic (Night)', db: 44.1, category: 'Quiet' },
  { source: 'Rail (Day)', db: 48.7, category: 'Moderate' },
  { source: 'Rail (Night)', db: 38.2, category: 'Quiet' },
];

const DEMOGRAPHICS = [
  { label: 'White British', pct: 62.4 },
  { label: 'Asian/Asian British', pct: 14.8 },
  { label: 'Black/Black British', pct: 11.2 },
  { label: 'Mixed/Multiple', pct: 5.1 },
  { label: 'White Other', pct: 4.3 },
  { label: 'Other', pct: 2.2 },
];

const TENURE_SPLIT = [
  { label: 'Owner occupied', pct: 68.2 },
  { label: 'Private rented', pct: 18.4 },
  { label: 'Social rented', pct: 10.1 },
  { label: 'Other', pct: 3.3 },
];

/* ══════════════════════════════════════════════════════════════════════
   UTILITY COMPONENTS
   ══════════════════════════════════════════════════════════════════════ */

function ComparisonArrow({ value, parentValue, direction }: {
  value: string; parentValue: string; direction: string;
}) {
  const numVal = parseFloat(value.replace(/[^0-9.\-]/g, ''));
  const numParent = parseFloat(parentValue.replace(/[^0-9.\-]/g, ''));
  if (isNaN(numVal) || isNaN(numParent)) return <span style={{ color: T.inkFaint, fontFamily: T.sans, fontSize: 11 }}>—</span>;
  const diff = numVal - numParent;
  const isHigher = diff > 0;
  const isGood = direction === 'higher_is_better' ? isHigher : direction === 'lower_is_better' ? !isHigher : null;
  const color = isGood === true ? T.good : isGood === false ? T.caution : T.inkFaint;
  const Icon = diff > 0 ? ArrowUpRight : diff < 0 ? ArrowDownRight : Minus;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color, fontSize: 11, fontWeight: 600, fontFamily: T.sans }}>
      <Icon size={12} /> vs {AREA.parent}
    </span>
  );
}

function Sparkline({ data, color = T.accent, width = 120, height = 32 }: { data: { value: number }[]; color?: string; width?: number; height?: number }) {
  const max = Math.max(...data.map(d => d.value));
  const min = Math.min(...data.map(d => d.value));
  const range = max - min || 1;
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((d.value - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  }).join(' ');
  const lastX = width;
  const lastY = height - ((data[data.length - 1].value - min) / range) * (height - 4) - 2;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ overflow: 'visible' }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastX} cy={lastY} r={3} fill={color} />
    </svg>
  );
}

function SimilarityBar({ pct }: { pct: number }) {
  const color = pct >= 75 ? T.good : pct >= 50 ? '#84cc16' : T.caution;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 3, background: T.divider, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', borderRadius: 3, background: color, transition: 'width 0.6s ease-out' }} />
      </div>
      <span style={{ fontFamily: T.mono, fontSize: 12, fontWeight: 700, color }}>{pct}%</span>
    </div>
  );
}

function SectionHeading({ icon: Icon, title, subtitle }: { icon: React.ElementType; title: string; subtitle?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
      <div style={{ width: 32, height: 32, borderRadius: 8, background: T.accentLight, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon size={16} color={T.accent} />
      </div>
      <div>
        <h2 style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 22, color: T.ink, letterSpacing: '-0.02em', margin: 0 }}>{title}</h2>
        {subtitle && <p style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, margin: '2px 0 0' }}>{subtitle}</p>}
      </div>
    </div>
  );
}

function Card({ children, style, hover = true }: { children: React.ReactNode; style?: React.CSSProperties; hover?: boolean }) {
  return (
    <div style={{
      background: T.cardBg, borderRadius: 16, border: `1px solid ${T.divider}`, overflow: 'hidden',
      transition: 'box-shadow 0.2s, transform 0.2s', ...style,
    }}
      onMouseEnter={hover ? e => { e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.06)'; } : undefined}
      onMouseLeave={hover ? e => { e.currentTarget.style.boxShadow = 'none'; } : undefined}
    >
      {children}
    </div>
  );
}

/* Helper: format £ */
const fmtPrice = (n: number) => '£' + n.toLocaleString('en-GB');
const fmtDate = (d: string) => new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const typeLabel = (t: string) => ({ D: 'Detached', S: 'Semi', T: 'Terraced', F: 'Flat' }[t] || t);
const epcColour = (r: string) => ({ A: '#008054', B: '#19b459', C: '#8dce46', D: '#ffd500', E: '#fcaa65', F: '#ef8023', G: '#e9153b' }[r] || T.inkFaint);

/* ══════════════════════════════════════════════════════════════════════
   CHART COMPONENTS — warm-themed, static SVG
   ══════════════════════════════════════════════════════════════════════ */

function PriceTrendChart() {
  const max = Math.max(...PRICE_TREND.map(d => d.median));
  const min = Math.min(...PRICE_TREND.map(d => d.median));
  const range = max - min || 1;
  const W = 680, H = 200, padL = 60, padR = 20, padT = 20, padB = 40;
  const chartW = W - padL - padR, chartH = H - padT - padB;

  // Area fill path
  const pts = PRICE_TREND.map((d, i) => {
    const x = padL + (i / (PRICE_TREND.length - 1)) * chartW;
    const y = padT + chartH - ((d.median - min) / range) * chartH;
    return { x, y };
  });
  const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
  const areaPath = linePath + ` L${pts[pts.length - 1].x},${padT + chartH} L${pts[0].x},${padT + chartH} Z`;

  return (
    <Card>
      <div style={{ padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
          <div>
            <div style={{ fontFamily: T.serif, fontSize: 16, fontWeight: 700, color: T.ink }}>Median Price Trend</div>
            <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted }}>Rolling 13-month median · 142 transactions</div>
          </div>
          <div style={{ fontFamily: T.mono, fontSize: 22, fontWeight: 800, color: T.ink }}>{fmtPrice(485000)}</div>
        </div>
        <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ overflow: 'visible' }}>
          {/* Y gridlines */}
          {[0, 0.25, 0.5, 0.75, 1].map(frac => {
            const y = padT + chartH * (1 - frac);
            const val = min + range * frac;
            return (
              <g key={frac}>
                <line x1={padL} x2={W - padR} y1={y} y2={y} stroke={T.divider} strokeDasharray="3,3" />
                <text x={padL - 8} y={y + 4} textAnchor="end" style={{ fontFamily: T.mono, fontSize: 10, fill: T.inkFaint }}>
                  £{Math.round(val / 1000)}k
                </text>
              </g>
            );
          })}
          {/* Area + line */}
          <path d={areaPath} fill={`${T.accent}12`} />
          <path d={linePath} fill="none" stroke={T.accent} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
          {/* Dots */}
          {pts.map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r={3.5} fill={T.cardBg} stroke={T.accent} strokeWidth={2} />
          ))}
          {/* X labels */}
          {PRICE_TREND.map((d, i) => {
            const x = padL + (i / (PRICE_TREND.length - 1)) * chartW;
            return i % 2 === 0 ? (
              <text key={i} x={x} y={H - 8} textAnchor="middle" style={{ fontFamily: T.mono, fontSize: 10, fill: T.inkFaint }}>
                {d.period}
              </text>
            ) : null;
          })}
        </svg>
      </div>
    </Card>
  );
}

function CrimeBreakdownChart() {
  const maxPct = Math.max(...CRIME_BREAKDOWN.map(c => c.pct));
  return (
    <Card>
      <div style={{ padding: 24 }}>
        <div style={{ fontFamily: T.serif, fontSize: 16, fontWeight: 700, color: T.ink, marginBottom: 4 }}>Crime Breakdown</div>
        <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, marginBottom: 16 }}>
          1,110 offences recorded · 12 months to Dec 2024
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {CRIME_BREAKDOWN.map(c => (
            <div key={c.type} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 140, fontFamily: T.sans, fontSize: 12, color: T.inkMuted, textAlign: 'right', flexShrink: 0 }}>{c.type}</div>
              <div style={{ flex: 1, height: 22, borderRadius: 6, background: T.dividerSoft, overflow: 'hidden', position: 'relative' }}>
                <div style={{
                  width: `${(c.pct / maxPct) * 100}%`, height: '100%', borderRadius: 6,
                  background: `linear-gradient(90deg, ${T.bad}90, ${T.bad}60)`,
                  transition: 'width 0.6s ease-out',
                }} />
              </div>
              <div style={{ width: 40, fontFamily: T.mono, fontSize: 12, fontWeight: 600, color: T.ink, textAlign: 'right' }}>{c.pct}%</div>
              <div style={{ width: 40, fontFamily: T.mono, fontSize: 10, color: T.inkFaint, textAlign: 'right' }}>{c.count}</div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

function AirQualityGauge() {
  const value = 10.2;
  const whoLimit = 15; // WHO guideline
  const maxScale = 30;
  const pctFill = Math.min((value / maxScale) * 100, 100);
  const pctWho = (whoLimit / maxScale) * 100;
  const isGood = value <= whoLimit;

  return (
    <Card>
      <div style={{ padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
          <div>
            <div style={{ fontFamily: T.serif, fontSize: 16, fontWeight: 700, color: T.ink }}>Air Quality — PM2.5</div>
            <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted }}>Annual mean concentration</div>
          </div>
          <div style={{ fontFamily: T.mono, fontSize: 22, fontWeight: 800, color: isGood ? T.good : T.bad }}>
            {value} <span style={{ fontSize: 12, fontWeight: 500, color: T.inkFaint }}>µg/m³</span>
          </div>
        </div>
        {/* Gauge bar */}
        <div style={{ position: 'relative', height: 28, borderRadius: 14, background: T.dividerSoft, overflow: 'visible', marginBottom: 8 }}>
          <div style={{
            width: `${pctFill}%`, height: '100%', borderRadius: 14,
            background: isGood
              ? 'linear-gradient(90deg, #059669, #34d399)'
              : 'linear-gradient(90deg, #d97706, #dc2626)',
            transition: 'width 0.8s ease-out',
          }} />
          {/* WHO marker */}
          <div style={{
            position: 'absolute', top: -4, left: `${pctWho}%`, transform: 'translateX(-50%)',
            display: 'flex', flexDirection: 'column', alignItems: 'center',
          }}>
            <div style={{ width: 2, height: 36, background: T.ink, opacity: 0.3, borderRadius: 1 }} />
            <div style={{ fontFamily: T.mono, fontSize: 9, color: T.inkMuted, marginTop: 2, whiteSpace: 'nowrap' }}>WHO limit</div>
          </div>
        </div>
        <div style={{ fontFamily: T.sans, fontSize: 12, color: isGood ? T.good : T.bad, fontWeight: 600 }}>
          {isGood ? '✓ Within WHO guideline' : '✗ Exceeds WHO guideline'}
          <span style={{ color: T.inkFaint, fontWeight: 400 }}> · Parent avg: 11.8 µg/m³</span>
        </div>
      </div>
    </Card>
  );
}

function NoiseScaleChart() {
  const dbColor = (db: number) => db <= 40 ? T.good : db <= 55 ? T.caution : db <= 65 ? '#f59e0b' : T.bad;
  return (
    <Card>
      <div style={{ padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <Volume2 size={16} color={T.accent} />
          <div style={{ fontFamily: T.serif, fontSize: 16, fontWeight: 700, color: T.ink }}>Noise Levels</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {NOISE_LEVELS.map(n => (
            <div key={n.source}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted }}>{n.source}</span>
                <span style={{ fontFamily: T.mono, fontSize: 12, fontWeight: 600, color: T.ink }}>{n.db} dB</span>
              </div>
              <div style={{ height: 10, borderRadius: 5, background: T.dividerSoft, overflow: 'hidden' }}>
                <div style={{
                  width: `${(n.db / 80) * 100}%`, height: '100%', borderRadius: 5,
                  background: dbColor(n.db), transition: 'width 0.6s ease-out',
                }} />
              </div>
              <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, marginTop: 2 }}>{n.category}</div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

function DemographicsChart() {
  const COLORS = ['#C2410C', '#7C3AED', '#059669', '#0891B2', '#D97706', '#A8A29E'];
  // Horizontal stacked bar
  return (
    <Card>
      <div style={{ padding: 24 }}>
        <div style={{ fontFamily: T.serif, fontSize: 16, fontWeight: 700, color: T.ink, marginBottom: 4 }}>Ethnic Composition</div>
        <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, marginBottom: 16 }}>Census 2021</div>
        {/* Stacked bar */}
        <div style={{ display: 'flex', height: 28, borderRadius: 14, overflow: 'hidden', marginBottom: 12 }}>
          {DEMOGRAPHICS.map((d, i) => (
            <div key={d.label} style={{
              width: `${d.pct}%`, height: '100%', background: COLORS[i],
              transition: 'width 0.5s ease-out',
            }}
              title={`${d.label}: ${d.pct}%`}
            />
          ))}
        </div>
        {/* Legend */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          {DEMOGRAPHICS.map((d, i) => (
            <div key={d.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 10, height: 10, borderRadius: 3, background: COLORS[i] }} />
              <span style={{ fontFamily: T.sans, fontSize: 11, color: T.inkMuted }}>{d.label}</span>
              <span style={{ fontFamily: T.mono, fontSize: 11, fontWeight: 600, color: T.ink }}>{d.pct}%</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

function TenureSplitChart() {
  const COLORS = ['#C2410C', '#7C3AED', '#0891B2', '#A8A29E'];
  return (
    <Card>
      <div style={{ padding: 24 }}>
        <div style={{ fontFamily: T.serif, fontSize: 16, fontWeight: 700, color: T.ink, marginBottom: 4 }}>Housing Tenure</div>
        <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, marginBottom: 16 }}>Census 2021</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {TENURE_SPLIT.map((t, i) => (
            <div key={t.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 110, fontFamily: T.sans, fontSize: 12, color: T.inkMuted, textAlign: 'right', flexShrink: 0 }}>{t.label}</div>
              <div style={{ flex: 1, height: 20, borderRadius: 6, background: T.dividerSoft, overflow: 'hidden' }}>
                <div style={{ width: `${t.pct}%`, height: '100%', borderRadius: 6, background: COLORS[i], transition: 'width 0.5s ease-out' }} />
              </div>
              <div style={{ width: 40, fontFamily: T.mono, fontSize: 12, fontWeight: 600, color: T.ink, textAlign: 'right' }}>{t.pct}%</div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   TABLE COMPONENTS
   ══════════════════════════════════════════════════════════════════════ */

function TransactionTableFull() {
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const thStyle: React.CSSProperties = {
    fontFamily: T.sans, fontSize: 10, fontWeight: 700, color: T.inkFaint,
    textTransform: 'uppercase', letterSpacing: '0.06em', padding: '10px 12px',
    textAlign: 'left', borderBottom: `2px solid ${T.divider}`,
    position: 'sticky' as const, top: 0, background: T.cardBg, zIndex: 1,
  };
  const tdStyle: React.CSSProperties = {
    fontFamily: T.sans, fontSize: 13, padding: '10px 12px',
    borderBottom: `1px solid ${T.dividerSoft}`, verticalAlign: 'middle',
  };

  return (
    <Card hover={false}>
      <div style={{ padding: '20px 24px 12px' }}>
        <div style={{ fontFamily: T.serif, fontSize: 16, fontWeight: 700, color: T.ink, marginBottom: 4 }}>Recent Transactions</div>
        <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, marginBottom: 16 }}>Showing 6 of 142 sales in the last 13 months</div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 700 }}>
          <thead>
            <tr>
              <th style={thStyle}>Date</th>
              <th style={thStyle}>Address</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Price</th>
              <th style={thStyle}>Type</th>
              <th style={thStyle}>Beds</th>
              <th style={thStyle}>Size</th>
              <th style={thStyle}>Tenure</th>
              <th style={thStyle}>EPC</th>
              <th style={{ ...thStyle, width: 32 }}></th>
            </tr>
          </thead>
          <tbody>
            {TRANSACTIONS.map((tx, i) => (
              <>
                <tr key={i} style={{ cursor: 'pointer', transition: 'background 0.15s', background: expandedRow === i ? T.accentLight : 'transparent' }}
                  onClick={() => setExpandedRow(expandedRow === i ? null : i)}
                  onMouseEnter={e => { if (expandedRow !== i) e.currentTarget.style.background = T.dividerSoft; }}
                  onMouseLeave={e => { if (expandedRow !== i) e.currentTarget.style.background = 'transparent'; }}
                >
                  <td style={{ ...tdStyle, fontFamily: T.mono, fontSize: 12, color: T.inkMuted, whiteSpace: 'nowrap' }}>{fmtDate(tx.date)}</td>
                  <td style={{ ...tdStyle, fontWeight: 500, color: T.ink }}>{tx.address}</td>
                  <td style={{ ...tdStyle, fontFamily: T.mono, fontWeight: 700, color: T.ink, textAlign: 'right' }}>{fmtPrice(tx.price)}</td>
                  <td style={tdStyle}>
                    <span style={{
                      fontFamily: T.sans, fontSize: 10, fontWeight: 600,
                      padding: '2px 8px', borderRadius: 6,
                      background: T.dividerSoft, color: T.inkMuted,
                    }}>{typeLabel(tx.type)}</span>
                  </td>
                  <td style={{ ...tdStyle, fontFamily: T.mono, fontSize: 12 }}>{tx.beds}</td>
                  <td style={{ ...tdStyle, fontFamily: T.mono, fontSize: 12 }}>{tx.sqft} sqft</td>
                  <td style={{ ...tdStyle, fontSize: 12, color: T.inkMuted }}>{tx.tenure}</td>
                  <td style={tdStyle}>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                      width: 22, height: 22, borderRadius: 5,
                      background: epcColour(tx.epc), color: 'white',
                      fontFamily: T.mono, fontSize: 10, fontWeight: 700,
                    }}>{tx.epc}</span>
                  </td>
                  <td style={tdStyle}>
                    {expandedRow === i ? <ChevronUp size={14} color={T.inkFaint} /> : <ChevronDown size={14} color={T.inkFaint} />}
                  </td>
                </tr>
                {expandedRow === i && (
                  <tr key={`${i}-detail`}>
                    <td colSpan={9} style={{ padding: 0 }}>
                      <div style={{
                        margin: '0 12px 12px', padding: '14px 18px', borderRadius: 12,
                        background: T.accentLight, borderLeft: `3px solid ${T.accent}`,
                      }}>
                        <div style={{ fontFamily: T.sans, fontSize: 10, fontWeight: 700, color: T.accent, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                          Transaction Detail
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                          <div>
                            <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint }}>Price/sqft</div>
                            <div style={{ fontFamily: T.mono, fontSize: 14, fontWeight: 700, color: T.ink }}>£{Math.round(tx.price / tx.sqft)}</div>
                          </div>
                          {tx.prevPrice && (
                            <>
                              <div>
                                <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint }}>Previous Sale</div>
                                <div style={{ fontFamily: T.mono, fontSize: 14, fontWeight: 700, color: T.ink }}>{fmtPrice(tx.prevPrice)}</div>
                                <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint }}>{tx.prevDate && fmtDate(tx.prevDate)}</div>
                              </div>
                              <div>
                                <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint }}>Price Change</div>
                                <div style={{
                                  fontFamily: T.mono, fontSize: 14, fontWeight: 700,
                                  color: tx.price > tx.prevPrice ? T.good : T.bad,
                                }}>
                                  {tx.price > tx.prevPrice ? '+' : ''}{((tx.price - tx.prevPrice) / tx.prevPrice * 100).toFixed(1)}%
                                </div>
                                <div style={{ fontFamily: T.mono, fontSize: 10, color: T.inkFaint }}>
                                  {tx.price > tx.prevPrice ? '+' : ''}{fmtPrice(tx.price - tx.prevPrice)}
                                </div>
                              </div>
                            </>
                          )}
                          {!tx.prevPrice && (
                            <div style={{ gridColumn: 'span 2' }}>
                              <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkFaint, fontStyle: 'italic' }}>No previous sale on record</div>
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function SchoolTableFull() {
  const [phaseFilter, setPhaseFilter] = useState('All');
  const [expandedSchool, setExpandedSchool] = useState<number | null>(null);
  const [detailTab, setDetailTab] = useState('overview');

  const filtered = phaseFilter === 'All' ? SCHOOLS : SCHOOLS.filter(s => s.phase === phaseFilter);

  const ofstedStyle = (rating: string) => {
    const m: Record<string, { bg: string; text: string }> = {
      'Outstanding': { bg: '#DCFCE7', text: '#15803D' },
      'Good': { bg: '#DBEAFE', text: '#1D4ED8' },
      'Requires Improvement': { bg: '#FEF3C7', text: '#92400E' },
      'Inadequate': { bg: '#FEE2E2', text: '#991B1B' },
    };
    return m[rating] || { bg: T.dividerSoft, text: T.inkFaint };
  };

  return (
    <Card hover={false}>
      <div style={{ padding: '20px 24px 0' }}>
        <div style={{ fontFamily: T.serif, fontSize: 16, fontWeight: 700, color: T.ink, marginBottom: 4 }}>Nearby Schools</div>
        <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, marginBottom: 14 }}>
          5 schools within 1 mile · sorted by distance
        </div>
        {/* Filter pills */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
          {['All', 'Primary', 'Secondary'].map(p => (
            <button key={p} onClick={() => { setPhaseFilter(p); setExpandedSchool(null); }} style={{
              fontFamily: T.sans, fontSize: 12, fontWeight: 600,
              padding: '6px 14px', borderRadius: 8, cursor: 'pointer',
              border: `1px solid ${phaseFilter === p ? T.accent : T.divider}`,
              background: phaseFilter === p ? T.accentLight : T.cardBg,
              color: phaseFilter === p ? T.accent : T.inkMuted,
              transition: 'all 0.15s',
            }}>
              {p}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {filtered.map((s, i) => {
          const oc = ofstedStyle(s.ofsted);
          const isExpanded = expandedSchool === i;
          return (
            <div key={s.name}>
              <div
                onClick={() => { setExpandedSchool(isExpanded ? null : i); setDetailTab('overview'); }}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '12px 24px', cursor: 'pointer',
                  borderTop: i === 0 ? `1px solid ${T.divider}` : 'none',
                  borderBottom: `1px solid ${T.dividerSoft}`,
                  background: isExpanded ? T.accentLight : 'transparent',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => { if (!isExpanded) e.currentTarget.style.background = T.dividerSoft; }}
                onMouseLeave={e => { if (!isExpanded) e.currentTarget.style.background = 'transparent'; }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontFamily: T.sans, fontSize: 13, fontWeight: 600, color: T.ink }}>{s.name}</div>
                  <div style={{ fontFamily: T.sans, fontSize: 11, color: T.inkFaint, marginTop: 2 }}>
                    {s.phase} · {s.distance} · {s.pupils} pupils
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {s.ks2 !== undefined && (
                    <span style={{ fontFamily: T.mono, fontSize: 12, fontWeight: 600, color: T.ink }}>KS2: {s.ks2}%</span>
                  )}
                  {s.p8 !== undefined && (
                    <span style={{ fontFamily: T.mono, fontSize: 12, fontWeight: 600, color: s.p8 >= 0 ? T.good : T.bad }}>
                      P8: {s.p8 > 0 ? '+' : ''}{s.p8}
                    </span>
                  )}
                  <span style={{
                    fontFamily: T.sans, fontSize: 10, fontWeight: 700,
                    padding: '3px 10px', borderRadius: 6,
                    background: oc.bg, color: oc.text,
                  }}>{s.ofsted}</span>
                  {isExpanded ? <ChevronUp size={14} color={T.inkFaint} /> : <ChevronDown size={14} color={T.inkFaint} />}
                </div>
              </div>

              {/* Expanded detail panel */}
              {isExpanded && (
                <div style={{ padding: '0 24px 16px', background: T.accentLight }}>
                  {/* Detail tabs */}
                  <div style={{ display: 'flex', gap: 2, marginBottom: 14, paddingTop: 12 }}>
                    {['overview', 'results', 'ofsted', 'demographics'].map(tab => (
                      <button key={tab} onClick={e => { e.stopPropagation(); setDetailTab(tab); }} style={{
                        fontFamily: T.sans, fontSize: 11, fontWeight: detailTab === tab ? 700 : 500,
                        padding: '5px 12px', borderRadius: 6, cursor: 'pointer',
                        background: detailTab === tab ? T.accent : 'transparent',
                        color: detailTab === tab ? 'white' : T.inkMuted,
                        border: 'none', transition: 'all 0.15s', textTransform: 'capitalize',
                      }}>
                        {tab}
                      </button>
                    ))}
                  </div>

                  {detailTab === 'overview' && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                      {[
                        { label: 'Pupils', value: s.pupils.toString() },
                        { label: 'FSM %', value: `${s.fsm}%` },
                        { label: 'Last Inspected', value: s.lastInspection },
                        { label: 'Distance', value: s.distance },
                        { label: 'Phase', value: s.phase },
                        { label: 'Ofsted', value: s.ofsted },
                      ].map(item => (
                        <div key={item.label} style={{ background: T.cardBg, borderRadius: 10, padding: '10px 14px', border: `1px solid ${T.divider}` }}>
                          <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{item.label}</div>
                          <div style={{ fontFamily: T.mono, fontSize: 14, fontWeight: 700, color: T.ink, marginTop: 4 }}>{item.value}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {detailTab === 'results' && (
                    <div style={{ background: T.cardBg, borderRadius: 10, padding: 16, border: `1px solid ${T.divider}` }}>
                      {s.ks2 !== undefined && (
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, color: T.inkMuted, marginBottom: 6 }}>KS2 — Expected Standard (RWM)</div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <div style={{ flex: 1, height: 16, borderRadius: 8, background: T.dividerSoft, overflow: 'hidden' }}>
                              <div style={{ width: `${s.ks2}%`, height: '100%', borderRadius: 8, background: s.ks2 >= 65 ? T.good : T.caution }} />
                            </div>
                            <span style={{ fontFamily: T.mono, fontSize: 14, fontWeight: 700, color: T.ink }}>{s.ks2}%</span>
                          </div>
                          <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, marginTop: 4 }}>National average: 60%</div>
                        </div>
                      )}
                      {s.p8 !== undefined && (
                        <div>
                          <div style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, color: T.inkMuted, marginBottom: 6 }}>Progress 8 Score</div>
                          <div style={{ fontFamily: T.mono, fontSize: 24, fontWeight: 800, color: s.p8 >= 0 ? T.good : T.bad }}>
                            {s.p8 > 0 ? '+' : ''}{s.p8}
                          </div>
                          <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, marginTop: 4 }}>
                            {s.p8 >= 0.2 ? 'Well above average' : s.p8 >= 0 ? 'Above average' : s.p8 >= -0.2 ? 'Below average' : 'Well below average'}
                          </div>
                        </div>
                      )}
                      {s.ks2 === undefined && s.p8 === undefined && (
                        <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkFaint, fontStyle: 'italic' }}>No results data available</div>
                      )}
                    </div>
                  )}

                  {detailTab === 'ofsted' && (
                    <div style={{ background: T.cardBg, borderRadius: 10, padding: 16, border: `1px solid ${T.divider}` }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                        <span style={{
                          fontFamily: T.sans, fontSize: 13, fontWeight: 700,
                          padding: '4px 14px', borderRadius: 8,
                          background: ofstedStyle(s.ofsted).bg, color: ofstedStyle(s.ofsted).text,
                        }}>{s.ofsted}</span>
                        <span style={{ fontFamily: T.sans, fontSize: 12, color: T.inkFaint }}>Last inspected {s.lastInspection}</span>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                        {['Quality of Education', 'Behaviour & Attitudes', 'Personal Development', 'Leadership & Management'].map(area => (
                          <div key={area} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${T.dividerSoft}` }}>
                            <span style={{ fontFamily: T.sans, fontSize: 11, color: T.inkMuted }}>{area}</span>
                            <span style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, color: T.ink }}>
                              {s.ofsted === 'Outstanding' ? 'Outstanding' : s.ofsted === 'Good' ? 'Good' : 'Requires Improvement'}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {detailTab === 'demographics' && (
                    <div style={{ background: T.cardBg, borderRadius: 10, padding: 16, border: `1px solid ${T.divider}` }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                        {[
                          { label: 'FSM Eligible', value: `${s.fsm}%`, note: s.fsm > 20 ? 'Above national avg (22.5%)' : 'Below national avg (22.5%)' },
                          { label: 'Pupil Count', value: s.pupils.toString(), note: s.phase === 'Primary' ? 'Average primary: 280' : 'Average secondary: 1,050' },
                        ].map(item => (
                          <div key={item.label}>
                            <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{item.label}</div>
                            <div style={{ fontFamily: T.mono, fontSize: 18, fontWeight: 700, color: T.ink, marginTop: 4 }}>{item.value}</div>
                            <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, marginTop: 2 }}>{item.note}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   MAP PANEL — Real MapView placeholder with warm styling
   ══════════════════════════════════════════════════════════════════════ */

function MapPanel() {
  return (
    <div style={{
      borderRadius: 16, overflow: 'hidden', border: `1px solid ${T.divider}`,
      height: 400, position: 'relative', background: T.warmBg,
    }}>
      {/* OSM embed as map background */}
      <iframe
        title="Area map"
        src="https://www.openstreetmap.org/export/embed.html?bbox=-0.15,51.30,-0.10,51.34&layer=mapnik&marker=51.32,-0.125"
        style={{ width: '100%', height: '100%', border: 'none' }}
      />
      {/* Floating legend card */}
      <div style={{
        position: 'absolute', top: 12, right: 12, background: 'rgba(255,255,255,0.92)',
        backdropFilter: 'blur(8px)', borderRadius: 12, padding: '10px 14px',
        boxShadow: '0 2px 12px rgba(0,0,0,0.1)', border: `1px solid ${T.divider}`,
      }}>
        <div style={{ fontFamily: T.sans, fontSize: 10, fontWeight: 700, color: T.inkFaint, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Legend</div>
        {[
          { color: '#C2410C', label: 'Sold prices' },
          { color: '#059669', label: 'Outstanding schools' },
          { color: '#2563eb', label: 'Good schools' },
          { color: '#7C3AED', label: 'Stations' },
        ].map(l => (
          <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: 4, background: l.color }} />
            <span style={{ fontFamily: T.sans, fontSize: 10, color: T.inkMuted }}>{l.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   PAGE SECTIONS
   ══════════════════════════════════════════════════════════════════════ */

function NavBar() {
  return (
    <nav style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '16px 32px', borderBottom: `1px solid ${T.divider}`,
      background: T.cardBg, position: 'sticky', top: 0, zIndex: 50,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: T.accent, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Leaf size={16} color="white" />
        </div>
        <span style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 20, color: T.ink, letterSpacing: '-0.02em' }}>PropertyPulse</span>
      </div>
      <span style={{
        fontFamily: T.sans, fontSize: 11, fontWeight: 600,
        background: T.accentLight, color: T.accent, padding: '4px 12px', borderRadius: 20,
        border: `1px solid ${T.accentBg}`,
      }}>PROTOTYPE 2</span>
    </nav>
  );
}

function HeroSection() {
  return (
    <div style={{ background: T.heroGrad, padding: '40px 32px' }}>
      <div style={{ maxWidth: 820, margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <h1 style={{ fontFamily: T.serif, fontWeight: 800, fontSize: 36, color: 'white', letterSpacing: '-0.03em', lineHeight: 1.1, margin: 0 }}>
              {AREA.name}
              <span style={{ fontWeight: 400, fontSize: 20, color: 'rgba(255,255,255,0.45)', marginLeft: 8 }}>{AREA.parent}</span>
            </h1>
            <p style={{ fontFamily: T.sans, fontSize: 13, color: 'rgba(255,255,255,0.4)', marginTop: 8, lineHeight: 1.5 }}>
              {AREA.type} · {AREA.lsoaCount} LSOAs · {AREA.county}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {[{ icon: Bookmark, label: 'Save' }, { icon: FileDown, label: 'Report' }].map(b => (
              <button key={b.label} style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '8px 16px', borderRadius: 10, fontSize: 13, fontWeight: 600,
                fontFamily: T.sans, background: 'rgba(255,255,255,0.08)', color: 'white',
                border: '1px solid rgba(255,255,255,0.12)', cursor: 'pointer', transition: 'background 0.2s',
              }}
                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.14)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
              >
                <b.icon size={14} /> {b.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function PersonaFitBanner() {
  const score = 74;
  const verdictColor = score >= 70 ? T.good : score >= 45 ? T.caution : T.bad;
  const verdict = score >= 70 ? 'Strong' : score >= 45 ? 'Mixed' : 'Weak';
  return (
    <div style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px', transform: 'translateY(-28px)', marginBottom: -12 }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: T.cardBg, borderRadius: 16, padding: '16px 24px',
        border: `1px solid ${T.divider}`, boxShadow: '0 4px 16px rgba(0,0,0,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <svg width={52} height={52} viewBox="0 0 52 52">
            <circle cx={26} cy={26} r={22} fill="none" stroke={T.divider} strokeWidth={5} />
            <circle cx={26} cy={26} r={22} fill="none" stroke={verdictColor} strokeWidth={5}
              strokeDasharray={`${(score / 100) * 138.2} 138.2`} strokeLinecap="round" transform="rotate(-90 26 26)"
              style={{ transition: 'stroke-dasharray 0.7s ease-out' }} />
            <text x={26} y={26} textAnchor="middle" dominantBaseline="central"
              style={{ fontFamily: T.mono, fontSize: 14, fontWeight: 700, fill: T.ink }}>{score}</text>
          </svg>
          <div>
            <div style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 16, color: T.ink }}>
              Persona Fit: <span style={{ color: verdictColor }}>{verdict}</span>
            </div>
            <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, marginTop: 2 }}>Based on 72 metrics · First-Time Buyer</div>
          </div>
        </div>
        <button style={{
          fontFamily: T.sans, fontSize: 12, fontWeight: 600, color: T.accent, background: T.accentLight,
          border: `1px solid ${T.accentBg}`, padding: '6px 14px', borderRadius: 8, cursor: 'pointer',
        }}>Change persona</button>
      </div>
    </div>
  );
}

function SnapshotGrid() {
  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px 32px' }}>
      <h2 style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 22, color: T.ink, letterSpacing: '-0.02em', marginBottom: 16 }}>Area Snapshot</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(145px, 1fr))', gap: 12 }}>
        {HEADLINE_METRICS.map((m, i) => (
          <div key={m.id} style={{
            background: T.cardBg, borderRadius: 14, padding: '16px 18px',
            border: `1px solid ${T.divider}`, transition: 'box-shadow 0.2s, transform 0.2s', cursor: 'default',
            animation: `fadeInUp 0.4s ease-out ${i * 60}ms both`,
          }}
            onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.transform = 'translateY(0)'; }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <div style={{ width: 28, height: 28, borderRadius: 7, background: T.accentLight, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <m.icon size={14} color={T.accent} />
              </div>
              <span style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, color: T.inkMuted }}>{m.label}</span>
            </div>
            <div style={{ fontFamily: T.mono, fontSize: 20, fontWeight: 700, color: T.ink, lineHeight: 1.1 }}>{m.value}</div>
            {m.unit && <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, marginTop: 2 }}>{m.unit}</div>}
            <div style={{ marginTop: 8 }}><ComparisonArrow value={m.value} parentValue={m.parent} direction={m.direction} /></div>
            {m.trend && (
              <div style={{ fontFamily: T.mono, fontSize: 10, fontWeight: 600, color: m.trend.startsWith('-') ? T.good : T.inkMuted, marginTop: 4 }}>
                {m.trend} YoY
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function TabScoreCards() {
  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px 32px' }}>
      <h2 style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 22, color: T.ink, letterSpacing: '-0.02em', marginBottom: 16 }}>Tab Scores</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(145px, 1fr))', gap: 12 }}>
        {TAB_SCORES.map((t, i) => {
          const verdict = t.score >= 70 ? 'Strong' : t.score >= 45 ? 'Mixed' : 'Weak';
          const vColor = t.score >= 70 ? T.good : t.score >= 45 ? T.caution : T.bad;
          return (
            <div key={t.tab} style={{
              background: T.cardBg, borderRadius: 14, padding: '18px 20px',
              border: `1px solid ${T.divider}`, cursor: 'pointer', transition: 'all 0.2s',
              animation: `fadeInUp 0.4s ease-out ${i * 60}ms both`,
            }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = t.colour; e.currentTarget.style.boxShadow = `0 4px 12px ${t.colour}15`; e.currentTarget.style.transform = 'translateY(-2px)'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = T.divider; e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.transform = 'translateY(0)'; }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <t.icon size={16} color={t.colour} />
                <span style={{ fontFamily: T.sans, fontSize: 12, fontWeight: 600, color: T.ink }}>{t.tab.split(' & ')[0]}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                <span style={{ fontFamily: T.mono, fontSize: 28, fontWeight: 800, color: T.ink }}>{t.score}</span>
                <span style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, color: vColor, background: vColor + '15', padding: '2px 8px', borderRadius: 6 }}>{verdict}</span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ComparableAreasSection() {
  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px 32px' }}>
      <h2 style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 22, color: T.ink, letterSpacing: '-0.02em', marginBottom: 6 }}>Comparable Areas</h2>
      <p style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, marginBottom: 16, lineHeight: 1.5 }}>
        Matched across 11 dimensions: price, rent, earnings, air quality, growth, crime, deprivation, demographics, transport, and council tax.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {COMPARABLE_AREAS.map((a, i) => (
          <Card key={a.name} style={{ animation: `fadeInUp 0.4s ease-out ${i * 80}ms both` }}>
            <div style={{ padding: '18px 22px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div>
                  <span style={{ fontFamily: T.sans, fontSize: 14, fontWeight: 700, color: T.ink }}>{a.name}</span>
                  <span style={{ fontFamily: T.sans, fontSize: 12, color: T.inkFaint, marginLeft: 6 }}>{a.parent}</span>
                </div>
                <button style={{
                  fontFamily: T.sans, fontSize: 11, fontWeight: 600, color: T.accent, background: T.accentLight,
                  border: `1px solid ${T.accentBg}`, padding: '4px 12px', borderRadius: 8, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 4,
                }}>View area <ArrowRight size={11} /></button>
              </div>
              <SimilarityBar pct={a.match} />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 14, paddingTop: 14, borderTop: `1px solid ${T.dividerSoft}` }}>
                <div>
                  <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Avg Price</div>
                  <div style={{ fontFamily: T.mono, fontSize: 13, fontWeight: 700, color: T.ink, marginTop: 2 }}>{a.avgPrice}</div>
                </div>
                <div>
                  <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Crime Rate</div>
                  <div style={{ fontFamily: T.mono, fontSize: 13, fontWeight: 700, color: T.ink, marginTop: 2 }}>{a.crimeRate}</div>
                </div>
                <div>
                  <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Match</div>
                  <div style={{ fontFamily: T.mono, fontSize: 13, fontWeight: 700, color: a.match >= 75 ? T.good : T.caution, marginTop: 2 }}>{a.match}%</div>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </section>
  );
}

function CrimeTrendSection() {
  const latest = CRIME_TREND[CRIME_TREND.length - 1];
  const prev = CRIME_TREND[CRIME_TREND.length - 2];
  const change = ((latest.rate - prev.rate) / prev.rate * 100).toFixed(1);
  const isDown = latest.rate < prev.rate;
  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px 32px' }}>
      <Card hover={false}>
        <div style={{ padding: 24 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <Shield size={16} color={T.accent} />
                <h3 style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 18, color: T.ink, margin: 0 }}>Crime Trend</h3>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
                <span style={{ fontFamily: T.mono, fontSize: 32, fontWeight: 800, color: T.ink }}>{latest.rate}</span>
                <span style={{ fontFamily: T.sans, fontSize: 12, color: T.inkFaint }}>per 1,000 pop</span>
              </div>
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 4, fontFamily: T.mono, fontSize: 12, fontWeight: 600,
                color: isDown ? T.good : T.bad, background: isDown ? T.goodBg : T.badBg,
                padding: '3px 10px', borderRadius: 6, marginTop: 8,
              }}>
                {isDown ? <TrendingDown size={12} /> : <TrendingUp size={12} />}
                {isDown ? '' : '+'}{change}% vs last year
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
              <Sparkline data={CRIME_TREND.map(d => ({ value: d.rate }))} color={isDown ? T.good : T.bad} />
              <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, marginTop: 4 }}>{CRIME_TREND[0].year}–{latest.year}</div>
            </div>
          </div>
          {/* Extremes */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 20, paddingTop: 20, borderTop: `1px solid ${T.dividerSoft}` }}>
            <div>
              <div style={{ fontFamily: T.sans, fontSize: 10, fontWeight: 700, color: T.good, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8 }}>Safest Nearby</div>
              {[{ name: 'Sanderstead', rate: 41.7 }, { name: 'Kenley', rate: 52.9 }, { name: 'Coulsdon', rate: 62.4 }].map(a => (
                <div key={a.name} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${T.dividerSoft}` }}>
                  <span style={{ fontFamily: T.sans, fontSize: 13, color: T.ink, fontWeight: a.name === 'Coulsdon' ? 700 : 400 }}>{a.name} {a.name === 'Coulsdon' && '←'}</span>
                  <span style={{ fontFamily: T.mono, fontSize: 12, color: T.inkMuted }}>{a.rate}</span>
                </div>
              ))}
            </div>
            <div>
              <div style={{ fontFamily: T.sans, fontSize: 10, fontWeight: 700, color: T.bad, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8 }}>Highest Crime</div>
              {[{ name: 'Broad Green', rate: 142.3 }, { name: 'Thornton Heath', rate: 128.7 }, { name: 'West Croydon', rate: 115.2 }].map(a => (
                <div key={a.name} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${T.dividerSoft}` }}>
                  <span style={{ fontFamily: T.sans, fontSize: 13, color: T.ink }}>{a.name}</span>
                  <span style={{ fontFamily: T.mono, fontSize: 12, color: T.inkMuted }}>{a.rate}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>
    </section>
  );
}

function HomePageDemo() {
  return (
    <section style={{ position: 'relative', overflow: 'hidden', minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Map background */}
      <div style={{ position: 'absolute', inset: 0, zIndex: 0 }}>
        <iframe title="Decorative map background"
          src="https://www.openstreetmap.org/export/embed.html?bbox=-6.5,49.5,2.5,56.5&layer=mapnik"
          style={{ width: '100%', height: '100%', border: 'none', pointerEvents: 'none', filter: 'grayscale(100%) brightness(1.1) contrast(0.7)', transform: 'scale(1.15)', transformOrigin: 'center center' }}
          tabIndex={-1} aria-hidden="true" />
        <div style={{ position: 'absolute', inset: 0, background: `linear-gradient(180deg, ${T.pageBg}E8 0%, ${T.pageBg}CC 30%, ${T.pageBg}B8 50%, ${T.pageBg}CC 70%, ${T.pageBg}F0 100%)`, zIndex: 1 }} />
        <div style={{ position: 'absolute', inset: 0, zIndex: 2, pointerEvents: 'none', background: `radial-gradient(ellipse 60% 50% at 50% 40%, ${T.accent}08 0%, transparent 70%)` }} />
      </div>
      {/* Content */}
      <div style={{ position: 'relative', zIndex: 10, flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '80px 32px' }}>
        <div style={{ maxWidth: 820, margin: '0 auto', width: '100%' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
            <h2 style={{ fontFamily: T.serif, fontWeight: 800, fontSize: 48, color: T.ink, letterSpacing: '-0.03em', lineHeight: 1.05, marginBottom: 16, maxWidth: 560 }}>
              Know your{' '}
              <span style={{ background: `linear-gradient(135deg, ${T.accent}, ${T.accentMid})`, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>neighbourhood.</span>
            </h2>
            <p style={{ fontFamily: T.sans, fontSize: 17, color: T.inkMuted, maxWidth: 420, lineHeight: 1.6, marginBottom: 36 }}>
              The most complete area analysis for UK property. Every postcode, every metric, personalised for you.
            </p>
            <div style={{ width: '100%', maxWidth: 540, position: 'relative' }}>
              <div style={{
                display: 'flex', alignItems: 'center', height: 58, background: 'rgba(255,255,255,0.85)',
                backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', borderRadius: 18,
                border: `2px solid ${T.divider}`, padding: '0 8px 0 18px',
                boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
              }}>
                <Search size={18} color={T.inkFaint} style={{ marginRight: 12, flexShrink: 0 }} />
                <span style={{ fontFamily: T.sans, fontSize: 15, color: T.inkFaint, flex: 1 }}>Enter a postcode or place name...</span>
                <button style={{
                  padding: '10px 24px', borderRadius: 12, background: T.accent, color: 'white',
                  fontFamily: T.sans, fontSize: 14, fontWeight: 700, border: 'none', cursor: 'pointer', flexShrink: 0,
                }}>Analyse</button>
              </div>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 16, justifyContent: 'center' }}>
              {['SW1A 1AA', 'M1 1AE', 'E1 6RF', 'BS1 4DJ', 'CR5 1RA'].map(q => (
                <span key={q} style={{
                  fontFamily: T.mono, fontSize: 12, fontWeight: 600, padding: '6px 14px', borderRadius: 20,
                  background: 'rgba(255,255,255,0.75)', backdropFilter: 'blur(8px)', border: `1px solid ${T.divider}`,
                  color: T.inkMuted, cursor: 'pointer', transition: 'all 0.15s',
                }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = T.accent; e.currentTarget.style.color = T.accent; e.currentTarget.style.background = 'rgba(255,247,237,0.9)'; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = T.divider; e.currentTarget.style.color = T.inkMuted; e.currentTarget.style.background = 'rgba(255,255,255,0.75)'; }}
                >{q}</span>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <span style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, padding: '4px 12px', borderRadius: 20, background: 'rgba(236,253,245,0.85)', color: T.good, border: `1px solid ${T.sageLight}` }}>Live: England, Wales</span>
              <span style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, padding: '4px 12px', borderRadius: 20, background: 'rgba(255,251,235,0.85)', color: T.caution, border: '1px solid #FDE68A' }}>Planned: Scotland, NI</span>
            </div>
          </div>
        </div>
      </div>
      {/* Feature tiles */}
      <div style={{ position: 'relative', zIndex: 10, padding: '0 32px 60px' }}>
        <div style={{ maxWidth: 820, margin: '0 auto' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
            {[
              { icon: TrendingUp, title: 'Property & Market', hint: 'Prices, yields, trends' },
              { icon: Coffee, title: 'Lifestyle', hint: 'Transport, broadband, amenities' },
              { icon: Shield, title: 'Safety', hint: 'Flood, air quality, crime' },
              { icon: GraduationCap, title: 'Schools', hint: 'Ofsted, KS2/KS4, walk time' },
              { icon: Users, title: 'Community', hint: 'Demographics, deprivation' },
              { icon: Landmark, title: 'Governance', hint: 'Council tax, politics' },
            ].map(f => (
              <div key={f.title} style={{
                display: 'flex', alignItems: 'center', gap: 14, padding: '14px 18px', borderRadius: 14,
                background: 'rgba(255,255,255,0.8)', backdropFilter: 'blur(10px)', border: `1px solid ${T.divider}`,
                cursor: 'pointer', transition: 'all 0.2s',
              }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = T.accent; e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.08)'; e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.background = 'rgba(255,255,255,0.95)'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = T.divider; e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.background = 'rgba(255,255,255,0.8)'; }}
              >
                <div style={{ width: 36, height: 36, borderRadius: 9, background: T.accentLight, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <f.icon size={16} color={T.accent} />
                </div>
                <div>
                  <div style={{ fontFamily: T.sans, fontSize: 13, fontWeight: 700, color: T.ink }}>{f.title}</div>
                  <div style={{ fontFamily: T.sans, fontSize: 11, color: T.inkFaint }}>{f.hint}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function FooterDemo() {
  return (
    <footer style={{
      padding: '20px 32px', textAlign: 'center', fontFamily: T.sans, fontSize: 11, color: T.inkFaint,
      borderTop: `1px solid ${T.divider}`, background: T.pageBg,
    }}>
      Data from OS, Land Registry, ONS, Ofcom, Ofsted, NHS &copy; Crown Copyright. &copy; OpenStreetMap Contributors.
    </footer>
  );
}

function TabBarDemo({ active, onChange }: { active: string; onChange: (tab: string) => void }) {
  const tabs = [
    { name: 'Overview', icon: LayoutDashboard },
    { name: 'Property', icon: Home },
    { name: 'Safety', icon: Shield },
    { name: 'Community', icon: Users },
  ];
  return (
    <div style={{ position: 'sticky', top: 65, zIndex: 40, background: T.cardBg, borderBottom: `1px solid ${T.divider}`, padding: '0 32px' }}>
      <div style={{ maxWidth: 820, margin: '0 auto', display: 'flex', gap: 2, overflowX: 'auto', padding: '8px 0' }}>
        {tabs.map(t => {
          const isActive = active === t.name;
          return (
            <button key={t.name} onClick={() => onChange(t.name)} style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 10, cursor: 'pointer',
              fontFamily: T.sans, fontSize: 13, fontWeight: isActive ? 700 : 500,
              color: isActive ? T.accent : T.inkMuted, background: isActive ? T.accentLight : 'transparent',
              border: 'none', transition: 'all 0.15s', whiteSpace: 'nowrap', position: 'relative',
            }}>
              <t.icon size={14} />
              {t.name}
              {isActive && <div style={{ position: 'absolute', bottom: -8, left: '20%', right: '20%', height: 2, borderRadius: 1, background: T.accent }} />}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   MAIN PAGE
   ══════════════════════════════════════════════════════════════════════ */
export default function Prototype2() {
  const [activeTab, setActiveTab] = useState('Overview');
  const [showHomepage, setShowHomepage] = useState(true);

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@400;500;600;700;800;900&display=swap');
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div style={{ minHeight: '100dvh', display: 'flex', flexDirection: 'column', background: T.pageBg }}>
        {/* Toggle */}
        <div style={{ position: 'fixed', bottom: 20, right: 20, zIndex: 100, display: 'flex', gap: 8 }}>
          {['Homepage', 'Results'].map(v => (
            <button key={v} onClick={() => setShowHomepage(v === 'Homepage')} style={{
              padding: '10px 18px', borderRadius: 12, fontFamily: T.sans, fontSize: 12, fontWeight: 700,
              background: (v === 'Homepage') === showHomepage ? T.accent : T.cardBg,
              color: (v === 'Homepage') === showHomepage ? 'white' : T.ink,
              border: `1px solid ${(v === 'Homepage') === showHomepage ? T.accent : T.divider}`,
              cursor: 'pointer', boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            }}>{v}</button>
          ))}
        </div>

        {showHomepage ? (
          <>
            <NavBar />
            <HomePageDemo />
            <FooterDemo />
          </>
        ) : (
          <>
            <NavBar />
            <HeroSection />
            <PersonaFitBanner />
            <TabBarDemo active={activeTab} onChange={setActiveTab} />

            <div style={{ paddingTop: 28, paddingBottom: 48, minHeight: 600 }}>
              {activeTab === 'Overview' && (
                <>
                  <SnapshotGrid />
                  <TabScoreCards />
                  {/* Map */}
                  <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px 32px' }}>
                    <MapPanel />
                  </section>
                  <CrimeTrendSection />
                  <ComparableAreasSection />
                </>
              )}

              {activeTab === 'Property' && (
                <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px' }}>
                  <SectionHeading icon={Home} title="Property & Market" subtitle="Prices, transactions, yields, and trends" />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                    <PriceTrendChart />
                    <TransactionTableFull />
                  </div>
                </section>
              )}

              {activeTab === 'Safety' && (
                <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px' }}>
                  <SectionHeading icon={Shield} title="Environment & Safety" subtitle="Crime, air quality, noise, and flood risk" />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                    <CrimeBreakdownChart />
                    <AirQualityGauge />
                    <NoiseScaleChart />
                  </div>
                </section>
              )}

              {activeTab === 'Community' && (
                <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px' }}>
                  <SectionHeading icon={Users} title="Community & Education" subtitle="Schools, demographics, deprivation, and tenure" />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                    <SchoolTableFull />
                    <DemographicsChart />
                    <TenureSplitChart />
                  </div>
                </section>
              )}
            </div>

            <FooterDemo />
          </>
        )}
      </div>
    </>
  );
}
