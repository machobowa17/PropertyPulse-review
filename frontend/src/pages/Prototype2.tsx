/**
 * Prototype 2 — BurbScore-inspired design refresh mockup.
 *
 * Standalone page at /prototype2 with MOCK DATA. Demonstrates:
 * - Warm earth-tone palette (cream, burnt orange, sage green)
 * - 3-font system (serif display + sans body + mono data)
 * - Generous whitespace and narrower max-width
 * - Micro-interactions (staggered reveals, hover elevations)
 * - Narrative-first data presentation
 * - Trend sparklines and extremes comparisons
 *
 * Does NOT touch any existing components or pages.
 */
import { useState } from 'react';
import {
  Search, Leaf, TrendingUp, TrendingDown, Shield, Users,
  Building2, Home, Coffee, TreePine, Landmark, ArrowRight, ArrowUpRight,
  ArrowDownRight, Minus, ChevronDown,
  GraduationCap, Train, Wind, Wifi, PoundSterling,
  Scale, FileDown, Bookmark,
  LayoutDashboard,
} from 'lucide-react';

/* ── Design Tokens ──────────────────────────────────────────────────── */
// BurbScore-inspired warm palette
const T = {
  // backgrounds
  pageBg:      '#FAF8F5',   // warm cream
  cardBg:      '#FFFFFF',
  cardHoverBg: '#FEFDFB',
  warmBg:      '#F5F0EB',   // slightly warmer
  heroBg:      '#1C1917',   // stone-950 (warm dark)
  heroGrad:    'linear-gradient(135deg, #1C1917 0%, #292524 50%, #1C1917 100%)',

  // accent
  accent:      '#C2410C',   // burnt orange-700
  accentLight: '#FFF7ED',   // orange-50
  accentMid:   '#EA580C',   // orange-600
  accentHover: '#9A3412',   // orange-800
  accentBg:    '#FED7AA',   // orange-200

  // secondary accent (sage green)
  sage:        '#15803D',   // green-700
  sageBg:      '#F0FDF4',   // green-50
  sageLight:   '#DCFCE7',   // green-100

  // text
  ink:         '#1C1917',   // stone-900
  inkMuted:    '#57534E',   // stone-600
  inkFaint:    '#A8A29E',   // stone-400

  // borders
  divider:     '#E7E5E4',   // stone-200
  dividerSoft: '#F5F5F4',   // stone-100

  // signals
  good:        '#059669',
  goodBg:      '#ECFDF5',
  caution:     '#D97706',
  cautionBg:   '#FFFBEB',
  bad:         '#DC2626',
  badBg:       '#FEF2F2',

  // fonts
  serif:       "'Fraunces', 'Playfair Display', Georgia, serif",
  sans:        "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  mono:        "'JetBrains Mono', 'IBM Plex Mono', ui-monospace, monospace",
} as const;

/* ── Mock Data ──────────────────────────────────────────────────────── */
const AREA = {
  name: 'Coulsdon',
  parent: 'Croydon',
  county: 'Greater London',
  type: 'Ward',
  lsoaCount: 7,
};

const Receipt = Building2; // stand-in icon for council tax

