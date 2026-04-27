/**
 * Icon Showcase — 4 icon sets (A / B / C / D) side-by-side for comparison.
 *
 *  A = Subtle/light    — pastel bg, muted icon
 *  B = Solid bold       — saturated bg, white icon, thick stroke
 *  C = Monzo-style      — unique vivid color per ROW, white icon, full circle
 *  D = Gradient glass   — gradient bg, white icon, slight shadow/glow
 *
 * Lives at /icons. Pure visual — no data fetching.
 */
import {
  // Set A icons (subtle)
  Home, Coffee, TreePine, Users, Landmark,
  PoundSterling, TrendingUp, BarChart3, Receipt, Building2,
  Train, Wifi, Shield, Wind, Leaf, Droplets, Zap,
  UserCircle, Globe, GraduationCap, Scale, HeartPulse,
  Bike, Radio, Plug, Navigation, Clock, Search,
  ShoppingBag, Utensils, Trees, Dumbbell, Baby, Church,
  // Set B icons (bold alternatives)
  House, Compass, Mountain, UsersRound, Crown,
  Coins, CandlestickChart, ChartArea, Wallet, Warehouse,
  TrainFront, Antenna, Store,
  Siren, Thermometer, Sprout,
  Fingerprint, Earth, School, Gauge, Stethoscope,
  Castle,
  Banknote, Activity, ChartLine,
  BadgePoundSterling,
  Bus, Route, PlugZap,
  Signal, Satellite,
  MapPinned,
  ShieldAlert, Waves, Cloudy,
  Flower2, Medal,
  PersonStanding, Languages,
  Backpack, Vote,
  Hospital, Flame,
  Gavel,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// ─── Row data ───────────────────────────────────────────────────────
type Row = {
  label: string;
  /** Set A + C + D share this icon */
  iconA: LucideIcon;
  /** Set B uses an alternative icon */
  iconB: LucideIcon;
  level: 'tab' | 'section' | 'metric';
  parent?: string;
  /** Unique Monzo-style color for this row (Set C) */
  monzoColor: string;
  /** CSS gradient for Set D */
  gradient: string;
};

// Monzo-inspired palette: each row gets a unique vivid hue
const ROWS: Row[] = [
  // ── TABS ──
  { label: 'Property & Market',       iconA: Home,       iconB: House,      level: 'tab', monzoColor: '#2563eb', gradient: 'linear-gradient(135deg, #3b82f6, #1d4ed8)' },
  { label: 'Lifestyle & Connectivity', iconA: Coffee,     iconB: Compass,    level: 'tab', monzoColor: '#7c3aed', gradient: 'linear-gradient(135deg, #8b5cf6, #6d28d9)' },
  { label: 'Environment & Safety',     iconA: TreePine,   iconB: Mountain,   level: 'tab', monzoColor: '#059669', gradient: 'linear-gradient(135deg, #10b981, #047857)' },
  { label: 'Community & Education',    iconA: Users,      iconB: UsersRound, level: 'tab', monzoColor: '#e11d48', gradient: 'linear-gradient(135deg, #f43f5e, #be123c)' },
  { label: 'Local Governance',         iconA: Landmark,   iconB: Crown,      level: 'tab', monzoColor: '#d97706', gradient: 'linear-gradient(135deg, #f59e0b, #b45309)' },

  // ── PROPERTY SECTIONS ──
  { label: 'Prices & Value',    iconA: PoundSterling, iconB: Coins,            level: 'section', parent: 'Property', monzoColor: '#2563eb', gradient: 'linear-gradient(135deg, #60a5fa, #2563eb)' },
  { label: 'Market Activity',   iconA: TrendingUp,    iconB: CandlestickChart, level: 'section', parent: 'Property', monzoColor: '#0891b2', gradient: 'linear-gradient(135deg, #22d3ee, #0e7490)' },
  { label: 'Trends',            iconA: BarChart3,     iconB: ChartArea,        level: 'section', parent: 'Property', monzoColor: '#4f46e5', gradient: 'linear-gradient(135deg, #818cf8, #4338ca)' },
  { label: 'Costs & Income',    iconA: Receipt,       iconB: Wallet,           level: 'section', parent: 'Property', monzoColor: '#ca8a04', gradient: 'linear-gradient(135deg, #facc15, #a16207)' },
  { label: 'Housing Stock',     iconA: Building2,     iconB: Warehouse,        level: 'section', parent: 'Property', monzoColor: '#64748b', gradient: 'linear-gradient(135deg, #94a3b8, #475569)' },

  // ── LIFESTYLE SECTIONS ──
  { label: 'Transport & Access',   iconA: Train,       iconB: TrainFront, level: 'section', parent: 'Lifestyle', monzoColor: '#7c3aed', gradient: 'linear-gradient(135deg, #a78bfa, #6d28d9)' },
  { label: 'Digital Connectivity', iconA: Wifi,        iconB: Antenna,    level: 'section', parent: 'Lifestyle', monzoColor: '#0d9488', gradient: 'linear-gradient(135deg, #2dd4bf, #0f766e)' },
  { label: 'Amenities',            iconA: ShoppingBag, iconB: Store,      level: 'section', parent: 'Lifestyle', monzoColor: '#db2777', gradient: 'linear-gradient(135deg, #f472b6, #be185d)' },

  // ── ENVIRONMENT SECTIONS ──
  { label: 'Safety',       iconA: Shield, iconB: Siren,       level: 'section', parent: 'Environment', monzoColor: '#dc2626', gradient: 'linear-gradient(135deg, #f87171, #b91c1c)' },
  { label: 'Environment',  iconA: Wind,   iconB: Thermometer, level: 'section', parent: 'Environment', monzoColor: '#0284c7', gradient: 'linear-gradient(135deg, #38bdf8, #0369a1)' },
  { label: 'Green Space',  iconA: Leaf,   iconB: Sprout,      level: 'section', parent: 'Environment', monzoColor: '#16a34a', gradient: 'linear-gradient(135deg, #4ade80, #15803d)' },

  // ── COMMUNITY SECTIONS ──
  { label: 'People',          iconA: UserCircle,    iconB: Fingerprint, level: 'section', parent: 'Community', monzoColor: '#e11d48', gradient: 'linear-gradient(135deg, #fb7185, #be123c)' },
  { label: 'Diversity',       iconA: Globe,         iconB: Earth,       level: 'section', parent: 'Community', monzoColor: '#8b5cf6', gradient: 'linear-gradient(135deg, #c084fc, #7c3aed)' },
  { label: 'Schools',         iconA: GraduationCap, iconB: School,      level: 'section', parent: 'Community', monzoColor: '#ea580c', gradient: 'linear-gradient(135deg, #fb923c, #c2410c)' },
  { label: 'Deprivation',     iconA: Scale,         iconB: Gauge,       level: 'section', parent: 'Community', monzoColor: '#78716c', gradient: 'linear-gradient(135deg, #a8a29e, #57534e)' },
  { label: 'Health Services', iconA: HeartPulse,    iconB: Stethoscope, level: 'section', parent: 'Community', monzoColor: '#e11d48', gradient: 'linear-gradient(135deg, #fda4af, #e11d48)' },

  // ── GOVERNANCE SECTIONS ──
  { label: 'Governance', iconA: Landmark, iconB: Castle, level: 'section', parent: 'Governance', monzoColor: '#d97706', gradient: 'linear-gradient(135deg, #fbbf24, #92400e)' },

  // ── SAMPLE METRICS ──
  { label: 'avg_price',             iconA: PoundSterling, iconB: Banknote,           level: 'metric', parent: 'Prices & Value',      monzoColor: '#2563eb', gradient: 'linear-gradient(135deg, #60a5fa, #2563eb)' },
  { label: 'transaction_volume',    iconA: TrendingUp,    iconB: Activity,           level: 'metric', parent: 'Market Activity',     monzoColor: '#0891b2', gradient: 'linear-gradient(135deg, #22d3ee, #0e7490)' },
  { label: 'price_trend_yoy',       iconA: BarChart3,     iconB: ChartLine,          level: 'metric', parent: 'Trends',              monzoColor: '#4f46e5', gradient: 'linear-gradient(135deg, #818cf8, #4338ca)' },
  { label: 'council_tax',           iconA: Receipt,       iconB: BadgePoundSterling, level: 'metric', parent: 'Costs & Income',      monzoColor: '#ca8a04', gradient: 'linear-gradient(135deg, #facc15, #a16207)' },
  { label: 'housing_tenure',        iconA: Building2,     iconB: Warehouse,          level: 'metric', parent: 'Housing Stock',       monzoColor: '#64748b', gradient: 'linear-gradient(135deg, #94a3b8, #475569)' },
  { label: 'nearest_station',       iconA: Train,         iconB: TrainFront,         level: 'metric', parent: 'Transport & Access',  monzoColor: '#7c3aed', gradient: 'linear-gradient(135deg, #a78bfa, #6d28d9)' },
  { label: 'cycling',               iconA: Bike,          iconB: Bus,                level: 'metric', parent: 'Transport & Access',  monzoColor: '#059669', gradient: 'linear-gradient(135deg, #34d399, #047857)' },
  { label: 'commute_distance',      iconA: Navigation,    iconB: Route,              level: 'metric', parent: 'Transport & Access',  monzoColor: '#6366f1', gradient: 'linear-gradient(135deg, #a5b4fc, #4f46e5)' },
  { label: 'ev_chargers',           iconA: Plug,          iconB: PlugZap,            level: 'metric', parent: 'Transport & Access',  monzoColor: '#16a34a', gradient: 'linear-gradient(135deg, #4ade80, #15803d)' },
  { label: 'broadband',             iconA: Wifi,          iconB: Signal,             level: 'metric', parent: 'Digital Connectivity', monzoColor: '#0d9488', gradient: 'linear-gradient(135deg, #2dd4bf, #0f766e)' },
  { label: 'mobile_coverage',       iconA: Radio,         iconB: Satellite,          level: 'metric', parent: 'Digital Connectivity', monzoColor: '#0284c7', gradient: 'linear-gradient(135deg, #38bdf8, #0369a1)' },
  { label: 'amenities_15min',       iconA: Utensils,      iconB: MapPinned,          level: 'metric', parent: 'Amenities',           monzoColor: '#db2777', gradient: 'linear-gradient(135deg, #f472b6, #be185d)' },
  { label: 'crime_rate',            iconA: Shield,        iconB: ShieldAlert,        level: 'metric', parent: 'Safety',              monzoColor: '#dc2626', gradient: 'linear-gradient(135deg, #f87171, #b91c1c)' },
  { label: 'flood_risk',            iconA: Droplets,      iconB: Waves,              level: 'metric', parent: 'Environment',         monzoColor: '#0284c7', gradient: 'linear-gradient(135deg, #7dd3fc, #0369a1)' },
  { label: 'air_quality_no2',       iconA: Wind,          iconB: Cloudy,             level: 'metric', parent: 'Environment',         monzoColor: '#64748b', gradient: 'linear-gradient(135deg, #cbd5e1, #475569)' },
  { label: 'green_cover',           iconA: Trees,         iconB: Flower2,            level: 'metric', parent: 'Green Space',         monzoColor: '#16a34a', gradient: 'linear-gradient(135deg, #86efac, #15803d)' },
  { label: 'sports_recreation',     iconA: Dumbbell,      iconB: Medal,              level: 'metric', parent: 'Green Space',         monzoColor: '#ea580c', gradient: 'linear-gradient(135deg, #fdba74, #c2410c)' },
  { label: 'demographics_overview', iconA: UserCircle,    iconB: PersonStanding,     level: 'metric', parent: 'People',              monzoColor: '#e11d48', gradient: 'linear-gradient(135deg, #fda4af, #be123c)' },
  { label: 'median_age',            iconA: Clock,         iconB: Fingerprint,        level: 'metric', parent: 'People',              monzoColor: '#78716c', gradient: 'linear-gradient(135deg, #d6d3d1, #57534e)' },
  { label: 'ethnicity',             iconA: Globe,         iconB: Languages,          level: 'metric', parent: 'Diversity',           monzoColor: '#8b5cf6', gradient: 'linear-gradient(135deg, #c4b5fd, #7c3aed)' },
  { label: 'religion',              iconA: Church,        iconB: Earth,              level: 'metric', parent: 'Diversity',           monzoColor: '#a855f7', gradient: 'linear-gradient(135deg, #d8b4fe, #9333ea)' },
  { label: 'primary_schools',       iconA: GraduationCap, iconB: Backpack,           level: 'metric', parent: 'Schools',             monzoColor: '#ea580c', gradient: 'linear-gradient(135deg, #fb923c, #c2410c)' },
  { label: 'nurseries',             iconA: Baby,          iconB: School,             level: 'metric', parent: 'Schools',             monzoColor: '#f472b6', gradient: 'linear-gradient(135deg, #fbcfe8, #ec4899)' },
  { label: 'deprivation',           iconA: Scale,         iconB: Gauge,              level: 'metric', parent: 'Deprivation',         monzoColor: '#78716c', gradient: 'linear-gradient(135deg, #a8a29e, #57534e)' },
  { label: 'nhs_facilities',        iconA: HeartPulse,    iconB: Hospital,           level: 'metric', parent: 'Health Services',     monzoColor: '#e11d48', gradient: 'linear-gradient(135deg, #fda4af, #e11d48)' },
  { label: 'epc_energy_score',      iconA: Zap,           iconB: Flame,              level: 'metric', parent: 'Housing Stock',       monzoColor: '#ca8a04', gradient: 'linear-gradient(135deg, #fde047, #a16207)' },
  { label: 'local_authority',        iconA: Landmark,      iconB: Gavel,              level: 'metric', parent: 'Governance',          monzoColor: '#d97706', gradient: 'linear-gradient(135deg, #fbbf24, #92400e)' },
  { label: 'ptal_score',            iconA: Search,        iconB: Vote,               level: 'metric', parent: 'Transport & Access',  monzoColor: '#7c3aed', gradient: 'linear-gradient(135deg, #c084fc, #6d28d9)' },
];

// ─── Set A style (same pastel-by-level) ─────────────────────────────
const STYLE_A: Record<string, { bg: string; text: string }> = {
  tab:     { bg: 'bg-blue-50',  text: 'text-blue-700' },
  section: { bg: 'bg-amber-50', text: 'text-amber-700' },
  metric:  { bg: 'bg-slate-50', text: 'text-slate-600' },
};

// ─── Set B style (solid bold by level) ──────────────────────────────
const STYLE_B: Record<string, { bg: string; text: string }> = {
  tab:     { bg: 'bg-blue-600',   text: 'text-white' },
  section: { bg: 'bg-orange-500', text: 'text-white' },
  metric:  { bg: 'bg-slate-700',  text: 'text-white' },
};

const LEVEL_BADGE: Record<string, string> = {
  tab:     'bg-blue-100 text-blue-700',
  section: 'bg-amber-100 text-amber-700',
  metric:  'bg-slate-100 text-slate-600',
};

// ─── Component ──────────────────────────────────────────────────────
export default function IconShowcase() {
  const tabs = ROWS.filter(r => r.level === 'tab');
  const sections = ROWS.filter(r => r.level === 'section');
  const metrics = ROWS.filter(r => r.level === 'metric');

  return (
    <div className="min-h-screen bg-[#faf9f7] px-6 py-8">
      <h1 className="text-2xl font-bold text-[#18181b] mb-2">Icon Showcase</h1>
      <p className="text-sm text-[#71717a] mb-1">Four icon sets side-by-side.</p>
      <div className="flex flex-wrap gap-3 text-xs mb-8">
        <span className="px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 font-medium">A — Subtle / Pastel</span>
        <span className="px-2.5 py-1 rounded-full bg-orange-500 text-white font-medium">B — Solid Bold</span>
        <span className="px-2.5 py-1 rounded-full text-white font-medium" style={{ background: '#e11d48' }}>C — Monzo (unique color per row)</span>
        <span className="px-2.5 py-1 rounded-full text-white font-medium" style={{ background: 'linear-gradient(135deg, #818cf8, #4338ca)' }}>D — Gradient Glass</span>
      </div>

      <SectionHeader badge="TAB" badgeClass="bg-blue-100 text-blue-700" title="Tab Icons" />
      <ComparisonTable rows={tabs} />

      <SectionHeader badge="SECTION" badgeClass="bg-amber-100 text-amber-700" title="Section Group Icons" />
      <ComparisonTable rows={sections} showParent />

      <SectionHeader badge="METRIC" badgeClass="bg-slate-100 text-slate-600" title="Sample Metric Icons" subtitle="(optional)" />
      <ComparisonTable rows={metrics} showParent />
    </div>
  );
}

function SectionHeader({ badge, badgeClass, title, subtitle }: { badge: string; badgeClass: string; title: string; subtitle?: string }) {
  return (
    <h2 className="text-lg font-semibold text-[#18181b] mt-10 mb-3 flex items-center gap-2">
      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${badgeClass}`}>{badge}</span>
      {title}
      {subtitle && <span className="text-xs font-normal text-[#a1a1aa] ml-2">{subtitle}</span>}
    </h2>
  );
}

function ComparisonTable({ rows, showParent }: { rows: Row[]; showParent?: boolean }) {
  return (
    <div className="border border-[#e4e4e7] rounded-xl overflow-hidden bg-white">
      <table className="w-full">
        <thead>
          <tr className="bg-[#f5f3ef] text-left text-xs text-[#71717a] uppercase tracking-wider">
            <th className="px-3 py-3 w-16 text-center">A</th>
            <th className="px-3 py-3 w-16 text-center">B</th>
            <th className="px-3 py-3 w-16 text-center">C</th>
            <th className="px-3 py-3 w-16 text-center">D</th>
            <th className="px-4 py-3">Label</th>
            {showParent && <th className="px-4 py-3">Parent</th>}
            <th className="px-4 py-3 w-20">Level</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const IconA = row.iconA;
            const IconB = row.iconB;
            const sA = STYLE_A[row.level];
            const sB = STYLE_B[row.level];
            const badge = LEVEL_BADGE[row.level];
            return (
              <tr key={`${row.label}-${i}`} className="border-t border-[#e4e4e7] hover:bg-[#faf9f7] transition-colors">
                {/* Set A: pastel/subtle */}
                <td className="px-3 py-3">
                  <div className="flex justify-center">
                    <div className={`w-10 h-10 rounded-lg ${sA.bg} flex items-center justify-center`}>
                      <IconA size={20} className={sA.text} />
                    </div>
                  </div>
                </td>
                {/* Set B: solid bold */}
                <td className="px-3 py-3">
                  <div className="flex justify-center">
                    <div className={`w-10 h-10 rounded-xl ${sB.bg} flex items-center justify-center shadow-sm`}>
                      <IconB size={20} className={sB.text} strokeWidth={2.5} />
                    </div>
                  </div>
                </td>
                {/* Set C: Monzo — unique vivid color circle, white icon */}
                <td className="px-3 py-3">
                  <div className="flex justify-center">
                    <div
                      className="w-10 h-10 rounded-full flex items-center justify-center shadow-md"
                      style={{ backgroundColor: row.monzoColor }}
                    >
                      <IconA size={20} color="#fff" strokeWidth={2.25} />
                    </div>
                  </div>
                </td>
                {/* Set D: gradient glass */}
                <td className="px-3 py-3">
                  <div className="flex justify-center">
                    <div
                      className="w-10 h-10 rounded-2xl flex items-center justify-center shadow-lg"
                      style={{ background: row.gradient }}
                    >
                      <IconA size={20} color="rgba(255,255,255,0.95)" strokeWidth={2} />
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm font-medium text-[#18181b]">{row.label}</td>
                {showParent && (
                  <td className="px-4 py-3 text-xs text-[#a1a1aa]">{row.parent || '—'}</td>
                )}
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${badge}`}>
                    {row.level}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
