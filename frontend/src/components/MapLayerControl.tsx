import { useMemo, useState } from 'react';
import { Layers2, MapPinned, Sparkles } from 'lucide-react';

interface LayerDef {
  key: string;
  label: string;
  colour: string;
  group: 'data' | 'heatmap' | 'boundary';
  help: string;
}

const CHOROPLETH_KEYS = [
  'choropleth_avg_price',
  'choropleth_price_per_sqft',
  'choropleth_median_rent',
  'choropleth_epc_score',
  'choropleth_population_density',
  'choropleth_median_age',
  'choropleth_household_composition',
  'choropleth_good_health',
  'choropleth_economically_active',
  'choropleth_degree_educated',
  'choropleth_no_car',
  'choropleth_born_abroad',
  'choropleth_wfh',
  'choropleth_housing_tenure',
  'choropleth_housing_type',
  'choropleth_household_size',
  'choropleth_deprivation',
  'choropleth_deprivation_income',
  'choropleth_deprivation_employment',
  'choropleth_deprivation_education',
  'choropleth_deprivation_health',
  'choropleth_deprivation_crime',
  'choropleth_deprivation_barriers',
  'choropleth_deprivation_living_environment',
  'choropleth_broadband',
  'choropleth_full_fibre',
  'choropleth_superfast_broadband',
  'choropleth_mobile_coverage',
  'choropleth_mobile_4g_indoor',
  'choropleth_mobile_5g_outdoor',
  'choropleth_air_quality_no2',
  'choropleth_air_quality_pm25',
  'choropleth_council_tax',
  'choropleth_median_earnings',
];

const PROPERTY_TYPE_LEGEND = [
  { label: 'Detached', colour: '#2563eb' },
  { label: 'Semi-Detached', colour: '#16a34a' },
  { label: 'Terraced', colour: '#d97706' },
  { label: 'Flat', colour: '#9333ea' },
];