const HEADLINE_METRICS = [
  { id: 'avg_price', label: 'Avg Price', value: '£485,200', parent: '£412,800', direction: 'higher_is_neutral' as const, icon: PoundSterling, trend: '+3.2%' },
  { id: 'council_tax', label: 'Council Tax', value: '£1,891', parent: '£1,724', direction: 'lower_is_better' as const, icon: Receipt, trend: '+4.1%' },
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

const CRIME_TREND = [
  { year: '2019', rate: 74.2 },
  { year: '2020', rate: 65.1 },
  { year: '2021', rate: 68.9 },
  { year: '2022', rate: 71.3 },
  { year: '2023', rate: 67.8 },
  { year: '2024', rate: 62.4 },
];

const SAMPLE_METRICS = [
  { label: 'Median Price (13m)', value: '£465,000', parent: '£398,500', good: true, detail: 'Based on 142 transactions in the past 13 months across 7 LSOAs.' },
  { label: 'Avg Price/sqft', value: '£412', parent: '£378', good: true, detail: 'Derived from EPC-matched transactions with known floor area.' },
  { label: 'Yield Estimate', value: '4.1%', parent: '3.8%', good: true, detail: 'Annual rental income as % of average purchase price.' },
  { label: 'Transactions (13m)', value: '142', parent: '1,847', good: false, detail: 'Total completed sales in the last 13 months.' },
  { label: 'Price Growth (1yr)', value: '+3.2%', parent: '+2.1%', good: true, detail: 'Year-on-year change in rolling 13-month median price.' },
  { label: 'Days on Market', value: '34', parent: '42', good: true, detail: 'Average time from listing to sale completion (estimated).' },
];

const SCHOOL_DATA = [
  { name: 'Woodcote Primary', phase: 'Primary', ofsted: 'Outstanding', distance: '0.3 mi', ks2: 72 },
  { name: 'Coulsdon C of E Primary', phase: 'Primary', ofsted: 'Good', distance: '0.4 mi', ks2: 65 },
  { name: 'Smitham Primary', phase: 'Primary', ofsted: 'Good', distance: '0.6 mi', ks2: 68 },
  { name: 'Oasis Academy Coulsdon', phase: 'Secondary', ofsted: 'Good', distance: '0.5 mi', p8: 0.21 },
  { name: 'Woodcote High School', phase: 'Secondary', ofsted: 'Requires Improvement', distance: '0.8 mi', p8: -0.15 },
];

/* ── Utility Components ─────────────────────────────────────────────── */

function ComparisonArrow({ value, parentValue, direction }: {
  value: string; parentValue: string; direction: string;
}) {
  // Simple heuristic: strip non-numeric, compare
  const numVal = parseFloat(value.replace(/[^0-9.\-]/g, ''));
  const numParent = parseFloat(parentValue.replace(/[^0-9.\-]/g, ''));
  if (isNaN(numVal) || isNaN(numParent)) return <span style={{ color: T.inkFaint, fontFamily: T.sans, fontSize: 11 }}>—</span>;

  const diff = numVal - numParent;
  const isHigher = diff > 0;
  const isGood = direction === 'higher_is_better' ? isHigher
    : direction === 'lower_is_better' ? !isHigher
    : null;

  const color = isGood === true ? T.good : isGood === false ? T.caution : T.inkFaint;
  const Icon = diff > 0 ? ArrowUpRight : diff < 0 ? ArrowDownRight : Minus;

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color, fontSize: 11, fontWeight: 600, fontFamily: T.sans }}>
      <Icon size={12} />
      vs {AREA.parent}
    </span>
  );
}

function Sparkline({ data, color = T.accent }: { data: { year: string; rate: number }[]; color?: string }) {
  const max = Math.max(...data.map(d => d.rate));
  const min = Math.min(...data.map(d => d.rate));
  const range = max - min || 1;
  const w = 120, h = 32;
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((d.rate - min) / range) * h;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ overflow: 'visible' }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      {/* end dot */}
      {data.length > 0 && (() => {
        const last = data[data.length - 1];
        const x = w;
        const y = h - ((last.rate - min) / range) * h;
        return <circle cx={x} cy={y} r={3} fill={color} />;
      })()}
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

/* ── Page Sections ──────────────────────────────────────────────────── */

function NavBar() {
  return (
    <nav style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '16px 32px',
      borderBottom: `1px solid ${T.divider}`,
      background: T.cardBg,
      position: 'sticky', top: 0, zIndex: 50,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8, background: T.accent,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Leaf size={16} color="white" />
        </div>
        <span style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 20, color: T.ink, letterSpacing: '-0.02em' }}>
          PropertyPulse
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{
          fontFamily: T.sans, fontSize: 11, fontWeight: 600,
          background: T.accentLight, color: T.accent, padding: '4px 12px', borderRadius: 20,
          border: `1px solid ${T.accentBg}`,
        }}>
          PROTOTYPE 2
        </span>
      </div>
    </nav>
  );
}

