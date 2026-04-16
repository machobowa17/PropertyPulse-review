import { useNavigate } from 'react-router-dom';
import { MapPin, TrendingUp, Shield, Users, Building2, Leaf, ArrowRight } from 'lucide-react';
import SearchBox from '../components/SearchBox';

const FEATURES = [
  { num: '01', icon: TrendingUp, title: 'Property & Market', desc: 'Prices, rents, yields, affordability and trends across every property type' },
  { num: '02', icon: MapPin, title: 'Lifestyle & Connectivity', desc: '15-minute neighbourhood score, transport links, broadband and EV charging' },
  { num: '03', icon: Shield, title: 'Environment & Safety', desc: 'Flood risk, air quality, green space, crime rates and environmental grading' },
  { num: '04', icon: Users, title: 'Community & Education', desc: 'Demographics, Ofsted-rated schools, NHS facilities and deprivation data' },
  { num: '05', icon: Building2, title: 'Local Governance', desc: 'Council tax bands, political control, water company and financial health' },
];

const EXAMPLE_PLACES = [
  { q: 'SW1A 1AA', hint: 'Westminster' },
  { q: 'M1 1AE',   hint: 'Manchester' },
  { q: 'E1 6RF',   hint: 'Whitechapel' },
  { q: 'BS1 4DJ',  hint: 'Bristol' },
  { q: 'CR5 1RA',  hint: 'Coulsdon' },
  { q: 'Edinburgh', hint: 'Scotland' },
];