const TAB_LAYERS: Record<string, LayerDef[]> = {
  'Property & Market': [
    { key: 'sold_price', label: 'Sold prices', colour: '#0891b2', group: 'data', help: 'Shows recent nearby transactions as point markers.' },
    { key: 'choropleth_avg_price', label: 'Average price heatmap', colour: '#ef4444', group: 'heatmap', help: 'Shows how average prices vary across nearby areas.' },
    { key: 'choropleth_price_per_sqft', label: 'Price per sqft heatmap', colour: '#f97316', group: 'heatmap', help: 'Highlights value density rather than headline prices.' },
    { key: 'choropleth_median_rent', label: 'Median rent heatmap', colour: '#ec4899', group: 'heatmap', help: 'Shows the latest official private-rent evidence using a local-authority proxy repeated across nearby LSOAs.' },
    { key: 'choropleth_epc_score', label: 'EPC score heatmap', colour: '#22c55e', group: 'heatmap', help: 'Shows where energy performance is stronger or weaker.' },
    { key: 'ward_boundary', label: 'Wider area boundary', colour: '#2563eb', group: 'boundary', help: 'Shows the broader boundary used for area context.' },
    { key: 'lsoa_boundary', label: 'Local analysis boundary', colour: '#7c3aed', group: 'boundary', help: 'Shows the smaller local geography used for analysis.' },
  ],
  'Lifestyle & Connectivity': [
    { key: 'station', label: 'Stations', colour: '#7c3aed', group: 'data', help: 'Shows nearby rail and major transport stops.' },
    { key: 'ev_charger', label: 'EV chargers', colour: '#16a34a', group: 'data', help: 'Shows nearby public electric vehicle chargers.' },
    { key: 'amenity', label: 'Amenities', colour: '#0f766e', group: 'data', help: 'Shows nearby everyday amenities such as supermarkets, cafés, pharmacies, and similar services.' },
    { key: 'park', label: 'Parks and green spaces', colour: '#22c55e', group: 'data', help: 'Shows mapped parks and green-space sites near the selected area.' },
    { key: 'sports_recreation', label: 'Sports and recreation', colour: '#84cc16', group: 'data', help: 'Shows sports and recreation places near the selected area.' },
    { key: 'choropleth_broadband', label: 'Gigabit broadband heatmap', colour: '#2563eb', group: 'heatmap', help: 'Shows how gigabit-capable broadband availability varies across nearby areas.' },
    { key: 'choropleth_full_fibre', label: 'Full fibre heatmap', colour: '#1d4ed8', group: 'heatmap', help: 'Shows where full-fibre availability is stronger or weaker.' },
    { key: 'choropleth_superfast_broadband', label: 'Superfast broadband heatmap', colour: '#60a5fa', group: 'heatmap', help: 'Shows variation in superfast broadband availability across nearby areas.' },
    { key: 'choropleth_mobile_coverage', label: '4G outdoor coverage heatmap', colour: '#a855f7', group: 'heatmap', help: 'Shows a postcode-level proxy for outdoor mobile coverage.' },
    { key: 'choropleth_mobile_4g_indoor', label: '4G indoor coverage heatmap', colour: '#9333ea', group: 'heatmap', help: 'Shows a postcode-level proxy for indoor 4G coverage.' },
    { key: 'choropleth_mobile_5g_outdoor', label: '5G outdoor coverage heatmap', colour: '#7e22ce', group: 'heatmap', help: 'Shows a postcode-level proxy for outdoor 5G coverage.' },
    { key: 'ward_boundary', label: 'Wider area boundary', colour: '#2563eb', group: 'boundary', help: 'Shows the broader boundary used for area context.' },
    { key: 'lsoa_boundary', label: 'Local analysis boundary', colour: '#7c3aed', group: 'boundary', help: 'Shows the smaller local geography used for analysis.' },
  ],
  'Environment & Safety': [
    { key: 'flood_zone', label: 'Flood zones', colour: '#3b82f6', group: 'data', help: 'Shows mapped flood-risk zones near the selected area.' },
    { key: 'choropleth_air_quality_no2', label: 'NO2 heatmap', colour: '#0ea5e9', group: 'heatmap', help: 'Shows published NO2 pollution patterns aggregated from DEFRA air-quality grid cells to nearby LSOAs.' },
    { key: 'choropleth_air_quality_pm25', label: 'PM2.5 heatmap', colour: '#0284c7', group: 'heatmap', help: 'Shows published PM2.5 pollution patterns aggregated from DEFRA air-quality grid cells to nearby LSOAs.' },
    { key: 'ward_boundary', label: 'Wider area boundary', colour: '#2563eb', group: 'boundary', help: 'Shows the broader boundary used for area context.' },
    { key: 'lsoa_boundary', label: 'Local analysis boundary', colour: '#7c3aed', group: 'boundary', help: 'Shows the smaller local geography used for analysis.' },
  ],
  'Community & Education': [
    { key: 'school', label: 'Schools', colour: '#ea580c', group: 'data', help: 'Shows schools near the selected area.' },
    { key: 'nhs_facility', label: 'NHS facilities', colour: '#dc2626', group: 'data', help: 'Shows GP, hospital, and other NHS facilities near the selected area.' },
    { key: 'choropleth_population_density', label: 'Population density heatmap', colour: '#0f766e', group: 'heatmap', help: 'Shows how dense or spacious nearby LSOAs are.' },
    { key: 'choropleth_median_age', label: 'Median age heatmap', colour: '#0ea5e9', group: 'heatmap', help: 'Shows whether nearby LSOAs skew younger or older.' },
    { key: 'choropleth_household_composition', label: 'Family households heatmap', colour: '#14b8a6', group: 'heatmap', help: 'Shows the family-household share across nearby LSOAs.' },
    { key: 'choropleth_good_health', label: 'Good health heatmap', colour: '#22c55e', group: 'heatmap', help: 'Shows the share of residents reporting good or very good health.' },
    { key: 'choropleth_economically_active', label: 'Economic activity heatmap', colour: '#84cc16', group: 'heatmap', help: 'Shows how labour-market participation varies across nearby LSOAs.' },
    { key: 'choropleth_degree_educated', label: 'Degree education heatmap', colour: '#eab308', group: 'heatmap', help: 'Shows where degree-level qualification rates are higher or lower.' },
    { key: 'choropleth_no_car', label: 'No-car households heatmap', colour: '#f59e0b', group: 'heatmap', help: 'Shows the share of households without a car or van.' },
    { key: 'choropleth_born_abroad', label: 'Born abroad heatmap', colour: '#f97316', group: 'heatmap', help: 'Shows the share of residents born outside the UK.' },
    { key: 'choropleth_wfh', label: 'Works from home heatmap', colour: '#a855f7', group: 'heatmap', help: 'Shows where work-from-home rates are stronger or weaker.' },
    { key: 'choropleth_housing_tenure', label: 'Owner-occupation heatmap', colour: '#9333ea', group: 'heatmap', help: 'Shows the owner-occupied share across nearby LSOAs.' },
    { key: 'choropleth_housing_type', label: 'Detached homes heatmap', colour: '#c026d3', group: 'heatmap', help: 'Shows the detached-home share across nearby LSOAs.' },
    { key: 'choropleth_household_size', label: 'One-person households heatmap', colour: '#db2777', group: 'heatmap', help: 'Shows the one-person-household share across nearby LSOAs.' },
    { key: 'choropleth_deprivation', label: 'Deprivation heatmap', colour: '#f97316', group: 'heatmap', help: 'Shows overall deprivation variation across nearby LSOAs.' },
    { key: 'choropleth_deprivation_income', label: 'Income deprivation heatmap', colour: '#fb7185', group: 'heatmap', help: 'Shows the income-deprivation subdomain across nearby LSOAs.' },
    { key: 'choropleth_deprivation_employment', label: 'Employment deprivation heatmap', colour: '#f43f5e', group: 'heatmap', help: 'Shows the employment-deprivation subdomain across nearby LSOAs.' },
    { key: 'choropleth_deprivation_education', label: 'Education deprivation heatmap', colour: '#ef4444', group: 'heatmap', help: 'Shows the education-deprivation subdomain across nearby LSOAs.' },
    { key: 'choropleth_deprivation_health', label: 'Health deprivation heatmap', colour: '#dc2626', group: 'heatmap', help: 'Shows the health-deprivation subdomain across nearby LSOAs.' },
    { key: 'choropleth_deprivation_crime', label: 'Crime deprivation heatmap', colour: '#b91c1c', group: 'heatmap', help: 'Shows the crime-deprivation subdomain across nearby LSOAs.' },
    { key: 'choropleth_deprivation_barriers', label: 'Housing and services barriers heatmap', colour: '#ea580c', group: 'heatmap', help: 'Shows the barriers-to-housing-and-services subdomain across nearby LSOAs.' },
    { key: 'choropleth_deprivation_living_environment', label: 'Living environment heatmap', colour: '#c2410c', group: 'heatmap', help: 'Shows the living-environment deprivation subdomain across nearby LSOAs.' },
    { key: 'ward_boundary', label: 'Wider area boundary', colour: '#2563eb', group: 'boundary', help: 'Shows the broader boundary used for area context.' },
    { key: 'lsoa_boundary', label: 'Local analysis boundary', colour: '#7c3aed', group: 'boundary', help: 'Shows the smaller local geography used for analysis.' },
  ],
  'Local Governance': [
    { key: 'choropleth_council_tax', label: 'Council tax heatmap', colour: '#2563eb', group: 'heatmap', help: 'Shows published Band D council-tax charges using a local-authority proxy repeated across nearby LSOAs.' },
    { key: 'choropleth_median_earnings', label: 'Median earnings heatmap', colour: '#7c3aed', group: 'heatmap', help: 'Shows published ASHE median annual earnings using a local-authority proxy repeated across nearby LSOAs.' },
    { key: 'ward_boundary', label: 'Wider area boundary', colour: '#2563eb', group: 'boundary', help: 'Shows the broader boundary used for area context.' },
    { key: 'lsoa_boundary', label: 'Local analysis boundary', colour: '#7c3aed', group: 'boundary', help: 'Shows the smaller local geography used for analysis.' },
  ],
};