function HeroSection() {
  return (
    <div style={{ background: T.heroGrad, padding: '40px 32px' }}>
      <div style={{ maxWidth: 820, margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <h1 style={{
              fontFamily: T.serif, fontWeight: 800, fontSize: 36,
              color: 'white', letterSpacing: '-0.03em', lineHeight: 1.1, margin: 0,
            }}>
              {AREA.name}
              <span style={{ fontWeight: 400, fontSize: 20, color: 'rgba(255,255,255,0.45)', marginLeft: 8 }}>
                {AREA.parent}
              </span>
            </h1>
            <p style={{
              fontFamily: T.sans, fontSize: 13, color: 'rgba(255,255,255,0.4)',
              marginTop: 8, lineHeight: 1.5,
            }}>
              {AREA.type} · {AREA.lsoaCount} LSOAs · {AREA.county}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 16px', borderRadius: 10, fontSize: 13, fontWeight: 600,
              fontFamily: T.sans, background: 'rgba(255,255,255,0.08)', color: 'white',
              border: '1px solid rgba(255,255,255,0.12)', cursor: 'pointer',
              transition: 'background 0.2s',
            }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.14)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
            >
              <Bookmark size={14} /> Save
            </button>
            <button style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 16px', borderRadius: 10, fontSize: 13, fontWeight: 600,
              fontFamily: T.sans, background: 'rgba(255,255,255,0.08)', color: 'white',
              border: '1px solid rgba(255,255,255,0.12)', cursor: 'pointer',
              transition: 'background 0.2s',
            }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.14)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
            >
              <FileDown size={14} /> Report
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PersonaFitBanner() {
  const score = 74;
  const verdict = score >= 70 ? 'Strong' : score >= 45 ? 'Mixed' : 'Weak';
  const verdictColor = score >= 70 ? T.good : score >= 45 ? T.caution : T.bad;

  return (
    <div style={{
      maxWidth: 820, margin: '0 auto', padding: '0 32px',
      transform: 'translateY(-28px)', marginBottom: -12,
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: T.cardBg, borderRadius: 16, padding: '16px 24px',
        border: `1px solid ${T.divider}`,
        boxShadow: '0 4px 16px rgba(0,0,0,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {/* Mini dial */}
          <svg width={52} height={52} viewBox="0 0 52 52">
            <circle cx={26} cy={26} r={22} fill="none" stroke={T.divider} strokeWidth={5} />
            <circle cx={26} cy={26} r={22} fill="none" stroke={verdictColor} strokeWidth={5}
              strokeDasharray={`${(score / 100) * 138.2} 138.2`}
              strokeLinecap="round" transform="rotate(-90 26 26)"
              style={{ transition: 'stroke-dasharray 0.7s ease-out' }}
            />
            <text x={26} y={26} textAnchor="middle" dominantBaseline="central"
              style={{ fontFamily: T.mono, fontSize: 14, fontWeight: 700, fill: T.ink }}>
              {score}
            </text>
          </svg>
          <div>
            <div style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 16, color: T.ink }}>
              Persona Fit: <span style={{ color: verdictColor }}>{verdict}</span>
            </div>
            <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, marginTop: 2 }}>
              Based on 72 metrics across all tabs · First-Time Buyer
            </div>
          </div>
        </div>
        <button style={{
          fontFamily: T.sans, fontSize: 12, fontWeight: 600,
          color: T.accent, background: T.accentLight, border: `1px solid ${T.accentBg}`,
          padding: '6px 14px', borderRadius: 8, cursor: 'pointer',
          transition: 'background 0.2s',
        }}>
          Change persona
        </button>
      </div>
    </div>
  );
}

