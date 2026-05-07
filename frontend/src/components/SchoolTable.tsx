import { Fragment, useState, useCallback, useMemo, useEffect, useRef } from 'react';
import {
  GraduationCap, School, ChevronRight, ChevronDown,
  MapPin, Globe, Phone, Building, Footprints,
  ExternalLink, TrendingUp, TrendingDown, Minus,
  Users, BookOpen, Shield, Loader2, AlertCircle,
  Heart, BarChart3, ClipboardList, PoundSterling,
  FileText, Eye,
} from 'lucide-react';
import { useResultsData } from '../context/ResultsContext';
import { useResults } from '../context/ResultsContext';

/* ── List-level row (from nearby/by-lsoa endpoint) ── */
export interface SchoolRow {
  urn: number;
  name: string;
  type_code?: string | null;
  phase?: string | null;
  gender?: string | null;
  religious_char?: string | null;
  age_low?: number | null;
  age_high?: number | null;
  capacity?: number | null;
  pupil_count?: number | null;
  postcode?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  la_name?: string | null;
  lad_code?: string | null;
  website?: string | null;
  phone?: string | null;
  admissions_policy?: string | null;
  boarding?: string | null;
  nursery_provision?: string | null;
  sixth_form?: string | null;
  distance_m?: number | null;
  ofsted_rating?: number | null;
  ofsted_date?: string | null;
  quality_of_education?: number | null;
  behaviour_attitudes?: number | null;
  personal_development?: number | null;
  leadership_management?: number | null;
  ks2_rwm_expected?: number | null;
  ks2_reading_progress?: number | null;
  ks2_maths_progress?: number | null;
  ks2_writing_progress?: number | null;
  ks2_reading_score?: number | null;
  ks2_maths_score?: number | null;
  attainment_8?: number | null;
  progress_8?: number | null;
  ks4_basics_5?: number | null;
  ks5_a_level_score?: number | null;
  pct_fsm?: number | null;
  pct_eal?: number | null;
  dem_total_pupils?: number | null;
  pupil_teacher_ratio?: number | null;
  overall_absence_pct?: number | null;
  persistent_absence_pct?: number | null;
  adm_applications?: number | null;
  adm_offers?: number | null;
  is_oversubscribed?: boolean | null;
  per_pupil_expenditure?: number | null;
  pct_budget_staff?: number | null;
  // LA admissions detail (scraped from booklets)
  la_ldo?: number | null;
  la_ldo_unit?: string | null;
  la_sif?: boolean | null;
  la_allocation?: Record<string, number> | null;
  velocity?: 'rising' | 'stable' | 'declining' | null;
  quality_flags?: string[];
}

/* ── Detail response (from /school-detail?urn=) ── */
interface Inspection {
  overall_rating?: number | null;
  rating_text?: string | null;
  inspection_date?: string | null;
  inspection_body?: string | null;
  category?: string | null;
  report_url?: string | null;
  previous_rating?: number | null;
  quality_of_education?: number | null;
  behaviour_attitudes?: number | null;
  personal_development?: number | null;
  leadership_management?: number | null;
  early_years?: number | null;
  sixth_form?: number | null;
  safeguarding?: boolean | null;
}
interface KS2Year {
  academic_year?: string;
  pct_rwm_expected?: number | null;
  pct_rwm_higher?: number | null;
  pct_reading_expected?: number | null;
  pct_maths_expected?: number | null;
  pct_writing_expected?: number | null;
  reading_scaled_score?: number | null;
  maths_scaled_score?: number | null;
  reading_progress?: number | null;
  writing_progress?: number | null;
  maths_progress?: number | null;
}
interface KS4Year {
  academic_year?: string;
  attainment_8?: number | null;
  progress_8?: number | null;
  progress_8_lower_ci?: number | null;
  progress_8_upper_ci?: number | null;
  pct_grade_5_em?: number | null;
  pct_grade_4_em?: number | null;
  pct_entering_ebacc?: number | null;
}
interface KS5Year {
  academic_year?: string;
  avg_point_score_a?: number | null;
  avg_point_score_academic?: number | null;
  avg_point_score_applied?: number | null;
}
interface DemYear {
  academic_year?: string;
  total_pupils?: number | null;
  pct_boys?: number | null;
  pct_girls?: number | null;
  pct_fsm?: number | null;
  pct_eal?: number | null;
  pct_sen_support?: number | null;
  pct_sen_ehcp?: number | null;
  pct_white_british?: number | null;
  pct_asian?: number | null;
  pct_black?: number | null;
  pct_mixed?: number | null;
  pct_chinese?: number | null;
  pct_other_ethnic?: number | null;
}
interface WorkforceYear {
  academic_year?: string;
  total_teachers_fte?: number | null;
  total_ta_fte?: number | null;
  total_support_fte?: number | null;
  pupil_teacher_ratio?: number | null;
  mean_salary_teachers?: number | null;
  pct_teachers_qualified?: number | null;
  teacher_turnover_pct?: number | null;
}
interface AdmYear {
  academic_year?: string;
  year_group?: string | null;
  applications_received?: number | null;
  first_preference?: number | null;
  second_preference?: number | null;
  third_preference?: number | null;
  offers_made?: number | null;
  is_oversubscribed?: boolean | null;
  last_distance_offered?: number | null;
}
interface AdmLaDetail {
  academic_year?: string;
  year_group?: string | null;
  last_distance_offered?: number | null;
  ldo_unit?: string | null;
  ldo_detail?: Record<string, number> | null;
  distance_method?: string | null;
  allocation_breakdown?: Record<string, number> | null;
  oversubscription_criteria?: string[] | null;
  sif_required?: boolean | null;
  open_days?: Array<{ date?: string; time?: string; type?: string }> | null;
  appeals_heard?: number | null;
  appeals_upheld?: number | null;
  waiting_list_size?: number | null;
  source_confidence?: string | null;
  data_quality_flags?: Array<{ flag: string; detail?: string }> | null;
}
interface AbsYear {
  academic_year?: string;
  overall_absence_pct?: number | null;
  authorised_absence_pct?: number | null;
  unauthorised_absence_pct?: number | null;
  persistent_absence_pct?: number | null;
  severe_absence_pct?: number | null;
}
interface FinYear {
  academic_year?: string;
  total_income?: number | null;
  total_expenditure?: number | null;
  per_pupil_expenditure?: number | null;
  staff_expenditure?: number | null;
  in_year_balance?: number | null;
  revenue_reserves?: number | null;
  pct_budget_staff?: number | null;
}
interface DestYear {
  academic_year?: string;
  destination_level?: string | null;
  pct_education_employment?: number | null;
  pct_further_education?: number | null;
  pct_higher_education?: number | null;
  pct_apprenticeships?: number | null;
  pct_employment?: number | null;
  pct_not_sustained?: number | null;
}
interface SubjectRow {
  academic_year?: string;
  key_stage?: string | null;
  subject_name?: string | null;
  entries?: number | null;
  pct_grade_9?: number | null;
  pct_grade_a_star?: number | null;
  pct_grade_a?: number | null;
  avg_point_score?: number | null;
}
interface ParentViewYear {
  academic_year?: string;
  total_responses?: number | null;
  happy_at_school?: number | null;
  feels_safe?: number | null;
  good_behaviour?: number | null;
  tackled_bullying?: number | null;
  challenging_work?: number | null;
  well_taught?: number | null;
  good_communication?: number | null;
  wide_curriculum?: number | null;
  would_recommend?: number | null;
  well_looked_after?: number | null;
  supported_sen?: number | null;
  good_leadership?: number | null;
}
interface SenProvision {
  provision_type?: string | null;
  sen_specialisms?: string | null;
  capacity?: number | null;
}
interface SchoolDetailData {
  headteacher?: string | null;
  address?: string | null;
  is_open?: boolean | null;
  updated_at?: string | null;
  inspections?: Inspection[];
  ks2_results?: KS2Year[];
  ks4_results?: KS4Year[];
  ks5_results?: KS5Year[];
  demographics?: DemYear[];
  workforce?: WorkforceYear[];
  admissions?: AdmYear[];
  admissions_la_detail?: AdmLaDetail[];
  absence?: AbsYear[];
  finances?: FinYear[];
  destinations?: DestYear[];
  subjects?: SubjectRow[];
  parent_view?: ParentViewYear[];
  sen_provisions?: SenProvision[];
  velocity?: string | null;
  quality_flags?: string[];
}

export interface QualitySummary {
  total_schools?: number;
  primary_count?: number;
  secondary_count?: number;
  allthrough_count?: number;
  post16_count?: number;
  outstanding?: number;
  good?: number;
  requires_improvement?: number;
  inadequate?: number;
  not_inspected?: number;
  avg_rating?: number | null;
}

interface Props {
  schools: SchoolRow[];
  summary?: QualitySummary | null;
  isArea?: boolean;
}

const PHASES = [
  { key: 'all', label: 'All' },
  { key: 'Primary', label: 'Primary' },
  { key: 'Secondary', label: 'Secondary' },
  { key: 'All-through', label: 'All-through' },
  { key: '16 plus', label: '16+' },
] as const;

const SORT_OPTIONS = [
  { key: 'distance', label: 'Distance' },
  { key: 'ofsted', label: 'Ofsted Rating' },
  { key: 'progress', label: 'Progress Score' },
  { key: 'attainment', label: 'Attainment' },
  { key: 'fsm', label: 'FSM %' },
  { key: 'name', label: 'Name' },
] as const;

const OFSTED_COLORS: Record<number, { bg: string; text: string; label: string }> = {
  1: { bg: 'bg-emerald-100', text: 'text-emerald-800', label: 'Outstanding' },
  2: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Good' },
  3: { bg: 'bg-amber-100', text: 'text-amber-800', label: 'Requires Improvement' },
  4: { bg: 'bg-red-100', text: 'text-red-800', label: 'Inadequate' },
};

type DetailTab = 'overview' | 'results' | 'inspections' | 'demographics' | 'admissions' | 'finances' | 'walk';