const TAB_GUIDANCE: Record<string, { intro: string; recommended: string[] }> = {
  'Property & Market': {
    intro: 'Start with boundaries for context, then add one value layer at a time so price signals stay easy to read.',
    recommended: ['Local analysis boundary', 'Average price heatmap', 'Median rent heatmap'],
  },
  'Lifestyle & Connectivity': {
    intro: 'Use the local boundary first, then add stations, amenities, parks, or one connectivity heatmap depending on what part of daily practicality you are testing.',
    recommended: ['Local analysis boundary', 'Stations', 'Amenities'],
  },
  'Environment & Safety': {
    intro: 'Keep the map simple in this section and add flood or air-quality layers one by one so you can tell whether a problem is concentrated or widespread.',
    recommended: ['Local analysis boundary', 'Flood zones', 'NO2 heatmap'],
  },
  'Community & Education': {
    intro: 'Use schools, NHS facilities, and one deprivation layer at a time so service access and neighbourhood conditions stay easy to interpret.',
    recommended: ['Local analysis boundary', 'Schools', 'Deprivation heatmap'],
  },
  'Local Governance': {
    intro: 'Use one governance heatmap at a time so authority-level tax and earnings patterns stay readable without implying finer-grain precision than the source publishes.',
    recommended: ['Local analysis boundary', 'Council tax heatmap', 'Median earnings heatmap'],
  },
};

