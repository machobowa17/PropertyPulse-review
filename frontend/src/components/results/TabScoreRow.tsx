/**
 * TabScoreRow — 5 clickable mini-cards, one per data tab.
 * Shows persona-weighted fit score per tab. Click navigates to that tab.
 */
import {
  Home, Coffee, TreePine, Users, Landmark,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { Metric, PersonaId, TabName } from '../../types';
import type { DecisionMode } from '../DecisionModeSelector';
import { rankSectionsForPersona } from '../../utils/personalization';
import { TABS } from '../../utils/tabs';

interface Props {
  metrics: Metric[];
  persona: PersonaId;
  decisionMode: DecisionMode;
  onTabClick: (tab: TabName) => void;
}

const TAB_ICONS: Record<string, LucideIcon> = {
  'Property & Market': Home,
  'Lifestyle & Connectivity': Coffee,
  'Environment & Safety': TreePine,
  'Community & Education': Users,
  'Local Governance': Landmark,
};

const DATA_TABS: TabName[] = [
  'Property & Market',
  'Lifestyle & Connectivity',
  'Environment & Safety',
  'Community & Education',
  'Local Governance',
];

function scoreColor(score: number): string {
  if (score >= 70) return 'text-emerald-700 bg-emerald-50 border-emerald-200';
  if (score >= 45) return 'text-amber-700 bg-amber-50 border-amber-200';
  return 'text-red-700 bg-red-50 border-red-200';
}

function scoreVerdict(score: number): string {
  if (score >= 70) return 'Strong';
  if (score >= 45) return 'Mixed';
  return 'Weak';
}

export default function TabScoreRow({ metrics, persona, decisionMode, onTabClick }: Props) {
  const ranked = rankSectionsForPersona(metrics, persona, decisionMode);
  if (ranked.length === 0) return null;

  const scoreMap = new Map(ranked.map(r => [r.section, r]));

  return (
    <div className="rounded-2xl border border-divider bg-white overflow-hidden shadow-sm">
      <div className="px-5 py-3 border-b border-divider/50">
        <h3 className="text-sm font-semibold text-ink">Tab Scores</h3>
        <p className="text-[11px] text-ink-faint mt-0.5">Persona-weighted fit score per tab — click to explore</p>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 p-3">
        {DATA_TABS.map(tab => {
          const Icon = TAB_ICONS[tab] || Home;
          const tabConfig = TABS.find(t => t.name === tab);
          const section = scoreMap.get(tab);
          const score = section?.score ?? 50;
          const shortName = tabConfig?.shortName || tab.split(' ')[0];

          return (
            <button
              key={tab}
              onClick={() => onTabClick(tab)}
              className="rounded-xl border border-divider bg-surface-warm/30 px-3 py-2.5 text-left hover:bg-surface-warm transition-colors cursor-pointer group"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <Icon size={14} className="text-ink-muted group-hover:text-ink transition-colors" />
                <span className="text-xs font-medium text-ink truncate">{shortName}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold text-ink tabular-nums">{score}</span>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${scoreColor(score)}`}>
                  {scoreVerdict(score)}
                </span>
              </div>
              {section && section.strengths.length > 0 && (
                <p className="text-[10px] text-ink-faint mt-1 line-clamp-1">
                  {section.strengths[0].name}
                </p>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
