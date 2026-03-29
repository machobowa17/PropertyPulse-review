import { useNavigate } from 'react-router-dom';
import { MapPin, TrendingUp, Shield, Users, Building2 } from 'lucide-react';
import SearchBox from '../components/SearchBox';

const FEATURES = [
  { icon: TrendingUp, title: 'Property & Market', desc: 'Prices, rents, yields, trends' },
  { icon: MapPin, title: 'Lifestyle & Connectivity', desc: '15-min neighbourhood, transport, broadband' },
  { icon: Shield, title: 'Environment & Safety', desc: 'Flood risk, air quality, green space' },
  { icon: Users, title: 'Community & Education', desc: 'Demographics, schools, deprivation' },
  { icon: Building2, title: 'Local Governance', desc: 'Council tax, local authority info' },
];

export default function Home() {
  const navigate = useNavigate();

  return (
    <div className="min-h-dvh flex flex-col">
      {/* Nav */}
      <nav className="px-6 py-4 flex items-center justify-between border-b border-divider bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
            <MapPin className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-lg tracking-tight text-ink">PropertyPulse</span>
        </div>
        <a href="/data-attribution" className="text-sm text-ink-muted hover:text-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500 rounded transition-colors">
          Data Sources
        </a>
      </nav>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-16">
        <div className="max-w-2xl w-full text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-brand-50 text-brand-700 text-sm font-medium mb-6">
            <span className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
            184 data points across 5 themes
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-ink leading-tight mb-4">
            Deep Area Intelligence
            <span className="block text-brand-600">for UK Property</span>
          </h1>

          <p className="text-lg text-ink-muted mb-10 max-w-lg mx-auto leading-relaxed">
            Enter a postcode or place name. Get comprehensive area analysis with
            personalised insights for your situation.
          </p>

          {/* Search */}
          <div className="max-w-xl mx-auto">
            <SearchBox size="lg" placeholder="Try CR5 1RA or Coulsdon..." />
          </div>

          {/* Quick examples */}
          <div className="mt-5 space-y-2.5">
            <div className="flex flex-wrap justify-center gap-2 items-center">
              <span className="text-[11px] text-ink-faint uppercase tracking-wide font-medium w-full text-center mb-0.5">
                Try a postcode
              </span>
              {[
                { q: 'SW1A 1AA', label: 'SW1A 1AA', hint: 'Westminster' },
                { q: 'M1 1AE',   label: 'M1 1AE',   hint: 'Manchester' },
                { q: 'E1 6RF',   label: 'E1 6RF',   hint: 'Whitechapel' },
                { q: 'BS1 4DJ',  label: 'BS1 4DJ',  hint: 'Bristol' },
                { q: 'LS1 1BA',  label: 'LS1 1BA',  hint: 'Leeds' },
                { q: 'CR5 1RA',  label: 'CR5 1RA',  hint: 'Coulsdon' },
              ].map(({ q, label, hint }) => (
                <button
                  key={q}
                  onClick={() => navigate(`/results?q=${encodeURIComponent(q)}`)}
                  className="group flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm bg-white border border-divider
                             hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700 transition-all cursor-pointer"
                >
                  <MapPin className="w-3 h-3 text-ink-faint group-hover:text-brand-500 shrink-0" />
                  <span className="font-semibold text-ink group-hover:text-brand-700">{label}</span>
                  <span className="text-ink-faint text-xs group-hover:text-brand-500">{hint}</span>
                </button>
              ))}
            </div>
            <div className="flex flex-wrap justify-center gap-2 items-center">
              <span className="text-[11px] text-ink-faint uppercase tracking-wide font-medium w-full text-center mb-0.5">
                Or a place name
              </span>
              {[
                { q: 'Manchester',  hint: 'North West' },
                { q: 'Birmingham',  hint: 'West Midlands' },
                { q: 'Edinburgh',   hint: 'Scotland' },
                { q: 'Bristol',     hint: 'South West' },
                { q: 'Leeds',       hint: 'Yorkshire' },
                { q: 'Hackney',     hint: 'East London' },
              ].map(({ q, hint }) => (
                <button
                  key={q}
                  onClick={() => navigate(`/results?q=${encodeURIComponent(q)}`)}
                  className="group flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm bg-surface border border-divider
                             hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700 transition-all cursor-pointer"
                >
                  <MapPin className="w-3 h-3 text-ink-faint group-hover:text-brand-500 shrink-0" />
                  <span className="font-semibold text-ink group-hover:text-brand-700">{q}</span>
                  <span className="text-ink-faint text-xs group-hover:text-brand-500">{hint}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Feature cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 max-w-5xl mx-auto mt-20 px-4">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className="p-5 rounded-2xl bg-white border border-divider hover:shadow-lg hover:-translate-y-1
                         transition-all duration-200 text-left"
            >
              <div className="w-10 h-10 rounded-xl bg-brand-50 flex items-center justify-center mb-3">
                <Icon className="w-5 h-5 text-brand-600" />
              </div>
              <h3 className="font-semibold text-sm text-ink mb-1">{title}</h3>
              <p className="text-xs text-ink-muted leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </main>

      {/* Footer */}
      <footer className="px-6 py-4 text-center text-xs text-ink-faint border-t border-divider">
        Contains OS, Land Registry, ONS, Ofcom, Ofsted, NHS data &copy; Crown copyright. &copy; OpenStreetMap contributors.
      </footer>
    </div>
  );
}