function SnapshotGrid() {
  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px 32px' }}>
      <h2 style={{
        fontFamily: T.serif, fontWeight: 700, fontSize: 22,
        color: T.ink, letterSpacing: '-0.02em', marginBottom: 16,
      }}>
        Area Snapshot
      </h2>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(145px, 1fr))',
        gap: 12,
      }}>
        {HEADLINE_METRICS.map((m, i) => (
          <div key={m.id} style={{
            background: T.cardBg, borderRadius: 14, padding: '16px 18px',
            border: `1px solid ${T.divider}`,
            transition: 'box-shadow 0.2s, transform 0.2s',
            cursor: 'default',
            animation: `fadeInUp 0.4s ease-out ${i * 60}ms both`,
          }}
            onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.transform = 'translateY(0)'; }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <div style={{
                width: 28, height: 28, borderRadius: 7,
                background: T.accentLight, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <m.icon size={14} color={T.accent} />
              </div>
              <span style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, color: T.inkMuted, letterSpacing: '0.02em' }}>
                {m.label}
              </span>
            </div>
            <div style={{ fontFamily: T.mono, fontSize: 20, fontWeight: 700, color: T.ink, lineHeight: 1.1 }}>
              {m.value}
            </div>
            {m.unit && (
              <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, marginTop: 2 }}>{m.unit}</div>
            )}
            <div style={{ marginTop: 8 }}>
              <ComparisonArrow value={m.value} parentValue={m.parent} direction={m.direction} />
            </div>
            {m.trend && (
              <div style={{
                fontFamily: T.mono, fontSize: 10, fontWeight: 600,
                color: m.trend.startsWith('-') ? T.good : m.trend.startsWith('+') ? T.inkMuted : T.inkFaint,
                marginTop: 4,
              }}>
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
      <h2 style={{
        fontFamily: T.serif, fontWeight: 700, fontSize: 22,
        color: T.ink, letterSpacing: '-0.02em', marginBottom: 16,
      }}>
        Tab Scores
      </h2>
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(145px, 1fr))', gap: 12,
      }}>
        {TAB_SCORES.map((t, i) => {
          const verdict = t.score >= 70 ? 'Strong' : t.score >= 45 ? 'Mixed' : 'Weak';
          const vColor = t.score >= 70 ? T.good : t.score >= 45 ? T.caution : T.bad;
          return (
            <div key={t.tab} style={{
              background: T.cardBg, borderRadius: 14, padding: '18px 20px',
              border: `1px solid ${T.divider}`, cursor: 'pointer',
              transition: 'all 0.2s',
              animation: `fadeInUp 0.4s ease-out ${i * 60}ms both`,
            }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = t.colour;
                e.currentTarget.style.boxShadow = `0 4px 12px ${t.colour}15`;
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = T.divider;
                e.currentTarget.style.boxShadow = 'none';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <t.icon size={16} color={t.colour} />
                <span style={{ fontFamily: T.sans, fontSize: 12, fontWeight: 600, color: T.ink }}>
                  {t.tab.split(' & ')[0]}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                <span style={{ fontFamily: T.mono, fontSize: 28, fontWeight: 800, color: T.ink }}>
                  {t.score}
                </span>
                <span style={{
                  fontFamily: T.sans, fontSize: 11, fontWeight: 600, color: vColor,
                  background: vColor + '15', padding: '2px 8px', borderRadius: 6,
                }}>
                  {verdict}
                </span>
              </div>
            </div>
          );
        })}
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
      <div style={{
        background: T.cardBg, borderRadius: 16, border: `1px solid ${T.divider}`,
        padding: 24, overflow: 'hidden',
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Shield size={16} color={T.accent} />
              <h3 style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 18, color: T.ink, margin: 0 }}>
                Crime Trend
              </h3>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
              <span style={{ fontFamily: T.mono, fontSize: 32, fontWeight: 800, color: T.ink }}>
                {latest.rate}
              </span>
              <span style={{ fontFamily: T.sans, fontSize: 12, color: T.inkFaint }}>
                per 1,000 pop
              </span>
            </div>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              fontFamily: T.mono, fontSize: 12, fontWeight: 600,
              color: isDown ? T.good : T.bad,
              background: isDown ? T.goodBg : T.badBg,
              padding: '3px 10px', borderRadius: 6, marginTop: 8,
            }}>
              {isDown ? <TrendingDown size={12} /> : <TrendingUp size={12} />}
              {isDown ? '' : '+'}{change}% vs last year
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
            <Sparkline data={CRIME_TREND} color={isDown ? T.good : T.bad} />
            <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, marginTop: 4 }}>
              {CRIME_TREND[0].year}–{latest.year}
            </div>
          </div>
        </div>

        {/* Extremes comparison */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 20,
          paddingTop: 20, borderTop: `1px solid ${T.dividerSoft}`,
        }}>
          <div>
            <div style={{ fontFamily: T.sans, fontSize: 10, fontWeight: 700, color: T.good, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8 }}>
              Safest Nearby
            </div>
            {[
              { name: 'Sanderstead', rate: 41.7 },
              { name: 'Kenley', rate: 52.9 },
              { name: 'Coulsdon', rate: 62.4 },
            ].map(a => (
              <div key={a.name} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '6px 0', borderBottom: `1px solid ${T.dividerSoft}`,
              }}>
                <span style={{ fontFamily: T.sans, fontSize: 13, color: T.ink, fontWeight: a.name === 'Coulsdon' ? 700 : 400 }}>
                  {a.name} {a.name === 'Coulsdon' && '←'}
                </span>
                <span style={{ fontFamily: T.mono, fontSize: 12, color: T.inkMuted }}>{a.rate}</span>
              </div>
            ))}
          </div>
          <div>
            <div style={{ fontFamily: T.sans, fontSize: 10, fontWeight: 700, color: T.bad, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8 }}>
              Highest Crime
            </div>
            {[
              { name: 'Broad Green', rate: 142.3 },
              { name: 'Thornton Heath', rate: 128.7 },
              { name: 'West Croydon', rate: 115.2 },
            ].map(a => (
              <div key={a.name} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '6px 0', borderBottom: `1px solid ${T.dividerSoft}`,
              }}>
                <span style={{ fontFamily: T.sans, fontSize: 13, color: T.ink }}>{a.name}</span>
                <span style={{ fontFamily: T.mono, fontSize: 12, color: T.inkMuted }}>{a.rate}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function MetricCardDemo({ m, idx }: { m: typeof SAMPLE_METRICS[0]; idx: number }) {
  const [expanded, setExpanded] = useState(false);
  const isGood = m.good;
  const accentColor = isGood ? T.good : T.caution;
  const accentBg = isGood ? T.goodBg : T.cautionBg;

  return (
    <div style={{
      background: T.cardBg, borderRadius: 14,
      border: `1px solid ${T.divider}`,
      borderLeft: `4px solid ${accentColor}`,
      overflow: 'hidden',
      transition: 'box-shadow 0.2s',
      animation: `fadeInUp 0.4s ease-out ${idx * 60}ms both`,
    }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.06)')}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 18px', cursor: 'pointer', background: 'transparent', border: 'none',
          textAlign: 'left',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flex: 1, minWidth: 0 }}>
          <span style={{ fontFamily: T.sans, fontSize: 13, fontWeight: 500, color: T.ink, whiteSpace: 'nowrap' }}>
            {m.label}
          </span>
          <span style={{ fontFamily: T.mono, fontSize: 15, fontWeight: 700, color: T.ink }}>
            {m.value}
          </span>
          <span style={{
            fontFamily: T.sans, fontSize: 11, fontWeight: 600,
            color: accentColor, background: accentBg,
            padding: '2px 8px', borderRadius: 6, whiteSpace: 'nowrap',
          }}>
            vs {m.parent}
          </span>
        </div>
        <ChevronDown size={16} color={T.inkFaint} style={{
          transition: 'transform 0.2s',
          transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
        }} />
      </button>
      {expanded && (
        <div style={{
          padding: '0 18px 16px', borderTop: `1px solid ${T.dividerSoft}`,
          paddingTop: 12,
        }}>
          <p style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, lineHeight: 1.6, margin: 0 }}>
            {m.detail}
          </p>
        </div>
      )}
    </div>
  );
}

