import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, MapPin, TrendingUp, Shield, Users, Building2 } from 'lucide-react';

const FEATURES = [
  { icon: TrendingUp, title: 'Property & Market', desc: 'Prices, rents, yields, trends' },
  { icon: MapPin, title: 'Lifestyle & Connectivity', desc: '15-min neighbourhood, transport, broadband' },
  { icon: Shield, title: 'Environment & Safety', desc: 'Flood risk, air quality, green space' },
  { icon: Users, title: 'Community & Education', desc: 'Demographics, schools, deprivation' },
  { icon: Building2, title: 'Local Governance', desc: 'Council tax, local authority info' },
];

export default function Home() {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) navigate(`/results?q=${encodeURIComponent(query.trim())}`);
  };

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
        <a href="/data-attribution" className="text-sm text-ink-muted hover:text-brand-600 transition-colors">
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
          <form onSubmit={handleSearch} className="relative max-w-xl mx-auto">
            <div className="relative group">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-ink-faint group-focus-within:text-brand-600 transition-colors" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Try CR5 1RA or Coulsdon..."
                className="w-full h-14 pl-12 pr-32 rounded-2xl border-2 border-divider bg-white text-ink text-lg
                           placeholder:text-ink-faint focus:outline-none focus:border-brand-500 focus:ring-4
                           focus:ring-brand-100 transition-all shadow-sm hover:shadow-md"
              />
              <button
                type="submit"
                className="absolute right-2 top-1/2 -translate-y-1/2 h-10 px-6 rounded-xl bg-brand-600 text-white
                           font-semibold text-sm hover:bg-brand-700 active:scale-95 transition-all"
              >
                Analyse
              </button>
            </div>
          </form>

          {/* Quick examples */}
          <div className="flex flex-wrap justify-center gap-2 mt-4">
            {['CR5 1RA', 'Coulsdon', 'Manchester', 'SW1A 1AA'].map((ex) => (
              <button
                key={ex}
                onClick={() => { setQuery(ex); navigate(`/results?q=${encodeURIComponent(ex)}`); }}
                className="px-3 py-1.5 rounded-lg text-sm text-ink-muted bg-white border border-divider
                           hover:border-brand-300 hover:text-brand-600 transition-all cursor-pointer"
              >
                {ex}
              </button>
            ))}
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
