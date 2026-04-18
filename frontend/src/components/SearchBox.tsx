import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, MapPin, Building2, Landmark, Loader2, ArrowRight, Clock3 } from 'lucide-react';
import { fetchSuggestions, type CoverageMetadata, type Suggestion } from '../api/client';

import type { DecisionMode } from './DecisionModeSelector';

interface Props {
  initialValue?: string;
  size?: 'lg' | 'sm';
  placeholder?: string;
  variant?: 'light' | 'dark';
  decisionMode?: DecisionMode;
}

interface RecentSearchEntry {
  label: string;
  savedAt: string;
}

const RECENT_SEARCHES_KEY = 'propertypulse_recent_searches_v1';
const MAX_RECENT_SEARCHES = 6;

function canUseStorage(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

function readRecentSearches(): RecentSearchEntry[] {
  if (!canUseStorage()) return [];
  try {
    const raw = window.localStorage.getItem(RECENT_SEARCHES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is RecentSearchEntry => {
      return !!item && typeof item.label === 'string' && typeof item.savedAt === 'string';
    });
  } catch {
    return [];
  }
}

function writeRecentSearches(entries: RecentSearchEntry[]): void {
  if (!canUseStorage()) return;
  try {
    window.localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(entries.slice(0, MAX_RECENT_SEARCHES)));
  } catch { /* Safari private browsing or quota exceeded — safe to ignore */ }
}

function saveRecentSearch(label: string): RecentSearchEntry[] {
  const trimmed = label.trim();
  if (!trimmed) return readRecentSearches();
  const now = new Date().toISOString();
  const existing = readRecentSearches().filter((item) => item.label.toLowerCase() !== trimmed.toLowerCase());
  const next = [{ label: trimmed, savedAt: now }, ...existing].slice(0, MAX_RECENT_SEARCHES);
  writeRecentSearches(next);
  return next;
}

