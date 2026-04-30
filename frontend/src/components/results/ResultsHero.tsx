import { useState, useCallback } from 'react';
import { Bookmark, FileDown, Loader2, MapPin, X } from 'lucide-react';
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
  const { areaName, parentName, isSaved, toggleSave, sessionKey, resolved, selectedProperty, clearProperty } = useResults();
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const handleDownload = useCallback(async () => {
    if (!sessionKey || downloading) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      const res = await fetch(`/api/v1/report?session_key=${encodeURIComponent(sessionKey)}`);
      if (!res.ok) throw new Error(`Report generation failed (${res.status}). Please try again.`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `PropertyPulse-${areaName.replace(/[^a-zA-Z0-9]/g, '_')}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Report download failed. Please try again.';
      setDownloadError(message);
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
            {selectedProperty && (
              <div className="mt-1.5 flex items-center gap-2">
                <MapPin className="w-3.5 h-3.5 text-blue-300 shrink-0" />
                <span className="text-sm text-blue-200 font-medium">
                  {selectedProperty.addressDisplay || [selectedProperty.paon, selectedProperty.street, selectedProperty.postcode].filter(Boolean).join(', ')}
                </span>
                <button
                  onClick={clearProperty}
                  className="ml-1 p-0.5 rounded hover:bg-white/10 transition-colors"
                  title="Dismiss property"
                >
                  <X className="w-3.5 h-3.5 text-white/50 hover:text-white/80" />
                </button>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 self-start">
            <button
              type="button"
              onClick={toggleSave}
              aria-label={isSaved ? 'Remove from saved areas' : 'Save this area'}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold active:scale-95 transition-all backdrop-blur-sm border self-start ${
                isSaved
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-400/30'
                  : 'bg-white/10 text-white hover:bg-white/15 border-white/10'
              }`}
            >
              <Bookmark className={`w-4 h-4 ${isSaved ? 'fill-current' : ''}`} aria-hidden="true" />
              {isSaved ? 'Saved' : 'Save'}
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
        {downloadError && (
          <div className="mt-2 flex items-center gap-2 rounded-lg bg-red-500/15 border border-red-400/20 px-3 py-2 text-sm text-red-200">
            <span>{downloadError}</span>
            <button type="button" onClick={() => setDownloadError(null)} className="ml-auto text-red-300 hover:text-white text-xs font-semibold">Dismiss</button>
          </div>
        )}
        {resolved && <LsoaContextBlurb resolved={resolved} areaName={areaName} />}
      </div>
    </div>
  );
}
