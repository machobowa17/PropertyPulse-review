import { useMemo, useState } from 'react';
import {
  X, MapPin, Droplets, Volume2, Wifi, FileText, Landmark,
  Zap, PoundSterling, ChevronDown,
} from 'lucide-react';
import { useResults } from '../../context/ResultsContext';
import SkeletonCard from '../SkeletonCard';
import type { PropertyDataResponse, PropertyTransaction, PropertyEpc } from '../../api/client';

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatNoise(db: number | null, label: string): string | null {
  if (db == null) return null;
  if (db < 55) return `${label}: ${db.toFixed(0)} dB (quiet)`;
  if (db < 65) return `${label}: ${db.toFixed(0)} dB (moderate)`;
  if (db < 75) return `${label}: ${db.toFixed(0)} dB (noisy)`;
  return `${label}: ${db.toFixed(0)} dB (very noisy)`;
}

function formatPrice(p: number | undefined | null): string {
  if (p == null) return '—';
  return `£${p.toLocaleString('en-GB')}`;
}

function formatDate(d: string | undefined | null): string {
  if (!d) return '—';
  try {
    return new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return d;
  }
}

function formatCost(c: number | undefined | null): string {
  if (c == null) return '—';
  return `£${Math.round(c).toLocaleString('en-GB')}/yr`;
}

const PROPERTY_TYPES: Record<string, string> = {
  D: 'Detached', S: 'Semi-detached', T: 'Terraced', F: 'Flat/Maisonette', O: 'Other',
};
const DURATION_MAP: Record<string, string> = { F: 'Freehold', L: 'Leasehold', U: 'Unknown' };
const NEW_MAP: Record<string, string> = { Y: 'New Build', N: 'Existing' };

// EPC rating colour
function epcColor(rating: string | undefined | null): string {
  switch (rating?.toUpperCase()) {
    case 'A': return 'bg-green-700 text-white';
    case 'B': return 'bg-green-500 text-white';
    case 'C': return 'bg-lime-500 text-white';
    case 'D': return 'bg-yellow-400 text-gray-900';
    case 'E': return 'bg-orange-400 text-white';
    case 'F': return 'bg-orange-600 text-white';
    case 'G': return 'bg-red-600 text-white';
    default: return 'bg-gray-200 text-gray-600';
  }
}

// ── Shared sub-components ────────────────────────────────────────────────────

function PropertySection({ title, icon: Icon, children, defaultOpen = true }: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <button
        onClick={() => setOpen(!open)}
        className="w-full p-4 flex items-center justify-between"
      >
        <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
          <Icon className="w-4 h-4 text-blue-600" />
          {title}
        </h3>
        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && <div className="px-4 pb-4 space-y-2">{children}</div>}
    </div>
  );
}

function DataRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value == null || value === '' || value === '—') return null;
  return (
    <div className="flex justify-between text-sm gap-4">
      <span className="text-gray-500 shrink-0">{label}</span>
      <span className="font-medium text-gray-900 text-right">{value}</span>
    </div>
  );
}

// ── EPC Rating Badge ─────────────────────────────────────────────────────────

