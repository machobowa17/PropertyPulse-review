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

  const scoreColour =
    score >= 70 ? 'text-signal-green' : score >= 45 ? 'text-signal-amber' : 'text-signal-red';
  const scoreBg =
    score >= 70 ? 'bg-signal-green-bg' : score >= 45 ? 'bg-signal-amber-bg' : 'bg-signal-red-bg';

  return (
    <div className={`rounded-2xl p-4 border border-divider shadow-sm ${scoreBg} space-y-2`}>
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-semibold text-ink">Persona Verdict</h4>
          <p className="text-xs text-ink-muted">{personaLabel} suitability</p>
        </div>
        <div className="text-right">
          <div className={`text-3xl font-extrabold ${scoreColour}`}>{score}</div>
          <div className="text-[10px] text-ink-faint">/ 100</div>
        </div>
      </div>
      <div className="flex gap-0.5 h-2 rounded-full overflow-hidden bg-white/50">
        {breakdown.map((b, i) => (
          <div
            key={i}
            className={`h-full ${
              b.colour === 'green'
                ? 'bg-signal-green'
                : b.colour === 'amber'
                ? 'bg-signal-amber'
                : b.colour === 'red'
                ? 'bg-signal-red'
                : 'bg-ink-faint'
            }`}
            style={{ flex: b.weight }}
            title={`${b.name}: ${b.colour}`}
          />
        ))}
      </div>
      <div className="text-[10px] text-ink-muted">
        Based on {breakdown.length} metrics weighted for {personaLabel.toLowerCase()}
      </div>
    </div>
  );
}
