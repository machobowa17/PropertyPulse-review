import { useState } from 'react';
import { Layers } from 'lucide-react';

interface LayerDef {
  key: string;
  label: string;
  colour: string;
  group?: string;
}

const CHOROPLETH_KEYS = ['choropleth_avg_price', 'choropleth_price_per_sqft', 'choropleth_epc_score'];

const PROPERTY_TYPE_LEGEND = [
  { label: 'Detached', colour: '#2563eb' },
  { label: 'Semi-Det.', colour: '#16a34a' },
  { label: 'Terraced', colour: '#d97706' },
  { label: 'Flat', colour: '#9333ea' },
];

const TAB_LAYERS: Record<string, LayerDef[]> = {
  'Property & Market': [
    { key: 'sold_price', label: 'Sold Prices', colour: '#0891b2' },
    { key: 'choropleth_avg_price', label: 'Avg Price Heatmap', colour: '#ef4444' },
    { key: 'choropleth_price_per_sqft', label: '£/sqft Heatmap', colour: '#f97316' },
    { key: 'choropleth_epc_score', label: 'EPC Score Heatmap', colour: '#22c55e' },
    { key: 'ward_boundary', label: 'Ward Boundary', colour: '#2563eb' },
    { key: 'lsoa_boundary', label: 'LSOA Boundary', colour: '#7c3aed' },
  ],
  'Lifestyle & Connectivity': [
    { key: 'station', label: 'Rail Stations', colour: '#7c3aed' },
    { key: 'ev_charger', label: 'EV Chargers', colour: '#16a34a' },
    { key: 'ward_boundary', label: 'Ward Boundary', colour: '#2563eb' },
    { key: 'lsoa_boundary', label: 'LSOA Boundary', colour: '#7c3aed' },
  ],
  'Environment & Safety': [
    { key: 'flood_zone', label: 'Flood Zones', colour: '#3b82f6' },
    { key: 'ward_boundary', label: 'Ward Boundary', colour: '#2563eb' },
    { key: 'lsoa_boundary', label: 'LSOA Boundary', colour: '#7c3aed' },
  ],
  'Community & Education': [
    { key: 'school', label: 'Schools', colour: '#ea580c' },
    { key: 'ward_boundary', label: 'Ward Boundary', colour: '#2563eb' },
    { key: 'lsoa_boundary', label: 'LSOA Boundary', colour: '#7c3aed' },
  ],
  'Local Governance': [
    { key: 'ward_boundary', label: 'Ward Boundary', colour: '#2563eb' },
    { key: 'lsoa_boundary', label: 'LSOA Boundary', colour: '#7c3aed' },
  ],
};

interface Props {
  activeTab: string;
  visibleLayers: Record<string, boolean>;
  onToggle: (key: string) => void;
  soldPricesSince?: string | null;
}

export default function MapLayerControl({ activeTab, visibleLayers, onToggle, soldPricesSince }: Props) {
  const [open, setOpen] = useState(false);
  const baseLayers = TAB_LAYERS[activeTab] || TAB_LAYERS['Local Governance'];

  // Dynamically update sold_price label with "since MMM YYYY"
  const layers = baseLayers.map((layer) => {
    if (layer.key === 'sold_price' && soldPricesSince) {
      const d = new Date(soldPricesSince);
      const since = d.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' });
      return { ...layer, label: `Sold Prices (since ${since})` };
    }
    return layer;
  });

  return (
    <div className="absolute top-2 left-2 z-10">
      <button
        onClick={() => setOpen(!open)}
        aria-label={open ? 'Close layer controls' : 'Open layer controls'}
        aria-expanded={open}
        className="w-8 h-8 rounded-lg bg-white shadow-md flex items-center justify-center hover:bg-gray-50 transition-colors cursor-pointer"
        title="Map layers"
      >
        <Layers className="w-4 h-4 text-ink" />
      </button>

      {open && (
        <div className="mt-1.5 bg-white rounded-xl shadow-lg p-2.5 min-w-[170px] border border-divider/50">
          <p className="text-[10px] font-semibold text-ink-faint uppercase tracking-wider px-1 mb-1.5">Layers</p>
          {layers.map((layer, i) => {
            const isVisible = CHOROPLETH_KEYS.includes(layer.key)
              ? visibleLayers[layer.key] === true
              : visibleLayers[layer.key] !== false;
            const isChoropleth = CHOROPLETH_KEYS.includes(layer.key);
            const showHeatmapHeader = isChoropleth && (i === 0 || !CHOROPLETH_KEYS.includes(layers[i - 1]?.key));
            return (
              <div key={layer.key}>
                {showHeatmapHeader && (
                  <p className="text-[9px] font-semibold text-ink-faint uppercase tracking-wider px-1 mt-2 mb-0.5">Heatmaps</p>
                )}
                <label className="flex items-center gap-2 px-1 py-1 rounded-lg hover:bg-surface cursor-pointer text-xs">
                  <input
                    type="checkbox"
                    checked={isVisible}
                    onChange={() => onToggle(layer.key)}
                    className="sr-only"
                  />
                  <span
                    className="w-3 h-3 rounded-sm shrink-0 border transition-colors"
                    style={{
                      backgroundColor: isVisible ? layer.colour : 'transparent',
                      borderColor: layer.colour,
                    }}
                  />
                  <span className={`${isVisible ? 'text-ink' : 'text-ink-faint'} font-medium`}>
                    {layer.label}
                  </span>
                </label>
                {/* Property type colour legend under sold prices when visible */}
                {layer.key === 'sold_price' && isVisible && (
                  <div className="flex gap-2 px-1 py-0.5 ml-5 flex-wrap">
                    {PROPERTY_TYPE_LEGEND.map((t) => (
                      <span key={t.label} className="flex items-center gap-1 text-[9px] text-ink-faint">
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: t.colour }} />
                        {t.label}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
