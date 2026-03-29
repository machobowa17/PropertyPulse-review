import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, MapPin, Building2, Loader2 } from 'lucide-react';
import { fetchSuggestions, type Suggestion } from '../api/client';

interface Props {
  initialValue?: string;
  size?: 'lg' | 'sm';
  placeholder?: string;
}

export default function SearchBox({ initialValue = '', size = 'lg', placeholder }: Props) {
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
  const typeIcon = (type: string) => {
    if (type === 'postcode' || type === 'postcode_district') return <MapPin className="w-3.5 h-3.5 text-brand-500" />;
    if (type === 'City' || type === 'Town') return <Building2 className="w-3.5 h-3.5 text-brand-500" />;
    return <MapPin className="w-3.5 h-3.5 text-ink-faint" />;
  };

  return (
    <div ref={containerRef} className="relative w-full">
      <form onSubmit={(e) => { e.preventDefault(); doSearch(query); }} className="relative group">
        <Search className={`absolute left-4 top-1/2 -translate-y-1/2 text-ink-faint group-focus-within:text-brand-600 transition-colors ${isLg ? 'w-5 h-5' : 'w-4 h-4'}`} />
        {loading && <Loader2 className={`absolute right-4 top-1/2 -translate-y-1/2 animate-spin text-ink-faint ${isLg ? 'w-4 h-4' : 'w-3.5 h-3.5'}`} />}
        <input
          type="text"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setShowDropdown(true)}
          placeholder={placeholder || 'Search postcode or place...'}
          className={`w-full bg-white text-ink placeholder:text-ink-faint focus:outline-none focus:border-brand-500 transition-all
            ${isLg
              ? 'h-14 pl-12 pr-32 rounded-2xl border-2 border-divider text-lg focus:ring-4 focus:ring-brand-100 shadow-sm hover:shadow-md'
              : 'h-10 pl-9 pr-4 rounded-xl border border-divider text-sm focus:ring-2 focus:ring-brand-100'
            }`}
        />
        {isLg && (
          <button
            type="submit"
            className="absolute right-2 top-1/2 -translate-y-1/2 h-10 px-6 rounded-xl bg-brand-600 text-white font-semibold text-sm hover:bg-brand-700 active:scale-95 transition-all"
          >
            Analyse
          </button>
        )}
      </form>

      {/* Dropdown */}
      {showDropdown && (
        <div className="absolute z-50 mt-1 w-full bg-white rounded-xl border border-divider shadow-lg overflow-hidden">
          {suggestions.map((s, i) => (
            <button
              key={`${s.label}-${i}`}
              onMouseDown={() => doSearch(s.label)}
              onMouseEnter={() => setActiveIdx(i)}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors
                ${i === activeIdx ? 'bg-brand-50' : 'hover:bg-surface'}`}
            >
              {typeIcon(s.type)}
              <span className="font-medium text-ink">{s.label}</span>
              {s.area && <span className="text-ink-faint text-xs ml-auto">{s.area}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