function EpcBadge({ rating, score, label }: { rating?: string | null; score?: number | null; label: string }) {
  if (!rating) return null;
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500">{label}</span>
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${epcColor(rating)}`}>
        {rating?.toUpperCase()}{score != null ? ` (${score})` : ''}
      </span>
    </div>
  );
}

// ── Transaction History Section ──────────────────────────────────────────────

function TransactionHistory({ transactions }: { transactions: PropertyTransaction[] }) {
  if (!transactions.length) {
    return <p className="text-sm text-gray-500">No transaction history found.</p>;
  }

  // Sort by date descending
  const sorted = [...transactions].sort((a, b) => {
    const da = a.date_of_transfer || '';
    const db = b.date_of_transfer || '';
    return db.localeCompare(da);
  });

  return (
    <div className="space-y-2">
      {sorted.map((txn, i) => {
        const prevTxn = sorted[i + 1];
        const priceChange = prevTxn?.price && txn.price
          ? ((txn.price - prevTxn.price) / prevTxn.price * 100)
          : null;

        return (
          <div key={txn.transaction_id || i} className="flex items-center justify-between text-sm border-b border-gray-100 pb-2 last:border-0">
            <div>
              <span className="font-semibold text-gray-900">{formatPrice(txn.price)}</span>
              {priceChange != null && (
                <span className={`ml-2 text-xs ${priceChange >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(0)}%
                </span>
              )}
            </div>
            <div className="text-right text-xs text-gray-500">
              <div>{formatDate(txn.date_of_transfer)}</div>
              <div className="flex gap-1.5 justify-end mt-0.5">
                {txn.property_type && (
                  <span className="text-gray-400">{PROPERTY_TYPES[txn.property_type] || txn.property_type}</span>
                )}
                {txn.duration && (
                  <span className="text-gray-400">{DURATION_MAP[txn.duration] || txn.duration}</span>
                )}
                {txn.old_new && (
                  <span className="text-gray-400">{NEW_MAP[txn.old_new] || txn.old_new}</span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── EPC Section ──────────────────────────────────────────────────────────────

function EpcSection({ epc, epcHistory }: { epc: PropertyEpc | null; epcHistory: PropertyEpc[] }) {
  const [showFull, setShowFull] = useState(false);

  if (!epc) {
    return <p className="text-sm text-gray-500">No EPC data available for this property.</p>;
  }

  return (
    <div className="space-y-3">
      {/* Rating badges */}
      <div className="flex items-center gap-4 flex-wrap">
        <EpcBadge rating={epc.current_energy_rating} score={epc.current_energy_efficiency} label="Current" />
        <EpcBadge rating={epc.potential_energy_rating} score={epc.potential_energy_efficiency} label="Potential" />
      </div>

      {/* Key facts */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        <DataRow label="Property Type" value={epc.property_type} />
        <DataRow label="Built Form" value={epc.built_form} />
        <DataRow label="Construction Age" value={epc.construction_age_band} />
        <DataRow label="Tenure" value={epc.tenure} />
        <DataRow label="Floor Area" value={epc.total_floor_area ? `${epc.total_floor_area} m²` : null} />
        <DataRow label="Habitable Rooms" value={epc.number_habitable_rooms} />
        <DataRow label="Lodgement Date" value={formatDate(epc.lodgement_date)} />
        {epc.uprn != null && <DataRow label="UPRN" value={epc.uprn} />}
      </div>

      {/* Expandable full details */}
      <button
        onClick={() => setShowFull(!showFull)}
        className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
      >
        <ChevronDown className={`w-3 h-3 transition-transform ${showFull ? 'rotate-180' : ''}`} />
        {showFull ? 'Hide full details' : 'Show full EPC details'}
      </button>

      {showFull && (
        <div className="space-y-3 pt-1">
          {/* Building Fabric */}
          <div>
            <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-1">Building Fabric</h4>
            <div className="space-y-0.5">
              <DataRow label="Walls" value={epc.walls_description} />
              <DataRow label="Roof" value={epc.roof_description} />
              <DataRow label="Floor" value={epc.floor_description} />
              <DataRow label="Windows" value={epc.windows_description} />
            </div>
          </div>

          {/* Heating & Energy */}
          <div>
            <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-1">Heating & Energy</h4>
            <div className="space-y-0.5">
              <DataRow label="Main Heating" value={epc.main_heating_description} />
              <DataRow label="Main Fuel" value={epc.main_fuel} />
              <DataRow label="Hot Water" value={epc.hotwater_description} />
              <DataRow label="Lighting" value={epc.lighting_description} />
              <DataRow label="Solar Water" value={epc.solar_water_heating_flag === 'Y' ? 'Yes' : epc.solar_water_heating_flag === 'N' ? 'No' : null} />
              <DataRow label="PV Generation" value={epc.photo_supply ? `${epc.photo_supply} kWh/yr` : null} />
            </div>
          </div>

          {/* Running Costs */}
          <div>
            <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-1">Estimated Running Costs</h4>
            <div className="space-y-0.5">
              <DataRow label="Heating (current)" value={formatCost(epc.heating_cost_current)} />
              <DataRow label="Heating (potential)" value={formatCost(epc.heating_cost_potential)} />
              <DataRow label="Hot Water (current)" value={formatCost(epc.hot_water_cost_current)} />
              <DataRow label="Hot Water (potential)" value={formatCost(epc.hot_water_cost_potential)} />
              <DataRow label="Lighting (current)" value={formatCost(epc.lighting_cost_current)} />
              <DataRow label="Lighting (potential)" value={formatCost(epc.lighting_cost_potential)} />
            </div>
          </div>

          {/* Environmental Impact */}
          <div>
            <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-1">Environmental Impact</h4>
            <div className="space-y-0.5">
              <DataRow label="Energy Use" value={epc.energy_consumption_current ? `${epc.energy_consumption_current} kWh/m²/yr` : null} />
              <DataRow label="CO₂ Current" value={epc.co2_emissions_current ? `${epc.co2_emissions_current} tonnes/yr` : null} />
              <DataRow label="CO₂ Potential" value={epc.co2_emissions_potential ? `${epc.co2_emissions_potential} tonnes/yr` : null} />
              <DataRow label="Impact Current" value={epc.environment_impact_current} />
              <DataRow label="Impact Potential" value={epc.environment_impact_potential} />
            </div>
          </div>

          {/* EPC History */}
          {epcHistory.length > 1 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-1">
                EPC History ({epcHistory.length} certificates)
              </h4>
              <div className="space-y-1">
                {epcHistory.map((h, i) => (
                  <div key={i} className="flex items-center justify-between text-xs text-gray-600 border-b border-gray-50 pb-1">
                    <span>{formatDate(h.lodgement_date)}</span>
                    <div className="flex items-center gap-2">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-bold ${epcColor(h.current_energy_rating)}`}>
                        {h.current_energy_rating?.toUpperCase()}
                      </span>
                      <span className="text-gray-400">{h.current_energy_efficiency}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────

export default function PropertyTab() {
  const { selectedProperty, selectProperty, clearProperty, propertyData, propertyLoading, propertyError, resolved } = useResults();

  const addressDisplay = useMemo(() => {
    if (!selectedProperty) return '';
    const parts: string[] = [];
    if (selectedProperty.saon) parts.push(selectedProperty.saon);
    if (selectedProperty.paon) parts.push(selectedProperty.paon);
    if (selectedProperty.street) parts.push(selectedProperty.street);
    if (selectedProperty.postcode) parts.push(selectedProperty.postcode);
    return selectedProperty.addressDisplay || parts.join(', ');
  }, [selectedProperty]);

  // Disambiguation: if resolve found multiple addresses (flats), show picker
  const alternatives = resolved?.alternatives;
  const primaryProperty = resolved?.property;
  const needsDisambiguation = resolved?.type === 'address' && !selectedProperty && alternatives && alternatives.length > 0;

  if (needsDisambiguation && primaryProperty) {
    const allOptions = [
      { ...primaryProperty, saon: primaryProperty.saon ?? null },
      ...alternatives,
    ];
    return (
      <main id="main-content" className="flex-1 min-w-0 px-4 lg:px-6 py-6">
        <div className="mb-4">
          <div className="flex items-center gap-2 text-xs text-blue-600 font-medium uppercase tracking-wide mb-1">
            <MapPin className="w-3.5 h-3.5" />
            Select Address
          </div>
          <h2 className="text-lg font-semibold text-gray-900">
            Multiple units found at {primaryProperty.paon} {primaryProperty.street?.replace(/\b\w/g, (c: string) => c.toUpperCase())}
          </h2>
          <p className="text-sm text-gray-500 mt-1">Please select which property you want to view.</p>
        </div>
        <div className="space-y-2">
          {allOptions.map((opt, i) => {
            const label = [opt.saon, opt.paon, opt.street?.replace(/\b\w/g, (c: string) => c.toUpperCase()), opt.postcode].filter(Boolean).join(', ');
            return (
              <button
                key={i}
                className="w-full text-left p-3 rounded-lg border border-gray-200 hover:border-blue-400 hover:bg-blue-50 transition"
                onClick={() => selectProperty({
                  lat: opt.lat!,
                  lon: opt.lon!,
                  postcode: opt.postcode,
                  paon: opt.paon,
                  saon: opt.saon ?? null,
                  street: opt.street,
                  uprn: null,
                  addressDisplay: label,
                })}
              >
                <span className="text-sm font-medium text-gray-900">{label}</span>
              </button>
            );
          })}
        </div>
      </main>
    );
  }

  if (!selectedProperty) return null;

  if (propertyLoading) {
    return (
      <main id="main-content" className="flex-1 min-w-0 px-4 lg:px-6 py-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Property Details</h2>
          <button onClick={clearProperty} className="p-1 rounded hover:bg-gray-100" title="Close property view">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>
        <div className="space-y-4">
          <SkeletonCard /><SkeletonCard /><SkeletonCard /><SkeletonCard />
        </div>
      </main>
    );
  }

  if (propertyError) {
    return (
      <main id="main-content" className="flex-1 min-w-0 px-4 lg:px-6 py-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Property Details</h2>
          <button onClick={clearProperty} className="p-1 rounded hover:bg-gray-100" title="Close property view">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">Failed to load property data. Please try again.</p>
        </div>
      </main>
    );
  }

  const data: PropertyDataResponse | null = propertyData ?? null;
  const epc = data?.epc ?? null;

  // Derive headline info from latest transaction + EPC
  const latestTxn = data?.transactions?.length
    ? [...data.transactions].sort((a, b) => (b.date_of_transfer || '').localeCompare(a.date_of_transfer || ''))[0]
    : null;

  return (
    <main id="main-content" className="flex-1 min-w-0 px-4 lg:px-6 py-6">
      {/* Header with address and dismiss */}
      <div className="mb-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-xs text-blue-600 font-medium uppercase tracking-wide mb-1">
              <MapPin className="w-3.5 h-3.5" />
              Property
            </div>
            <h2 className="text-lg font-semibold text-gray-900 leading-tight">{addressDisplay}</h2>
            {/* Quick summary line */}
            <div className="flex items-center gap-3 mt-1.5 flex-wrap">
              {epc?.property_type && (
                <span className="text-xs text-gray-600">{epc.property_type}</span>
              )}
              {epc?.tenure && (
                <span className="text-xs text-gray-500">{epc.tenure}</span>
              )}
              {epc?.total_floor_area && (
                <span className="text-xs text-gray-500">{epc.total_floor_area} m²</span>
              )}
              {epc?.number_habitable_rooms && (
                <span className="text-xs text-gray-500">{epc.number_habitable_rooms} rooms (est.)</span>
              )}
              {epc?.current_energy_rating && (
                <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-bold ${epcColor(epc.current_energy_rating)}`}>
                  EPC {epc.current_energy_rating.toUpperCase()}
                </span>
              )}
            </div>
            {latestTxn?.price && (
              <p className="text-sm font-semibold text-gray-900 mt-1">
                Last sold: {formatPrice(latestTxn.price)} ({formatDate(latestTxn.date_of_transfer)})
              </p>
            )}
          </div>
          <button
            onClick={clearProperty}
            className="shrink-0 p-1.5 rounded-lg hover:bg-gray-100 transition"
            title="Close property view"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>
      </div>

      <div className="space-y-3">
        {/* 1. Transaction History */}
        <PropertySection title="Transaction History" icon={PoundSterling}>
          <TransactionHistory transactions={data?.transactions || []} />
        </PropertySection>

        {/* 2. Energy Performance Certificate */}
        <PropertySection title="Energy Performance Certificate" icon={Zap}>
          <EpcSection epc={epc} epcHistory={data?.epc_history || []} />
        </PropertySection>

        {/* 3. Flood Risk */}
        <PropertySection title="Flood Risk" icon={Droplets}>
          {data?.flood_zone ? (
            <div className="text-sm">
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                data.flood_zone.includes('3') ? 'bg-red-100 text-red-700' :
                data.flood_zone.includes('2') ? 'bg-amber-100 text-amber-700' :
                'bg-green-100 text-green-700'
              }`}>
                {data.flood_zone}
              </span>
              <p className="text-gray-600 mt-2 text-xs">
                {data.flood_zone.includes('3')
                  ? 'High probability of flooding from rivers or the sea.'
                  : data.flood_zone.includes('2')
                    ? 'Medium probability of flooding.'
                    : 'Low probability of flooding.'}
              </p>
            </div>
          ) : (
            <p className="text-sm text-green-700">Not in a mapped flood zone (Flood Zone 1).</p>
          )}
        </PropertySection>

        {/* 4. Noise */}
        <PropertySection title="Noise Levels" icon={Volume2} defaultOpen={false}>
          {data?.noise ? (
            <div className="space-y-1 text-sm">
              {data.noise.road_db != null && (
                <p className="text-gray-700">{formatNoise(data.noise.road_db, 'Road')}</p>
              )}
              {data.noise.rail_db != null && (
                <p className="text-gray-700">{formatNoise(data.noise.rail_db, 'Rail')}</p>
              )}
              {data.noise.road_db == null && data.noise.rail_db == null && (
                <p className="text-gray-500">No noise data available for this postcode.</p>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-500">No noise data available.</p>
          )}
        </PropertySection>

        {/* 5. Broadband */}
        <PropertySection title="Broadband" icon={Wifi} defaultOpen={false}>
          {data?.broadband ? (
            <div className="space-y-1">
              <DataRow label="Avg Download" value={data.broadband.avg_download != null ? `${data.broadband.avg_download.toFixed(0)} Mbps` : null} />
              <DataRow label="Avg Upload" value={data.broadband.avg_upload != null ? `${data.broadband.avg_upload.toFixed(0)} Mbps` : null} />
              <DataRow label="Superfast" value={data.broadband.superfast_pct != null ? `${data.broadband.superfast_pct.toFixed(0)}%` : null} />
              <DataRow label="Gigabit" value={data.broadband.gigabit_pct != null ? `${data.broadband.gigabit_pct.toFixed(0)}%` : null} />
              <DataRow label="Full Fibre (FTTP)" value={data.broadband.fttp_pct != null ? `${data.broadband.fttp_pct.toFixed(0)}%` : null} />
            </div>
          ) : (
            <p className="text-sm text-gray-500">No broadband data available.</p>
          )}
        </PropertySection>

        {/* 6. Land Parcel */}
        {data?.parcel && (
          <PropertySection title="Land Parcel (INSPIRE)" icon={Landmark} defaultOpen={false}>
            <DataRow label="INSPIRE ID" value={data.parcel.inspire_id} />
            <DataRow label="Authority" value={data.parcel.authority} />
            <p className="text-xs text-gray-500">
              Cadastral boundary from HM Land Registry INSPIRE index.
            </p>
          </PropertySection>
        )}

        {/* 7. Local Land Charges */}
        {data?.llc_charges && data.llc_charges.length > 0 && (
          <PropertySection title="Local Land Charges" icon={FileText} defaultOpen={false}>
            <div className="space-y-1.5">
              {data.llc_charges.map((c, i) => (
                <div key={i} className="text-sm text-gray-700">
                  <div className="flex items-start gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0 mt-1.5" />
                    <div>
                      <span className="font-medium">{c.charge_type.replace(/_/g, ' ')}</span>
                      {c.authority && (
                        <span className="text-xs text-gray-400 ml-1">({c.authority})</span>
                      )}
                      {c.valid_from && (
                        <span className="text-xs text-gray-400 ml-1">from {formatDate(c.valid_from)}</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </PropertySection>
        )}

        {/* Footer attribution */}
        <div className="text-xs text-gray-400 text-center pt-4 space-y-0.5">
          <p>Transaction data: HM Land Registry Price Paid Data (Crown Copyright).</p>
          <p>EPC data: DLUHC Energy Performance of Buildings Register.</p>
          <p>Spatial data: Environment Agency, DEFRA, Ofcom, HM Land Registry INSPIRE.</p>
        </div>
      </div>
    </main>
  );
}
