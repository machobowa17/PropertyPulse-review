import { useMemo } from 'react';
import type { Metric, PersonaId } from '../types';
import type { DecisionMode } from './DecisionModeSelector';
import { PERSONAS } from '../utils/personas';
import { buildPersonaFitSummary } from '../utils/personalization';

interface Props {
  metrics: Metric[];
  persona: PersonaId;
  decisionMode?: DecisionMode;
}

function CircularDial({ score, size = 80 }: { score: number; size?: number }) {
  const strokeWidth = 6;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const colour = score >= 70 ? '#059669' : score >= 45 ? '#d97706' : '#dc2626';

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-divider"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={colour}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-700 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="font-mono font-bold text-xl text-ink">{score}</span>
      </div>
    </div>
  );
}

export default function PersonaScoreCard({ metrics, persona, decisionMode = 'buy' }: Props) {
  const summary = useMemo(
    () => buildPersonaFitSummary(metrics, persona, decisionMode),
    [metrics, persona, decisionMode],
  );

  if (!summary || metrics.length === 0) return null;

  const personaLabel = PERSONAS.find((p) => p.id === persona)?.label || persona;

  return (
    <div className="rounded-2xl bg-white p-5 shadow-sm">
      <div className="flex items-center gap-5">
        <CircularDial score={summary.score} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="text-base font-bold text-ink">{summary.verdict}</h4>
          </div>
          <p className="text-sm text-ink-muted leading-relaxed">
            For a <span className="font-semibold text-ink">{personaLabel.toLowerCase()}</span>{' '}
            <span className="text-ink-faint">
              {decisionMode === 'rent' ? 'renting' : decisionMode === 'invest' ? 'investing' : 'buying'}
            </span>,
            this area scores {summary.score}/100 based on {summary.metricCount} weighted metrics.
          </p>
          <div className="flex items-center gap-3 mt-2 text-xs font-medium">
            {summary.greenCount > 0 && (
              <span className="flex items-center gap-1 text-signal-green">
                <span className="w-2 h-2 rounded-full bg-signal-green" />
                {summary.greenCount} positive
              </span>
            )}
            {summary.amberCount > 0 && (
              <span className="flex items-center gap-1 text-signal-amber">
                <span className="w-2 h-2 rounded-full bg-signal-amber" />
                {summary.amberCount} mixed
              </span>
            )}
            {summary.redCount > 0 && (
              <span className="flex items-center gap-1 text-signal-red">
                <span className="w-2 h-2 rounded-full bg-signal-red" />
                {summary.redCount} concern{summary.redCount !== 1 && 's'}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Top positives and concerns */}
      {(summary.positives.length > 0 || summary.concerns.length > 0) && (
        <div className="mt-4 pt-3 border-t border-divider/50 grid grid-cols-1 sm:grid-cols-2 gap-3">
          {summary.positives.length > 0 && (
            <div>
              <h5 className="text-[11px] font-semibold text-signal-green uppercase tracking-wide mb-1.5">Top strengths</h5>
              <ul className="space-y-1">
                {summary.positives.map((s) => (
                  <li key={s.id} className="text-xs text-ink-muted leading-relaxed">
                    <span className="font-medium text-ink">{s.name}</span>
                    {s.weight >= 3 && <span className="ml-1 text-[10px] text-signal-green">(critical)</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {summary.concerns.length > 0 && (
            <div>
              <h5 className="text-[11px] font-semibold text-signal-amber uppercase tracking-wide mb-1.5">Watch out for</h5>
              <ul className="space-y-1">
                {summary.concerns.map((s) => (
                  <li key={s.id} className="text-xs text-ink-muted leading-relaxed">
                    <span className="font-medium text-ink">{s.name}</span>
                    {s.colour === 'red' && <span className="ml-1 text-[10px] text-signal-red">(concern)</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