function PropertyTabDemo() {
  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px 32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: T.accentLight, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Home size={16} color={T.accent} />
        </div>
        <h2 style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 22, color: T.ink, letterSpacing: '-0.02em', margin: 0 }}>
          Property & Market
        </h2>
      </div>

      {/* Highlight strip — top 3 metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 20 }}>
        {SAMPLE_METRICS.slice(0, 3).map(m => (
          <div key={m.label} style={{
            background: T.cardBg, borderRadius: 12, padding: '14px 16px',
            border: `1px solid ${T.divider}`,
          }}>
            <div style={{ fontFamily: T.sans, fontSize: 10, fontWeight: 600, color: T.inkFaint, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              {m.label}
            </div>
            <div style={{ fontFamily: T.mono, fontSize: 18, fontWeight: 700, color: T.ink, marginTop: 4 }}>
              {m.value}
            </div>
            <div style={{ fontFamily: T.sans, fontSize: 10, fontWeight: 600, color: m.good ? T.good : T.caution, marginTop: 4 }}>
              {m.good ? '↑' : '↓'} vs {m.parent} ({AREA.parent})
            </div>
          </div>
        ))}
      </div>

      {/* Metric cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {SAMPLE_METRICS.map((m, i) => (
          <MetricCardDemo key={m.label} m={m} idx={i} />
        ))}
      </div>
    </section>
  );
}

function SchoolTableDemo() {
  const [phaseFilter, setPhaseFilter] = useState<string>('All');

  const filtered = phaseFilter === 'All'
    ? SCHOOL_DATA
    : SCHOOL_DATA.filter(s => s.phase === phaseFilter);

  const ofstedColor = (rating: string) => {
    if (rating === 'Outstanding') return { bg: '#DCFCE7', text: '#15803D' };
    if (rating === 'Good') return { bg: '#DBEAFE', text: '#1D4ED8' };
    if (rating === 'Requires Improvement') return { bg: '#FEF3C7', text: '#92400E' };
    return { bg: '#FEE2E2', text: '#991B1B' };
  };

  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px 32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: T.accentLight, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <GraduationCap size={16} color={T.accent} />
        </div>
        <h2 style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 22, color: T.ink, letterSpacing: '-0.02em', margin: 0 }}>
          Nearby Schools
        </h2>
      </div>

      {/* Phase filter pills */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
        {['All', 'Primary', 'Secondary'].map(p => (
          <button key={p} onClick={() => setPhaseFilter(p)} style={{
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

      {/* School cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {filtered.map(s => {
          const oc = ofstedColor(s.ofsted);
          return (
            <div key={s.name} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              background: T.cardBg, borderRadius: 12, padding: '12px 18px',
              border: `1px solid ${T.divider}`, transition: 'box-shadow 0.2s',
              cursor: 'pointer',
            }}
              onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.06)')}
              onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}
            >
              <div>
                <div style={{ fontFamily: T.sans, fontSize: 13, fontWeight: 600, color: T.ink }}>{s.name}</div>
                <div style={{ fontFamily: T.sans, fontSize: 11, color: T.inkFaint, marginTop: 2 }}>
                  {s.phase} · {s.distance}
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {'ks2' in s && s.ks2 !== undefined && (
                  <span style={{ fontFamily: T.mono, fontSize: 12, fontWeight: 600, color: T.ink }}>
                    KS2: {s.ks2}%
                  </span>
                )}
                {'p8' in s && s.p8 !== undefined && (
                  <span style={{
                    fontFamily: T.mono, fontSize: 12, fontWeight: 600,
                    color: (s.p8 as number) >= 0 ? T.good : T.bad,
                  }}>
                    P8: {(s.p8 as number) > 0 ? '+' : ''}{s.p8}
                  </span>
                )}
                <span style={{
                  fontFamily: T.sans, fontSize: 10, fontWeight: 700,
                  padding: '3px 10px', borderRadius: 6,
                  background: oc.bg, color: oc.text,
                }}>
                  {s.ofsted}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ComparableAreasDemo() {
  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px 32px' }}>
      <h2 style={{
        fontFamily: T.serif, fontWeight: 700, fontSize: 22,
        color: T.ink, letterSpacing: '-0.02em', marginBottom: 6,
      }}>
        Comparable Areas
      </h2>
      <p style={{
        fontFamily: T.sans, fontSize: 12, color: T.inkMuted, marginBottom: 16, lineHeight: 1.5,
      }}>
        Matched across 11 dimensions: price, rent, earnings, air quality, growth, crime, deprivation, demographics, transport, and council tax.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {COMPARABLE_AREAS.map((a, i) => (
          <div key={a.name} style={{
            background: T.cardBg, borderRadius: 14, padding: '18px 22px',
            border: `1px solid ${T.divider}`, transition: 'box-shadow 0.2s',
            animation: `fadeInUp 0.4s ease-out ${i * 80}ms both`,
          }}
            onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.06)')}
            onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div>
                <span style={{ fontFamily: T.sans, fontSize: 14, fontWeight: 700, color: T.ink }}>{a.name}</span>
                <span style={{ fontFamily: T.sans, fontSize: 12, color: T.inkFaint, marginLeft: 6 }}>{a.parent}</span>
              </div>
              <button style={{
                fontFamily: T.sans, fontSize: 11, fontWeight: 600,
                color: T.accent, background: T.accentLight,
                border: `1px solid ${T.accentBg}`,
                padding: '4px 12px', borderRadius: 8, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 4,
              }}>
                View area <ArrowRight size={11} />
              </button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <SimilarityBar pct={a.match} />
            </div>
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 14,
              paddingTop: 14, borderTop: `1px solid ${T.dividerSoft}`,
            }}>
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
        ))}
      </div>
    </section>
  );
}

function HomePageDemo() {
  return (
    <section style={{
      background: T.pageBg, padding: '80px 32px', borderTop: `1px solid ${T.divider}`,
      borderBottom: `1px solid ${T.divider}`, marginBottom: 0,
    }}>
      <div style={{ maxWidth: 820, margin: '0 auto' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
          <h2 style={{
            fontFamily: T.serif, fontWeight: 800, fontSize: 42,
            color: T.ink, letterSpacing: '-0.03em', lineHeight: 1.05,
            marginBottom: 16, maxWidth: 520,
          }}>
            Know your{' '}
            <span style={{
              background: `linear-gradient(135deg, ${T.accent}, ${T.accentMid})`,
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>
              neighbourhood.
            </span>
          </h2>
          <p style={{
            fontFamily: T.sans, fontSize: 16, color: T.inkMuted,
            maxWidth: 400, lineHeight: 1.6, marginBottom: 32,
          }}>
            The most complete area analysis for UK property.
            Every postcode, every metric, personalised for you.
          </p>

          {/* Search mockup */}
          <div style={{
            width: '100%', maxWidth: 520, position: 'relative',
          }}>
            <div style={{
              display: 'flex', alignItems: 'center', height: 56,
              background: T.cardBg, borderRadius: 16,
              border: `2px solid ${T.divider}`,
              padding: '0 16px',
              boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
              transition: 'border-color 0.2s, box-shadow 0.2s',
            }}>
              <Search size={18} color={T.inkFaint} style={{ marginRight: 12 }} />
              <span style={{ fontFamily: T.sans, fontSize: 15, color: T.inkFaint }}>
                Enter a postcode or place name...
              </span>
              <button style={{
                marginLeft: 'auto',
                padding: '8px 20px', borderRadius: 10,
                background: T.accent, color: 'white',
                fontFamily: T.sans, fontSize: 13, fontWeight: 700,
                border: 'none', cursor: 'pointer',
              }}>
                Analyse
              </button>
            </div>
          </div>

          {/* Example pills */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 16, justifyContent: 'center' }}>
            {['SW1A 1AA', 'M1 1AE', 'E1 6RF', 'BS1 4DJ', 'CR5 1RA'].map(q => (
              <span key={q} style={{
                fontFamily: T.mono, fontSize: 12, fontWeight: 600,
                padding: '6px 14px', borderRadius: 20,
                background: T.cardBg, border: `1px solid ${T.divider}`,
                color: T.inkMuted, cursor: 'pointer',
                transition: 'all 0.15s',
              }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = T.accent; e.currentTarget.style.color = T.accent; e.currentTarget.style.background = T.accentLight; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = T.divider; e.currentTarget.style.color = T.inkMuted; e.currentTarget.style.background = T.cardBg; }}
              >
                {q}
              </span>
            ))}
          </div>

          {/* Coverage badges */}
          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <span style={{
              fontFamily: T.sans, fontSize: 11, fontWeight: 600,
              padding: '4px 12px', borderRadius: 20,
              background: T.goodBg, color: T.good,
              border: `1px solid ${T.sageLight}`,
            }}>
              Live: England, Wales
            </span>
            <span style={{
              fontFamily: T.sans, fontSize: 11, fontWeight: 600,
              padding: '4px 12px', borderRadius: 20,
              background: T.cautionBg, color: T.caution,
              border: `1px solid #FDE68A`,
            }}>
              Planned: Scotland, NI
            </span>
          </div>

          {/* Feature tiles */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: 12, marginTop: 48, width: '100%',
          }}>
            {[
              { icon: TrendingUp, title: 'Property & Market', hint: 'Prices, yields, trends' },
              { icon: Coffee, title: 'Lifestyle', hint: 'Transport, broadband, amenities' },
              { icon: Shield, title: 'Safety', hint: 'Flood, air quality, crime' },
              { icon: GraduationCap, title: 'Schools', hint: 'Ofsted, KS2/KS4, walk time' },
              { icon: Users, title: 'Community', hint: 'Demographics, deprivation' },
              { icon: Landmark, title: 'Governance', hint: 'Council tax, politics' },
            ].map(f => (
              <div key={f.title} style={{
                display: 'flex', alignItems: 'center', gap: 14,
                padding: '14px 18px', borderRadius: 14,
                background: T.cardBg, border: `1px solid ${T.divider}`,
                cursor: 'pointer', transition: 'all 0.2s',
              }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = T.accent; e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.06)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = T.divider; e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.transform = 'translateY(0)'; }}
              >
                <div style={{
                  width: 36, height: 36, borderRadius: 9,
                  background: T.accentLight, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
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
      padding: '20px 32px', textAlign: 'center',
      fontFamily: T.sans, fontSize: 11, color: T.inkFaint,
      borderTop: `1px solid ${T.divider}`, background: T.pageBg,
    }}>
      Data from OS, Land Registry, ONS, Ofcom, Ofsted, NHS &copy; Crown Copyright. &copy; OpenStreetMap Contributors.
    </footer>
  );
}

/* ── Tab Demo ───────────────────────────────────────────────────────── */
function TabBarDemo({ active, onChange }: { active: string; onChange: (tab: string) => void }) {
  const tabs = [
    { name: 'Overview', icon: LayoutDashboard },
    { name: 'Property', icon: Home },
    { name: 'Lifestyle', icon: Coffee },
    { name: 'Safety', icon: TreePine },
    { name: 'Community', icon: Users },
    { name: 'Governance', icon: Landmark },
  ];

  return (
    <div style={{
      position: 'sticky', top: 65, zIndex: 40,
      background: T.cardBg, borderBottom: `1px solid ${T.divider}`,
      padding: '0 32px',
    }}>
      <div style={{
        maxWidth: 820, margin: '0 auto',
        display: 'flex', gap: 2, overflowX: 'auto',
        padding: '8px 0',
      }}>
        {tabs.map(t => {
          const isActive = active === t.name;
          return (
            <button key={t.name} onClick={() => onChange(t.name)} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 16px', borderRadius: 10, cursor: 'pointer',
              fontFamily: T.sans, fontSize: 13, fontWeight: isActive ? 700 : 500,
              color: isActive ? T.accent : T.inkMuted,
              background: isActive ? T.accentLight : 'transparent',
              border: 'none',
              transition: 'all 0.15s',
              whiteSpace: 'nowrap',
              position: 'relative',
            }}>
              <t.icon size={14} />
              {t.name}
              {isActive && (
                <div style={{
                  position: 'absolute', bottom: -8, left: '20%', right: '20%',
                  height: 2, borderRadius: 1, background: T.accent,
                }} />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ── Main Page ──────────────────────────────────────────────────────── */
export default function Prototype2() {
  const [activeTab, setActiveTab] = useState('Overview');
  const [showHomepage, setShowHomepage] = useState(true);

  return (
    <>
      {/* Inject Fraunces font */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@400;500;600;700;800;900&display=swap');
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div style={{ minHeight: '100dvh', display: 'flex', flexDirection: 'column', background: T.pageBg }}>
        {/* Section toggle */}
        <div style={{
          position: 'fixed', bottom: 20, right: 20, zIndex: 100,
          display: 'flex', gap: 8,
        }}>
          <button onClick={() => setShowHomepage(true)} style={{
            padding: '10px 18px', borderRadius: 12,
            fontFamily: T.sans, fontSize: 12, fontWeight: 700,
            background: showHomepage ? T.accent : T.cardBg,
            color: showHomepage ? 'white' : T.ink,
            border: `1px solid ${showHomepage ? T.accent : T.divider}`,
            cursor: 'pointer', boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          }}>
            Homepage
          </button>
          <button onClick={() => setShowHomepage(false)} style={{
            padding: '10px 18px', borderRadius: 12,
            fontFamily: T.sans, fontSize: 12, fontWeight: 700,
            background: !showHomepage ? T.accent : T.cardBg,
            color: !showHomepage ? 'white' : T.ink,
            border: `1px solid ${!showHomepage ? T.accent : T.divider}`,
            cursor: 'pointer', boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          }}>
            Results Page
          </button>
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
                  <CrimeTrendSection />
                  <ComparableAreasDemo />
                </>
              )}
              {activeTab === 'Property' && (
                <PropertyTabDemo />
              )}
              {activeTab === 'Community' && (
                <SchoolTableDemo />
              )}
              {(activeTab === 'Lifestyle' || activeTab === 'Safety' || activeTab === 'Governance') && (
                <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px' }}>
                  <div style={{
                    background: T.cardBg, borderRadius: 16, padding: 40,
                    border: `1px solid ${T.divider}`, textAlign: 'center',
                  }}>
                    <div style={{ fontFamily: T.serif, fontSize: 20, fontWeight: 700, color: T.ink, marginBottom: 8 }}>
                      {activeTab} Tab
                    </div>
                    <p style={{ fontFamily: T.sans, fontSize: 13, color: T.inkMuted }}>
                      Same design system applies here — warm palette, serif headings, generous spacing, metric cards with left accent borders.
                    </p>
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
