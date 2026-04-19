import {
  Users, Clock, Heart, Briefcase, GraduationCap, Car, Users2,
} from 'lucide-react';

interface StatCard {
  label: string;
  value: number | null;
  unit: string;
  parent?: number | null;
}

interface Props {
  cards: Record<string, StatCard>;
}

const CARD_ICONS: Record<string, React.ElementType> = {
  population_density: Users,
  median_age:         Clock,
  pct_families:       Users2,
  good_health:        Heart,
  employed:           Briefcase,
  degree:             GraduationCap,
  no_car:             Car,
};

const CARD_ORDER = [
  'population_density', 'median_age', 'pct_families',
  'good_health', 'employed', 'degree', 'no_car',
];

function formatVal(value: number | null, unit: string): string {
  if (value == null) return '—';
  if (unit === 'ppl/ha') return value.toFixed(1);
  if (unit === 'yrs') return Math.round(value).toString();
  if (unit === '%') return value.toFixed(1) + '%';
  return value.toLocaleString('en-GB');
}

export default function DemographicsCards({ cards }: Props) {
  const ordered = CARD_ORDER.filter((k) => k in cards);
  const extra = Object.keys(cards).filter((k) => !CARD_ORDER.includes(k));
  const allKeys = [...ordered, ...extra];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2">
      {allKeys.map((key) => {
        const card = cards[key];
        const Icon = CARD_ICONS[key] ?? Users;

        return (
          <div key={key} className="bg-white rounded-xl border border-divider p-3 flex flex-col gap-1.5">
            <div className="flex items-center gap-1.5">
              <Icon className="w-3.5 h-3.5 text-ink-faint shrink-0" />
              <span className="text-[10px] text-ink-faint uppercase tracking-wide font-medium leading-tight truncate">
                {card.label}
              </span>
            </div>
            <div className="text-xl font-bold text-ink leading-none">
              {formatVal(card.value, card.unit)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
