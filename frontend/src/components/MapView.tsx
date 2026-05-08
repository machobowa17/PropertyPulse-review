import { useRef, useEffect, useCallback } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import Supercluster from 'supercluster';
import type { ChoroplethResponse } from '../api/client';
import type { SelectedProperty } from '../context/ResultsContext';

interface Viewport {
  center: [number, number];
  zoom: number;
}

interface Props {
  lat: number;
  lon: number;
  boundary?: GeoJSON.Feature | null;
  lsoaBoundary?: GeoJSON.Feature | null;
  pois?: GeoJSON.FeatureCollection | null;
  activeTab?: string;
  visibleLayers?: Record<string, boolean>;
  searchLsoa?: string;
  initialViewport?: Viewport | null;
  onViewportChange?: (vp: Viewport) => void;
  choroplethData?: ChoroplethResponse | null;
  choroplethUrl?: string | null;
  onMapReady?: (flyTo: ((lng: number, lat: number, zoom?: number) => void) | null) => void;
  onHighlightReady?: (cb: ((lng: number, lat: number, props?: Record<string, unknown>) => void) | null) => void;
  onPropertySelect?: (prop: SelectedProperty) => void;
  selectedPropertyParcel?: GeoJSON.Feature | null;
}

const POI_COLOURS: Record<string, string> = {
  school: '#ea580c',
  station: '#7c3aed',
  ev_charger: '#16a34a',
  amenity: '#0f766e',
  park: '#22c55e',
  sports_recreation: '#84cc16',
  nhs_facility: '#dc2626',
  sold_price: '#0891b2',
};
const POI_ICONS: Record<string, string> = {
  school: '🎓',
  station: '🚆',
  ev_charger: '⚡',
  amenity: '🏪',
  park: '🌳',
  sports_recreation: '⚽',
  nhs_facility: '🏥',
};

/** Ofsted-coded school marker colours: 1=Outstanding, 2=Good, 3=RI, 4=Inadequate */
const OFSTED_MARKER_COLOURS: Record<number, string> = {
  1: '#059669', // emerald-600 — Outstanding
  2: '#2563eb', // blue-600 — Good
  3: '#d97706', // amber-600 — Requires Improvement
  4: '#dc2626', // red-600 — Inadequate
};

const PROPERTY_TYPE_COLOURS: Record<string, string> = {
  Detached: '#2563eb',
  'Semi-Detached': '#16a34a',
  Terraced: '#d97706',
  Flat: '#9333ea',
};

const CHOROPLETH_RAMPS: Record<string, string[]> = {
  avg_price: ['#2166ac', '#67a9cf', '#fddbc7', '#ef8a62', '#b2182b'],
  median_price: ['#2166ac', '#67a9cf', '#fddbc7', '#ef8a62', '#b2182b'],
  price_per_sqft: ['#2166ac', '#67a9cf', '#fddbc7', '#ef8a62', '#b2182b'],
  epc_score: ['#d73027', '#fc8d59', '#fee08b', '#91cf60', '#1a9850'],
  population_density: ['#ecfeff', '#a5f3fc', '#67e8f9', '#06b6d4', '#155e75'],
  median_age: ['#eff6ff', '#bfdbfe', '#60a5fa', '#2563eb', '#1e3a8a'],
  household_composition: ['#f0fdfa', '#99f6e4', '#2dd4bf', '#0f766e', '#134e4a'],
  good_health: ['#f0fdf4', '#bbf7d0', '#4ade80', '#16a34a', '#166534'],
  economically_active: ['#f7fee7', '#d9f99d', '#a3e635', '#65a30d', '#365314'],
  degree_educated: ['#fefce8', '#fde68a', '#facc15', '#ca8a04', '#713f12'],
  no_car: ['#fff7ed', '#fdba74', '#fb923c', '#ea580c', '#9a3412'],
  born_abroad: ['#fff7ed', '#fdba74', '#f97316', '#c2410c', '#7c2d12'],
  housing_tenure: ['#faf5ff', '#e9d5ff', '#d8b4fe', '#a855f7', '#6b21a8'],
  housing_type: ['#fdf4ff', '#f5d0fe', '#e879f9', '#c026d3', '#86198f'],
  household_size: ['#fdf2f8', '#fbcfe8', '#f472b6', '#db2777', '#831843'],
  deprivation: ['#1a9850', '#91cf60', '#fee08b', '#fc8d59', '#d73027'],
  deprivation_income: ['#1a9850', '#91cf60', '#fee08b', '#fc8d59', '#d73027'],
  deprivation_employment: ['#1a9850', '#91cf60', '#fee08b', '#fc8d59', '#d73027'],
  deprivation_education: ['#1a9850', '#91cf60', '#fee08b', '#fc8d59', '#d73027'],
  deprivation_health: ['#1a9850', '#91cf60', '#fee08b', '#fc8d59', '#d73027'],
  deprivation_crime: ['#1a9850', '#91cf60', '#fee08b', '#fc8d59', '#d73027'],
  deprivation_barriers: ['#1a9850', '#91cf60', '#fee08b', '#fc8d59', '#d73027'],
  deprivation_living_environment: ['#1a9850', '#91cf60', '#fee08b', '#fc8d59', '#d73027'],
  broadband: ['#eff6ff', '#bfdbfe', '#60a5fa', '#2563eb', '#1d4ed8'],
  mobile_coverage: ['#f3e8ff', '#d8b4fe', '#c084fc', '#a855f7', '#7e22ce'],
  air_quality_no2: ['#ecfeff', '#bae6fd', '#38bdf8', '#0284c7', '#0c4a6e'],
  air_quality_pm25: ['#f0f9ff', '#bae6fd', '#7dd3fc', '#0369a1', '#082f49'],
  council_tax: ['#eff6ff', '#93c5fd', '#3b82f6', '#1d4ed8', '#1e3a8a'],
  median_earnings: ['#f5f3ff', '#d8b4fe', '#a855f7', '#7e22ce', '#581c87'],
  median_rent: ['#fdf2f8', '#f9a8d4', '#ec4899', '#be185d', '#831843'],
};

const CHOROPLETH_UNITS: Record<string, string> = {
  avg_price: '£',
  median_price: '£',
  price_per_sqft: '£/sqft',
  epc_score: 'score',
  population_density: 'people/hectare',
  median_age: 'years',
  household_composition: '%',
  good_health: '%',
  economically_active: '%',
  degree_educated: '%',
  no_car: '%',
  born_abroad: '%',
  housing_tenure: '%',
  housing_type: '%',
  household_size: '%',
  deprivation: 'score',
  deprivation_income: 'score',
  deprivation_employment: 'score',
  deprivation_education: 'score',
  deprivation_health: 'score',
  deprivation_crime: 'score',
  deprivation_barriers: 'score',
  deprivation_living_environment: 'score',
  broadband: '%',
  mobile_coverage: '%',
  air_quality_no2: 'µg/m³',
  air_quality_pm25: 'µg/m³',
  council_tax: '£',
  median_earnings: '£',
  median_rent: '£',
};

const POI_TABS = ['Property & Market', 'Community & Education', 'Lifestyle & Connectivity', 'Environment & Safety'];
const ISOCHRONE_LAYERS = [
  'iso-15-fill', 'iso-15-line', 'iso-15-label',
  'iso-10-fill', 'iso-10-line', 'iso-10-label',
  'iso-5-fill',  'iso-5-line',  'iso-5-label',
] as const;
const ISOCHRONE_SOURCES = ['iso-5', 'iso-10', 'iso-15', 'iso-5-pt', 'iso-10-pt', 'iso-15-pt'] as const;

function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function formatPrice(price: number): string {
  if (!Number.isFinite(price)) return '£--';
  if (price >= 999_500) return `£${(price / 1_000_000).toFixed(1)}m`;
  if (price >= 1_000) return `£${Math.round(price / 1_000)}k`;
  return `£${price}`;
}

// DOM element pools to avoid constant create/destroy on zoom/pan (reduces GC pressure on mobile)
const pillPool: HTMLDivElement[] = [];
const clusterPool: HTMLDivElement[] = [];
const MAX_POOL_SIZE = 200;

function recyclePill(el: HTMLDivElement): void {
  // Handlers (onclick, onmouseenter, onmouseleave) are overwritten in createPricePillElement
  if (pillPool.length < MAX_POOL_SIZE) pillPool.push(el);
}
function recycleCluster(el: HTMLDivElement): void {
  if (clusterPool.length < MAX_POOL_SIZE) clusterPool.push(el);
}

function createPricePillElement(price: number, propertyType?: string): HTMLDivElement {
  const bg = (propertyType && PROPERTY_TYPE_COLOURS[propertyType]) || '#0891b2';
  const el = pillPool.pop() || document.createElement('div');
  // Outer div: MapLibre controls its `transform` for positioning — NEVER set transform on this element.
  el.style.cssText = 'cursor: pointer;';
  // Inner span: carries all visual styling + hover scale (safe — doesn't conflict with MapLibre's transform)
  let inner = el.firstElementChild as HTMLSpanElement | null;
  if (!inner) {
    inner = document.createElement('span');
    el.appendChild(inner);
  }
  inner.style.cssText = `
    display: inline-block;
    background: ${bg}; color: white; font-size: 11px; font-weight: 700;
    padding: 2px 7px; border-radius: 9999px; white-space: nowrap;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    line-height: 1.4; border: 1.5px solid rgba(255,255,255,0.6);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  `;
  inner.textContent = formatPrice(price);
  el.onclick = null;
  el.onmouseenter = () => { inner!.style.transform = 'scale(1.15)'; inner!.style.boxShadow = '0 2px 6px rgba(0,0,0,0.4)'; };
  el.onmouseleave = () => { inner!.style.transform = ''; inner!.style.boxShadow = '0 1px 3px rgba(0,0,0,0.3)'; };
  return el;
}

