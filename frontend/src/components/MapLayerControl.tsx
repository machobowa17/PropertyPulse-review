import { useMemo, useState, useRef, useEffect } from 'react';
import { Layers2 } from 'lucide-react';

interface LayerDef {
  key: string;
  label: string;
  colour: string;
  group: 'data' | 'heatmap' | 'boundary';
}

const CHOROPLETH_KEYS = [
  'choropleth_avg_price',
  'choropleth_median_price',
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
  'choropleth_mobile_coverage',
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
    { key: 'sold_price', label: 'Sold prices', colour: '#0891b2', group: 'data' },
    { key: 'choropleth_avg_price', label: 'Average price heatmap', colour: '#ef4444', group: 'heatmap' },
    { key: 'choropleth_median_price', label: 'Median price heatmap', colour: '#dc2626', group: 'heatmap' },
    { key: 'choropleth_price_per_sqft', label: 'Price per sqft heatmap', colour: '#f97316', group: 'heatmap' },
    { key: 'choropleth_median_rent', label: 'Median rent heatmap', colour: '#ec4899', group: 'heatmap' },
    { key: 'choropleth_epc_score', label: 'EPC score heatmap', colour: '#22c55e', group: 'heatmap' },
    { key: 'ward_boundary', label: 'Ward boundary', colour: '#2563eb', group: 'boundary' },
    { key: 'lsoa_boundary', label: 'LSOA boundary', colour: '#7c3aed', group: 'boundary' },
  ],
  'Lifestyle & Connectivity': [
    { key: 'station', label: 'Stations', colour: '#7c3aed', group: 'data' },
    { key: 'ev_charger', label: 'EV chargers', colour: '#16a34a', group: 'data' },
    { key: 'amenity', label: 'Amenities', colour: '#0f766e', group: 'data' },
    { key: 'park', label: 'Parks and green spaces', colour: '#22c55e', group: 'data' },
    { key: 'sports_recreation', label: 'Sports and recreation', colour: '#84cc16', group: 'data' },
    { key: 'choropleth_broadband', label: 'Gigabit broadband heatmap', colour: '#2563eb', group: 'heatmap' },
    { key: 'choropleth_mobile_coverage', label: '4G outdoor coverage heatmap', colour: '#a855f7', group: 'heatmap' },
    { key: 'ward_boundary', label: 'Ward boundary', colour: '#2563eb', group: 'boundary' },
    { key: 'lsoa_boundary', label: 'LSOA boundary', colour: '#7c3aed', group: 'boundary' },
  ],
  'Environment & Safety': [
    { key: 'flood_zone', label: 'Flood zones', colour: '#3b82f6', group: 'data' },
    { key: 'choropleth_air_quality_no2', label: 'NO2 heatmap', colour: '#0ea5e9', group: 'heatmap' },
    { key: 'choropleth_air_quality_pm25', label: 'PM2.5 heatmap', colour: '#0284c7', group: 'heatmap' },
    { key: 'ward_boundary', label: 'Ward boundary', colour: '#2563eb', group: 'boundary' },
    { key: 'lsoa_boundary', label: 'LSOA boundary', colour: '#7c3aed', group: 'boundary' },
  ],
  'Community & Education': [
    { key: 'school', label: 'Schools', colour: '#ea580c', group: 'data' },
    { key: 'nhs_facility', label: 'NHS facilities', colour: '#dc2626', group: 'data' },
    { key: 'choropleth_population_density', label: 'Population density heatmap', colour: '#0f766e', group: 'heatmap' },
    { key: 'choropleth_median_age', label: 'Median age heatmap', colour: '#0ea5e9', group: 'heatmap' },
    { key: 'choropleth_household_composition', label: 'Family households heatmap', colour: '#14b8a6', group: 'heatmap' },
    { key: 'choropleth_good_health', label: 'Good health heatmap', colour: '#22c55e', group: 'heatmap' },
    { key: 'choropleth_economically_active', label: 'Economic activity heatmap', colour: '#84cc16', group: 'heatmap' },
    { key: 'choropleth_degree_educated', label: 'Degree education heatmap', colour: '#eab308', group: 'heatmap' },
    { key: 'choropleth_no_car', label: 'No-car households heatmap', colour: '#f59e0b', group: 'heatmap' },
    { key: 'choropleth_born_abroad', label: 'Born abroad heatmap', colour: '#f97316', group: 'heatmap' },
    { key: 'choropleth_median_earnings', label: 'Median earnings heatmap', colour: '#7c3aed', group: 'heatmap' },
    { key: 'choropleth_housing_tenure', label: 'Owner-occupation heatmap', colour: '#9333ea', group: 'heatmap' },
    { key: 'choropleth_housing_type', label: 'Detached homes heatmap', colour: '#c026d3', group: 'heatmap' },
    { key: 'choropleth_household_size', label: 'One-person households heatmap', colour: '#db2777', group: 'heatmap' },
    { key: 'choropleth_deprivation', label: 'Deprivation heatmap', colour: '#f97316', group: 'heatmap' },
    { key: 'choropleth_deprivation_income', label: 'Income deprivation heatmap', colour: '#fb7185', group: 'heatmap' },
    { key: 'choropleth_deprivation_employment', label: 'Employment deprivation heatmap', colour: '#f43f5e', group: 'heatmap' },
    { key: 'choropleth_deprivation_education', label: 'Education deprivation heatmap', colour: '#ef4444', group: 'heatmap' },
    { key: 'choropleth_deprivation_health', label: 'Health deprivation heatmap', colour: '#dc2626', group: 'heatmap' },
    { key: 'choropleth_deprivation_crime', label: 'Crime deprivation heatmap', colour: '#b91c1c', group: 'heatmap' },
    { key: 'choropleth_deprivation_barriers', label: 'Housing and services barriers heatmap', colour: '#ea580c', group: 'heatmap' },
    { key: 'choropleth_deprivation_living_environment', label: 'Living environment heatmap', colour: '#c2410c', group: 'heatmap' },
    { key: 'ward_boundary', label: 'Ward boundary', colour: '#2563eb', group: 'boundary' },
    { key: 'lsoa_boundary', label: 'LSOA boundary', colour: '#7c3aed', group: 'boundary' },
  ],
  'Local Governance': [
    { key: 'choropleth_council_tax', label: 'Council tax heatmap', colour: '#2563eb', group: 'heatmap' },
    { key: 'ward_boundary', label: 'Ward boundary', colour: '#2563eb', group: 'boundary' },
    { key: 'lsoa_boundary', label: 'LSOA boundary', colour: '#7c3aed', group: 'boundary' },
  ],
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

