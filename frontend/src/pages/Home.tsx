import { useNavigate } from 'react-router-dom';
import { MapPin, TrendingUp, Shield, Users, Building2, Leaf } from 'lucide-react';
import SearchBox from '../components/SearchBox';

const THEMES = [
  { icon: TrendingUp, title: 'Property & Market', hint: 'Prices, yields, trends' },
  { icon: MapPin, title: 'Lifestyle & Connectivity', hint: 'Transport, broadband, amenities' },
  { icon: Shield, title: 'Environment & Safety', hint: 'Flood, air quality, crime' },
  { icon: Users, title: 'Community & Education', hint: 'Schools, NHS, demographics' },
  { icon: Building2, title: 'Local Governance', hint: 'Council tax, politics, utilities' },
];

const EXAMPLE_PLACES = [
  { q: 'SW1A 1AA', hint: 'Westminster' },
  { q: 'M1 1AE',   hint: 'Manchester' },
  { q: 'E1 6RF',   hint: 'Whitechapel' },
  { q: 'BS1 4DJ',  hint: 'Bristol' },
  { q: 'CR5 1RA',  hint: 'Coulsdon' },
  { q: 'Edinburgh', hint: 'Scotland' },
];

export default function Home() {
  const navigate = useNavigate();

  return (
    <div className="min-h-dvh flex flex-col bg-white">
      {/* Nav */}
      <nav className="px-6 lg:px-10 py-5 flex items-center justify-between relative z-20">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center">
            <Leaf className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-lg tracking-tight text-gray-900">PropertyPulse</span>
        </div>
      </nav>

      {/* Subtle background accents */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0" aria-hidden="true">
        <div
          className="absolute w-[800px] h-[800px] rounded-full opacity-[0.04]"
          style={{
            background: 'radial-gradient(circle, #3b82f6, transparent 70%)',
            top: '-15%',
            right: '-5%',
          }}
        />
        <div
          className="absolute w-[600px] h-[600px] rounded-full opacity-[0.03]"
          style={{
            background: 'radial-gradient(circle, #8b5cf6, transparent 70%)',
            bottom: '0%',
            left: '-5%',
          }}
        />
      </div>

      {/* Single-screen layout */}
      <main className="flex-1 flex flex-col justify-center relative z-10">
        <div className="max-w-7xl mx-auto w-full px-6 lg:px-10">
          <div className="flex flex-col lg:flex-row lg:items-start lg:gap-16">
            {/* Left: headline + search */}
            <div className="flex-1 max-w-2xl">
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter text-gray-900 leading-[0.95] mb-4">
                Know your{'\n'}
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-600 to-brand-400">
                  neighbourhood.
                </span>
              </h1>

              <p className="text-base text-gray-500 mb-8 max-w-md leading-relaxed">
                The most complete area analysis for UK property.
                Every postcode, every metric, personalised for you.
              </p>

              {/* Search */}
              <div className="max-w-xl">
                <SearchBox size="lg" placeholder="Enter a postcode or place name..." variant="light" />
              </div>

              {/* Quick links */}
              <div className="flex flex-wrap gap-2 mt-5">
                {EXAMPLE_PLACES.map(({ q, hint }) => (
                  <button
                    key={q}
                    onClick={() => navigate(`/results?q=${encodeURIComponent(q)}`)}
                    className="group flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm
                               bg-gray-50 border border-gray-200
                               hover:bg-brand-50 hover:border-brand-200 transition-all cursor-pointer"
                  >
                    <span className="font-mono font-semibold text-gray-700 group-hover:text-brand-700 text-xs">{q}</span>
                    <span className="text-gray-400 text-xs group-hover:text-brand-500">{hint}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Right: 5 theme tiles */}
            <div className="flex-1 max-w-md mt-10 lg:mt-0">
              <div className="grid grid-cols-1 gap-2.5">
                {THEMES.map(({ icon: Icon, title, hint }) => (
                  <div
                    key={title}
                    className="group flex items-center gap-4 px-4 py-3.5 rounded-xl bg-gray-50/80 border border-gray-100
                               hover:bg-white hover:border-gray-200 hover:shadow-md hover:shadow-gray-100/50 transition-all duration-200"
                  >
                    <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center shrink-0 group-hover:bg-brand-100 transition-colors">
                      <Icon className="w-5 h-5 text-brand-500 group-hover:text-brand-600 transition-colors" />
                    </div>
                    <div className="min-w-0">
                      <div className="font-semibold text-sm text-gray-800 group-hover:text-gray-900 transition-colors">{title}</div>
                      <div className="text-xs text-gray-400 group-hover:text-gray-500 transition-colors">{hint}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 px-6 lg:px-10 py-4 text-center text-xs text-gray-400 border-t border-gray-100">
        Data from OS, Land Registry, ONS, Ofcom, Ofsted, NHS data &copy; Crown Copyright. &copy; OpenStreetMap Contributors. See <a href="/data-attribution" className="underline hover:text-gray-600 transition-colors">data sources</a> for the full list.
      </footer>
    </div>
  );
}