function createClusterElement(count: number): HTMLDivElement {
  const size = 28 + Math.min(count, 80) * 0.2;
  const el = clusterPool.pop() || document.createElement('div');
  el.style.cssText = `
    background: rgba(8,145,178,0.85); color: white; width: ${size}px; height: ${size}px;
    border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; cursor: pointer;
    box-shadow: 0 1px 4px rgba(0,0,0,0.3); border: 2px solid rgba(255,255,255,0.7);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
  `;
  el.textContent = `${count}`;
  el.onclick = null;
  return el;
}

const EPC_COLOURS: Record<string, string> = {
  A: '#008054', B: '#19b459', C: '#8dce46',
  D: '#ffd500', E: '#fcaa65', F: '#ef8023', G: '#e9153b',
};

function formatLabel(value: string): string {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function genericPoiPopupHtml(props: Record<string, unknown>): string {
  const detailRows = [
    props.ofsted ? `Ofsted: ${esc({1:'Outstanding',2:'Good',3:'Requires Improvement',4:'Inadequate'}[Number(props.ofsted)] ?? String(props.ofsted))}` : null,
    props.phase ? esc(String(props.phase)) : null,
    props.facility_type ? `Type: ${esc(formatLabel(String(props.facility_type)))}` : null,
    props.site_type ? `Type: ${esc(String(props.site_type))}` : null,
    props.amenity_type ? `Amenity: ${esc(formatLabel(String(props.amenity_type)))}` : null,
    props.operator ? esc(String(props.operator)) : null,
    props.connectors != null ? `${props.connectors} connector${props.connectors !== 1 ? 's' : ''}` : null,
    props.max_kw != null ? `${props.max_kw}kW max` : null,
    props.area_ha != null ? `${props.area_ha} ha` : null,
    props.dist_m ? `${props.dist_m}m away` : null,
  ].filter(Boolean);

  return `<div style="font-size:12px"><strong>${esc(String(props.name || ''))}</strong>${detailRows.length ? `<br>${detailRows.join('<br>')}` : ''}</div>`;
}

const OFSTED_PILL_COLOURS: Record<number, string> = {
  1: '#059669', 2: '#2563eb', 3: '#d97706', 4: '#dc2626',
};
const OFSTED_LABELS: Record<number, string> = {
  1: 'Outstanding', 2: 'Good', 3: 'Requires Improvement', 4: 'Inadequate',
};

function schoolPopupHtml(props: Record<string, unknown>): string {
  const name = esc(String(props.name || ''));

  // Line 2: Phase · Gender · Religious char · Age range
  const infoParts: string[] = [];
  if (props.phase) infoParts.push(esc(String(props.phase)));
  const gender = String(props.gender || '');
  if (gender && gender !== 'Mixed' && gender !== 'Not applicable') infoParts.push(esc(gender));
  const relig = String(props.religious_char || '');
  if (relig && relig !== 'Does not apply' && relig !== 'None') infoParts.push(esc(relig));
  if (props.age_low != null && props.age_high != null) infoParts.push(`${props.age_low}\u2013${props.age_high}`);

  // Line 3: Ofsted pill + date
  const ofstedNum = Number(props.ofsted);
  let ofstedHtml = '';
  if (OFSTED_LABELS[ofstedNum]) {
    const col = OFSTED_PILL_COLOURS[ofstedNum];
    const label = OFSTED_LABELS[ofstedNum];
    const dateStr = props.ofsted_date
      ? ` (${new Date(String(props.ofsted_date)).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })})`
      : '';
    ofstedHtml = `<span style="display:inline-block;background:${col};color:#fff;font-weight:600;font-size:10px;padding:1px 6px;border-radius:3px">${label}</span><span style="color:#888;font-size:10px">${dateStr}</span>`;
  }

  // Line 4: Admissions policy (only if notable)
  const policy = String(props.admissions_policy || '');
  const policyHtml = (policy && policy !== 'Not applicable' && policy !== 'Comprehensive')
    ? `<span style="display:inline-block;background:#f0f0ff;color:#4338ca;font-size:10px;padding:1px 5px;border-radius:3px;font-weight:500">${esc(policy)}</span>`
    : '';

  // Line 5: SEN provisions + special school badge
  const typeCode = String(props.type_code || '').toLowerCase();
  const isSpecial = typeCode.includes('special');
  let senHtml = '';
  const senProvisions = Array.isArray(props.sen_provisions) ? props.sen_provisions as Record<string, unknown>[] : [];
  if (isSpecial || senProvisions.length > 0) {
    const badges: string[] = [];
    if (isSpecial) {
      badges.push('<span style="display:inline-block;background:#7c3aed;color:#fff;font-size:9px;padding:1px 5px;border-radius:3px;font-weight:600">Special School</span>');
    }
    for (const p of senProvisions) {
      const pType = String(p.type || '');
      if (pType === 'SEN unit') {
        badges.push('<span style="display:inline-block;background:#6d28d9;color:#fff;font-size:9px;padding:1px 5px;border-radius:3px;font-weight:500">SEN Unit</span>');
      } else if (pType === 'Resourced provision') {
        badges.push('<span style="display:inline-block;background:#8b5cf6;color:#fff;font-size:9px;padding:1px 5px;border-radius:3px;font-weight:500">Resourced Prov.</span>');
      }
      const specs = Array.isArray(p.specialisms) ? (p.specialisms as string[]) : [];
      for (const spec of specs) {
        // Shorten "ASD - Autistic Spectrum Disorder" to "ASD"
        const short = String(spec).split(' - ')[0].trim();
        if (short) badges.push(`<span style="display:inline-block;background:#ede9fe;color:#5b21b6;font-size:9px;padding:0 4px;border-radius:2px">${esc(short)}</span>`);
      }
      if (p.capacity != null && Number(p.capacity) > 0) {
        badges.push(`<span style="color:#7c3aed;font-size:9px">${p.capacity} places</span>`);
      }
    }
    if (badges.length) senHtml = badges.join(' ');
  }
  // SEN demographics
  let senDemHtml = '';
  if (props.pct_sen_ehcp != null && Number(props.pct_sen_ehcp) > 0) {
    const parts: string[] = [];
    if (props.pct_sen_support != null) parts.push(`SEN Support: ${Number(props.pct_sen_support).toFixed(0)}%`);
    parts.push(`EHCP: ${Number(props.pct_sen_ehcp).toFixed(0)}%`);
    senDemHtml = `<span style="color:#7c3aed;font-size:10px">${parts.join(' · ')}</span>`;
  }

  // Line 6: Academic scores (phase-aware) + FSM%
  const scoreParts: string[] = [];
  const phase = String(props.phase || '').toLowerCase();
  if (phase.includes('primary') && props.ks2_rwm_expected != null) {
    scoreParts.push(`KS2: ${Number(props.ks2_rwm_expected).toFixed(0)}%`);
  }
  if ((phase.includes('secondary') || phase.includes('all')) && props.progress_8 != null) {
    const p8 = Number(props.progress_8);
    scoreParts.push(`P8: ${p8 >= 0 ? '+' : ''}${p8.toFixed(2)}`);
  }
  if ((phase.includes('secondary') || phase.includes('all')) && props.attainment_8 != null) {
    scoreParts.push(`A8: ${Number(props.attainment_8).toFixed(1)}`);
  }
  if (props.pct_fsm != null) {
    scoreParts.push(`FSM: ${Number(props.pct_fsm).toFixed(0)}%`);
  }

  // Line 6: LDO + SIF
  let ldoHtml = '';
  if (props.la_ldo != null) {
    const val = Number(props.la_ldo);
    const unit = String(props.la_ldo_unit || '');
    let formatted: string;
    if (unit === 'miles') formatted = `${val.toFixed(2)} mi`;
    else if (unit === 'metres') formatted = `${Math.round(val)} m`;
    else if (unit === 'km') formatted = `${val.toFixed(2)} km`;
    else formatted = val.toFixed(2);
    ldoHtml = `LDO: <strong>${formatted}</strong>`;
    if (props.la_sif) {
      ldoHtml += ` <span style="display:inline-block;background:#fef3c7;color:#92400e;font-size:9px;padding:0 4px;border-radius:2px;font-weight:600">SIF</span>`;
    }
  } else if (props.la_sif) {
    ldoHtml = `<span style="display:inline-block;background:#fef3c7;color:#92400e;font-size:9px;padding:0 4px;border-radius:2px;font-weight:600">SIF Required</span>`;
  }

  // Line 7: Velocity + distance + capacity
  const footerParts: string[] = [];
  const vel = String(props.velocity || '');
  if (vel === 'rising') footerParts.push('<span style="color:#059669">&#8599; Rising</span>');
  else if (vel === 'declining') footerParts.push('<span style="color:#dc2626">&#8600; Declining</span>');
  if (props.capacity != null) footerParts.push(`${props.capacity} pupils`);
  if (props.dist_m != null) {
    const d = Number(props.dist_m);
    footerParts.push(d < 1000 ? `${d}m away` : `${(d / 1000).toFixed(1)}km away`);
  }
  // Sixth form / nursery flags
  const flags: string[] = [];
  if (props.sixth_form === 'Has a sixth form') flags.push('6th Form');
  if (props.nursery_provision === 'Has Nursery Classes') flags.push('Nursery');
  const flagsHtml = flags.length
    ? flags.map(f => `<span style="display:inline-block;background:#f0fdf4;color:#166534;font-size:9px;padding:0 4px;border-radius:2px">${f}</span>`).join(' ')
    : '';

  // Assemble
  const lines: string[] = [];
  lines.push(`<strong>${name}</strong>`);
  if (infoParts.length) lines.push(`<span style="color:#666">${infoParts.join(' · ')}</span>`);
  if (ofstedHtml) lines.push(ofstedHtml);
  if (policyHtml || flagsHtml) lines.push([policyHtml, flagsHtml].filter(Boolean).join(' '));
  if (senHtml) lines.push(senHtml);
  if (senDemHtml) lines.push(senDemHtml);
  if (scoreParts.length) lines.push(`<span style="color:#555">${scoreParts.join(' · ')}</span>`);
  if (ldoHtml) lines.push(ldoHtml);
  if (footerParts.length) lines.push(`<span style="color:#888;font-size:10px">${footerParts.join(' · ')}</span>`);

  return `<div style="font-size:11px;line-height:1.5">${lines.join('<br>')}</div>`;
}

function soldPricePopupHtml(props: Record<string, unknown>): string {
  const bedStr = props.bedrooms != null ? `${props.bedrooms} bed (est.)` : '';
  const floorStr = props.floor_area_sqm != null ? `${Math.round(Number(props.floor_area_sqm))} m²` : '';
  const typeStr = props.property_type ? esc(String(props.property_type)) : '';
  const tenureStr = props.tenure ? esc(String(props.tenure)) : '';
  const detailParts = [typeStr, tenureStr, bedStr, floorStr].filter(Boolean);

  const dateStr = props.date
    ? new Date(String(props.date)).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
    : '';
  const priceStr = formatPrice(props.price as number);

  const epcRating = props.epc_rating ? String(props.epc_rating) : null;
  const epcColour = epcRating ? (EPC_COLOURS[epcRating] || '#888') : null;
  const hasEstimate = props.bedrooms != null;

  return `<div style="font-size:12px">
    <strong>${esc(String(props.name || ''))}</strong>
    ${detailParts.length ? `<br>${detailParts.join(' · ')}` : ''}
    ${dateStr || priceStr ? `<br>Last sold: ${dateStr}${dateStr && priceStr ? ', ' : ''}${priceStr ? `<span style="font-weight:700">${priceStr}</span>` : ''}` : ''}
    ${epcRating ? `<br><span style="display:inline-block;background:${epcColour};color:${epcRating === 'D' ? '#333' : '#fff'};font-weight:700;font-size:10px;padding:1px 6px;border-radius:3px;vertical-align:middle">EPC ${epcRating}</span>` : ''}
    ${props.actual_psf ? `<br>£${Number(props.actual_psf).toLocaleString('en-GB')}/sqft` : ''}
    ${props.dist_m ? `<br><span style="color:#888">${esc(String(props.dist_m))}m away</span>` : ''}
    ${hasEstimate ? `<br><span style="color:#aaa;font-size:10px">* Bedroom count estimated from total habitable rooms (EPC data)</span>` : ''}
  </div>`;
}

export default function MapView({ lat, lon, boundary, lsoaBoundary, pois, activeTab, visibleLayers = {}, searchLsoa, initialViewport, onViewportChange, choroplethData, choroplethUrl, onMapReady, onHighlightReady, onPropertySelect, selectedPropertyParcel }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  // Separate marker refs: sold prices (clustered, re-rendered on zoom) vs other POIs (static)
  const soldMarkersRef = useRef<maplibregl.Marker[]>([]);
  const poiMarkersRef = useRef<maplibregl.Marker[]>([]);

  // Temporary highlight marker for transactions not in the current map POI set
  const highlightMarkerRef = useRef<maplibregl.Marker | null>(null);

  // Supercluster index and filtered features
  const clusterIndexRef = useRef<Supercluster | null>(null);
  const renderSoldPriceMarkersRef = useRef<((map: maplibregl.Map) => void) | null>(null);

  // Spider fan-out state for overlapping markers
  const spiderRef = useRef<{
    markers: maplibregl.Marker[];
    layerId: string | null;
    center: [number, number] | null;
    leaves: Supercluster.PointFeature<Record<string, unknown>>[] | null;
  }>({
    markers: [], layerId: null, center: null, leaves: null,
  });

  // Store onMapReady callback in a ref so it's available inside the load handler
  const onMapReadyRef = useRef(onMapReady);
  onMapReadyRef.current = onMapReady;
  const onHighlightReadyRef = useRef(onHighlightReady);
  onHighlightReadyRef.current = onHighlightReady;

  // Track previous tab to detect tab changes (for stale marker cleanup)
  const prevTabRef = useRef(activeTab);

  // R10: guard sold price marker rebuild when pois + all filter inputs are unchanged
  const lastRenderedPoisRef = useRef<GeoJSON.FeatureCollection | null | undefined>(undefined);
  const lastRenderedLayersRef = useRef<Record<string, boolean> | undefined>(undefined);
  const lastRenderedLsoaRef = useRef<string | undefined>(undefined);

  // Store choropleth event handlers for cleanup
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cleanupHandlersRef = useRef<{ clickHandler: any; enterHandler: any; leaveHandler: any; moveHandler?: any } | null>(null);
  const hoveredFeatureIdRef = useRef<string | null>(null);
  // hoverPopupRef removed — hover info now shown in the legend

  // Keep refs so the map on('load') callback and moveend handler can read current values
  const activeTabRef = useRef(activeTab);
  useEffect(() => { activeTabRef.current = activeTab; }, [activeTab]);
  const poisRef = useRef(pois);
  useEffect(() => { poisRef.current = pois; }, [pois]);
  const visibleLayersRef = useRef(visibleLayers);
  useEffect(() => { visibleLayersRef.current = visibleLayers; }, [visibleLayers]);
  const searchLsoaRef = useRef(searchLsoa);
  useEffect(() => { searchLsoaRef.current = searchLsoa; }, [searchLsoa]);
  const onViewportChangeRef = useRef(onViewportChange);
  useEffect(() => { onViewportChangeRef.current = onViewportChange; }, [onViewportChange]);
  const initialViewportRef = useRef(initialViewport);
  useEffect(() => { initialViewportRef.current = initialViewport; }, [initialViewport]);
  const boundaryRef = useRef(boundary);
  useEffect(() => { boundaryRef.current = boundary; }, [boundary]);
  const lsoaBoundaryRef = useRef(lsoaBoundary);
  useEffect(() => { lsoaBoundaryRef.current = lsoaBoundary; }, [lsoaBoundary]);
  const onPropertySelectRef = useRef(onPropertySelect);
  useEffect(() => { onPropertySelectRef.current = onPropertySelect; }, [onPropertySelect]);
  const selectedPropertyParcelRef = useRef(selectedPropertyParcel);
  useEffect(() => { selectedPropertyParcelRef.current = selectedPropertyParcel; }, [selectedPropertyParcel]);

  const applyIsochronesToMap = useCallback((map: maplibregl.Map, tab: string | undefined, latVal: number, lonVal: number) => {
    ISOCHRONE_LAYERS.forEach((l) => { if (map.getLayer(l)) map.removeLayer(l); });
    ISOCHRONE_SOURCES.forEach((s) => { if (map.getSource(s)) map.removeSource(s); });
    if (tab !== 'Lifestyle & Connectivity') return;
    const rings = [
      { id: 'iso-15', metres: 1250, colour: '#16a34a', label: '15 min walk' },
      { id: 'iso-10', metres: 833,  colour: '#ca8a04', label: '10 min walk' },
      { id: 'iso-5',  metres: 417,  colour: '#dc2626', label: '5 min walk' },
    ];
    rings.forEach(({ id, metres, colour, label }) => {
      map.addSource(id, { type: 'geojson', data: createCircle(lonVal, latVal, metres) });
      map.addLayer({ id: `${id}-fill`, type: 'fill', source: id, paint: { 'fill-color': colour, 'fill-opacity': 0.05 } });
      map.addLayer({ id: `${id}-line`, type: 'line', source: id, paint: { 'line-color': colour, 'line-width': 1.5, 'line-dasharray': [4, 3], 'line-opacity': 0.7 } });
      // Label at the east point of the circle
      const dLon = (metres / 1000) / (111.32 * Math.cos((latVal * Math.PI) / 180));
      map.addSource(`${id}-pt`, { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [lonVal + dLon, latVal] } } });
      map.addLayer({ id: `${id}-label`, type: 'symbol', source: `${id}-pt`, layout: { 'text-field': label, 'text-size': 11, 'text-anchor': 'left', 'text-offset': [0.5, 0] }, paint: { 'text-color': colour, 'text-halo-color': '#fff', 'text-halo-width': 1.5 } });
    });
  }, []);

  /** Remove spider markers and leg lines only (keep center/leaves for re-render) */
  const removeSpiderVisuals = useCallback((map: maplibregl.Map) => {
    spiderRef.current.markers.forEach((m) => m.remove());
    spiderRef.current.markers = [];
    if (spiderRef.current.layerId) {
      try {
        if (map.getLayer(spiderRef.current.layerId)) map.removeLayer(spiderRef.current.layerId);
        if (map.getSource(spiderRef.current.layerId)) map.removeSource(spiderRef.current.layerId);
      } catch { /* layer already removed */ }
      spiderRef.current.layerId = null;
    }
  }, []);

  /** Fully clear spider state (visuals + stored center/leaves) */
  const clearSpider = useCallback((map: maplibregl.Map) => {
    removeSpiderVisuals(map);
    spiderRef.current.center = null;
    spiderRef.current.leaves = null;
  }, [removeSpiderVisuals]);

  /** Render spider visuals from stored center + leaves at current zoom */
  const renderSpiderVisuals = useCallback((map: maplibregl.Map) => {
    const { center, leaves } = spiderRef.current;
    if (!center || !leaves || leaves.length === 0) return;

    removeSpiderVisuals(map);

    const count = leaves.length;
    const zoom = map.getZoom();

    // Convert a fixed pixel radius to degrees at current zoom
    const pixelRadius = 40 + Math.min(count, 20) * 3;
    const metersPerPixel =
      (40075016.686 * Math.cos((center[1] * Math.PI) / 180)) /
      (256 * Math.pow(2, zoom));
    const degOffset = (pixelRadius * metersPerPixel) / 111320;

    const legFeatures: GeoJSON.Feature[] = [];

    for (let i = 0; i < count; i++) {
      const angle = (2 * Math.PI * i) / count - Math.PI / 2;
      const offsetLng = center[0] + degOffset * Math.cos(angle);
      const offsetLat = center[1] + degOffset * Math.sin(angle);

      const props = leaves[i].properties || {};
      const el = createPricePillElement(
        props.price as number,
        props.property_type as string | undefined,
      );
      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([offsetLng, offsetLat])
        .setPopup(
          new maplibregl.Popup({ offset: 12, maxWidth: '220px' }).setHTML(
            soldPricePopupHtml(props),
          ),
        )
        .addTo(map);
      spiderRef.current.markers.push(marker);

      legFeatures.push({
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: [center, [offsetLng, offsetLat]],
        },
        properties: {},
      });
    }

    const legId = 'spider-legs';
    // Safety: remove stale source/layer if removal previously failed
    try {
      if (map.getLayer(legId)) map.removeLayer(legId);
      if (map.getSource(legId)) map.removeSource(legId);
    } catch { /* already clean */ }
    map.addSource(legId, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: legFeatures },
    });
    map.addLayer({
      id: legId,
      type: 'line',
      source: legId,
      paint: {
        'line-color': '#888',
        'line-width': 1,
        'line-dasharray': [2, 2],
      },
    });
    spiderRef.current.layerId = legId;
  }, [removeSpiderVisuals]);

  /** Render sold price markers from the current supercluster index at the map's current zoom/bounds */
  const renderSoldPriceMarkers = useCallback((map: maplibregl.Map) => {
    // Recycle old sold markers into DOM pool (but NOT the spider — it persists across zoom/pan)
    for (const m of soldMarkersRef.current) {
      const el = m.getElement();
      m.remove();
      // Recycle based on shape: cluster = round (border-radius 50%), pill = pill-shaped
      if (el.style.borderRadius === '50%') recycleCluster(el as HTMLDivElement);
      else recyclePill(el as HTMLDivElement);
    }
    soldMarkersRef.current = [];

    const index = clusterIndexRef.current;
    if (!index) return;

    // If spider is active, check if we should keep it or close it
    let spiderCenter = spiderRef.current.center;
    if (spiderCenter && spiderRef.current.leaves) {
      // Check if the spider center is still a "stuck" cluster at the current zoom.
      // If we zoomed out enough that it's now part of a bigger expandable cluster, close spider.
      const zoom = Math.floor(map.getZoom());
      const nearClusters = index.getClusters(
        [spiderCenter[0] - 0.001, spiderCenter[1] - 0.001,
         spiderCenter[0] + 0.001, spiderCenter[1] + 0.001],
        zoom,
      );
      const matchingCluster = nearClusters.find(
        (c) => c.properties?.cluster &&
          Math.abs(c.geometry.coordinates[0] - spiderCenter![0]) < 1e-4 &&
          Math.abs(c.geometry.coordinates[1] - spiderCenter![1]) < 1e-4,
      );
      if (matchingCluster && index.getClusterExpansionZoom(matchingCluster.properties!.cluster_id as number) <= 16) {
        // Zoomed out — cluster is now expandable normally. Close spider.
        clearSpider(map);
        spiderCenter = null;
      } else {
        // Still stuck or individual points — re-render spider at new zoom
        removeSpiderVisuals(map);
        renderSpiderVisuals(map);
      }
    }

    try {
      const bounds = map.getBounds();
      const zoom = Math.floor(map.getZoom());
      const clusters = index.getClusters(
        [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()],
        zoom,
      );

      // Cap individual (non-cluster) DOM markers to prevent mobile stutter
      const MAX_INDIVIDUAL_MARKERS = 150;
      let individualCount = 0;

      for (const feature of clusters) {
        const coords = feature.geometry.coordinates as [number, number];
        if (!coords || !Number.isFinite(coords[0]) || !Number.isFinite(coords[1])) continue;

        // Skip features at the spider center — they're shown as spider markers
        if (spiderCenter &&
            Math.abs(coords[0] - spiderCenter[0]) < 1e-4 &&
            Math.abs(coords[1] - spiderCenter[1]) < 1e-4) {
          continue;
        }

        const props = feature.properties || {};

        if (props.cluster) {
          // Cluster marker
          const count = props.point_count as number;
          const el = createClusterElement(count);
          const clusterId = props.cluster_id as number;
          el.addEventListener('click', () => {
            const expZoom = index.getClusterExpansionZoom(clusterId);
            if (expZoom > 16) {
              // All points overlap — fan them out in a spider pattern (cap at 30 to prevent DOM freeze)
              clearSpider(map);
              const leaves = index.getLeaves(clusterId, 30) as Supercluster.PointFeature<Record<string, unknown>>[];
              spiderRef.current.center = coords;
              spiderRef.current.leaves = leaves;
              renderSoldPriceMarkersRef.current?.(map);
            } else {
              clearSpider(map);
              map.flyTo({ center: coords, zoom: expZoom, duration: 500 });
            }
          });
          const marker = new maplibregl.Marker({ element: el })
            .setLngLat(coords)
            .addTo(map);
          soldMarkersRef.current.push(marker);
        } else {
          // Individual sold price pill — cap to prevent DOM churn on mobile
          if (individualCount >= MAX_INDIVIDUAL_MARKERS) continue;
          individualCount++;
          const el = createPricePillElement(props.price as number, props.property_type as string | undefined);
          const marker = new maplibregl.Marker({ element: el })
            .setLngLat(coords)
            .setPopup(new maplibregl.Popup({ offset: 12, maxWidth: '220px' }).setHTML(soldPricePopupHtml(props)))
            .addTo(map);
          soldMarkersRef.current.push(marker);
        }
      }
    } catch (err) {
      console.error('[MapView] renderSoldPriceMarkers error:', err);
    }
  }, [clearSpider, removeSpiderVisuals, renderSpiderVisuals]);

  useEffect(() => {
    renderSoldPriceMarkersRef.current = renderSoldPriceMarkers;
  }, [renderSoldPriceMarkers]);

  /** Render POI markers + flood zone polygons on the given map */
  const renderPoisOnMap = useCallback((
    map: maplibregl.Map,
    poisData: GeoJSON.FeatureCollection | null | undefined,
    layers: Record<string, boolean>,
    lsoaCode?: string,
  ) => {
    // Don't clear markers if no new data — keeps old markers visible during tab-switch loading
    if (!poisData?.features) return;

    // R10: skip full rebuild if pois + filter inputs are all unchanged
    // (lastRenderedPoisRef is reset to undefined by the effect when tab/layers/lsoa change)
    if (poisData === lastRenderedPoisRef.current) return;
    lastRenderedPoisRef.current = poisData;
    lastRenderedLayersRef.current = layers;
    lastRenderedLsoaRef.current = lsoaCode;

    // Clear old markers (new data is ready to render)
    soldMarkersRef.current.forEach((m) => m.remove());
    soldMarkersRef.current = [];
    poiMarkersRef.current.forEach((m) => m.remove());
    poiMarkersRef.current = [];
    clusterIndexRef.current = null;
    clearSpider(map);

    // Remove old flood zone layers/source
    const FLOOD_SOURCE = 'flood-zones';
    if (map.getLayer('flood-zones-fill')) map.removeLayer('flood-zones-fill');
    if (map.getLayer('flood-zones-line')) map.removeLayer('flood-zones-line');
    if (map.getSource(FLOOD_SOURCE)) map.removeSource(FLOOD_SOURCE);

    try {
      const wardOn = layers.ward_boundary !== false;
      const lsoaOn = layers.lsoa_boundary !== false;

      const visibleFeatures = poisData.features.filter((f) => {
        if (!f.geometry) return false;
        const cat = f.properties?.category;
        if (cat && layers[cat] === false) return false;
        if (cat === 'sold_price') {
          const inWard = f.properties?.in_ward;
          const inLsoa = lsoaCode && f.properties?.lsoa_code === lsoaCode;
          if (wardOn && lsoaOn) return true;
          if (wardOn) return inWard;
          if (lsoaOn && lsoaCode) return inLsoa;
          return true;
        }
        return true;
      });

      // Separate sold prices from other POIs
      const soldFeatures = visibleFeatures.filter(
        (f) => f.geometry.type === 'Point' && f.properties?.category === 'sold_price',
      );
      const otherPointFeatures = visibleFeatures.filter(
        (f) => f.geometry.type === 'Point' && f.properties?.category !== 'sold_price',
      );
      const polygonFeatures = visibleFeatures.filter(
        (f) => f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon',
      );

      // Build supercluster index for sold prices
      if (soldFeatures.length > 0) {
        const index = new Supercluster({ radius: 60, maxZoom: 16 });
        index.load(soldFeatures as Supercluster.PointFeature<Record<string, unknown>>[]);
        clusterIndexRef.current = index;
        renderSoldPriceMarkers(map);
      }

      // Render other POI markers with distinct icons per category
      const MAX_POI_MARKERS = 100;
      let poiCount = 0;
      for (const feature of otherPointFeatures) {
        if (poiCount >= MAX_POI_MARKERS) break;
        const coords = (feature.geometry as GeoJSON.Point).coordinates;
        if (!coords || coords.length < 2 || !Number.isFinite(coords[0]) || !Number.isFinite(coords[1])) continue;
        const [lng, lt] = coords as [number, number];
        const props = feature.properties || {};

        const isSchool = props.category === 'school';
        const ofstedNum = isSchool ? Number(props.ofsted) : NaN;
        const schoolTypeCode = isSchool ? String(props.type_code || '').toLowerCase() : '';
        const isSpecialSchool = schoolTypeCode.includes('special');
        const senProvs = Array.isArray(props.sen_provisions) ? props.sen_provisions as Record<string, unknown>[] : [];
        const hasSenUnit = senProvs.some(p => p.type === 'SEN unit' || p.type === 'Resourced provision');
        const colour = isSpecialSchool
          ? '#7c3aed' // purple-600 for special schools
          : isSchool && OFSTED_MARKER_COLOURS[ofstedNum]
            ? OFSTED_MARKER_COLOURS[ofstedNum]
            : POI_COLOURS[props.category] || '#6b7280';
        const borderColour = hasSenUnit && !isSpecialSchool ? '#7c3aed' : '#fff';
        const icon = POI_ICONS[props.category] || '●';
        const el = document.createElement('div');
        el.style.cssText = `width:24px;height:24px;border-radius:50%;background:${colour};color:#fff;font-size:13px;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,0.4);border:2px solid ${borderColour};`;
        el.textContent = icon;
        const popupHtml = isSchool ? schoolPopupHtml(props) : genericPoiPopupHtml(props);
        const popupWidth = isSchool ? '280px' : '200px';
        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([lng, lt])
          .setPopup(
            new maplibregl.Popup({ offset: 14, maxWidth: popupWidth }).setHTML(popupHtml),
          )
          .addTo(map);
        poiMarkersRef.current.push(marker);
        poiCount++;
      }

      // Flood zone polygons
      if (polygonFeatures.length > 0) {
        const floodCollection: GeoJSON.FeatureCollection = {
          type: 'FeatureCollection',
          features: polygonFeatures,
        };
        map.addSource(FLOOD_SOURCE, { type: 'geojson', data: floodCollection });
        map.addLayer({
          id: 'flood-zones-fill',
          type: 'fill',
          source: FLOOD_SOURCE,
          paint: { 'fill-color': '#3b82f6', 'fill-opacity': 0.2 },
        });
        map.addLayer({
          id: 'flood-zones-line',
          type: 'line',
          source: FLOOD_SOURCE,
          paint: { 'line-color': '#1d4ed8', 'line-width': 1.5, 'line-opacity': 0.8 },
        });
      }
    } catch (err) {
      console.error('[MapView] renderPoisOnMap error:', err);
    }
  }, [clearSpider, renderSoldPriceMarkers]);

  // Reactive effect: handles tab switches on an already-loaded map
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (!map.isStyleLoaded()) return;
    applyIsochronesToMap(map, activeTab, lat, lon);
  }, [activeTab, applyIsochronesToMap, lat, lon]);

  // Update LSOA boundary layer when lsoaBoundary changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const applyLsoaBoundary = () => {
      const SOURCE = 'lsoa-boundary';
      if (map.getSource(SOURCE)) {
        (map.getSource(SOURCE) as maplibregl.GeoJSONSource).setData(
          lsoaBoundary ?? { type: 'FeatureCollection', features: [] }
        );
      } else if (lsoaBoundary && lsoaBoundary.geometry) {
        map.addSource(SOURCE, { type: 'geojson', data: lsoaBoundary });
        map.addLayer({
          id: 'lsoa-boundary-fill',
          type: 'fill',
          source: SOURCE,
          paint: { 'fill-color': '#7c3aed', 'fill-opacity': 0.12 },
        });
        map.addLayer({
          id: 'lsoa-boundary-line',
          type: 'line',
          source: SOURCE,
          paint: {
            'line-color': '#7c3aed',
            'line-width': 1.5,
            'line-dasharray': [3, 2],
            'line-opacity': 0.8,
          },
        });
      }
    };

    if (!map.isStyleLoaded()) {
      map.once('load', applyLsoaBoundary);
      return () => { map.off('load', applyLsoaBoundary); };
    }
    applyLsoaBoundary();
  }, [lsoaBoundary]);

  // Update ward boundary layer when boundary arrives or changes (avoids re-creating the map)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const applyBoundary = () => {
      const WARD_SOURCE = 'ward-boundary';
      const RADIUS_SOURCE = 'radius';

      if (map.getSource(WARD_SOURCE)) {
        // Source already exists — update its data
        (map.getSource(WARD_SOURCE) as maplibregl.GeoJSONSource).setData(
          boundary ?? { type: 'FeatureCollection', features: [] }
        );
        if (boundary && boundary.geometry) {
          const coords = getAllCoords(boundary.geometry);
          if (coords.length > 0) {
            const bounds = new maplibregl.LngLatBounds(coords[0], coords[0]);
            coords.forEach((c) => bounds.extend(c));
            map.fitBounds(bounds, { padding: 40, maxZoom: 15 });
          }
        }
      } else if (boundary && boundary.geometry) {
        // Source doesn't exist yet — boundary arrived after map creation
        // Remove fallback radius circle if present
        if (map.getLayer('radius-fill')) map.removeLayer('radius-fill');
        if (map.getLayer('radius-line')) map.removeLayer('radius-line');
        if (map.getSource(RADIUS_SOURCE)) map.removeSource(RADIUS_SOURCE);

        map.addSource(WARD_SOURCE, { type: 'geojson', data: boundary });
        map.addLayer({
          id: 'ward-boundary-fill',
          type: 'fill',
          source: WARD_SOURCE,
          paint: { 'fill-color': '#2563eb', 'fill-opacity': 0.06 },
        });
        map.addLayer({
          id: 'ward-boundary-line',
          type: 'line',
          source: WARD_SOURCE,
          paint: { 'line-color': '#2563eb', 'line-width': 2.5, 'line-opacity': 0.7 },
        });

        // Fit to boundary (only on first arrival, not when restoring viewport)
        if (!initialViewportRef.current) {
          const coords = getAllCoords(boundary.geometry);
          if (coords.length > 0) {
            const bounds = new maplibregl.LngLatBounds(coords[0], coords[0]);
            coords.forEach((c) => bounds.extend(c));
            map.fitBounds(bounds, { padding: 40, maxZoom: 15 });
          }
        }
      }
    };

    if (!map.isStyleLoaded()) {
      map.once('load', applyBoundary);
      return () => { map.off('load', applyBoundary); };
    }
    applyBoundary();
  }, [boundary]);

  // Update POI markers + flood zone polygons when pois, visibility, searchLsoa, or tab change
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // If style not loaded yet, defer until it is. The 'load' event only fires once in the
    // map's lifetime, so use 'idle' which fires whenever the map finishes rendering.
    // This handles the case where tiles are briefly reloading when pois data arrives.
    if (!map.isStyleLoaded()) {
      const onIdle = () => {
        if (!map.isStyleLoaded()) return;  // still not ready, wait for next idle
        map.off('idle', onIdle);  // one-shot: remove after first successful fire
        const tc = prevTabRef.current !== activeTab;
        prevTabRef.current = activeTab;
        if (tc || searchLsoa !== lastRenderedLsoaRef.current || visibleLayers !== lastRenderedLayersRef.current) {
          lastRenderedPoisRef.current = undefined;
        }
        if (!POI_TABS.includes(activeTab || '')) return;
        renderPoisOnMap(map, pois, visibleLayers, searchLsoa);
      };
      map.on('idle', onIdle);
      return () => { map.off('idle', onIdle); };
    }

    const tabChanged = prevTabRef.current !== activeTab;
    prevTabRef.current = activeTab;

    // R10: reset pois guard when non-pois inputs change so rebuild still happens
    if (tabChanged || searchLsoa !== lastRenderedLsoaRef.current || visibleLayers !== lastRenderedLayersRef.current) {
      lastRenderedPoisRef.current = undefined;
    }

    // Helper: clear all markers + flood zone layers
    const clearAll = () => {
      soldMarkersRef.current.forEach((m) => m.remove());
      soldMarkersRef.current = [];
      poiMarkersRef.current.forEach((m) => m.remove());
      poiMarkersRef.current = [];
      clusterIndexRef.current = null;
      clearSpider(map);
      if (map.getLayer('flood-zones-fill')) map.removeLayer('flood-zones-fill');
      if (map.getLayer('flood-zones-line')) map.removeLayer('flood-zones-line');
      if (map.getSource('flood-zones')) map.removeSource('flood-zones');
    };

    // If tab doesn't fetch POIs (Local Governance), clear everything
    if (!POI_TABS.includes(activeTab || '')) {
      clearAll();
      return;
    }

    // If tab changed but new data hasn't arrived yet, clear stale markers from old tab
    // (prevents flood zones / old POIs lingering during loading gap)
    if (tabChanged && !pois?.features) {
      clearAll();
      return;
    }

    renderPoisOnMap(map, pois, visibleLayers, searchLsoa);
  }, [activeTab, clearSpider, pois, renderPoisOnMap, searchLsoa, visibleLayers]);

  // Choropleth rendering
  const choroplethLegendRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const CHORO_SOURCE = 'choropleth';
    const CHORO_FILL = 'choropleth-fill';
    const CHORO_LINE = 'choropleth-line';

    const cleanup = () => {
      try {
        if (map.getLayer(CHORO_FILL)) map.removeLayer(CHORO_FILL);
        if (map.getLayer(CHORO_LINE)) map.removeLayer(CHORO_LINE);
        if (map.getSource(CHORO_SOURCE)) map.removeSource(CHORO_SOURCE);
      } catch { /* map may be removed */ }
      if (choroplethLegendRef.current) {
        choroplethLegendRef.current.remove();
        choroplethLegendRef.current = null;
      }
    };

    // If map style not loaded yet, wait for it then re-trigger via a one-shot listener
    if (!map.isStyleLoaded()) {
      const m = map;
      const onLoad = () => { cleanup(); applyChoropleth(m); };
      m.once('load', onLoad);
      return () => { m.off('load', onLoad); cleanup(); };
    }

    cleanup();
    applyChoropleth(map);

    function applyChoropleth(m: maplibregl.Map) {
      if (!choroplethData || !choroplethData.features?.length) return;

      const meta = choroplethData.metadata;
      const ramp = CHOROPLETH_RAMPS[meta.layer] || CHOROPLETH_RAMPS.avg_price;
      const noDataColour = '#d1d5db';
      const legendUnit = CHOROPLETH_UNITS[meta.layer] || meta.unit || '';

      // Build match expression: quantile → colour
      // Determine actual bucket count from data (may be <5 if few unique values)
      const usedBuckets = new Set<number>();
      for (const f of choroplethData.features) {
        const q = f.properties?.quantile;
        if (typeof q === 'number' && q >= 0) usedBuckets.add(q);
      }
      const maxBucket = usedBuckets.size > 0 ? Math.max(...usedBuckets) + 1 : 5;
      const bucketCount = Math.min(Math.max(maxBucket, 1), 5);
      const matchExpr: unknown[] = ['match', ['get', 'quantile']];
      for (let i = 0; i < bucketCount; i++) {
        // Map bucket i to evenly-spaced colour from the 5-colour ramp
        // When only 1 bucket (all values identical), use the middle colour so it's visible
        const colourIdx = bucketCount === 1 ? 2 : (bucketCount < 5 ? Math.round(i * 4 / (bucketCount - 1)) : i);
        matchExpr.push(i, ramp[colourIdx]);
      }
      matchExpr.push(noDataColour); // fallback for -1 / null

      try {
        // R2: use URL when available so MapLibre fetches + parses GeoJSON off the main thread
        const sourceData = choroplethUrl ?? (choroplethData as GeoJSON.FeatureCollection);
        m.addSource(CHORO_SOURCE, { type: 'geojson', data: sourceData, promoteId: 'lsoa_code' });

        // Insert below boundary layers so they remain visible on top
        const beforeLayer = m.getLayer('lsoa-boundary-fill')
          ? 'lsoa-boundary-fill'
          : m.getLayer('ward-boundary-fill')
            ? 'ward-boundary-fill'
            : undefined;

        m.addLayer({
          id: CHORO_FILL,
          type: 'fill',
          source: CHORO_SOURCE,
          paint: {
            'fill-color': matchExpr as unknown as string,
            'fill-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.9, 0.55] as unknown as number,
          },
        }, beforeLayer);

        m.addLayer({
          id: CHORO_LINE,
          type: 'line',
          source: CHORO_SOURCE,
          paint: { 'line-color': '#ffffff', 'line-width': 0.5, 'line-opacity': 0.7 },
        }, beforeLayer);
      } catch (err) {
        console.error('[MapView] choropleth layer error:', err);
        return;
      }

      // Format a choropleth value for display (used by legend, hover info, and click popup)
      const fmtVal = (v: number | null): string => {
        if (v == null) return 'n/a';
        if (meta.layer === 'epc_score') return `${Math.round(v)}`;
        if (legendUnit === '%') return `${Number(v).toFixed(1)}%`;
        if (legendUnit === 'score') return Number(v).toFixed(1);
        if (legendUnit === 'years') return `${Number(v).toFixed(1)} years`;
        if (legendUnit === 'people/hectare') return `${Number(v).toFixed(1)} ppl/ha`;
        if (legendUnit === 'µg/m³') return `${Number(v).toFixed(1)} µg/m³`;
        if (meta.layer === 'price_per_sqft') return `£${Math.round(v).toLocaleString('en-GB')}`;
        if (meta.layer === 'median_rent') return `£${Math.round(v).toLocaleString('en-GB')}/mo`;
        if (meta.layer === 'council_tax' || meta.layer === 'median_earnings') return `£${Math.round(v).toLocaleString('en-GB')}`;
        if (v >= 1_000_000) return `£${(v / 1_000_000).toFixed(1)}m`;
        if (v >= 1_000) return `£${Math.round(v / 1_000)}k`;
        return `£${Math.round(v).toLocaleString('en-GB')}`;
      };

      // Click popup for LSOA details
      const clickHandler = (e: maplibregl.MapMouseEvent) => {
        try {
          if (!m.getLayer(CHORO_FILL)) return;
          const features = m.queryRenderedFeatures(e.point, { layers: [CHORO_FILL] });
          if (!features.length) return;
          const p = features[0].properties;
          if (!p) return;
          const valStr = p.value != null ? fmtVal(Number(p.value)) : 'No data';
          new maplibregl.Popup({ maxWidth: '200px' })
            .setLngLat(e.lngLat)
            .setHTML(`<div style="font-size:12px"><strong>${esc(String(p.lsoa_name || p.lsoa_code || ''))}</strong><br>${valStr}</div>`)
            .addTo(m);
        } catch { /* map may be disposed */ }
      };
      m.on('click', CHORO_FILL, clickHandler);

      // Hover highlight via feature-state + tooltip
      const enterHandler = () => { try { m.getCanvas().style.cursor = 'pointer'; } catch { /* */ } };
      const moveHandler = (e: maplibregl.MapMouseEvent) => {
        try {
          if (!m.getLayer(CHORO_FILL)) return;
          const features = m.queryRenderedFeatures(e.point, { layers: [CHORO_FILL] });

          // Clear previous hover
          if (hoveredFeatureIdRef.current !== null) {
            m.setFeatureState({ source: CHORO_SOURCE, id: hoveredFeatureIdRef.current }, { hover: false });
            hoveredFeatureIdRef.current = null;
          }

          // Update legend hover info
          const hoverEl = choroplethLegendRef.current?.querySelector('[data-hover-info]') as HTMLDivElement | null;

          if (!features.length) {
            m.getCanvas().style.cursor = '';
            if (hoverEl) hoverEl.style.display = 'none';
            return;
          }

          const feat = features[0];
          const fid = feat.properties?.lsoa_code ?? (feat.id != null ? String(feat.id) : null);
          if (fid) {
            hoveredFeatureIdRef.current = fid;
            m.setFeatureState({ source: CHORO_SOURCE, id: fid }, { hover: true });
          }

          // Show hovered value in the legend (not a floating tooltip)
          const p = feat.properties;
          if (p && hoverEl) {
            const valStr = p.value != null ? fmtVal(Number(p.value)) : 'No data';
            const name = String(p.lsoa_name || p.lsoa_code || '');
            hoverEl.innerHTML = `<strong>${esc(name)}</strong>&ensp;${valStr}`;
            hoverEl.style.display = 'block';
          }
        } catch { /* map may be disposed */ }
      };
      const leaveHandler = () => {
        try {
          m.getCanvas().style.cursor = '';
          if (hoveredFeatureIdRef.current !== null) {
            m.setFeatureState({ source: CHORO_SOURCE, id: hoveredFeatureIdRef.current }, { hover: false });
            hoveredFeatureIdRef.current = null;
          }
          const hoverEl = choroplethLegendRef.current?.querySelector('[data-hover-info]') as HTMLDivElement | null;
          if (hoverEl) hoverEl.style.display = 'none';
        } catch { /* */ }
      };
      m.on('mouseenter', CHORO_FILL, enterHandler);
      m.on('mousemove', CHORO_FILL, moveHandler);
      m.on('mouseleave', CHORO_FILL, leaveHandler);

      // Floating legend
      const legend = document.createElement('div');
      legend.style.cssText = `
        position: absolute; bottom: 8px; left: 8px; background: white;
        border-radius: 8px; padding: 8px 10px; font-size: 10px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.15); z-index: 5; pointer-events: none;
        width: 180px; word-wrap: break-word;
      `;
      const layerLabels: Record<string, string> = {
        avg_price: 'Average price',
        median_price: 'Median price',
        price_per_sqft: 'Price per sqft',
        epc_score: 'EPC score',
        population_density: 'Population density',
        median_age: 'Median age',
        household_composition: 'Family households',
        good_health: 'Good health',
        economically_active: 'Economically active',
        degree_educated: 'Degree educated',
        no_car: 'No-car households',
        born_abroad: 'Born abroad',
        housing_tenure: 'Owner-occupation',
        housing_type: 'Detached homes',
        household_size: 'One-person households',
        deprivation: 'Deprivation',
        deprivation_income: 'Income deprivation',
        deprivation_employment: 'Employment deprivation',
        deprivation_education: 'Education deprivation',
        deprivation_health: 'Health deprivation',
        deprivation_crime: 'Crime deprivation',
        deprivation_barriers: 'Barriers to housing and services',
        deprivation_living_environment: 'Living environment deprivation',
        broadband: 'Gigabit broadband',
        mobile_coverage: '4G outdoor coverage',
        air_quality_no2: 'NO2 pollution',
        air_quality_pm25: 'PM2.5 pollution',
        council_tax: 'Council tax',
        median_earnings: 'Median earnings',
        median_rent: 'Median rent',
      };
      const layerLabel = layerLabels[meta.layer] || formatLabel(meta.layer);

      const sameMinMax = meta.min_value != null && meta.max_value != null && meta.min_value === meta.max_value;
      legend.innerHTML = `
        <div style="font-weight:600;margin-bottom:4px">${layerLabel}</div>
        <div style="display:flex;gap:0;height:10px;border-radius:3px;overflow:hidden;margin-bottom:3px">
          ${ramp.map((c) => `<div style="flex:1;background:${c}"></div>`).join('')}
        </div>
        ${sameMinMax
          ? `<div style="text-align:center;color:#666">Uniform: ${fmtVal(meta.min_value)}</div>`
          : `<div style="display:flex;justify-content:space-between;color:#666">
              <span>${fmtVal(meta.min_value)}</span><span>${fmtVal(meta.max_value)}</span>
            </div>`
        }
        <div data-hover-info style="display:none;margin-top:5px;padding-top:5px;border-top:1px solid #e2e8f0;font-size:11px;color:#334155"></div>
      `;
      containerRef.current?.appendChild(legend);
      choroplethLegendRef.current = legend;

      // Store handlers for cleanup
      cleanupHandlersRef.current = { clickHandler, enterHandler, leaveHandler, moveHandler };
    }

    return () => {
      const h = cleanupHandlersRef.current;
      if (h) {
        try {
          map.off('click', CHORO_FILL, h.clickHandler);
          map.off('mouseenter', CHORO_FILL, h.enterHandler);
          if (h.moveHandler) map.off('mousemove', CHORO_FILL, h.moveHandler);
          map.off('mouseleave', CHORO_FILL, h.leaveHandler);
        } catch { /* map may be removed */ }
        cleanupHandlersRef.current = null;
      }
      hoveredFeatureIdRef.current = null;
      cleanup();
    };
  }, [choroplethData, choroplethUrl]);

  // Toggle boundary layer visibility
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const wardVis = visibleLayers.ward_boundary !== false ? 'visible' : 'none';
    const lsoaVis = visibleLayers.lsoa_boundary !== false ? 'visible' : 'none';

    for (const id of ['ward-boundary-fill', 'ward-boundary-line']) {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', wardVis);
    }
    for (const id of ['lsoa-boundary-fill', 'lsoa-boundary-line']) {
      if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', lsoaVis);
    }
  }, [visibleLayers]);

  useEffect(() => {
    if (!containerRef.current) return;

    // Use restored viewport if available, otherwise default
    const restoredViewport = initialViewportRef.current;
    const useViewport = restoredViewport != null;
    const mapCenter: [number, number] = useViewport ? restoredViewport.center : [lon, lat];
    const mapZoom = useViewport ? restoredViewport.zoom : 14;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          },
        },
        layers: [
          { id: 'osm-tiles', type: 'raster', source: 'osm', minzoom: 0, maxzoom: 19 },
        ],
      },
      center: mapCenter,
      zoom: mapZoom,
      attributionControl: { compact: true },
      cooperativeGestures: true,
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    // Re-render sold price clusters on zoom/pan change (debounced to avoid churn during pinch-zoom)
    let moveendTimer: ReturnType<typeof setTimeout> | null = null;
    map.on('moveend', () => {
      if (moveendTimer) clearTimeout(moveendTimer);
      moveendTimer = setTimeout(() => {
        if (clusterIndexRef.current) {
          // Skip re-render if a sold-price popup is currently open — destroying the marker
          // mid-popup causes the map to jump (popup loses anchor → flies to [0,0])
          const hasOpenPopup = soldMarkersRef.current.some(
            (m) => m.getPopup()?.isOpen(),
          ) || spiderRef.current.markers.some(
            (m) => m.getPopup()?.isOpen(),
          );
          if (!hasOpenPopup) {
            renderSoldPriceMarkers(map);
          }
        }
        // Report viewport to parent for preservation across mount/unmount
        const c = map.getCenter();
        onViewportChangeRef.current?.({ center: [c.lng, c.lat], zoom: map.getZoom() });
      }, 100);
    });

    // Close spider when clicking empty map area
    map.on('click', (e: maplibregl.MapMouseEvent) => {
      // Only close if spider is active and click wasn't on a marker element
      if (spiderRef.current.center) {
        const target = e.originalEvent.target as HTMLElement;
        if (target === map.getCanvas()) {
          clearSpider(map);
          renderSoldPriceMarkers(map);
        }
      }
    });

    map.on('load', () => {
      // Walking isochrones
      applyIsochronesToMap(map, activeTabRef.current, lat, lon);

      // LSOA boundary
      const liveLsoaBoundary = lsoaBoundaryRef.current;
      if (liveLsoaBoundary && liveLsoaBoundary.geometry) {
        map.addSource('lsoa-boundary', { type: 'geojson', data: liveLsoaBoundary });
        map.addLayer({
          id: 'lsoa-boundary-fill',
          type: 'fill',
          source: 'lsoa-boundary',
          paint: { 'fill-color': '#7c3aed', 'fill-opacity': 0.12 },
        });
        map.addLayer({
          id: 'lsoa-boundary-line',
          type: 'line',
          source: 'lsoa-boundary',
          paint: {
            'line-color': '#7c3aed',
            'line-width': 1.5,
            'line-dasharray': [3, 2],
            'line-opacity': 0.8,
          },
        });
      }

      // Ward boundary polygon (reads from ref so boundary can arrive later without re-creating the map)
      const liveBoundary = boundaryRef.current;
      if (liveBoundary && liveBoundary.geometry) {
        map.addSource('ward-boundary', {
          type: 'geojson',
          data: liveBoundary,
        });
        map.addLayer({
          id: 'ward-boundary-fill',
          type: 'fill',
          source: 'ward-boundary',
          paint: {
            'fill-color': '#2563eb',
            'fill-opacity': 0.06,
          },
        });
        map.addLayer({
          id: 'ward-boundary-line',
          type: 'line',
          source: 'ward-boundary',
          paint: {
            'line-color': '#2563eb',
            'line-width': 2.5,
            'line-opacity': 0.7,
          },
        });

        // Fit map to boundary bounds (skip if restoring a saved viewport)
        if (!useViewport) {
          const coords = getAllCoords(liveBoundary.geometry);
          if (coords.length > 0) {
            const bounds = new maplibregl.LngLatBounds(coords[0], coords[0]);
            coords.forEach((c) => bounds.extend(c));
            map.fitBounds(bounds, { padding: 40, maxZoom: 15 });
          }
        }
      } else if (!useViewport) {
        // Fallback: 1km radius circle
        map.addSource('radius', {
          type: 'geojson',
          data: createCircle(lon, lat, 1000),
        });
        map.addLayer({
          id: 'radius-fill',
          type: 'fill',
          source: 'radius',
          paint: { 'fill-color': '#3b82f6', 'fill-opacity': 0.08 },
        });
        map.addLayer({
          id: 'radius-line',
          type: 'line',
          source: 'radius',
          paint: { 'line-color': '#3b82f6', 'line-width': 2, 'line-dasharray': [3, 2], 'line-opacity': 0.5 },
        });
      }

      // ── INSPIRE parcel polygons (vector tiles from Martin, z16+) ──
      const tilesBaseUrl = window.location.origin + '/tiles';
      map.addSource('inspire-parcels', {
        type: 'vector',
        tiles: [`${tilesBaseUrl}/core_inspire_parcels/{z}/{x}/{y}`],
        minzoom: 16,
        maxzoom: 22,
      });
      map.addLayer({
        id: 'inspire-parcels-fill',
        type: 'fill',
        source: 'inspire-parcels',
        'source-layer': 'core_inspire_parcels',
        minzoom: 16,
        paint: {
          'fill-color': '#3b82f6',
          'fill-opacity': ['interpolate', ['linear'], ['zoom'], 16, 0.04, 18, 0.08],
        },
      });
      map.addLayer({
        id: 'inspire-parcels-line',
        type: 'line',
        source: 'inspire-parcels',
        'source-layer': 'core_inspire_parcels',
        minzoom: 16,
        paint: {
          'line-color': '#3b82f6',
          'line-width': ['interpolate', ['linear'], ['zoom'], 16, 0.5, 18, 1.2],
          'line-opacity': 0.6,
        },
      });

      // ── Address point labels (vector tiles from Martin, z17+) ──
      map.addSource('address-points', {
        type: 'vector',
        tiles: [`${tilesBaseUrl}/address_points/{z}/{x}/{y}`],
        minzoom: 17,
        maxzoom: 22,
      });
      map.addLayer({
        id: 'address-labels',
        type: 'symbol',
        source: 'address-points',
        'source-layer': 'address_points',
        minzoom: 17,
        layout: {
          'text-field': ['coalesce', ['get', 'paon'], ''],
          'text-size': ['interpolate', ['linear'], ['zoom'], 17, 10, 19, 13],
          'text-anchor': 'center',
          'text-allow-overlap': false,
          'text-ignore-placement': false,
        },
        paint: {
          'text-color': '#1e293b',
          'text-halo-color': '#ffffff',
          'text-halo-width': 1.5,
        },
      });

      // ── Selected property parcel highlight (GeoJSON overlay) ──
      map.addSource('selected-parcel', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
      map.addLayer({
        id: 'selected-parcel-fill',
        type: 'fill',
        source: 'selected-parcel',
        paint: { 'fill-color': '#2563eb', 'fill-opacity': 0.2 },
      });
      map.addLayer({
        id: 'selected-parcel-line',
        type: 'line',
        source: 'selected-parcel',
        paint: { 'line-color': '#2563eb', 'line-width': 3, 'line-opacity': 0.9 },
      });

      // ── Click handler for INSPIRE parcels / address points → reverse geocode → property select ──
      const handleParcelOrAddressClick = async (e: maplibregl.MapMouseEvent) => {
        if (!onPropertySelectRef.current) return;
        const { lat: clickLat, lng: clickLng } = e.lngLat;
        try {
          const { fetchReverseGeocode } = await import('../api/client');
          const result = await fetchReverseGeocode(clickLat, clickLng);
          if (result.type === 'property' && result.property) {
            const p = result.property;
            const parts = [p.saon, p.paon, p.street, p.postcode].filter(Boolean);
            onPropertySelectRef.current({
              lat: p.lat,
              lon: p.lon,
              postcode: p.postcode,
              paon: p.paon,
              saon: p.saon,
              street: p.street,
              uprn: p.uprn,
              addressDisplay: parts.join(', '),
            });
          }
        } catch { /* ignore */ }
      };
      map.on('click', 'inspire-parcels-fill', handleParcelOrAddressClick);
      map.on('click', 'address-labels', handleParcelOrAddressClick);

      // Cursor change on hover over parcels / address labels
      map.on('mouseenter', 'inspire-parcels-fill', () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', 'inspire-parcels-fill', () => { map.getCanvas().style.cursor = ''; });
      map.on('mouseenter', 'address-labels', () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', 'address-labels', () => { map.getCanvas().style.cursor = ''; });

      // Apply initial selected parcel if available
      if (selectedPropertyParcelRef.current?.geometry) {
        (map.getSource('selected-parcel') as maplibregl.GeoJSONSource).setData(selectedPropertyParcelRef.current);
      }

      // Render any POIs that arrived before or during map creation
      renderPoisOnMap(map, poisRef.current, visibleLayersRef.current, searchLsoaRef.current);

      // Expose flyTo callback to parent
      onMapReadyRef.current?.((lng, lat, zoom) => {
        map.flyTo({ center: [lng, lat], zoom: zoom ?? 17, duration: 1000 });
      });

      // Expose highlight marker callback — shows a temporary pulsing marker
      // Call with (0,0) or any invalid coords to clear
      onHighlightReadyRef.current?.((lng, lat, props) => {
        // Remove previous highlight
        highlightMarkerRef.current?.remove();
        highlightMarkerRef.current = null;
        if (!lng && !lat) return; // clear-only call

        const el = document.createElement('div');
        el.className = 'map-highlight-marker';
        el.style.cssText = `
          width: 18px; height: 18px; border-radius: 50%;
          background: #0891b2; border: 3px solid white;
          box-shadow: 0 0 0 4px rgba(8,145,178,0.35), 0 2px 8px rgba(0,0,0,0.3);
          animation: highlight-pulse 1.5s ease-in-out 3;
          pointer-events: none;
        `;
        // Inject keyframes if not already present
        if (!document.getElementById('highlight-pulse-style')) {
          const style = document.createElement('style');
          style.id = 'highlight-pulse-style';
          style.textContent = `@keyframes highlight-pulse {
            0%, 100% { box-shadow: 0 0 0 4px rgba(8,145,178,0.35), 0 2px 8px rgba(0,0,0,0.3); }
            50% { box-shadow: 0 0 0 10px rgba(8,145,178,0.15), 0 2px 8px rgba(0,0,0,0.3); }
          }`;
          document.head.appendChild(style);
        }

        const marker = new maplibregl.Marker({ element: el }).setLngLat([lng, lat]);
        if (props) {
          marker.setPopup(
            new maplibregl.Popup({ offset: 14, maxWidth: '220px', closeButton: false })
              .setHTML(soldPricePopupHtml(props))
          );
        }
        marker.addTo(map);
        if (props) marker.togglePopup();
        highlightMarkerRef.current = marker;
      });
    });

    // R11: resize map whenever the container changes size (e.g. CSS Grid mobile animation)
    const ro = new ResizeObserver(() => { map.resize(); });
    ro.observe(containerRef.current!);

    mapRef.current = map;
    return () => {
      highlightMarkerRef.current?.remove();
      ro.disconnect(); map.remove(); mapRef.current = null;
      onMapReadyRef.current?.(null); onHighlightReadyRef.current?.(null);
    };
  // boundary + lsoaBoundary handled by their own effects; exclude from deps to avoid map recreation
  }, [applyIsochronesToMap, clearSpider, lat, lon, renderPoisOnMap, renderSoldPriceMarkers]);

  // Update selected property parcel overlay when it changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const src = map.getSource('selected-parcel') as maplibregl.GeoJSONSource | undefined;
    if (!src) return;
    if (selectedPropertyParcel?.geometry) {
      src.setData(selectedPropertyParcel);
    } else {
      src.setData({ type: 'FeatureCollection', features: [] });
    }
  }, [selectedPropertyParcel]);

  return <div ref={containerRef} className="w-full h-full" role="application" aria-label="Interactive map" />;
}

/** Extract all coordinate pairs from any GeoJSON geometry */
function getAllCoords(geometry: GeoJSON.Geometry): [number, number][] {
  const coords: [number, number][] = [];
  function extract(c: unknown) {
    if (Array.isArray(c)) {
      if (typeof c[0] === 'number' && typeof c[1] === 'number') {
        coords.push([c[0] as number, c[1] as number]);
      } else {
        c.forEach(extract);
      }
    }
  }
  if ('coordinates' in geometry) extract(geometry.coordinates);
  return coords;
}

/** Generate a GeoJSON circle polygon (approx) */
function createCircle(lon: number, lat: number, radiusM: number, steps = 64): GeoJSON.Feature {
  const coords: [number, number][] = [];
  const km = radiusM / 1000;
  for (let i = 0; i <= steps; i++) {
    const angle = (i / steps) * 2 * Math.PI;
    const dx = km * Math.cos(angle);
    const dy = km * Math.sin(angle);
    const dLat = dy / 110.574;
    const dLon = dx / (111.32 * Math.cos((lat * Math.PI) / 180));
    coords.push([lon + dLon, lat + dLat]);
  }
  return { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [coords] } };
}