export default function MapLayerControl({ activeTab, visibleLayers, onToggle, soldPricesSince, focusMode, focusLabel, focusReason }: Props) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const baseLayers = TAB_LAYERS[activeTab] || TAB_LAYERS['Local Governance'];

  const layers = useMemo(() => {
    return baseLayers.map((layer) => {
      if (layer.key === 'sold_price' && soldPricesSince) {
        const d = new Date(soldPricesSince);
        const since = d.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' });
        return { ...layer, label: `Sold prices (since ${since})` };
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

  return (
    <div ref={containerRef} className="absolute top-2 left-2 z-10 max-w-[280px]">
      <button
        onClick={() => setOpen((prev) => !prev)}
        aria-label={open ? 'Close map layers' : 'Open map layers'}
        aria-expanded={open}
        className="flex h-9 items-center gap-2 rounded-xl bg-white/95 px-3 shadow-md backdrop-blur hover:bg-gray-50 transition-colors cursor-pointer border border-divider/60"
        title="Map layers"
      >
        <Layers2 className="w-4 h-4 text-ink" />
        <span className="text-xs font-semibold text-ink">Layers</span>
      </button>

      {focusMode && focusMode !== 'manual' && focusLabel && (
        <div className="mt-1.5 rounded-lg bg-brand-50/80 border border-brand-200/40 px-2.5 py-1.5 backdrop-blur" title={focusReason ?? undefined}>
          <span className="text-[10px] font-medium text-brand-700 line-clamp-2">{focusLabel}</span>
        </div>
      )}

      {open && (
        <div className="mt-2 rounded-2xl border border-divider/60 bg-white shadow-lg overflow-hidden">
          <div className="max-h-[480px] overflow-y-auto px-3 py-3 space-y-3">
            {groupedLayers.map(({ group, layers: items }) => (
              <section key={group}>
                <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-ink-faint">
                  {group === 'data' ? 'Points' : group === 'heatmap' ? 'Heatmaps' : 'Boundaries'}
                </div>
                <div className="space-y-1">
                  {items.map((layer) => {
                    const isVisible = CHOROPLETH_KEYS.includes(layer.key)
                      ? visibleLayers[layer.key] === true
                      : visibleLayers[layer.key] !== false;
                    return (
                      <button
                        key={layer.key}
                        type="button"
                        onClick={() => onToggle(layer.key)}
                        className={`w-full flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors ${
                          isVisible ? 'bg-brand-50/60' : 'hover:bg-surface'
                        }`}
                        aria-pressed={isVisible}
                      >
                        <span
                          className="h-3 w-3 shrink-0 rounded-sm border"
                          style={{
                            backgroundColor: isVisible ? layer.colour : 'transparent',
                            borderColor: layer.colour,
                          }}
                        />
                        <span className={`text-xs font-medium ${isVisible ? 'text-ink' : 'text-ink-muted'}`}>
                          {layer.label}
                        </span>
                      </button>
                    );
                  })}
                </div>

                {group === 'data' && items.some((item) => item.key === 'sold_price') && visibleLayers.sold_price !== false && (
                  <div className="mt-1.5 ml-5 flex flex-wrap gap-1.5">
                    {PROPERTY_TYPE_LEGEND.map((t) => (
                      <span key={t.label} className="inline-flex items-center gap-1 rounded-full bg-surface px-2 py-0.5 text-[10px] text-ink-faint border border-divider">
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: t.colour }} />
                        {t.label}
                      </span>
                    ))}
                  </div>
                )}
              </section>
            ))}

            {activeTab === 'Lifestyle & Connectivity' && (
              <section>
                <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-ink-faint">
                  Walk rings
                </div>
                <div className="space-y-1">
                  {[
                    { colour: '#dc2626', label: '5 min walk (~420m)' },
                    { colour: '#ca8a04', label: '10 min walk (~830m)' },
                    { colour: '#16a34a', label: '15 min walk (~1.25km)' },
                  ].map(({ colour, label }) => (
                    <div key={label} className="flex items-center gap-2.5 px-2.5 py-1">
                      <span
                        className="h-0 w-5 shrink-0 border-t-2 border-dashed"
                        style={{ borderColor: colour }}
                      />
                      <span className="text-xs text-ink-muted">{label}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