export default function SearchBox({ initialValue = '', size = 'lg', placeholder, variant = 'light', decisionMode }: Props) {
  const navigate = useNavigate();
  const [query, setQuery] = useState(initialValue);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [coverage, setCoverage] = useState<CoverageMetadata | null>(null);
  const [recentSearches, setRecentSearches] = useState<RecentSearchEntry[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const [hasTyped, setHasTyped] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const fetchSeqRef = useRef(0);

  useEffect(() => {
    setRecentSearches(readRecentSearches());
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, []);

  useEffect(() => {
    setQuery(initialValue);
  }, [initialValue]);

  const showRecentSearches = query.trim().length < 2 && recentSearches.length > 0;
  const showEmptyGuidance = query.trim().length >= 2 && !loading && suggestions.length === 0 && hasTyped;
  const dropdownItems = useMemo(() => {
    if (showRecentSearches) {
      return recentSearches.map((item) => ({ kind: 'recent' as const, label: item.label }));
    }
    return suggestions.map((item) => ({ kind: 'suggestion' as const, suggestion: item }));
  }, [recentSearches, showRecentSearches, suggestions]);

  const doSearch = useCallback((value: string) => {
    const trimmed = value.trim();
    if (trimmed) {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      ++fetchSeqRef.current;
      const nextRecent = saveRecentSearch(trimmed);
      setRecentSearches(nextRecent);
      const next = new URLSearchParams({ q: trimmed });
      if (decisionMode) next.set('mode', decisionMode);
      navigate(`/results?${next.toString()}`);
      setShowDropdown(false);
      setSuggestions([]);
      setActiveIdx(-1);
    }
  }, [decisionMode, navigate]);

  const pickSuggestion = useCallback((suggestion: Suggestion) => {
    doSearch(suggestion.selection_value || suggestion.label);
  }, [doSearch]);

  const handleChange = (value: string) => {
    setQuery(value);
    setHasTyped(true);
    setActiveIdx(-1);
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (value.trim().length < 2) {
      ++fetchSeqRef.current;
      setSuggestions([]);
      setShowDropdown(true);
      setLoading(false);
      return;
    }

    setLoading(true);
    const seq = ++fetchSeqRef.current;
    debounceRef.current = setTimeout(async () => {
      const result = await fetchSuggestions(value.trim());
      if (seq !== fetchSeqRef.current) return;
      setSuggestions(result.suggestions);
      setCoverage(result.coverage || null);
      setShowDropdown(true);
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
      setActiveIdx((i) => Math.min(i + 1, dropdownItems.length - 1));
      return;
    }

    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, -1));
      return;
    }

    if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIdx >= 0 && activeIdx < dropdownItems.length) {
        const activeItem = dropdownItems[activeIdx];
        if (activeItem.kind === 'recent') {
          doSearch(activeItem.label);
        } else {
          pickSuggestion(activeItem.suggestion);
        }
      } else {
        doSearch(query);
      }
      return;
    }

    if (e.key === 'Escape') {
      setShowDropdown(false);
    }
  };

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
    if (type === 'borough' || type === 'district' || type === 'county' || type === 'ward') return <Landmark className="w-3.5 h-3.5 text-brand-400" />;
    if (type === 'City' || type === 'Town' || type === 'place') return <Building2 className="w-3.5 h-3.5 text-brand-400" />;
    return <MapPin className="w-3.5 h-3.5 text-ink-faint" />;
  };

  const typeLabel = (suggestion: Suggestion) => suggestion.display_type || suggestion.secondary || '';
  const coverageMessage = coverage?.coverage_message || 'England remains the only fully live end-to-end country today. Wales now has live support for council tax plus selected England-and-Wales census and market datasets, but wider Wales coverage is still partial and some search and dataset paths remain staged. Scotland remains in an earlier staged rollout through shared geography and selected authority-level sources.';
  const liveCountries = coverage?.live_countries?.length ? coverage.live_countries : ['England'];
  const partialCountries = coverage?.partial_countries ?? ['Wales'];
  const plannedCountries = coverage?.planned_countries ?? ['Scotland'];
  const parkedCountries = coverage?.parked_countries ?? ['Northern Ireland'];

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
          id="search-input"
          type="text"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={(e) => {
            e.target.select();
            setRecentSearches(readRecentSearches());
            setShowDropdown(true);
          }}
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
            className={`absolute right-2.5 top-1/2 -translate-y-1/2 font-semibold text-sm active:scale-95 transition-all flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
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

      {isLg && (
        <div className="mt-3 space-y-2">
          <div className={`flex flex-wrap items-center gap-x-3 gap-y-1 text-xs ${isDark ? 'text-white/45' : 'text-ink-faint'}`}>
            <span>Search by postcode for block-level evidence, or by town, borough, ward, district, or county for broader context. {coverageMessage}</span>
          </div>
          <div className="flex flex-wrap gap-2 text-[11px]">
            <span className={`inline-flex items-center rounded-full px-2.5 py-1 font-medium ${isDark ? 'bg-emerald-500/10 text-emerald-200 border border-emerald-400/20' : 'bg-emerald-50 text-emerald-800 border border-emerald-200'}`}>
              Live: {liveCountries.join(', ')}
            </span>
            {plannedCountries.length > 0 && (
              <span className={`inline-flex items-center rounded-full px-2.5 py-1 font-medium ${isDark ? 'bg-amber-500/10 text-amber-100 border border-amber-300/20' : 'bg-amber-50 text-amber-800 border border-amber-200'}`}>
                Planned next: {plannedCountries.join(', ')}
              </span>
            )}
            {parkedCountries.length > 0 && (
              <span className={`inline-flex items-center rounded-full px-2.5 py-1 font-medium ${isDark ? 'bg-slate-500/10 text-slate-200 border border-slate-300/20' : 'bg-slate-100 text-slate-700 border border-slate-200'}`}>
                Parked: {parkedCountries.join(', ')}
              </span>
            )}
          </div>
        </div>
      )}

      {showDropdown && (
        <div className={`absolute z-50 mt-2 w-full rounded-2xl shadow-2xl overflow-hidden ${
          isDark
            ? 'bg-[#1a1a1e] border border-white/10'
            : 'bg-white border border-divider'
        }`}>
          {showRecentSearches && (
            <div className={`px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] ${isDark ? 'text-white/40 bg-white/[0.03]' : 'text-ink-faint bg-surface/70'}`}>
              Recent searches
            </div>
          )}

          {showRecentSearches && recentSearches.map((item, i) => (
            <button
              key={`${item.label}-${item.savedAt}`}
              onMouseDown={() => doSearch(item.label)}
              onMouseEnter={() => setActiveIdx(i)}
              className={`w-full flex items-center gap-3 px-4 py-3 text-left text-sm transition-colors ${
                isDark
                  ? i === activeIdx ? 'bg-white/10' : 'hover:bg-white/[0.06]'
                  : i === activeIdx ? 'bg-brand-50' : 'hover:bg-surface'
              }`}
            >
              <Clock3 className="w-3.5 h-3.5 text-brand-400" />
              <div className="min-w-0 flex-1">
                <div className={`font-medium truncate ${isDark ? 'text-white' : 'text-ink'}`}>{item.label}</div>
                <div className={`text-xs truncate mt-0.5 ${isDark ? 'text-white/40' : 'text-ink-faint'}`}>
                  Re-open a recent area search
                </div>
              </div>
            </button>
          ))}

          {!showRecentSearches && suggestions.map((s, i) => (
            <button
              key={`${s.label}-${s.area || ''}-${i}`}
              onMouseDown={() => pickSuggestion(s)}
              onMouseEnter={() => setActiveIdx(i)}
              className={`w-full flex items-center gap-3 px-4 py-3 text-left text-sm transition-colors ${
                isDark
                  ? i === activeIdx ? 'bg-white/10' : 'hover:bg-white/[0.06]'
                  : i === activeIdx ? 'bg-brand-50' : 'hover:bg-surface'
              }`}
            >
              {typeIcon(s.type)}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`font-medium truncate ${isDark ? 'text-white' : 'text-ink'}`}>{s.display_label || s.label}</span>
                  {typeLabel(s) && (
                    <span className={`shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                      isDark ? 'bg-white/10 text-white/50' : 'bg-surface text-ink-faint'
                    }`}>{typeLabel(s)}</span>
                  )}
                </div>
                {s.display_context && (
                  <div className={`text-xs truncate mt-0.5 ${isDark ? 'text-white/40' : 'text-ink-faint'}`}>
                    {s.display_context}
                  </div>
                )}
              </div>
            </button>
          ))}

          {showEmptyGuidance && (
            <div className="px-4 py-4">
              <div className={`rounded-2xl border px-4 py-3 ${isDark ? 'border-white/10 bg-white/[0.04]' : 'border-divider bg-surface/70'}`}>
                <div className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-ink'}`}>
                  No direct matches yet
                </div>
                <p className={`mt-1 text-xs leading-relaxed ${isDark ? 'text-white/48' : 'text-ink-faint'}`}>
                  Try a full postcode, a nearby town, a London borough, a district, a ward, or a county name. Shorter place fragments can be harder to resolve cleanly than official names. {coverageMessage}
                </p>
                <div className={`mt-2 flex flex-wrap gap-1.5 text-[11px] ${isDark ? 'text-white/55' : 'text-ink-faint'}`}>
                  <span>Live: {liveCountries.join(', ')}</span>
                  {partialCountries.length > 0 && <span>Partial: {partialCountries.join(', ')}</span>}
                  {plannedCountries.length > 0 && <span>Planned: {plannedCountries.join(', ')}</span>}
                  {parkedCountries.length > 0 && <span>Parked: {parkedCountries.join(', ')}</span>}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
