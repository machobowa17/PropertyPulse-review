import { useMemo } from 'react';
import type { Metric, PersonaId } from '../types';
import { getTakeaway } from '../utils/personas';
import { PERSONAS } from '../utils/personas';

interface Props {
  metrics: Metric[];
  persona: PersonaId;
}

/** Weighted importance per metric per persona (higher = more important for that persona) */
const WEIGHTS: Record<string, Partial<Record<PersonaId, number>>> = {
  // Property
  avg_price: { family: 3, investor: 3, young_professional: 2, retired: 2, student: 1, expat: 2 },
  gross_yield: { investor: 3, family: 0, young_professional: 0, retired: 0, student: 0, expat: 0 },
  affordability: { young_professional: 3, student: 3, family: 2, investor: 1, retired: 1, expat: 2 },
  price_trend_yoy: { investor: 3, family: 2, young_professional: 1, retired: 1, student: 0, expat: 1 },
  // Lifestyle
  nearest_station: { young_professional: 3, student: 3, family: 2, retired: 1, investor: 1, expat: 2 },
  fifteen_min_score: { retired: 3, family: 2, young_professional: 2, student: 2, investor: 1, expat: 2 },
  broadband: { young_professional: 3, student: 2, family: 2, investor: 1, retired: 1, expat: 2 },
  // Environment
  crime_rate: { family: 3, retired: 3, young_professional: 2, student: 2, investor: 2, expat: 3 },
  air_quality_pm25: { family: 3, retired: 3, young_professional: 1, student: 1, investor: 0, expat: 2 },
  flood_risk: { family: 3, investor: 3, retired: 2, young_professional: 1, student: 1, expat: 2 },
  nearest_park: { family: 3, retired: 3, young_professional: 1, student: 1, investor: 0, expat: 2 },
  // Community
  primary_schools: { family: 3, expat: 3, young_professional: 0, investor: 0, retired: 0, student: 0 },
  secondary_schools: { family: 3, expat: 3, young_professional: 0, investor: 0, retired: 0, student: 0 },
  deprivation: { family: 3, retired: 2, young_professional: 1, investor: 2, student: 1, expat: 2 },
  nhs_facilities: { retired: 3, family: 2, young_professional: 1, student: 1, investor: 0, expat: 1 },
  // Governance
  council_tax: { investor: 2, family: 2, young_professional: 1, retired: 2, student: 1, expat: 1 },
  financial_health: { family: 2, investor: 2, retired: 2, young_professional: 1, student: 1, expat: 1 },
  epc_energy_score: { investor: 2, family: 2, young_professional: 1, retired: 1, student: 1, expat: 1 },
  epc_rating_c_plus: { investor: 2, family: 2, young_professional: 1, retired: 1, student: 1, expat: 1 },
};

const COLOUR_SCORE: Record<string, number> = {
  green: 100,
  amber: 50,
  red: 0,
  neutral: 50,
};

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

export default function PersonaScoreCard({ metrics, persona }: Props) {
  const { score, breakdown } = useMemo(() => {
    let totalWeight = 0;
    let totalScore = 0;
    const breakdown: { name: string; colour: string; weight: number }[] = [];

    for (const m of metrics) {
      const takeaway = getTakeaway(m, persona);
      const weight = WEIGHTS[m.id]?.[persona] ?? 1;
      if (weight === 0) continue;
      const pts = COLOUR_SCORE[takeaway.colour] ?? 50;
      totalWeight += weight;
      totalScore += pts * weight;
      breakdown.push({ name: m.name, colour: takeaway.colour, weight });
    }

    return {
      score: totalWeight > 0 ? Math.round(totalScore / totalWeight) : null,
      breakdown,
    };
  }, [metrics, persona]);

  if (score === null || metrics.length === 0) return null;

  const personaLabel = PERSONAS.find((p) => p.id === persona)?.label || persona;

  const greenCount = breakdown.filter(b => b.colour === 'green').length;
  const amberCount = breakdown.filter(b => b.colour === 'amber').length;
  const redCount = breakdown.filter(b => b.colour === 'red').length;

  const verdict = score >= 70 ? 'Strong fit' : score >= 45 ? 'Mixed signals' : 'Significant concerns';

  return (
    <div className="rounded-2xl bg-white p-5 shadow-sm">
      <div className="flex items-center gap-5">
        <CircularDial score={score} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="text-base font-bold text-ink">{verdict}</h4>
          </div>
          <p className="text-sm text-ink-muted leading-relaxed">
            For a <span className="font-semibold text-ink">{personaLabel.toLowerCase()}</span>,
            this area scores {score}/100 based on {breakdown.length} weighted metrics.
          </p>
          <div className="flex items-center gap-3 mt-2 text-xs font-medium">
            {greenCount > 0 && (
              <span className="flex items-center gap-1 text-signal-green">
                <span className="w-2 h-2 rounded-full bg-signal-green" />
                {greenCount} positive
              </span>
            )}
            {amberCount > 0 && (
              <span className="flex items-center gap-1 text-signal-amber">
                <span className="w-2 h-2 rounded-full bg-signal-amber" />
                {amberCount} mixed
              </span>
            )}
            {redCount > 0 && (
              <span className="flex items-center gap-1 text-signal-red">
                <span className="w-2 h-2 rounded-full bg-signal-red" />
                {redCount} concern{redCount !== 1 && 's'}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