/* Floating preview card — shows a "taste" of the product on the hero */
function PreviewCard() {
  return (
    <div className="relative w-full max-w-sm">
      {/* Glass card */}
      <div className="rounded-2xl bg-white/[0.06] border border-white/[0.1] backdrop-blur-md p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[11px] font-mono text-white/40 tracking-wider uppercase">Illustrative example</div>
            <div className="text-lg font-bold text-white mt-0.5">Your postcode</div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center">
            <span className="text-emerald-400 font-mono font-bold text-sm">--</span>
          </div>
        </div>

        {/* Mini metrics */}
        <div className="grid grid-cols-2 gap-2">
          {[
            { label: 'Median Price', value: '£---,---', signal: 'text-emerald-400' },
            { label: 'Crime Rate', value: '--/1000', signal: 'text-amber-400' },
            { label: 'Top School', value: '--------', signal: 'text-emerald-400' },
            { label: 'Flood Risk', value: '--------', signal: 'text-emerald-400' },
          ].map(({ label, value, signal }) => (
            <div key={label} className="rounded-xl bg-white/[0.04] border border-white/[0.06] p-3">
              <div className="text-[10px] text-white/35 font-medium uppercase tracking-wide">{label}</div>
              <div className={`text-sm font-mono font-bold mt-0.5 ${signal}`}>{value}</div>
            </div>
          ))}
        </div>

        {/* Mini bar */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-[10px] text-white/40">
            <span>Persona Score</span>
            <span className="font-mono">-- / 100</span>
          </div>
          <div className="h-1.5 rounded-full bg-white/[0.08] overflow-hidden">
            <div className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400" style={{ width: '65%' }} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const navigate = useNavigate();

  return (
    <div className="min-h-dvh flex flex-col bg-[#0c0c0e]">
      {/* Nav */}
      <nav className="px-6 lg:px-10 py-5 flex items-center justify-between relative z-20">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center">
            <Leaf className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-lg tracking-tight text-white">PropertyPulse</span>
        </div>
        <div className="flex items-center gap-6">
          <a href="/data-attribution" className="text-sm text-white/50 hover:text-white/80 transition-colors hidden sm:block">
            Data Sources
          </a>
          <button
            onClick={() => document.getElementById('search-input')?.focus()}
            className="px-4 py-2 rounded-full text-sm font-medium bg-white text-[#0c0c0e] hover:bg-white/90 active:scale-95 transition-all"
          >
            Get started
          </button>
        </div>
      </nav>

      {/* Aurora background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0" aria-hidden="true">
        {/* Blue orb */}
        <div
          className="absolute w-[600px] h-[600px] rounded-full opacity-[0.12]"
          style={{
            background: 'radial-gradient(circle, #3b82f6, transparent 70%)',
            top: '-5%',
            right: '10%',
            animation: 'aurora-drift 20s ease-in-out infinite',
          }}
        />
        {/* Warm amber orb */}
        <div
          className="absolute w-[500px] h-[500px] rounded-full opacity-[0.08]"
          style={{
            background: 'radial-gradient(circle, #f59e0b, transparent 70%)',
            top: '15%',
            right: '25%',
            animation: 'aurora-drift 25s ease-in-out infinite reverse',
          }}
        />
        {/* Faint purple accent */}
        <div
          className="absolute w-[400px] h-[400px] rounded-full opacity-[0.06]"
          style={{
            background: 'radial-gradient(circle, #8b5cf6, transparent 70%)',
            bottom: '10%',
            left: '5%',
            animation: 'aurora-drift 22s ease-in-out infinite',
          }}
        />
      </div>

      {/* Hero */}
      <main className="flex-1 flex flex-col justify-center relative z-10">
        <div className="max-w-7xl mx-auto w-full px-6 lg:px-10 py-12 lg:py-0">
          <div className="flex flex-col lg:flex-row lg:items-center lg:gap-16">
            {/* Left: text + search */}
            <div className="flex-1 max-w-2xl">
              {/* Badge */}
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/[0.06] border border-white/[0.08] text-[13px] font-medium text-white/60 mb-8">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                184 data points across 5 themes
              </div>

              <h1 className="text-5xl sm:text-6xl lg:text-7xl font-black tracking-tighter text-white leading-[0.95] mb-5">
                Know your{'\n'}
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-400 to-blue-300">
                  neighbourhood.
                </span>
              </h1>

              <p className="text-lg text-white/45 mb-10 max-w-md leading-relaxed">
                The most complete area analysis for UK property.
                Every postcode, every metric, personalised for you.
              </p>

              {/* Search */}
              <div className="max-w-xl">
                <SearchBox size="lg" placeholder="Enter a postcode or place name..." variant="dark" />
              </div>

              {/* Quick links */}
              <div className="flex flex-wrap gap-2 mt-6">
                {EXAMPLE_PLACES.map(({ q, hint }) => (
                  <button
                    key={q}
                    onClick={() => navigate(`/results?q=${encodeURIComponent(q)}`)}
                    className="group flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm
                               bg-white/[0.04] border border-white/[0.08]
                               hover:bg-white/[0.08] hover:border-white/[0.15] transition-all cursor-pointer"
                  >
                    <span className="font-mono font-semibold text-white/70 group-hover:text-white text-xs">{q}</span>
                    <span className="text-white/30 text-xs group-hover:text-white/50">{hint}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Right: floating preview card (desktop only) */}
            <div className="hidden lg:flex flex-1 items-center justify-center">
              <PreviewCard />
            </div>
          </div>
        </div>

        {/* Data source strip */}
        <div className="max-w-7xl mx-auto w-full px-6 lg:px-10 mt-20 lg:mt-28">
          <div className="flex flex-wrap items-center gap-x-8 gap-y-3 py-6 border-t border-white/[0.06]">
            <span className="text-[11px] text-white/25 uppercase tracking-wider font-medium">Powered by</span>
            {['ONS', 'HM Land Registry', 'Ofsted', 'Ofcom', 'Environment Agency', 'NHS Digital'].map((source) => (
              <span key={source} className="text-[13px] text-white/30 font-medium tracking-wide">{source}</span>
            ))}
          </div>
        </div>
      </main>

      {/* Features */}
      <section className="relative z-10 max-w-7xl mx-auto w-full px-6 lg:px-10 py-24">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8">
          {FEATURES.map(({ num, icon: Icon, title, desc }) => (
            <div
              key={title}
              className="group p-6 rounded-2xl bg-white/[0.03] border border-white/[0.06]
                         hover:bg-white/[0.06] hover:border-white/[0.1] transition-all duration-300"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="w-11 h-11 rounded-xl bg-white/[0.06] flex items-center justify-center group-hover:bg-brand-500/20 transition-colors">
                  <Icon className="w-5 h-5 text-white/50 group-hover:text-brand-400 transition-colors" />
                </div>
                <span className="font-mono text-xs text-white/15 font-bold">{num}</span>
              </div>
              <h3 className="font-bold text-[15px] text-white/80 mb-2 group-hover:text-white transition-colors">{title}</h3>
              <p className="text-sm text-white/35 leading-relaxed group-hover:text-white/50 transition-colors">{desc}</p>
            </div>
          ))}

          {/* CTA card */}
          <div className="p-6 rounded-2xl bg-gradient-to-br from-brand-600/20 to-brand-800/20 border border-brand-500/20 flex flex-col justify-center">
            <h3 className="font-bold text-[15px] text-white/90 mb-2">Ready to explore?</h3>
            <p className="text-sm text-white/40 leading-relaxed mb-4">
              Try any UK postcode or place name — the analysis takes seconds.
            </p>
            <button
              onClick={() => navigate('/results?q=CR5+1RA')}
              className="inline-flex items-center gap-2 text-sm font-semibold text-brand-400 hover:text-brand-300 transition-colors"
            >
              See example report <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 px-6 lg:px-10 py-6 text-center text-xs text-white/20 border-t border-white/[0.04]">
        Contains OS, Land Registry, ONS, Ofcom, Ofsted, NHS data &copy; Crown copyright. &copy; OpenStreetMap contributors.
      </footer>
    </div>
  );
}
