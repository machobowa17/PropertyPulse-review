import { useState, useCallback } from 'react';
import { Car, Train, Bike, Footprints, Loader2 } from 'lucide-react';
import { fetchCommute } from '../api/client';
import type { CommuteResult } from '../api/client';

interface Props {
  sessionKey: string;
  originLabel: string;
}

const MODE_META: Record<string, { Icon: React.ElementType; colour: string }> = {
  driving: { Icon: Car,        colour: '#2563eb' },
  transit: { Icon: Train,      colour: '#7c3aed' },
  cycling: { Icon: Bike,       colour: '#059669' },
  walking: { Icon: Footprints, colour: '#b45309' },
};

export default function CommuteEstimator({ sessionKey, originLabel }: Props) {
  const [dest, setDest] = useState('');
  const [result, setResult] = useState<CommuteResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const estimate = useCallback(async () => {
    if (!dest.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await fetchCommute(sessionKey, dest.trim());
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not resolve destination');
    } finally {
      setLoading(false);
    }
  }, [dest, sessionKey]);

  return (
    <div className="bg-surface rounded-xl p-4 space-y-3 mt-2">
      <div>
        <h4 className="text-sm font-semibold text-ink">Commute Estimator</h4>
        <p className="text-xs text-ink-muted mt-0.5">From {originLabel}</p>
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={dest}
          onChange={(e) => setDest(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && estimate()}
          placeholder="Destination postcode or place..."
          className="flex-1 h-9 px-3 rounded-lg border border-divider bg-white text-sm text-ink focus:outline-none focus:border-brand-500"
        />
        <button
          onClick={estimate}
          disabled={loading || !dest.trim()}
          className="h-9 px-4 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50 transition-colors flex items-center gap-1.5"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Go'}
        </button>
      </div>

      {error && <p className="text-xs text-signal-red">{error}</p>}

      {result && (
        <div className="space-y-2">
          <div className="text-xs text-ink-muted">
            To <span className="font-semibold text-ink">{result.destination}</span>
            {' '}— {result.straight_km} km straight-line
          </div>

          <div className="grid grid-cols-4 gap-2">
            {(['driving', 'transit', 'cycling', 'walking'] as const).map((key) => {
              const mode = result.modes[key];
              const { Icon, colour } = MODE_META[key];
              return (
                <div key={key} className="bg-white rounded-xl border border-divider p-3 flex flex-col items-center gap-1">
                  <Icon className="w-4 h-4" style={{ color: colour }} />
                  <div className="text-sm font-bold text-ink leading-tight">{mode.label}</div>
                  <div className="text-[10px] text-ink-faint">{mode.mode}</div>
                  <div className="text-[10px] text-ink-faint">{mode.route_km} km</div>
                </div>
              );
            })}
          </div>

          <p className="text-[10px] text-ink-faint">
            Estimates: driving ~50 km/h, transit ~30 km/h (+10 min wait), cycling ~18 km/h, walking ~5 km/h.
            Straight-line × route factor applied per mode.
          </p>
        </div>
      )}
    </div>
  );
}
