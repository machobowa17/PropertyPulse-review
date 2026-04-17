import { useState, useCallback } from 'react';
import { Heart, BellRing, FileDown, Loader2 } from 'lucide-react';
import { useResults } from '../../context/ResultsContext';
import { LSOA_SUFFIX } from '../../utils/resultsConstants';

function lsoaList(codes: string[], count: number): string {
  if (count === 0) return '';
  const label = count === 1 ? 'Lower Layer Super Output Area (LSOA)' : 'Lower Layer Super Output Areas (LSOAs)';
  if (codes.length > 0) return `${count} ${label}: ${codes.join(', ')}`;
  return `${count} ${label}`;
}

function LsoaContextBlurb({ resolved, areaName }: { resolved: any; areaName: string }) {
  const type = resolved?.type;
  const rc = resolved?.resolved_codes;
  const count: number = resolved?.lsoa_count ?? 0;
  const lsoaCodes: string[] = resolved?.lsoa_codes ?? [];

  if (!type || count === 0) return null;

  let intro = '';
  if (type === 'postcode' && rc?.lsoa && rc.lsoa !== '_') {
    intro = `${areaName} is part of Lower Layer Super Output Area (LSOA) ${rc.lsoa}.`;
  } else if (type === 'postcode_district') {
    intro = `${areaName} postcode district spans ${lsoaList(lsoaCodes, count)}.`;
  } else if (type === 'ward') {
    intro = `${areaName} ward spans ${lsoaList(lsoaCodes, count)}.`;
  } else if (type === 'borough') {
    intro = `${areaName} is a London Borough spanning ${lsoaList(lsoaCodes, count)}.`;
  } else if (type === 'district' || type === 'lad') {
    intro = `${areaName} is a Local Authority District spanning ${lsoaList(lsoaCodes, count)}.`;
  } else if (type === 'county') {
    intro = `${areaName} is a county spanning ${lsoaList(lsoaCodes, count)} across its constituent Local Authority Districts.`;
  } else if (type === 'place') {
    intro = `${areaName} is mapped to ${lsoaList(lsoaCodes, count)}.`;
  } else {
    return null;
  }

  return (
    <p className="mt-2 text-[11px] text-white/40 leading-relaxed">
      <span className="text-white/60">{intro}</span>{' '}{LSOA_SUFFIX}
    </p>
  );
}

export function ResultsHero() {
  const { areaName, parentName, savedCollections, toggleSave, sessionKey, resolved } = useResults();
  const [downloading, setDownloading] = useState(false);

  const handleDownload = useCallback(async () => {
    if (!sessionKey || downloading) return;
    setDownloading(true);
    try {
      const res = await fetch(`/api/v1/report?session_key=${encodeURIComponent(sessionKey)}`);
      if (!res.ok) throw new Error(`Report failed: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `PropertyPulse-${areaName.replace(/[^a-zA-Z0-9]/g, '_')}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('PDF download failed:', err);
    } finally {
      setDownloading(false);
    }
  }, [sessionKey, areaName, downloading]);

  return (
    <div className="bg-gradient-to-r from-brand-950 via-brand-900 to-brand-800 border-b border-brand-800/50">
      <div className="max-w-[1400px] mx-auto px-4 lg:px-6 py-5 lg:py-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-white leading-tight">
              {areaName}
              {parentName && (
                <span className="text-base sm:text-lg lg:text-xl font-medium text-white/50">, {parentName}</span>
              )}
            </h1>
          </div>
          <div className="flex items-center gap-2 self-start">
            <button
              type="button"
              onClick={() => toggleSave('shortlist')}
              aria-label={savedCollections.shortlist ? 'Remove from shortlist' : 'Save to shortlist'}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold active:scale-95 transition-all backdrop-blur-sm border self-start ${
                savedCollections.shortlist
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-400/30'
                  : 'bg-white/10 text-white hover:bg-white/15 border-white/10'
              }`}
            >
              <Heart className={`w-4 h-4 ${savedCollections.shortlist ? 'fill-current' : ''}`} aria-hidden="true" />
              {savedCollections.shortlist ? 'Shortlisted' : 'Shortlist'}
            </button>
            <button
              type="button"
              onClick={() => toggleSave('watchlist')}
              aria-label={savedCollections.watchlist ? 'Remove from watchlist' : 'Save to watchlist'}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold active:scale-95 transition-all backdrop-blur-sm border self-start ${
                savedCollections.watchlist
                  ? 'bg-sky-500/20 text-sky-300 border-sky-400/30'
                  : 'bg-white/10 text-white hover:bg-white/15 border-white/10'
              }`}
            >
              <BellRing className={`w-4 h-4`} aria-hidden="true" />
              {savedCollections.watchlist ? 'Watching' : 'Watch'}
            </button>
            {sessionKey && (
              <button
                type="button"
                onClick={handleDownload}
                disabled={downloading}
                aria-label={`Download PDF report for ${areaName}`}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-white/10 text-white hover:bg-white/15 active:scale-95 transition-all backdrop-blur-sm border border-white/10 self-start disabled:opacity-60"
              >
                {downloading
                  ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                  : <FileDown className="w-4 h-4" aria-hidden="true" />
                }
                {downloading ? 'Generating…' : 'Download Report'}
              </button>
            )}
          </div>
        </div>
        {resolved && <LsoaContextBlurb resolved={resolved} areaName={areaName} />}
      </div>
    </div>
  );
}
