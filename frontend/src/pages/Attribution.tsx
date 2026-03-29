import { Link } from 'react-router-dom';
import { ArrowLeft, MapPin } from 'lucide-react';

/** Bible Part 1.3 — Data attribution page listing all OGL/CC BY/ODbL sources */
const SOURCES = [
  { name: 'ONS National Statistics Postcode Lookup (ONSPD)', licence: 'OGL v3', org: 'Office for National Statistics',
    note: 'Contains OS data \u00a9 Crown copyright and database right 2026.' },
  { name: 'ONS Open Geography Portal (Boundaries)', licence: 'OGL v3', org: 'Office for National Statistics',
    note: 'Contains National Statistics data \u00a9 Crown copyright and database right 2026.' },
  { name: 'HM Land Registry Price Paid Data', licence: 'OGL v3', org: 'HM Land Registry',
    note: 'Contains HM Land Registry data \u00a9 Crown copyright and database right 2026.' },
  { name: 'ONS UK House Price Index (HPI)', licence: 'OGL v3', org: 'Land Registry / ONS',
    note: 'UK House Price Index data.' },
  { name: 'VOA Private Rental Market Statistics', licence: 'OGL v3', org: 'Valuation Office Agency',
    note: 'Private rental market statistics.' },
  { name: 'Census 2021 (Demographics & Housing)', licence: 'OGL v3', org: 'Office for National Statistics',
    note: 'Census 2021 data \u00a9 Crown copyright.' },
  { name: 'Index of Multiple Deprivation (IMD) 2025', licence: 'OGL v3', org: 'MHCLG',
    note: 'English indices of deprivation. Uses 2021 LSOA boundaries.' },
  { name: 'DfE Get Information About Schools (GIAS)', licence: 'OGL v3', org: 'Department for Education',
    note: 'School information and performance data.' },
  { name: 'NHS Organisation Data Service (ODS)', licence: 'OGL v3', org: 'NHS Digital',
    note: 'GP surgeries and health facility data.' },
  { name: 'DfT NaPTAN (Transport Stops)', licence: 'OGL v3', org: 'Department for Transport',
    note: 'National public transport access nodes.' },
  { name: 'Ofcom Connected Nations (Broadband)', licence: 'OGL v3', org: 'Ofcom',
    note: 'Fixed broadband coverage data.' },
  { name: 'OZEV Open Charge Point Data', licence: 'OGL v3', org: 'Office for Zero Emission Vehicles',
    note: 'EV charging point locations.' },
  { name: 'Environment Agency Flood Zones', licence: 'OGL v3', org: 'Environment Agency',
    note: 'Flood Zone 2 and 3 boundaries.' },
  { name: 'Defra PCM Air Quality', licence: 'OGL v3', org: 'Defra',
    note: 'NO\u2082 and PM2.5 modelled concentrations.' },
  { name: 'Natural England Green Infrastructure', licence: 'OGL v3', org: 'Natural England',
    note: 'OS Open Greenspace data.' },
  { name: 'VOA Council Tax Valuation List', licence: 'OGL v3', org: 'Valuation Office Agency',
    note: 'Council tax band amounts by local authority.' },
  { name: 'OpenStreetMap (15-Minute Amenities)', licence: 'ODbL', org: 'OpenStreetMap Contributors',
    note: '\u00a9 OpenStreetMap contributors. Data available under the Open Database License.' },
  { name: 'Police.uk Crime Data', licence: 'OGL v3', org: 'Home Office',
    note: 'Street-level crime and outcome data.' },
  { name: 'Ofsted Management Information', licence: 'OGL v3', org: 'Ofsted',
    note: 'School inspection outcomes and ratings.' },
  { name: 'UCL House Price Per Square Metre', licence: 'CC BY 4.0', org: 'University College London',
    note: 'Residential property price per square metre data.' },
  { name: 'ASHE Resident Analysis (Earnings)', licence: 'OGL v3', org: 'Office for National Statistics',
    note: 'Annual Survey of Hours and Earnings \u2014 median earnings by LAD.' },
  { name: 'TfL Public Transport Accessibility Levels (PTAL)', licence: 'OGL v3', org: 'Transport for London',
    note: 'PTAL scores for London LSOAs.' },
  { name: 'Census 2021 Travel to Work (TS061)', licence: 'OGL v3', org: 'Office for National Statistics',
    note: 'Method of travel to work including cycling.' },
  { name: 'Ofcom Mobile Coverage (Connected Nations)', licence: 'OGL v3', org: 'Ofcom',
    note: '4G and 5G mobile network coverage data.' },
  { name: 'Open Council Data UK', licence: 'CC BY-SA', org: 'Open Council Data UK',
    note: 'Local council political control and councillor data.' },
  { name: 'Ofwat Water Company Boundaries', licence: 'CC BY 4.0', org: 'Ofwat / Stream Water Data Portal',
    note: 'Water company service area boundaries.' },
  { name: 'Census 2021 TS017 — Household Size', licence: 'OGL v3', org: 'Office for National Statistics',
    note: 'Number of people per household by LSOA.' },
  { name: 'Census 2021 TS022 — Ethnic Group', licence: 'OGL v3', org: 'Office for National Statistics',
    note: 'Detailed ethnic group breakdown by ward.' },
  { name: 'Census 2021 TS058 — Distance Travelled to Work', licence: 'OGL v3', org: 'Office for National Statistics',
    note: 'Distance bands and work-from-home rates by LSOA.' },
  { name: 'MHCLG EPC Register (Energy Performance Certificates)', licence: 'OGL v3', org: 'MHCLG',
    note: 'Energy efficiency ratings and heating type data by LSOA.' },
];

export default function Attribution() {
  return (
    <div className="min-h-dvh flex flex-col bg-surface">
      <header className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-divider">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
          <Link to="/" className="p-2 rounded-xl hover:bg-surface transition-colors">
            <ArrowLeft className="w-5 h-5 text-ink-muted" />
          </Link>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center">
              <MapPin className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="font-bold text-sm tracking-tight text-ink">PropertyPulse</span>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto w-full px-4 py-10">
        <h1 className="text-3xl font-extrabold tracking-tight text-ink mb-2">Data Sources & Attribution</h1>
        <p className="text-ink-muted mb-8 leading-relaxed">
          PropertyPulse aggregates publicly available open data from UK government and community sources.
          All data is used under OGL v3, CC BY 4.0, or ODbL licences.
        </p>

        <div className="space-y-3">
          {SOURCES.map((s) => (
            <div key={s.name} className="p-5 rounded-2xl bg-white border border-divider">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="font-semibold text-sm text-ink">{s.name}</h3>
                  <p className="text-xs text-ink-muted mt-1">{s.org}</p>
                  <p className="text-xs text-ink-faint mt-1">{s.note}</p>
                </div>
                <span className="shrink-0 px-2.5 py-1 rounded-lg bg-brand-50 text-brand-700 text-xs font-medium">
                  {s.licence}
                </span>
              </div>
            </div>
          ))}
        </div>
      </main>

      <footer className="px-6 py-4 text-center text-xs text-ink-faint border-t border-divider mt-auto">
        Contains OS data &copy; Crown copyright and database right 2026. &copy; OpenStreetMap contributors.
      </footer>
    </div>
  );
}