const DETAIL_TABS: { key: DetailTab; label: string; icon: typeof BookOpen }[] = [
  { key: 'overview', label: 'Overview', icon: Building },
  { key: 'results', label: 'Results', icon: BookOpen },
  { key: 'inspections', label: 'Ofsted', icon: Shield },
  { key: 'demographics', label: 'Demographics', icon: Users },
  { key: 'admissions', label: 'Admissions', icon: ClipboardList },
  { key: 'finances', label: 'Finances', icon: PoundSterling },
  { key: 'walk', label: 'Walk', icon: Footprints },
];

/* ── Shared UI atoms ── */

function DataNote({ notes }: { notes: string[] }) {
  if (!notes.length) return null;
  return (
    <div className="mt-3 pt-2 border-t border-border-base/40 space-y-0.5">
      {notes.map((note, i) => (
        <p key={i} className="text-[10px] text-ink-faint leading-snug">
          <span className="font-medium">Note:</span> {note}
        </p>
      ))}
    </div>
  );
}

function OfstedBadge({ rating }: { rating: number | null }) {
  if (!rating) return <span className="text-xs text-ink-faint">Not inspected</span>;
  const info = OFSTED_COLORS[rating];
  if (!info) return null;
  return (
    <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium ${info.bg} ${info.text}`}>
      {info.label}
    </span>
  );
}

function SubJudgement({ label, rating }: { label: string; rating: number | null | undefined }) {
  if (rating == null) return null;
  const info = OFSTED_COLORS[rating];
  if (!info) return null;
  return (
    <div className="flex items-center justify-between text-xs py-0.5">
      <span className="text-ink-muted">{label}</span>
      <span className={`px-1.5 py-0.5 rounded ${info.bg} ${info.text} font-medium`}>
        {info.label}
      </span>
    </div>
  );
}

function StatRow({ label, value, suffix }: { label: string; value: number | string | null | undefined; suffix?: string }) {
  if (value == null) return null;
  return (
    <div className="flex justify-between text-xs py-0.5">
      <span className="text-ink-muted">{label}</span>
      <span className="font-medium text-ink-base">{typeof value === 'number' ? value.toLocaleString() : value}{suffix}</span>
    </div>
  );
}

function PercentBar({ label, value, color = 'bg-brand-primary' }: { label: string; value: number | null | undefined; color?: string }) {
  if (value == null) return null;
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-xs">
        <span className="text-ink-muted">{label}</span>
        <span className="font-medium">{value.toFixed(1)}%</span>
      </div>
      <div className="h-1.5 bg-surface-tertiary rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
    </div>
  );
}

const VELOCITY_STYLES = {
  rising:    { bg: 'bg-emerald-100', text: 'text-emerald-700', icon: TrendingUp,   label: 'Rising' },
  stable:    { bg: 'bg-slate-100',   text: 'text-slate-600',   icon: Minus,        label: 'Stable' },
  declining: { bg: 'bg-red-100',     text: 'text-red-700',     icon: TrendingDown, label: 'Declining' },
} as const;

function VelocityBadge({ velocity }: { velocity: SchoolRow['velocity'] }) {
  if (!velocity) return null;
  const style = VELOCITY_STYLES[velocity];
  const Icon = style.icon;
  return (
    <span className={`inline-flex items-center gap-0.5 px-1 py-0 rounded text-[10px] font-medium ${style.bg} ${style.text}`}>
      <Icon className="w-2.5 h-2.5" />
      {style.label}
    </span>
  );
}

function KeyMetric({ school }: { school: SchoolRow }) {
  const phase = school.phase;
  if (phase === 'Primary' && school.ks2_rwm_expected != null) {
    return (
      <span className="text-xs text-ink-muted whitespace-nowrap">
        <span className="font-medium text-ink-base">{Math.round(school.ks2_rwm_expected)}%</span> RWM
      </span>
    );
  }
  if ((phase === 'Secondary' || phase === 'All-through') && school.progress_8 != null) {
    const p8 = school.progress_8;
    const color = p8 > 0.5 ? 'text-emerald-600' : p8 < -0.5 ? 'text-red-600' : 'text-ink-base';
    return (
      <span className="text-xs whitespace-nowrap">
        <span className={`font-medium ${color}`}>{p8 > 0 ? '+' : ''}{p8.toFixed(2)}</span>
        <span className="text-ink-muted ml-0.5">P8</span>
      </span>
    );
  }
  if (school.ks5_a_level_score != null) {
    return (
      <span className="text-xs text-ink-muted whitespace-nowrap">
        <span className="font-medium text-ink-base">{school.ks5_a_level_score.toFixed(1)}</span> APS
      </span>
    );
  }
  return null;
}

/** Format year for display: "2023-24" → "23/24" */
function shortYear(y?: string) {
  if (!y) return '';
  const m = y.match(/^(\d{4})-(\d{2,4})$/);
  if (m) return `${m[1].slice(2)}/${m[2].slice(-2)}`;
  return y;
}

function fmtGBP(v: number | null | undefined) {
  if (v == null) return '—';
  if (Math.abs(v) >= 1_000_000) return `£${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `£${(v / 1_000).toFixed(0)}K`;
  return `£${v.toLocaleString()}`;
}

function fmtPct(v: number | null | undefined) {
  if (v == null) return '—';
  return `${Math.round(v)}%`;
}

function fmtProgress(v: number | null | undefined) {
  if (v == null) return '—';
  return (v > 0 ? '+' : '') + v.toFixed(1);
}

/* ── Detail tabs (use multi-year data from detail endpoint) ── */

function OverviewTab({ school, detail }: { school: SchoolRow; detail: SchoolDetailData | null }) {
  return (
    <div className="space-y-2">
      {/* Closed school warning */}
      {detail?.is_open === false && (
        <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          This school is permanently closed.
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-ink-faint">Type</span>
          <p className="font-medium text-ink-base">{school.type_code}</p>
        </div>
        <div>
          <span className="text-ink-faint">Phase</span>
          <p className="font-medium text-ink-base">{school.phase}</p>
        </div>
        {school.gender && (
          <div>
            <span className="text-ink-faint">Gender</span>
            <p className="font-medium text-ink-base">{school.gender}</p>
          </div>
        )}
        {school.religious_char && school.religious_char !== 'None' && school.religious_char !== 'Does not apply' && (
          <div>
            <span className="text-ink-faint">Faith</span>
            <p className="font-medium text-ink-base">{school.religious_char}</p>
          </div>
        )}
        {(school.age_low != null && school.age_high != null) && (
          <div>
            <span className="text-ink-faint">Age Range</span>
            <p className="font-medium text-ink-base">{school.age_low}–{school.age_high}</p>
          </div>
        )}
        {(school.pupil_count != null || school.capacity != null) && (
          <div>
            <span className="text-ink-faint">Pupils</span>
            <p className="font-medium text-ink-base">
              {school.pupil_count?.toLocaleString() ?? '—'}
              {school.capacity != null && ` / ${school.capacity.toLocaleString()}`}
              {school.pupil_count != null && school.capacity != null && school.capacity > 0 && (
                <span className="text-ink-faint ml-1">
                  ({Math.round(school.pupil_count / school.capacity * 100)}%)
                </span>
              )}
            </p>
          </div>
        )}
        {school.admissions_policy && school.admissions_policy !== 'Not applicable' && (
          <div>
            <span className="text-ink-faint">Admissions</span>
            <p className="font-medium text-ink-base">{school.admissions_policy}</p>
          </div>
        )}
        {school.pupil_teacher_ratio != null && (
          <div>
            <span className="text-ink-faint">Pupil:Teacher</span>
            <p className="font-medium text-ink-base">{school.pupil_teacher_ratio.toFixed(1)}:1</p>
          </div>
        )}
        {detail?.headteacher && (
          <div>
            <span className="text-ink-faint">Headteacher</span>
            <p className="font-medium text-ink-base">{detail.headteacher}</p>
          </div>
        )}
        {school.la_name && (
          <div>
            <span className="text-ink-faint">Local Authority</span>
            <p className="font-medium text-ink-base">{school.la_name}</p>
          </div>
        )}
        {school.sixth_form && school.sixth_form !== 'Not applicable' && school.sixth_form !== 'Does not have a sixth form' && (
          <div>
            <span className="text-ink-faint">Sixth Form</span>
            <p className="font-medium text-ink-base">{school.sixth_form}</p>
          </div>
        )}
        {school.boarding && school.boarding !== 'No boarders' && school.boarding !== 'Not applicable' && (
          <div>
            <span className="text-ink-faint">Boarding</span>
            <p className="font-medium text-ink-base">{school.boarding}</p>
          </div>
        )}
        {school.nursery_provision && school.nursery_provision !== 'No Nursery Classes' && school.nursery_provision !== 'Not applicable' && (
          <div>
            <span className="text-ink-faint">Nursery</span>
            <p className="font-medium text-ink-base">{school.nursery_provision}</p>
          </div>
        )}
      </div>

      {/* Parent View summary (if available) */}
      {detail?.parent_view && detail.parent_view.length > 0 && (() => {
        const pv = detail.parent_view[0];
        return (
          <div className="pt-1 border-t border-border-base/50 space-y-1.5">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-ink-base flex items-center gap-1">
                <Eye className="w-3 h-3" /> Parent View
              </p>
              {pv.total_responses != null && (
                <span className="text-[10px] text-ink-faint">{pv.total_responses} responses</span>
              )}
            </div>
            <div className="space-y-1">
              {pv.would_recommend != null && <PercentBar label="Would recommend" value={pv.would_recommend} color="bg-emerald-500" />}
              {pv.happy_at_school != null && <PercentBar label="Happy at school" value={pv.happy_at_school} color="bg-blue-500" />}
              {pv.feels_safe != null && <PercentBar label="Feels safe" value={pv.feels_safe} color="bg-sky-500" />}
              {pv.well_taught != null && <PercentBar label="Well taught" value={pv.well_taught} color="bg-indigo-500" />}
              {pv.good_behaviour != null && <PercentBar label="Good behaviour" value={pv.good_behaviour} color="bg-teal-500" />}
              {pv.tackled_bullying != null && <PercentBar label="Tackles bullying" value={pv.tackled_bullying} color="bg-violet-500" />}
              {pv.good_leadership != null && <PercentBar label="Good leadership" value={pv.good_leadership} color="bg-purple-500" />}
              {pv.wide_curriculum != null && <PercentBar label="Wide curriculum" value={pv.wide_curriculum} color="bg-cyan-500" />}
              {pv.good_communication != null && <PercentBar label="Good communication" value={pv.good_communication} color="bg-amber-500" />}
              {pv.well_looked_after != null && <PercentBar label="Well looked after" value={pv.well_looked_after} color="bg-rose-500" />}
              {pv.supported_sen != null && <PercentBar label="SEN support" value={pv.supported_sen} color="bg-fuchsia-500" />}
              {pv.challenging_work != null && <PercentBar label="Challenging work" value={pv.challenging_work} color="bg-orange-500" />}
            </div>
            {pv.academic_year && (
              <p className="text-[10px] text-ink-faint">Source: Ofsted Parent View {shortYear(pv.academic_year)}</p>
            )}
          </div>
        );
      })()}

      {/* Contact + address */}
      <div className="flex flex-wrap gap-2 pt-1 border-t border-border-base/50">
        {school.website && (
          <a
            href={school.website.startsWith('http') ? school.website : `https://${school.website}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-brand-primary hover:underline"
          >
            <Globe className="w-3 h-3" /> Website <ExternalLink className="w-2.5 h-2.5" />
          </a>
        )}
        {school.phone && (
          <a href={`tel:${school.phone}`} className="inline-flex items-center gap-1 text-xs text-ink-muted hover:text-ink-base">
            <Phone className="w-3 h-3" /> {school.phone}
          </a>
        )}
        <span className="inline-flex items-center gap-1 text-xs text-ink-muted">
          <MapPin className="w-3 h-3" /> {detail?.address ? `${detail.address}, ${school.postcode}` : school.postcode}
        </span>
      </div>

      {/* Data freshness */}
      {detail?.updated_at && (
        <p className="text-[10px] text-ink-faint">
          Last updated: {new Date(detail.updated_at).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })}
        </p>
      )}
      {detail && (!detail.parent_view || detail.parent_view.length === 0) && (
        <DataNote notes={['Ofsted Parent View data not available. Ofsted suppresses results for schools with fewer than 10 parent responses. Very small schools or recently opened schools may not have sufficient responses to publish.']} />
      )}
    </div>
  );
}

function ResultsTab({ school, detail }: { school: SchoolRow; detail: SchoolDetailData | null }) {
  const ks2 = detail?.ks2_results ?? [];
  const ks4 = detail?.ks4_results ?? [];
  const ks5 = detail?.ks5_results ?? [];
  const subjects = detail?.subjects ?? [];
  const destinations = detail?.destinations ?? [];

  const hasKs2 = ks2.length > 0 || (school.phase === 'Primary' && school.ks2_rwm_expected != null);
  const hasKs4 = ks4.length > 0 || ((school.phase === 'Secondary' || school.phase === 'All-through') && (school.attainment_8 != null || school.progress_8 != null));
  const hasKs5 = ks5.length > 0 || school.ks5_a_level_score != null;
  const hasSubjects = subjects.length > 0;
  const hasDest = destinations.length > 0;

  if (!hasKs2 && !hasKs4 && !hasKs5 && !hasSubjects && !hasDest) {
    const isPhaseExpected = school.phase === 'Primary' || school.phase === 'Secondary' || school.phase === 'All-through';
    const notes: string[] = [];
    if (isPhaseExpected) notes.push('Results data is published annually by the DfE. Newly opened or converted schools may not have a complete cohort yet — results typically appear 1–2 years after a school opens.');
    else notes.push('Exam results are not published for this school type. Special schools, PRUs, and alternative provision providers are not included in the DfE performance tables.');
    if (school.phase === 'Primary') notes.push('KS2 SATs are only published for schools with a Year 6 cohort. Infant schools (ages 4–7) and junior schools (ages 7–11) without KS2 results are not included.');
    return (
      <div>
        <p className="text-xs text-ink-faint py-2">No exam results available for this school.</p>
        <DataNote notes={notes} />
      </div>
    );
  }

  const vel = detail?.velocity ?? school.velocity;

  return (
    <div className="space-y-3">
      {vel && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-ink-faint">Academic Trend:</span>
          <VelocityBadge velocity={vel as SchoolRow['velocity']} />
        </div>
      )}

      {/* Multi-year KS2 */}
      {hasKs2 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-ink-base">KS2 Results (Year 6)</p>
          {ks2.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b border-border-base/50">
                    <th className="text-left py-0.5 text-ink-faint font-medium">Year</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">RWM %</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">Higher</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">Reading</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">Maths</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">Writing</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">R Prog</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">M Prog</th>
                  </tr>
                </thead>
                <tbody>
                  {ks2.map((y, i) => (
                    <tr key={y.academic_year ?? i} className={i === 0 ? 'font-medium' : 'text-ink-muted'}>
                      <td className="py-0.5">{shortYear(y.academic_year)}</td>
                      <td className="text-right">{fmtPct(y.pct_rwm_expected)}</td>
                      <td className="text-right">{fmtPct(y.pct_rwm_higher)}</td>
                      <td className="text-right">{y.pct_reading_expected != null ? fmtPct(y.pct_reading_expected) : (y.reading_scaled_score ?? '—')}</td>
                      <td className="text-right">{y.pct_maths_expected != null ? fmtPct(y.pct_maths_expected) : (y.maths_scaled_score ?? '—')}</td>
                      <td className="text-right">{fmtPct(y.pct_writing_expected)}</td>
                      <td className="text-right">{fmtProgress(y.reading_progress)}</td>
                      <td className="text-right">{fmtProgress(y.maths_progress)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <StatRow label="Expected RWM" value={school.ks2_rwm_expected != null ? `${Math.round(school.ks2_rwm_expected)}%` : null} />
              <StatRow label="Reading Score" value={school.ks2_reading_score} />
              <StatRow label="Maths Score" value={school.ks2_maths_score} />
            </div>
          )}
        </div>
      )}

      {/* Multi-year KS4 */}
      {hasKs4 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-ink-base">GCSE Results</p>
          {ks4.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b border-border-base/50">
                    <th className="text-left py-0.5 text-ink-faint font-medium">Year</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">A8</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">P8</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">5+ E&M</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">4+ E&M</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">EBacc</th>
                  </tr>
                </thead>
                <tbody>
                  {ks4.map((y, i) => (
                    <tr key={y.academic_year ?? i} className={i === 0 ? 'font-medium' : 'text-ink-muted'}>
                      <td className="py-0.5">{shortYear(y.academic_year)}</td>
                      <td className="text-right">{y.attainment_8?.toFixed(1) ?? '—'}</td>
                      <td className="text-right" title={y.progress_8_lower_ci != null && y.progress_8_upper_ci != null ? `95% CI: ${y.progress_8_lower_ci.toFixed(2)} to ${y.progress_8_upper_ci.toFixed(2)}` : undefined}>
                        {y.progress_8 != null ? (y.progress_8 > 0 ? '+' : '') + y.progress_8.toFixed(2) : '—'}
                      </td>
                      <td className="text-right">{fmtPct(y.pct_grade_5_em)}</td>
                      <td className="text-right">{fmtPct(y.pct_grade_4_em)}</td>
                      <td className="text-right">{fmtPct(y.pct_entering_ebacc)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <StatRow label="Attainment 8" value={school.attainment_8?.toFixed(1)} />
              <StatRow label="5+ English & Maths" value={school.ks4_basics_5 != null ? `${Math.round(school.ks4_basics_5)}%` : null} />
            </div>
          )}
          {school.quality_flags?.includes('igcse_caveat') && (
            <p className="text-[10px] text-amber-600 leading-tight mt-1">
              Independent school — scores may appear low if iGCSEs are used (not counted in A8/P8)
            </p>
          )}
        </div>
      )}

      {/* Multi-year KS5 */}
      {hasKs5 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-ink-base">A-Level Results</p>
          {ks5.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b border-border-base/50">
                    <th className="text-left py-0.5 text-ink-faint font-medium">Year</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">A-Level APS</th>
                    {ks5.some(y => y.avg_point_score_academic != null) && (
                      <th className="text-right py-0.5 text-ink-faint font-medium">Academic</th>
                    )}
                    {ks5.some(y => y.avg_point_score_applied != null) && (
                      <th className="text-right py-0.5 text-ink-faint font-medium">Applied</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {ks5.map((y, i) => (
                    <tr key={y.academic_year ?? i} className={i === 0 ? 'font-medium' : 'text-ink-muted'}>
                      <td className="py-0.5">{shortYear(y.academic_year)}</td>
                      <td className="text-right">{y.avg_point_score_a?.toFixed(1) ?? '—'}</td>
                      {ks5.some(yy => yy.avg_point_score_academic != null) && (
                        <td className="text-right">{y.avg_point_score_academic?.toFixed(1) ?? '—'}</td>
                      )}
                      {ks5.some(yy => yy.avg_point_score_applied != null) && (
                        <td className="text-right">{y.avg_point_score_applied?.toFixed(1) ?? '—'}</td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <StatRow label="Avg Point Score" value={school.ks5_a_level_score?.toFixed(1)} />
          )}
        </div>
      )}

      {/* Subject breakdown */}
      {hasSubjects && (
        <div className="pt-1 border-t border-border-base/50 space-y-1.5">
          <p className="text-xs font-medium text-ink-base">Subject Results</p>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-border-base/50">
                  <th className="text-left py-0.5 text-ink-faint font-medium">Subject</th>
                  <th className="text-right py-0.5 text-ink-faint font-medium">Entries</th>
                  {subjects.some(s => s.pct_grade_9 != null) && (
                    <th className="text-right py-0.5 text-ink-faint font-medium">% Grade 9</th>
                  )}
                  {subjects.some(s => s.pct_grade_a_star != null) && (
                    <th className="text-right py-0.5 text-ink-faint font-medium">% A*</th>
                  )}
                  {subjects.some(s => s.avg_point_score != null) && (
                    <th className="text-right py-0.5 text-ink-faint font-medium">APS</th>
                  )}
                  <th className="text-right py-0.5 text-ink-faint font-medium">Year</th>
                </tr>
              </thead>
              <tbody>
                {subjects.slice(0, 15).map((s, i) => (
                  <tr key={`${s.subject_name}-${s.academic_year}-${i}`} className="text-ink-muted">
                    <td className="py-0.5 font-medium text-ink-base">{s.subject_name}</td>
                    <td className="text-right">{s.entries ?? '—'}</td>
                    {subjects.some(ss => ss.pct_grade_9 != null) && (
                      <td className="text-right">{fmtPct(s.pct_grade_9)}</td>
                    )}
                    {subjects.some(ss => ss.pct_grade_a_star != null) && (
                      <td className="text-right">{fmtPct(s.pct_grade_a_star)}</td>
                    )}
                    {subjects.some(ss => ss.avg_point_score != null) && (
                      <td className="text-right">{s.avg_point_score?.toFixed(1) ?? '—'}</td>
                    )}
                    <td className="text-right text-ink-faint">{shortYear(s.academic_year)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {subjects.length > 15 && (
            <p className="text-[10px] text-ink-faint">Showing top 15 of {subjects.length} subjects</p>
          )}
        </div>
      )}

      {/* Destinations */}
      {hasDest && (
        <div className="pt-1 border-t border-border-base/50 space-y-1.5">
          <p className="text-xs font-medium text-ink-base">Destinations after Leaving</p>
          {destinations.map((d, i) => {
            const bars = [
              { label: 'Higher Education', pct: d.pct_higher_education, color: 'bg-blue-500' },
              { label: 'Further Education', pct: d.pct_further_education, color: 'bg-sky-500' },
              { label: 'Apprenticeships', pct: d.pct_apprenticeships, color: 'bg-amber-500' },
              { label: 'Employment', pct: d.pct_employment, color: 'bg-emerald-500' },
              { label: 'Not Sustained', pct: d.pct_not_sustained, color: 'bg-red-400' },
            ].filter(b => b.pct != null);
            if (bars.length === 0) return null;
            return (
              <div key={d.academic_year ?? i} className="space-y-1">
                <div className="flex items-center gap-2 text-[10px] text-ink-faint">
                  <span>{shortYear(d.academic_year)}</span>
                  {d.destination_level && <span>({d.destination_level})</span>}
                </div>
                <div className="flex h-4 rounded overflow-hidden">
                  {bars.map(b => (
                    <div
                      key={b.label}
                      className={`${b.color} flex items-center justify-center text-[9px] text-white font-medium`}
                      style={{ width: `${b.pct}%` }}
                      title={`${b.label}: ${b.pct!.toFixed(1)}%`}
                    >
                      {b.pct! >= 10 ? `${Math.round(b.pct!)}%` : ''}
                    </div>
                  ))}
                </div>
                <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                  {bars.map(b => (
                    <span key={b.label} className="inline-flex items-center gap-1 text-[10px] text-ink-muted">
                      <span className={`w-2 h-2 rounded-sm ${b.color}`} />
                      {b.label} {b.pct!.toFixed(1)}%
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <DataNote notes={[
        'Results are from DfE performance tables. Schools with fewer than 5 pupils in a cohort have results suppressed.',
        !hasDest && (school.phase === 'Secondary' || school.phase === 'All-through') ? 'Destination data (post-16 outcomes) is not available for this school. DfE only publishes destinations where sufficient leavers could be matched to further education, employment, and HE records.' : '',
      ].filter(Boolean)} />
    </div>
  );
}

function InspectionsTab({ school, detail }: { school: SchoolRow; detail: SchoolDetailData | null }) {
  const inspections = detail?.inspections ?? [];

  if (!school.ofsted_rating && inspections.length === 0) {
    const isNewSchool = !school.ofsted_date;
    return (
      <div>
        <p className="text-xs text-ink-faint py-2">No Ofsted inspection data available.</p>
        <DataNote notes={[
          isNewSchool
            ? 'Newly opened schools are typically inspected within 5 years of opening. This school has not yet received its first inspection.'
            : 'Inspection records are sourced from Ofsted\'s published management information. Some schools may have been inspected without the record being available in this dataset.'
        ]} />
      </div>
    );
  }

  // Latest inspection (from detail if available, else from list data)
  const latest = inspections[0];

  return (
    <div className="space-y-3">
      {/* Latest rating + trajectory */}
      <div className="flex items-center gap-2 flex-wrap">
        <OfstedBadge rating={latest?.overall_rating ?? school.ofsted_rating ?? null} />
        {latest?.previous_rating != null && latest.previous_rating !== latest.overall_rating && (
          <span className="text-[10px] text-ink-faint flex items-center gap-0.5">
            (was <OfstedBadge rating={latest.previous_rating} />)
          </span>
        )}
        {(latest?.inspection_date ?? school.ofsted_date) && (
          <span className="text-xs text-ink-faint">
            {new Date(latest?.inspection_date ?? school.ofsted_date!).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
          </span>
        )}
        {latest?.inspection_body && latest.inspection_body !== 'Ofsted' && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700">
            {latest.inspection_body}
          </span>
        )}
      </div>

      {/* Report link */}
      {latest?.report_url && (
        <a
          href={latest.report_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-brand-primary hover:underline"
        >
          <FileText className="w-3 h-3" /> View full report <ExternalLink className="w-2.5 h-2.5" />
        </a>
      )}

      {/* Sub-judgements from latest */}
      <div className="space-y-0.5">
        <SubJudgement label="Quality of Education" rating={latest?.quality_of_education ?? school.quality_of_education} />
        <SubJudgement label="Behaviour & Attitudes" rating={latest?.behaviour_attitudes ?? school.behaviour_attitudes} />
        <SubJudgement label="Personal Development" rating={latest?.personal_development ?? school.personal_development} />
        <SubJudgement label="Leadership & Management" rating={latest?.leadership_management ?? school.leadership_management} />
        <SubJudgement label="Early Years" rating={latest?.early_years} />
        <SubJudgement label="Sixth Form" rating={latest?.sixth_form} />
        {latest?.safeguarding != null && (
          <div className="flex items-center justify-between text-xs py-0.5">
            <span className="text-ink-muted">Safeguarding</span>
            <span className={`font-medium ${latest.safeguarding ? 'text-emerald-600' : 'text-red-600'}`}>
              {latest.safeguarding ? 'Effective' : 'Not effective'}
            </span>
          </div>
        )}
      </div>

      {/* Inspection history */}
      {inspections.length > 1 && (
        <div className="pt-1 border-t border-border-base/50 space-y-1">
          <p className="text-xs font-medium text-ink-base">Inspection History</p>
          {inspections.slice(1).map((insp, i) => (
            <div key={i} className="flex items-center justify-between text-xs py-0.5">
              <div className="flex items-center gap-2">
                <span className="text-ink-muted">
                  {insp.inspection_date ? new Date(insp.inspection_date).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' }) : '—'}
                </span>
                {insp.report_url && (
                  <a href={insp.report_url} target="_blank" rel="noopener noreferrer" className="text-brand-primary hover:underline">
                    <FileText className="w-3 h-3" />
                  </a>
                )}
              </div>
              <OfstedBadge rating={insp.overall_rating ?? null} />
            </div>
          ))}
        </div>
      )}
      <DataNote notes={[
        'Inspection history covers published Ofsted reports from 2019 onwards. Earlier inspections are not included.',
        inspections.length === 1 ? 'Only one inspection record found. This school may have been inspected less frequently or converted recently.' : '',
      ].filter(Boolean)} />
    </div>
  );
}

function DemographicsTab({ school, detail }: { school: SchoolRow; detail: SchoolDetailData | null }) {
  const demographics = detail?.demographics ?? [];
  const workforce = detail?.workforce ?? [];
  const senProvisions = detail?.sen_provisions ?? [];
  const dem = demographics[0];
  const wf = workforce[0];
  const hasDem = school.pct_fsm != null || school.pct_eal != null || dem != null;
  const hasWf = wf != null || school.pupil_teacher_ratio != null;
  const hasMultiDem = demographics.length > 1;
  const hasMultiWf = workforce.length > 1;

  if (!hasDem && !hasWf && senProvisions.length === 0) {
    return (
      <div>
        <p className="text-xs text-ink-faint py-2">No demographic data available.</p>
        <DataNote notes={['Demographic data is sourced from the DfE School Census. Newly opened or recently converted schools may not yet appear in published datasets.']} />
      </div>
    );
  }

  // Ethnicity data
  const ethData = dem ? [
    { label: 'White British', pct: dem.pct_white_british, color: 'bg-blue-400' },
    { label: 'Asian', pct: dem.pct_asian, color: 'bg-emerald-400' },
    { label: 'Black', pct: dem.pct_black, color: 'bg-purple-400' },
    { label: 'Mixed', pct: dem.pct_mixed, color: 'bg-amber-400' },
    { label: 'Chinese', pct: dem.pct_chinese, color: 'bg-red-400' },
    { label: 'Other', pct: dem.pct_other_ethnic, color: 'bg-slate-400' },
  ].filter(e => e.pct != null && e.pct > 0) : [];

  return (
    <div className="space-y-3">
      {(school.dem_total_pupils ?? dem?.total_pupils) != null && (
        <StatRow label="Total Pupils" value={school.dem_total_pupils ?? dem?.total_pupils} />
      )}

      {/* Gender split */}
      {dem?.pct_boys != null && dem?.pct_girls != null && (
        <div className="space-y-0.5">
          <div className="flex justify-between text-xs">
            <span className="text-ink-muted">Gender</span>
            <span className="font-medium">{dem.pct_boys.toFixed(0)}% boys / {dem.pct_girls.toFixed(0)}% girls</span>
          </div>
          <div className="flex h-2 rounded-full overflow-hidden">
            <div className="bg-sky-400" style={{ width: `${dem.pct_boys}%` }} />
            <div className="bg-pink-400" style={{ width: `${dem.pct_girls}%` }} />
          </div>
        </div>
      )}

      {/* FSM + EAL */}
      <PercentBar label="Free School Meals" value={dem?.pct_fsm ?? school.pct_fsm} color="bg-amber-500" />
      <PercentBar label="English as Additional Language" value={dem?.pct_eal ?? school.pct_eal} color="bg-sky-500" />

      {/* SEN */}
      {(dem?.pct_sen_support != null || dem?.pct_sen_ehcp != null) && (
        <div className="space-y-1">
          <PercentBar label="SEN Support" value={dem?.pct_sen_support} color="bg-violet-500" />
          <PercentBar label="SEN EHCP" value={dem?.pct_sen_ehcp} color="bg-violet-700" />
        </div>
      )}

      {/* Ethnicity breakdown */}
      {ethData.length > 0 && (
        <div className="pt-1 border-t border-border-base/50 space-y-1">
          <p className="text-xs font-medium text-ink-base">Ethnicity</p>
          <div className="flex h-3 rounded-full overflow-hidden">
            {ethData.map(e => (
              <div key={e.label} className={e.color} style={{ width: `${e.pct}%` }} title={`${e.label}: ${e.pct!.toFixed(1)}%`} />
            ))}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5">
            {ethData.map(e => (
              <span key={e.label} className="inline-flex items-center gap-1 text-[10px] text-ink-muted">
                <span className={`w-2 h-2 rounded-sm ${e.color}`} />
                {e.label} {e.pct!.toFixed(1)}%
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Multi-year demographics trend */}
      {hasMultiDem && (
        <div className="pt-1 border-t border-border-base/50 space-y-1.5">
          <p className="text-xs font-medium text-ink-base">Demographics Trend</p>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-border-base/50">
                  <th className="text-left py-0.5 text-ink-faint font-medium">Year</th>
                  <th className="text-right py-0.5 text-ink-faint font-medium">Pupils</th>
                  <th className="text-right py-0.5 text-ink-faint font-medium">FSM %</th>
                  <th className="text-right py-0.5 text-ink-faint font-medium">EAL %</th>
                  <th className="text-right py-0.5 text-ink-faint font-medium">SEN %</th>
                </tr>
              </thead>
              <tbody>
                {demographics.map((d, i) => (
                  <tr key={d.academic_year ?? i} className={i === 0 ? 'font-medium' : 'text-ink-muted'}>
                    <td className="py-0.5">{shortYear(d.academic_year)}</td>
                    <td className="text-right">{d.total_pupils?.toLocaleString() ?? '—'}</td>
                    <td className="text-right">{d.pct_fsm != null ? `${d.pct_fsm.toFixed(1)}%` : '—'}</td>
                    <td className="text-right">{d.pct_eal != null ? `${d.pct_eal.toFixed(1)}%` : '—'}</td>
                    <td className="text-right">{d.pct_sen_support != null ? `${d.pct_sen_support.toFixed(1)}%` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SEN Provisions */}
      {senProvisions.length > 0 && (
        <div className="pt-1 border-t border-border-base/50 space-y-1">
          <p className="text-xs font-medium text-ink-base">SEN Provisions</p>
          <div className="space-y-0.5">
            {senProvisions.map((sp, i) => (
              <div key={i} className="flex justify-between text-xs py-0.5">
                <span className="text-ink-muted">{sp.provision_type}</span>
                <div className="flex items-center gap-2">
                  {sp.capacity != null && <span className="text-ink-faint text-[10px]">(capacity: {sp.capacity})</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Workforce */}
      {hasWf && (
        <div className="pt-1 border-t border-border-base/50 space-y-1">
          <p className="text-xs font-medium text-ink-base">Workforce</p>
          {hasMultiWf ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b border-border-base/50">
                    <th className="text-left py-0.5 text-ink-faint font-medium">Year</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">PTR</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">Teachers</th>
                    <th className="text-right py-0.5 text-ink-faint font-medium">Support</th>
                    {workforce.some(w => w.teacher_turnover_pct != null) && (
                      <th className="text-right py-0.5 text-ink-faint font-medium">Turnover</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {workforce.map((w, i) => (
                    <tr key={w.academic_year ?? i} className={i === 0 ? 'font-medium' : 'text-ink-muted'}>
                      <td className="py-0.5">{shortYear(w.academic_year)}</td>
                      <td className="text-right">{w.pupil_teacher_ratio?.toFixed(1) ?? '—'}</td>
                      <td className="text-right">{w.total_teachers_fte?.toFixed(0) ?? '—'}</td>
                      <td className="text-right">{w.total_support_fte?.toFixed(0) ?? '—'}</td>
                      {workforce.some(ww => ww.teacher_turnover_pct != null) && (
                        <td className="text-right">{w.teacher_turnover_pct != null ? `${w.teacher_turnover_pct.toFixed(1)}%` : '—'}</td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
              <StatRow label="Pupil:Teacher" value={wf?.pupil_teacher_ratio != null ? `${wf.pupil_teacher_ratio.toFixed(1)}:1` : (school.pupil_teacher_ratio != null ? `${school.pupil_teacher_ratio.toFixed(1)}:1` : null)} />
              <StatRow label="Teachers (FTE)" value={wf?.total_teachers_fte?.toFixed(1)} />
              <StatRow label="Support Staff (FTE)" value={wf?.total_support_fte?.toFixed(1)} />
              {wf?.teacher_turnover_pct != null && <StatRow label="Teacher Turnover" value={`${wf.teacher_turnover_pct.toFixed(1)}%`} />}
            </div>
          )}
        </div>
      )}
      <DataNote notes={[
        'Demographic data is from the DfE School Census (annual). SEN percentages reflect pupils receiving SEN Support or with an Education, Health and Care Plan (EHCP).',
        senProvisions.length > 0 ? 'SEN Provisions shown are designated specialist resource bases within this school, sourced from GIAS.' : '',
        !hasWf ? 'Workforce data is not available for this school. Independent schools, post-16 providers, and newly converted academies may not appear in the DfE workforce census.' : '',
      ].filter(Boolean)} />
    </div>
  );
}

/* ── LDO formatting ── */
function formatLdo(value: number | null | undefined, unit: string | null | undefined): string {
  if (value == null) return '—';
  if (unit === 'miles') return `${value.toFixed(2)} mi`;
  if (unit === 'metres') return `${Math.round(value)} m`;
  if (unit === 'km') return `${value.toFixed(2)} km`;
  return value.toFixed(2);
}

/* ── Allocation breakdown bar ── */
const ALLOC_COLORS: Record<string, string> = {
  'looked after': 'bg-purple-500',
  'lac': 'bg-purple-500',
  'sen': 'bg-rose-500',
  'ehcp': 'bg-rose-500',
  'medical': 'bg-rose-400',
  'social': 'bg-rose-400',
  'sibling': 'bg-blue-500',
  'staff': 'bg-cyan-500',
  'distance': 'bg-teal-500',
  'faith': 'bg-amber-500',
  'foundation': 'bg-amber-500',
  'banding': 'bg-indigo-400',
  'catchment': 'bg-emerald-500',
  'feeder': 'bg-sky-500',
};

function getAllocColor(criterion: string): string {
  const lower = criterion.toLowerCase();
  for (const [key, color] of Object.entries(ALLOC_COLORS)) {
    if (lower.includes(key)) return color;
  }
  return 'bg-gray-400';
}

// Summary/metadata keys that should NOT appear as allocation criteria in the bar
const ALLOC_SUMMARY_KEYS = new Set([
  'total', 'total_offered', 'total_allocated', 'places_allocated', 'allocated',
  'offers_made', 'pan', 'oversubscribed', 'first_preferences', 'second_preferences',
  'third_preferences', 'all_applicants',
]);

function AllocationBar({ breakdown }: { breakdown: Record<string, number> }) {
  const entries = Object.entries(breakdown)
    .filter(([k, v]) => typeof v === 'number' && v > 0 && !ALLOC_SUMMARY_KEYS.has(k))
    .sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);
  if (total === 0) return null;

  return (
    <div className="space-y-1.5">
      <div className="flex h-4 rounded overflow-hidden">
        {entries.map(([criterion, count]) => {
          const pct = (count / total) * 100;
          return (
            <div
              key={criterion}
              className={`${getAllocColor(criterion)} relative`}
              style={{ width: `${Math.max(pct, 2)}%` }}
              title={`${criterion}: ${count} (${pct.toFixed(0)}%)`}
            />
          );
        })}
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
        {entries.map(([criterion, count]) => {
          const pct = ((count / total) * 100).toFixed(0);
          return (
            <div key={criterion} className="flex items-center justify-between text-[10px]">
              <span className="flex items-center gap-1">
                <span className={`w-2 h-2 rounded-sm inline-block ${getAllocColor(criterion)}`} />
                <span className="text-ink-muted truncate">{criterion}</span>
              </span>
              <span className="font-medium text-ink-base ml-1">{count} ({pct}%)</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AdmissionsTab({ school, detail }: { school: SchoolRow; detail: SchoolDetailData | null }) {
  const admissions = detail?.admissions ?? [];
  const laDetail = detail?.admissions_la_detail ?? [];
  const latestLa = laDetail[0];
  const absences = detail?.absence ?? [];
  const hasAdm = admissions.length > 0 || laDetail.length > 0 || school.adm_applications != null;
  const hasAbs = absences.length > 0 || school.overall_absence_pct != null;

  if (!hasAdm && !hasAbs) {
    const isSpecial = school.type_code?.toLowerCase().includes('special') || school.type_code?.toLowerCase().includes('pru') || school.type_code?.toLowerCase().includes('alternative');
    const isJunior = (school.age_low ?? 0) >= 7;
    const notes: string[] = [];
    if (isSpecial) notes.push('Special schools, PRUs, and alternative provision schools do not participate in the national co-ordinated admissions process.');
    else if (isJunior) notes.push('Junior schools (Year 3\u20136) do not have a Reception intake and are not included in the national admissions dataset.');
    else notes.push('Admissions data is published annually by the DfE. Newly converted academies and some smaller schools may not appear in the most recent published dataset.');
    notes.push('Attendance data is from the DfE School Absence Statistics. PRUs, special schools, and alternative provision report separately.');
    return (
      <div>
        <p className="text-xs text-ink-faint py-2">No admissions or attendance data available.</p>
        <DataNote notes={notes} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Multi-year admissions (DfE) */}
      {admissions.length > 0 ? (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-ink-base">Applications & Offers</p>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-border-base/50">
                  <th className="text-left py-0.5 text-ink-faint font-medium">Year</th>
                  {admissions.some(a => a.year_group != null) && (
                    <th className="text-left py-0.5 text-ink-faint font-medium">YG</th>
                  )}
                  <th className="text-right py-0.5 text-ink-faint font-medium">Apps</th>
                  <th className="text-right py-0.5 text-ink-faint font-medium">1st</th>
                  <th className="text-right py-0.5 text-ink-faint font-medium">Offers</th>
                  <th className="text-right py-0.5 text-ink-faint font-medium">O/S</th>
                  {admissions.some(a => a.last_distance_offered != null) && (
                    <th className="text-right py-0.5 text-ink-faint font-medium">Dist</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {admissions.map((a, i) => (
                  <tr key={`${a.academic_year}-${a.year_group}-${i}`} className={i === 0 ? 'font-medium' : 'text-ink-muted'}>
                    <td className="py-0.5">{shortYear(a.academic_year)}</td>
                    {admissions.some(aa => aa.year_group != null) && (
                      <td className="py-0.5">{a.year_group ?? '\u2014'}</td>
                    )}
                    <td className="text-right">{a.applications_received ?? '\u2014'}</td>
                    <td className="text-right">{a.first_preference ?? '\u2014'}</td>
                    <td className="text-right">{a.offers_made ?? '\u2014'}</td>
                    <td className="text-right">{a.is_oversubscribed != null ? (a.is_oversubscribed ? 'Yes' : 'No') : '\u2014'}</td>
                    {admissions.some(aa => aa.last_distance_offered != null) && (
                      <td className="text-right">{a.last_distance_offered != null ? `${a.last_distance_offered.toFixed(2)}km` : '\u2014'}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (admissions.length === 0 && laDetail.length === 0 && hasAdm) && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-ink-base">Applications & Offers</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            <StatRow label="Applications" value={school.adm_applications} />
            <StatRow label="Places Offered" value={school.adm_offers} />
          </div>
          {school.is_oversubscribed != null && (
            <div className="flex items-center gap-1 text-xs">
              <span className="text-ink-faint">Oversubscribed:</span>
              <span className={`font-medium ${school.is_oversubscribed ? 'text-red-600' : 'text-emerald-600'}`}>
                {school.is_oversubscribed ? 'Yes' : 'No'}
              </span>
            </div>
          )}
        </div>
      )}

      {/* LA Admissions Detail (scraped from booklets) */}
      {latestLa && (
        <div className="pt-1 border-t border-border-base/50 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-xs font-medium text-ink-base">Allocation Detail</p>
            {latestLa.academic_year && (
              <span className="text-[10px] text-ink-faint">{shortYear(latestLa.academic_year)}</span>
            )}
            {latestLa.sif_required && (
              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-700">
                SIF Required
              </span>
            )}
            {latestLa.source_confidence && latestLa.source_confidence !== 'high' && (
              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                {latestLa.source_confidence} confidence
              </span>
            )}
          </div>

          {/* LDO + Distance Method */}
          {latestLa.last_distance_offered != null && (
            <div className="flex items-baseline gap-2">
              <span className="text-xs text-ink-muted">Last Distance Offered:</span>
              <span className="text-sm font-semibold text-ink-base">
                {formatLdo(latestLa.last_distance_offered, latestLa.ldo_unit)}
              </span>
              {latestLa.distance_method && (
                <span className="text-[10px] text-ink-faint">
                  ({latestLa.distance_method.replace(/_/g, ' ')})
                </span>
              )}
            </div>
          )}

          {/* LDO detail (per-band/per-criterion breakdown) */}
          {latestLa.ldo_detail && typeof latestLa.ldo_detail === 'object' && (
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
              {Object.entries(latestLa.ldo_detail).map(([k, v]) => (
                <StatRow key={k} label={k.replace(/_/g, ' ')} value={formatLdo(v as number, latestLa.ldo_unit)} />
              ))}
            </div>
          )}

          {/* Allocation Breakdown */}
          {latestLa.allocation_breakdown && Object.keys(latestLa.allocation_breakdown).length > 0 && (
            <div className="space-y-1">
              <p className="text-[10px] text-ink-faint font-medium uppercase tracking-wide">
                Places allocated by criterion
              </p>
              <AllocationBar breakdown={latestLa.allocation_breakdown} />
            </div>
          )}

          {/* Oversubscription Criteria Order */}
          {latestLa.oversubscription_criteria && Array.isArray(latestLa.oversubscription_criteria) && latestLa.oversubscription_criteria.length > 0 && (
            <div>
              <p className="text-[10px] text-ink-faint font-medium uppercase tracking-wide mb-0.5">
                Oversubscription criteria
              </p>
              <ol className="list-decimal list-inside text-[11px] text-ink-muted space-y-0.5">
                {latestLa.oversubscription_criteria.map((c: string, i: number) => (
                  <li key={i}>{c}</li>
                ))}
              </ol>
            </div>
          )}

          {/* Appeals + Waiting List */}
          {(latestLa.appeals_heard != null || latestLa.appeals_upheld != null || latestLa.waiting_list_size != null) && (
            <div className="grid grid-cols-3 gap-x-4 gap-y-0.5">
              {latestLa.appeals_heard != null && (
                <StatRow label="Appeals Heard" value={latestLa.appeals_heard} />
              )}
              {latestLa.appeals_upheld != null && (
                <StatRow label="Appeals Upheld" value={latestLa.appeals_upheld} />
              )}
              {latestLa.waiting_list_size != null && (
                <StatRow label="Waiting List" value={latestLa.waiting_list_size} />
              )}
            </div>
          )}
        </div>
      )}

      {/* Multi-year absence */}
      {absences.length > 0 ? (
        <div className="pt-1 border-t border-border-base/50 space-y-1.5">
          <p className="text-xs font-medium text-ink-base">Attendance</p>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-border-base/50">
                  <th className="text-left py-0.5 text-ink-faint font-medium">Year</th>
                  <th className="text-right py-0.5 text-ink-faint font-medium">Overall</th>
                  <th className="text-right py-0.5 text-ink-faint font-medium">Auth</th>
                  <th className="text-right py-0.5 text-ink-faint font-medium">Unauth</th>
                  <th className="text-right py-0.5 text-ink-faint font-medium">Persistent</th>
                  {absences.some(a => a.severe_absence_pct != null) && (
                    <th className="text-right py-0.5 text-ink-faint font-medium">Severe</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {absences.map((a, i) => (
                  <tr key={a.academic_year ?? i} className={i === 0 ? 'font-medium' : 'text-ink-muted'}>
                    <td className="py-0.5">{shortYear(a.academic_year)}</td>
                    <td className="text-right">{a.overall_absence_pct != null ? `${a.overall_absence_pct.toFixed(1)}%` : '\u2014'}</td>
                    <td className="text-right">{a.authorised_absence_pct != null ? `${a.authorised_absence_pct.toFixed(1)}%` : '\u2014'}</td>
                    <td className="text-right">{a.unauthorised_absence_pct != null ? `${a.unauthorised_absence_pct.toFixed(1)}%` : '\u2014'}</td>
                    <td className="text-right">{a.persistent_absence_pct != null ? `${a.persistent_absence_pct.toFixed(1)}%` : '\u2014'}</td>
                    {absences.some(aa => aa.severe_absence_pct != null) && (
                      <td className="text-right">{a.severe_absence_pct != null ? `${a.severe_absence_pct.toFixed(1)}%` : '\u2014'}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : hasAbs && (
        <div className="space-y-2 pt-1 border-t border-border-base/50">
          <p className="text-xs font-medium text-ink-base">Attendance</p>
          <PercentBar label="Overall Absence" value={school.overall_absence_pct} color="bg-red-400" />
          <PercentBar label="Persistent Absence" value={school.persistent_absence_pct} color="bg-red-600" />
        </div>
      )}
      <DataNote notes={[
        hasAdm ? 'Admissions data covers co-ordinated LA admissions (Reception/Year 7). Some schools manage their own admissions — last distance offered may not apply.' : '',
        laDetail.length > 0 ? 'Allocation detail is scraped from Local Authority admissions booklets. LDO = Last Distance Offered (furthest distance at which a place was offered). SIF = Supplementary Information Form (required by some faith schools).' : '',
        hasAbs ? 'Persistent absence = missing 10% or more of possible sessions. Severe absence = missing 50% or more.' : '',
        !hasAbs ? 'Attendance data not available. Newly converted academies and some schools may not appear in the DfE absence dataset until the following academic year.' : '',
      ].filter(Boolean)} />
    </div>
  );
}

function FinancesTab({ school, detail }: { school: SchoolRow; detail: SchoolDetailData | null }) {
  const finances = detail?.finances ?? [];
  const hasData = finances.length > 0 || school.per_pupil_expenditure != null;

  if (!hasData) {
    const isIndependent = school.type_code?.toLowerCase().includes('independent');
    return (
      <div>
        <p className="text-xs text-ink-faint py-2">No financial data available.</p>
        <DataNote notes={[
          isIndependent
            ? 'Independent schools are not required to submit financial returns to the DfE and are excluded from this dataset.'
            : 'Financial data is sourced from the DfE Consistent Financial Reporting (CFR) dataset. Newly converted academies and post-16 providers may not appear until their first full financial year is published.'
        ]} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-ink-base">School Finances</p>

      {finances.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="border-b border-border-base/50">
                <th className="text-left py-0.5 text-ink-faint font-medium">Year</th>
                <th className="text-right py-0.5 text-ink-faint font-medium">Income</th>
                <th className="text-right py-0.5 text-ink-faint font-medium">Spend</th>
                <th className="text-right py-0.5 text-ink-faint font-medium">Per-pupil</th>
                {finances.some(f => f.staff_expenditure != null) && (
                  <th className="text-right py-0.5 text-ink-faint font-medium">Staff £</th>
                )}
                <th className="text-right py-0.5 text-ink-faint font-medium">Staff %</th>
                <th className="text-right py-0.5 text-ink-faint font-medium">Balance</th>
                {finances.some(f => f.revenue_reserves != null) && (
                  <th className="text-right py-0.5 text-ink-faint font-medium">Reserves</th>
                )}
              </tr>
            </thead>
            <tbody>
              {finances.map((f, i) => {
                const balColor = f.in_year_balance != null ? (f.in_year_balance >= 0 ? 'text-emerald-600' : 'text-red-600') : '';
                return (
                  <tr key={f.academic_year ?? i} className={i === 0 ? 'font-medium' : 'text-ink-muted'}>
                    <td className="py-0.5">{shortYear(f.academic_year)}</td>
                    <td className="text-right">{fmtGBP(f.total_income)}</td>
                    <td className="text-right">{fmtGBP(f.total_expenditure)}</td>
                    <td className="text-right">{f.per_pupil_expenditure != null ? `£${f.per_pupil_expenditure.toLocaleString()}` : '—'}</td>
                    {finances.some(ff => ff.staff_expenditure != null) && (
                      <td className="text-right">{fmtGBP(f.staff_expenditure)}</td>
                    )}
                    <td className="text-right">{f.pct_budget_staff != null ? `${f.pct_budget_staff.toFixed(0)}%` : '—'}</td>
                    <td className={`text-right ${balColor}`}>{fmtGBP(f.in_year_balance)}</td>
                    {finances.some(ff => ff.revenue_reserves != null) && (
                      <td className="text-right">{fmtGBP(f.revenue_reserves)}</td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            {school.per_pupil_expenditure != null && (
              <StatRow label="Per-pupil Spend" value={`£${school.per_pupil_expenditure.toLocaleString()}`} />
            )}
          </div>
          {school.pct_budget_staff != null && (
            <PercentBar label="Budget on Staff" value={school.pct_budget_staff} color="bg-indigo-500" />
          )}
        </>
      )}
      <DataNote notes={['Financial data is from the DfE Consistent Financial Reporting (CFR) dataset. Academy trusts consolidate finances; per-school figures may differ from trust-level accounts.']} />
    </div>
  );
}

interface WalkLeg {
  steps?: { streetName?: string; distance?: number }[];
}
interface WalkResult {
  walk_minutes?: number;
  distance_m?: number;
  source?: string;
  route_summary?: string;
  legs?: WalkLeg[];
  error?: string;
}

function extractRouteStreets(result: WalkResult): string | null {
  const steps = result.legs?.[0]?.steps;
  if (!steps?.length) return null;
  const streets = steps
    .filter(s => s.streetName && s.distance && s.distance >= 10)
    .map(s => s.streetName!)
    .filter((name, i, arr) => arr.indexOf(name) === i);
  if (!streets.length) return null;
  return `Via ${streets.slice(0, 3).join(', ')}`;
}

function WalkTab({ school }: { school: SchoolRow }) {
  const { resolved } = useResultsData();
  const [result, setResult] = useState<WalkResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);

  const originLat = resolved?.coordinates?.lat;
  const originLon = resolved?.coordinates?.lon;

  useEffect(() => {
    if (fetched || !originLat || !originLon) return;
    setFetched(true);
    setLoading(true);
    fetch(`/api/v1/school-walk?urn=${school.urn}&from_lat=${originLat}&from_lon=${originLon}`, { cache: 'no-store' })
      .then(res => res.json())
      .then((data: WalkResult) => setResult(data))
      .catch(() => setResult({ error: 'Failed to fetch walk time' }))
      .finally(() => setLoading(false));
  }, [fetched, school.urn, originLat, originLon]);

  if (!originLat || !originLon) {
    return <p className="text-xs text-ink-faint py-2">Walk time unavailable — no origin coordinates.</p>;
  }
  if (loading) {
    return (
      <div className="flex items-center gap-2 py-3 text-xs text-ink-muted">
        <Loader2 className="w-4 h-4 animate-spin" />
        Calculating walk route via MOTIS...
      </div>
    );
  }
  if (!result || result.error) {
    return (
      <div className="flex items-center gap-2 py-2 text-xs text-ink-muted">
        <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
        {result?.error || 'Walk time unavailable'}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <Footprints className="w-5 h-5 text-brand-primary" />
          <span className="text-lg font-semibold text-ink-base">{result.walk_minutes} min</span>
        </div>
        {result.distance_m != null && (
          <span className="text-xs text-ink-muted">
            {result.distance_m < 1000 ? `${result.distance_m}m` : `${(result.distance_m / 1000).toFixed(1)}km`}
          </span>
        )}
      </div>
      {(result.route_summary || extractRouteStreets(result)) && (
        <p className="text-xs text-ink-muted">{result.route_summary || extractRouteStreets(result)}</p>
      )}
      <div className="text-[10px] text-ink-faint pt-1 border-t border-border-base/50">
        {result.source === 'motis' ? 'Walking route via MOTIS (real street network)' : 'Estimated straight-line distance'}
      </div>
    </div>
  );
}

/* ── SchoolDetail: fetches detail on mount, passes to tabs ── */

function SchoolDetail({ school }: { school: SchoolRow }) {
  const [activeTab, setActiveTab] = useState<DetailTab>('overview');
  const [detail, setDetail] = useState<SchoolDetailData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/v1/school-detail?urn=${school.urn}`, { cache: 'no-store' })
      .then(r => r.json())
      .then(d => { if (!cancelled) setDetail(d); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [school.urn]);

  return (
    <div className="p-3 bg-surface-secondary/50 border-t border-border-base space-y-2">
      {/* Tab pills */}
      <div className="flex gap-1 overflow-x-auto">
        {DETAIL_TABS.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`shrink-0 flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                activeTab === tab.key
                  ? 'bg-brand-primary/10 text-brand-primary'
                  : 'text-ink-muted hover:bg-surface-tertiary'
              }`}
            >
              <Icon className="w-3 h-3" />
              {tab.label}
            </button>
          );
        })}
        {loading && <Loader2 className="w-3 h-3 animate-spin text-ink-faint ml-1 shrink-0" />}
      </div>

      {/* Tab content */}
      {activeTab === 'overview' && <OverviewTab school={school} detail={detail} />}
      {activeTab === 'results' && <ResultsTab school={school} detail={detail} />}
      {activeTab === 'inspections' && <InspectionsTab school={school} detail={detail} />}
      {activeTab === 'demographics' && <DemographicsTab school={school} detail={detail} />}
      {activeTab === 'admissions' && <AdmissionsTab school={school} detail={detail} />}
      {activeTab === 'finances' && <FinancesTab school={school} detail={detail} />}
      {activeTab === 'walk' && <WalkTab school={school} />}
    </div>
  );
}

/* ── Helpers ── */

function getProgressScore(s: SchoolRow): number {
  if (s.progress_8 != null) return s.progress_8;
  if (s.ks2_reading_progress != null) return s.ks2_reading_progress;
  return -999;
}

function getAttainmentScore(s: SchoolRow): number {
  if (s.attainment_8 != null) return s.attainment_8;
  if (s.ks2_rwm_expected != null) return s.ks2_rwm_expected;
  if (s.ks5_a_level_score != null) return s.ks5_a_level_score;
  return -999;
}

function useShortlist() {
  const STORAGE_KEY = 'pp_school_shortlist';
  const [urns, setUrns] = useState<Set<number>>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? new Set(JSON.parse(raw) as number[]) : new Set();
    } catch { return new Set(); }
  });

  const toggle = useCallback((urn: number) => {
    setUrns(prev => {
      const next = new Set(prev);
      if (next.has(urn)) next.delete(urn); else next.add(urn);
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...next]));
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    setUrns(new Set());
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return { urns, toggle, clear };
}

/* ── ComparePanel ── */

function ComparePanel({ schools, onClose }: { schools: SchoolRow[]; onClose: () => void }) {
  if (schools.length < 2) return null;
  return (
    <div className="p-3 bg-surface-secondary rounded-lg border border-border-base space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-ink-base flex items-center gap-1.5">
          <BarChart3 className="w-4 h-4 text-brand-primary" />
          Compare Schools ({schools.length})
        </p>
        <button onClick={onClose} className="text-xs text-ink-faint hover:text-ink-base">Close</button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border-base">
              <th className="text-left py-1 pr-3 text-ink-faint font-medium sticky left-0 bg-surface-secondary">Metric</th>
              {schools.map(s => (
                <th key={s.urn} className="text-left py-1 px-2 text-ink-base font-medium max-w-[120px] truncate">{s.name}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border-base/50">
            <tr>
              <td className="py-1 pr-3 text-ink-faint sticky left-0 bg-surface-secondary">Ofsted</td>
              {schools.map(s => <td key={s.urn} className="py-1 px-2"><OfstedBadge rating={s.ofsted_rating ?? null} /></td>)}
            </tr>
            <tr>
              <td className="py-1 pr-3 text-ink-faint sticky left-0 bg-surface-secondary">Distance</td>
              {schools.map(s => <td key={s.urn} className="py-1 px-2">{s.distance_m != null ? (s.distance_m < 1000 ? `${s.distance_m}m` : `${(s.distance_m / 1000).toFixed(1)}km`) : '—'}</td>)}
            </tr>
            <tr>
              <td className="py-1 pr-3 text-ink-faint sticky left-0 bg-surface-secondary">Pupils</td>
              {schools.map(s => <td key={s.urn} className="py-1 px-2">{s.pupil_count?.toLocaleString() ?? s.dem_total_pupils?.toLocaleString() ?? '—'}</td>)}
            </tr>
            <tr>
              <td className="py-1 pr-3 text-ink-faint sticky left-0 bg-surface-secondary">FSM %</td>
              {schools.map(s => <td key={s.urn} className="py-1 px-2">{s.pct_fsm != null ? `${s.pct_fsm.toFixed(1)}%` : '—'}</td>)}
            </tr>
            {schools.some(s => s.ks2_rwm_expected != null) && (
              <tr>
                <td className="py-1 pr-3 text-ink-faint sticky left-0 bg-surface-secondary">KS2 RWM %</td>
                {schools.map(s => <td key={s.urn} className="py-1 px-2">{s.ks2_rwm_expected != null ? `${Math.round(s.ks2_rwm_expected)}%` : '—'}</td>)}
              </tr>
            )}
            {schools.some(s => s.progress_8 != null) && (
              <tr>
                <td className="py-1 pr-3 text-ink-faint sticky left-0 bg-surface-secondary">Progress 8</td>
                {schools.map(s => <td key={s.urn} className="py-1 px-2">{s.progress_8 != null ? `${s.progress_8 > 0 ? '+' : ''}${s.progress_8.toFixed(2)}` : '—'}</td>)}
              </tr>
            )}
            {schools.some(s => s.attainment_8 != null) && (
              <tr>
                <td className="py-1 pr-3 text-ink-faint sticky left-0 bg-surface-secondary">Attainment 8</td>
                {schools.map(s => <td key={s.urn} className="py-1 px-2">{s.attainment_8?.toFixed(1) ?? '—'}</td>)}
              </tr>
            )}
            <tr>
              <td className="py-1 pr-3 text-ink-faint sticky left-0 bg-surface-secondary">PTR</td>
              {schools.map(s => <td key={s.urn} className="py-1 px-2">{s.pupil_teacher_ratio ? `${s.pupil_teacher_ratio.toFixed(1)}:1` : '—'}</td>)}
            </tr>
            {schools.some(s => s.overall_absence_pct != null) && (
              <tr>
                <td className="py-1 pr-3 text-ink-faint sticky left-0 bg-surface-secondary">Absence %</td>
                {schools.map(s => <td key={s.urn} className="py-1 px-2">{s.overall_absence_pct != null ? `${s.overall_absence_pct.toFixed(1)}%` : '—'}</td>)}
              </tr>
            )}
            {schools.some(s => s.per_pupil_expenditure != null) && (
              <tr>
                <td className="py-1 pr-3 text-ink-faint sticky left-0 bg-surface-secondary">Per-pupil £</td>
                {schools.map(s => <td key={s.urn} className="py-1 px-2">{s.per_pupil_expenditure != null ? `£${s.per_pupil_expenditure.toLocaleString()}` : '—'}</td>)}
              </tr>
            )}
            {schools.some(s => s.is_oversubscribed != null) && (
              <tr>
                <td className="py-1 pr-3 text-ink-faint sticky left-0 bg-surface-secondary">Oversubscribed</td>
                {schools.map(s => <td key={s.urn} className="py-1 px-2">{s.is_oversubscribed != null ? (s.is_oversubscribed ? 'Yes' : 'No') : '—'}</td>)}
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Main SchoolTable ── */

export default function SchoolTable({ schools, summary, isArea }: Props) {
  const [selectedPhase, setSelectedPhase] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('distance');
  const [expandedUrn, setExpandedUrn] = useState<number | null>(null);
  const [showCompare, setShowCompare] = useState(false);
  const shortlist = useShortlist();

  // Map interaction (fly-to + highlight on row expand — matches TransactionTable pattern)
  const { mapFlyToRef, mapViewportRef, mapHighlightRef, clearMapHighlight } = useResults();
  const preZoomViewportRef = useRef<{ center: [number, number]; zoom: number } | null>(null);

  const restoreMapViewport = useCallback(() => {
    const saved = preZoomViewportRef.current;
    if (saved && mapFlyToRef.current) {
      mapFlyToRef.current(saved.center[0], saved.center[1], saved.zoom);
      preZoomViewportRef.current = null;
    }
  }, [mapFlyToRef]);

  // Restore map viewport + clear highlight when SchoolTable unmounts (metric card collapsed)
  useEffect(() => {
    return () => { restoreMapViewport(); clearMapHighlight(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    let result = schools;
    if (selectedPhase !== 'all') {
      result = result.filter(s => s.phase === selectedPhase);
    }
    return [...result].sort((a, b) => {
      switch (sortBy) {
        case 'distance': return (a.distance_m ?? 99999) - (b.distance_m ?? 99999);
        case 'ofsted': return (a.ofsted_rating ?? 9) - (b.ofsted_rating ?? 9);
        case 'progress': return getProgressScore(b) - getProgressScore(a);
        case 'attainment': return getAttainmentScore(b) - getAttainmentScore(a);
        case 'fsm': return (a.pct_fsm ?? 999) - (b.pct_fsm ?? 999);
        case 'name': return a.name.localeCompare(b.name);
        default: return 0;
      }
    });
  }, [schools, selectedPhase, sortBy]);

  const phaseCounts = useMemo(() => {
    const counts: Record<string, number> = { all: schools.length };
    for (const s of schools) {
      const p = s.phase ?? 'Other';
      counts[p] = (counts[p] || 0) + 1;
    }
    return counts;
  }, [schools]);

  const toggleExpand = useCallback((urn: number, school: SchoolRow) => {
    setExpandedUrn(prev => {
      if (prev === urn) {
        // Collapsing — restore map and clear highlight
        clearMapHighlight();
        restoreMapViewport();
        return null;
      }
      // Expanding — fly to school location + show highlight marker
      const { latitude: lat, longitude: lon } = school;
      if (lat && lon && mapFlyToRef.current) {
        if (!preZoomViewportRef.current && mapViewportRef.current) {
          preZoomViewportRef.current = mapViewportRef.current;
        }
        mapFlyToRef.current(lon, lat);
        mapHighlightRef.current?.(lon, lat, {
          name: school.name,
          phase: school.phase,
          ofsted: school.ofsted_rating,
          distance_m: school.distance_m,
        });
      }
      return urn;
    });
  }, [mapFlyToRef, mapViewportRef, mapHighlightRef, clearMapHighlight, restoreMapViewport]);

  if (!schools.length) {
    return <div className="text-center py-6 text-sm text-ink-faint">No schools found in this area</div>;
  }

  return (
    <div className="space-y-2">
      {/* Summary Bar */}
      {summary && (
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="font-medium text-ink-base">{summary.total_schools} schools</span>
          {(summary.outstanding ?? 0) > 0 && <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">{summary.outstanding} Outstanding</span>}
          {(summary.good ?? 0) > 0 && <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-800">{summary.good} Good</span>}
          {(summary.requires_improvement ?? 0) > 0 && <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">{summary.requires_improvement} RI</span>}
          {(summary.inadequate ?? 0) > 0 && <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-800">{summary.inadequate} Inadequate</span>}
        </div>
      )}

      {/* Phase Filter Pills */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {PHASES.map(p => (
          <button
            key={p.key}
            onClick={() => setSelectedPhase(p.key)}
            className={`shrink-0 px-2 py-1 rounded-full text-xs font-medium transition-colors ${
              selectedPhase === p.key
                ? 'bg-brand-primary text-white'
                : 'bg-surface-secondary text-ink-muted hover:bg-surface-tertiary'
            }`}
          >
            {p.label}{phaseCounts[p.key] ? ` (${phaseCounts[p.key]})` : ''}
          </button>
        ))}
      </div>

      {/* Sort */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-ink-faint">Sort:</span>
        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value)}
          className="text-xs bg-surface-secondary border border-border-base rounded px-1.5 py-0.5"
        >
          {SORT_OPTIONS.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
        </select>
      </div>

      {/* School List */}
      <div className="max-h-[400px] overflow-y-auto space-y-0.5">
        {filtered.map((school, idx) => {
          const isExpanded = expandedUrn === school.urn;
          const isIndependent = school.type_code?.toLowerCase().includes('independent') ||
                                school.type_code?.toLowerCase().includes('free school');

          return (
            <Fragment key={school.urn}>
              <button
                onClick={() => toggleExpand(school.urn, school)}
                className={`w-full text-left px-2 py-1.5 rounded transition-colors ${
                  isExpanded ? 'bg-surface-secondary' : 'hover:bg-surface-secondary/50'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs text-ink-faint w-5 text-right shrink-0">{idx + 1}</span>
                  <span className="shrink-0">
                    {school.phase === 'Primary' ? (
                      <School className="w-3.5 h-3.5 text-blue-500" />
                    ) : school.phase === 'Secondary' ? (
                      <GraduationCap className="w-3.5 h-3.5 text-purple-500" />
                    ) : (
                      <Building className="w-3.5 h-3.5 text-ink-muted" />
                    )}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-ink-base truncate">{school.name}</p>
                    <div className="flex items-center gap-1.5 text-xs text-ink-muted">
                      <span>{school.phase}</span>
                      {isIndependent && (
                        <span className="px-1 py-0 rounded bg-yellow-100 text-yellow-800 text-[10px]">Independent</span>
                      )}
                      <KeyMetric school={school} />
                      <VelocityBadge velocity={school.velocity} />
                    </div>
                  </div>
                  <div className="shrink-0"><OfstedBadge rating={school.ofsted_rating ?? null} /></div>
                  {school.la_ldo != null && (
                    <span className="shrink-0 text-[10px] text-ink-faint" title="Last Distance Offered">
                      LDO {formatLdo(school.la_ldo, school.la_ldo_unit)}
                    </span>
                  )}
                  {school.distance_m != null && (
                    <span className="shrink-0 text-xs text-ink-faint w-12 text-right">
                      {school.distance_m < 1000 ? `${school.distance_m}m` : `${(school.distance_m / 1000).toFixed(1)}km`}
                    </span>
                  )}
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={(e) => { e.stopPropagation(); shortlist.toggle(school.urn); }}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); shortlist.toggle(school.urn); } }}
                    className="shrink-0 p-0.5"
                  >
                    <Heart className={`w-3.5 h-3.5 transition-colors ${shortlist.urns.has(school.urn) ? 'fill-red-500 text-red-500' : 'text-ink-faint hover:text-red-400'}`} />
                  </span>
                  <span className="shrink-0 text-ink-faint">
                    {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  </span>
                </div>
              </button>
              {isExpanded && <SchoolDetail school={school} />}
            </Fragment>
          );
        })}
      </div>

      {/* Compare panel */}
      {showCompare && (() => {
        const shortlisted = schools.filter(s => shortlist.urns.has(s.urn));
        return shortlisted.length >= 2
          ? <ComparePanel schools={shortlisted.slice(0, 5)} onClose={() => setShowCompare(false)} />
          : <p className="text-xs text-ink-faint p-2">Select at least 2 schools to compare (tap the heart icon).</p>;
      })()}

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-ink-faint pt-1 border-t border-border-base">
        <span>Showing {filtered.length} of {schools.length} schools{isArea && ' in this area'}</span>
        {shortlist.urns.size >= 2 && (
          <button
            onClick={() => setShowCompare(v => !v)}
            className="flex items-center gap-1 px-2 py-1 rounded bg-brand-primary/10 text-brand-primary text-xs font-medium hover:bg-brand-primary/20"
          >
            <BarChart3 className="w-3 h-3" />
            Compare ({shortlist.urns.size})
          </button>
        )}
      </div>
    </div>
  );
}