const GROUP_META: Record<LayerDef['group'], { label: string; help: string; icon: typeof Layers2 }> = {
  data: {
    label: 'Points and places',
    help: 'Useful location markers for this section.',
    icon: MapPinned,
  },
  heatmap: {
    label: 'Area heatmaps',
    help: 'Use one heatmap at a time for clean comparison.',
    icon: Sparkles,
  },
  boundary: {
    label: 'Geography guides',
    help: 'These show the local area and wider comparison footprint.',
    icon: Layers2,
  },
};

interface Props {
  activeTab: string;
  visibleLayers: Record<string, boolean>;
  onToggle: (key: string) => void;
  soldPricesSince?: string | null;
  focusMode?: 'section' | 'metric' | 'manual' | 'metric-fallback';
  focusLabel?: string | null;
  focusReason?: string | null;
}

function LayerRow({
  layer,
  visible,
  onToggle,
  isHeatmap,
}: {
  layer: LayerDef;
  visible: boolean;
  onToggle: () => void;
  isHeatmap: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`w-full rounded-xl border px-3 py-2 text-left transition-colors ${
        visible ? 'border-brand-200 bg-brand-50/60' : 'border-divider bg-white hover:bg-surface'
      }`}
      aria-pressed={visible}
    >
      <div className="flex items-start gap-3">
        <span
          className="mt-0.5 h-3.5 w-3.5 shrink-0 rounded-sm border"
          style={{
            backgroundColor: visible ? layer.colour : 'transparent',
            borderColor: layer.colour,
          }}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={`text-xs font-semibold ${visible ? 'text-ink' : 'text-ink-muted'}`}>{layer.label}</span>
            {isHeatmap && (
              <span className="rounded-full bg-surface px-2 py-0.5 text-[10px] font-medium text-ink-faint">
                one at a time
              </span>
            )}
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-ink-faint">{layer.help}</p>
        </div>
      </div>
    </button>
  );
}

