import { useMemo } from 'react';
import { X, MapPin, Droplets, Volume2, Wifi, FileText, Landmark } from 'lucide-react';
import { useResults } from '../../context/ResultsContext';
import SkeletonCard from '../SkeletonCard';
import type { PropertyDataResponse } from '../../api/client';

/** Format a dB value with label */
function formatNoise(db: number | null, label: string): string | null {
  if (db == null) return null;
  if (db < 55) return `${label}: ${db.toFixed(0)} dB (quiet)`;
  if (db < 65) return `${label}: ${db.toFixed(0)} dB (moderate)`;
  if (db < 75) return `${label}: ${db.toFixed(0)} dB (noisy)`;
  return `${label}: ${db.toFixed(0)} dB (very noisy)`;
}

function PropertySection({ title, icon: Icon, children }: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
      <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
        <Icon className="w-4 h-4 text-blue-600" />
        {title}
      </h3>
      {children}
    </div>
  );
}

function DataRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value == null) return null;
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-600">{label}</span>
      <span className="font-medium text-gray-900">{value}</span>
    </div>
  );
}

export default function PropertyTab() {
  const { selectedProperty, clearProperty, propertyData, propertyLoading, propertyError } = useResults();

  const addressDisplay = useMemo(() => {
    if (!selectedProperty) return '';
    const parts: string[] = [];
    if (selectedProperty.saon) parts.push(selectedProperty.saon);
    if (selectedProperty.paon) parts.push(selectedProperty.paon);
    if (selectedProperty.street) parts.push(selectedProperty.street);
    if (selectedProperty.postcode) parts.push(selectedProperty.postcode);
    return selectedProperty.addressDisplay || parts.join(', ');
  }, [selectedProperty]);

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
          <SkeletonCard /><SkeletonCard /><SkeletonCard />
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
            <p className="text-xs text-gray-500 mt-1">
              {selectedProperty.lat.toFixed(5)}, {selectedProperty.lon.toFixed(5)}
            </p>
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

      <div className="space-y-4">
        {/* INSPIRE Parcel */}
        {data?.parcel && (
          <PropertySection title="Land Parcel" icon={Landmark}>
            <DataRow label="INSPIRE ID" value={data.parcel.inspire_id} />
            <DataRow label="Authority" value={data.parcel.authority} />
            <p className="text-xs text-gray-500">
              Land boundary shown on map (blue outline).
            </p>
          </PropertySection>
        )}

        {/* Flood Risk */}
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

        {/* Noise */}
        <PropertySection title="Noise Levels" icon={Volume2}>
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

        {/* Broadband */}
        <PropertySection title="Broadband" icon={Wifi}>
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

        {/* Local Land Charges */}
        {data?.llc_charges && data.llc_charges.length > 0 && (
          <PropertySection title="Local Land Charges" icon={FileText}>
            <div className="space-y-1">
              {data.llc_charges.map((c, i) => (
                <div key={i} className="text-sm text-gray-700 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                  {c.charge_type.replace(/_/g, ' ')}
                </div>
              ))}
            </div>
          </PropertySection>
        )}

        {/* Coordinates */}
        <div className="text-xs text-gray-400 text-center pt-4">
          Property data from HM Land Registry, Environment Agency, DEFRA, and Ofcom.
        </div>
      </div>
    </main>
  );
}
