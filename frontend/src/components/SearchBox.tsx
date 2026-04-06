import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, MapPin, Building2, Landmark, Loader2, ArrowRight } from 'lucide-react';
import { fetchSuggestions, type Suggestion } from '../api/client';

interface Props {
  initialValue?: string;
  size?: 'lg' | 'sm';
  placeholder?: string;
  variant?: 'light' | 'dark';
}

export default function SearchBox({ initialValue = '', size = 'lg', placeholder, variant = 'light' }: Props) {
  const navigate = useNavigate();
  const [query, setQuery] = useState(initialValue);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const fetchSeqRef = useRef(0);

  const doSearch = useCallback((value: string) => {
    if (value.trim()) {
      // Invalidate any in-flight fetch before navigating (component will unmount)
      if (debounceRef.current) clearTimeout(debounceRef.current);
      ++fetchSeqRef.current;
      navigate(`/results?q=${encodeURIComponent(value.trim())}`);
      setShowDropdown(false);
      setSuggestions([]);
    }
  }, [navigate]);

  const handleChange = (value: string) => {
    setQuery(value);
    setActiveIdx(-1);
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (value.trim().length < 2) {
      ++fetchSeqRef.current; // invalidate any in-flight fetch
      setSuggestions([]);
      setShowDropdown(false);
      setLoading(false);
      return;
    }

    setLoading(true);
    const seq = ++fetchSeqRef.current;
    debounceRef.current = setTimeout(async () => {
      const results = await fetchSuggestions(value.trim());
      if (seq !== fetchSeqRef.current) return; // stale response — a newer fetch is in flight
      setSuggestions(results);
      setShowDropdown(results.length > 0);
      setLoading(false);
    }, 200);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showDropdown) {
      if (e.key === 'Enter') doSearch(query);
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, -1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIdx >= 0 && activeIdx < suggestions.length) {
        doSearch(suggestions[activeIdx].label);
      } else {
        doSearch(query);
      }
    } else if (e.key === 'Escape') {
      setShowDropdown(false);
    }
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const isLg = size === 'lg';
  const isDark = variant === 'dark';
  const typeIcon = (type: string) => {
    if (type === 'postcode' || type === 'postcode_district') return <MapPin className="w-3.5 h-3.5 text-brand-400" />;
    if (type === 'borough' || type === 'district' || type === 'county') return <Landmark className="w-3.5 h-3.5 text-brand-400" />;
    if (type === 'City' || type === 'Town') return <Building2 className="w-3.5 h-3.5 text-brand-400" />;
    return <MapPin className="w-3.5 h-3.5 text-ink-faint" />;
  };

  const typeLabel = (type: string) => {
    switch (type) {
      case 'postcode': case 'postcode_district': return 'Postcode';
      case 'place': return 'Place';
      case 'ward': return 'Ward';
      case 'borough': return 'Borough';
      case 'district': return 'District';
      case 'county': return 'County';
      case 'City': return 'City';
      case 'Town': return 'Town';
      case 'Suburban Area': return 'Area';
      case 'Village': return 'Village';
      case 'Other Settlement': return 'Place';
      case 'Hamlet': return 'Hamlet';
      default: return '';
    }
  };

  return (
    <div ref={containerRef} className="relative w-full">
      <form onSubmit={(e) => { e.preventDefault(); doSearch(query); }} className="relative group">
        <Search className={`absolute left-5 top-1/2 -translate-y-1/2 transition-colors ${isLg ? 'w-5 h-5' : 'w-4 h-4'} ${
          isDark
            ? 'text-white/40 group-focus-within:text-white/70'
            : 'text-ink-faint group-focus-within:text-brand-600'
        }`} />
        {loading && <Loader2 className={`absolute top-1/2 -translate-y-1/2 animate-spin ${isLg ? 'w-4 h-4 right-5' : 'w-3.5 h-3.5 right-4'} ${
          isDark ? 'text-white/40' : 'text-ink-faint'
        }`} />}
        <input
          type="text"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setShowDropdown(true)}
          placeholder={placeholder || 'Search postcode or place...'}
          className={`w-full focus:outline-none transition-all ${
            isDark
              ? isLg
                ? 'h-16 pl-14 pr-36 rounded-2xl bg-white/[0.08] border border-white/[0.12] text-white placeholder:text-white/30 text-lg backdrop-blur-sm focus:border-white/25 focus:ring-2 focus:ring-white/10 hover:bg-white/[0.1]'
                : 'h-10 pl-9 pr-4 rounded-xl bg-white/[0.08] border border-white/[0.12] text-white placeholder:text-white/30 text-sm focus:ring-2 focus:ring-white/10'
              : isLg
                ? 'h-14 pl-12 pr-32 rounded-2xl border-2 border-divider bg-white text-ink placeholder:text-ink-faint text-lg focus:border-brand-500 focus:ring-4 focus:ring-brand-100 shadow-sm hover:shadow-md'
                : 'h-10 pl-9 pr-4 rounded-xl border border-divider bg-white text-ink placeholder:text-ink-faint text-sm focus:ring-2 focus:ring-brand-100 focus:border-brand-500'
          }`}
        />
        {isLg && (
          <button
            type="submit"
            className={`absolute right-2.5 top-1/2 -translate-y-1/2 font-semibold text-sm active:scale-95 transition-all flex items-center gap-2 ${
              isDark
                ? 'h-11 px-6 rounded-xl bg-white text-[#0c0c0e] hover:bg-white/90'
                : 'h-10 px-6 rounded-xl bg-brand-600 text-white hover:bg-brand-700'
            }`}
          >
            Analyse
            {isDark && <ArrowRight className="w-4 h-4" />}
          </button>
        )}
      </form>

      {/* Dropdown */}
      {showDropdown && (
        <div className={`absolute z-50 mt-2 w-full rounded-2xl shadow-2xl overflow-hidden ${
          isDark
            ? 'bg-[#1a1a1e] border border-white/10'
            : 'bg-white border border-divider'
        }`}>
          {suggestions.map((s, i) => (
            <button
              key={`${s.label}-${i}`}
              onMouseDown={() => doSearch(s.label)}
              onMouseEnter={() => setActiveIdx(i)}
              className={`w-full flex items-center gap-3 px-4 py-3 text-left text-sm transition-colors ${
                isDark
                  ? i === activeIdx ? 'bg-white/10' : 'hover:bg-white/[0.06]'
                  : i === activeIdx ? 'bg-brand-50' : 'hover:bg-surface'
              }`}
            >
              {typeIcon(s.type)}
              <span className={`font-medium ${isDark ? 'text-white' : 'text-ink'}`}>{s.label}</span>
              {typeLabel(s.type) && (
                <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                  isDark ? 'bg-white/10 text-white/50' : 'bg-surface text-ink-faint'
                }`}>{typeLabel(s.type)}</span>
              )}
              {s.area && <span className={`text-xs ml-auto ${isDark ? 'text-white/40' : 'text-ink-faint'}`}>{s.area}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