export default function MapLayerControl({ activeTab, visibleLayers, onToggle, soldPricesSince, focusMode = 'section', focusLabel = null }: Props) {
  const [open, setOpen] = useState(false);
  const baseLayers = TAB_LAYERS[activeTab] || TAB_LAYERS['Local Governance'];
  const tabGuidance = TAB_GUIDANCE[activeTab] || TAB_GUIDANCE['Local Governance'];

  const layers = useMemo(() => {
    return baseLayers.map((layer) => {
      if (layer.key === 'sold_price' && soldPricesSince) {
        const d = new Date(soldPricesSince);
        const since = d.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' });
        return {
          ...layer,
          label: `Sold prices (since ${since})`,
        };
      }
      return layer;
    });
  }, [baseLayers, soldPricesSince]);

  const groupedLayers = useMemo(() => {
    return (['data', 'heatmap', 'boundary'] as LayerDef['group'][])
      .map((group) => ({
        group,
        layers: layers.filter((layer) => layer.group === group),
      }))
      .filter((entry) => entry.layers.length > 0);
  }, [layers]);

  const visibleLayerLabels = layers
    .filter((layer) => (
      CHOROPLETH_KEYS.includes(layer.key) ? visibleLayers[layer.key] === true : visibleLayers[layer.key] !== false
    ))
    .map((layer) => layer.label);

  const visibleCount = visibleLayerLabels.length;
  const activeHeatmapCount = CHOROPLETH_KEYS.filter((key) => visibleLayers[key] === true).length;

  const densityMessage = visibleCount <= 2
    ? 'Clean view focused on the essentials.'
    : visibleCount <= 4
      ? 'Balanced view with enough supporting context.'
      : 'Busy view — hide a layer or two for a calmer read.';

  return (
    <div className="absolute top-2 left-2 z-10 max-w-[320px]">
      <button
        onClick={() => setOpen((prev) => !prev)}
        aria-label={open ? 'Close map evidence and layers' : 'Open map evidence and layers'}
        aria-expanded={open}
        className="flex h-9 items-center gap-2 rounded-xl bg-white/95 px-3 shadow-md backdrop-blur hover:bg-gray-50 transition-colors cursor-pointer border border-divider/60"
        title="Map evidence and layers"
      >
        <Layers2 className="w-4 h-4 text-ink" />
        <span className="text-xs font-semibold text-ink">Map focus</span>
      </button>

      {open && (
          <div className="mt-2 rounded-2xl border border-divider/60 bg-white shadow-lg overflow-hidden">
          <div className="border-b border-divider/60 px-3 py-3 bg-surface/70">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-faint">Map evidence</div>
                <div className="mt-1 text-xs font-semibold text-ink">{activeTab}</div>
              </div>
              <div className="rounded-full border border-divider bg-white px-2.5 py-1 text-[11px] font-medium text-ink-muted">
                {visibleCount} visible
              </div>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-ink-muted">
              {tabGuidance.intro}
            </p>
            <div className="mt-3 rounded-xl border border-divider bg-white px-3 py-2">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-faint">Current view</div>
                  <div className="mt-1 text-xs font-medium text-ink">{densityMessage}</div>
                </div>
                {activeHeatmapCount > 1 && (
                  <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[10px] font-semibold text-amber-700">
                    Simplify heatmaps
                  </span>
                )}
              </div>
              {visibleLayerLabels.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {visibleLayerLabels.map((label) => (
                    <span key={label} className="inline-flex items-center rounded-full border border-divider bg-surface px-2.5 py-1 text-[10px] font-medium text-ink-muted">
                      {label}
                    </span>
                  ))}
                </div>
              )}
            </div>
            {focusLabel && (
              <div className="mt-3 rounded-xl border border-brand-100 bg-brand-50/60 px-3 py-2">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-faint">Map follow</div>
                    <div className="mt-1 text-xs font-semibold text-ink">{focusLabel}</div>
                  </div>
                  <span className="rounded-full border border-white/70 bg-white px-2.5 py-1 text-[10px] font-semibold text-brand-700">
                    {focusMode === 'metric' ? 'Metric-led' : focusMode === 'manual' ? 'Manual' : focusMode === 'metric-fallback' ? 'Context-only' : 'Section-led'}
                  </span>
                </div>
              </div>
            )}
            <div className="mt-3 rounded-xl border border-divider bg-white px-3 py-2">
              <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-faint">Suggested start</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {tabGuidance.recommended.map((label) => (
                  <span key={label} className="inline-flex items-center rounded-full bg-surface px-2.5 py-1 text-[10px] font-medium text-ink-muted border border-divider">
                    {label}
                  </span>
                ))}
              </div>
            </div>
          </div>


          <div className="max-h-[420px] overflow-y-auto px-3 py-3 space-y-4">
            {groupedLayers.map(({ group, layers: items }) => {
              const meta = GROUP_META[group];
              const GroupIcon = meta.icon;
              return (
                <section key={group}>
                  <div className="mb-2 flex items-start gap-2">
                    <div className="mt-0.5 rounded-lg bg-surface p-1.5 border border-divider">
                      <GroupIcon className="w-3.5 h-3.5 text-ink-faint" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-ink">{meta.label}</div>
                      <div className="text-[11px] leading-relaxed text-ink-faint">{meta.help}</div>
                    </div>
                  </div>
                  <div className="space-y-2">
                    {items.map((layer) => {
                      const isVisible = CHOROPLETH_KEYS.includes(layer.key)
                        ? visibleLayers[layer.key] === true
                        : visibleLayers[layer.key] !== false;
                      return (
                        <LayerRow
                          key={layer.key}
                          layer={layer}
                          visible={isVisible}
                          onToggle={() => onToggle(layer.key)}
                          isHeatmap={CHOROPLETH_KEYS.includes(layer.key)}
                        />
                      );
                    })}
                  </div>

                  {group === 'data' && items.some((item) => item.key === 'sold_price') && visibleLayers.sold_price !== false && (
                    <div className="mt-2 ml-2 flex flex-wrap gap-2">
                      {PROPERTY_TYPE_LEGEND.map((t) => (
                        <span key={t.label} className="inline-flex items-center gap-1 rounded-full bg-surface px-2 py-1 text-[10px] text-ink-faint border border-divider">
                          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: t.colour }} />
                          {t.label}
                        </span>
                      ))}
                    </div>
                  )}
                </section>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
