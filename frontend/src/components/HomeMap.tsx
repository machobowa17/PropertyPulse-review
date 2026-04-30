import { useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { fetchReverseGeocode } from '../api/client';

/** Lightweight map for the Home page — shows INSPIRE parcels + address labels at high zoom.
 *  Click a parcel/address → reverse geocode → navigate to /results with the address.
 */
export default function HomeMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const navigate = useNavigate();
  const navigateRef = useRef(navigate);
  useEffect(() => { navigateRef.current = navigate; }, [navigate]);

  const handleFeatureClick = useCallback(async (e: maplibregl.MapMouseEvent) => {
    const { lat, lng } = e.lngLat;
    try {
      const result = await fetchReverseGeocode(lat, lng);
      if (result.type === 'property' && result.property) {
        const p = result.property;
        const parts = [p.saon, p.paon, p.street, p.postcode].filter(Boolean);
        navigateRef.current(`/results?q=${encodeURIComponent(parts.join(', '))}`);
      } else if (result.lsoa_code) {
        // Fall back to area search using coordinates
        navigateRef.current(`/results?q=${lat.toFixed(5)},${lng.toFixed(5)}`);
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '&copy; OpenStreetMap Contributors',
          },
        },
        layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
      },
      center: [-1.5, 52.5], // Approximate center of England
      zoom: 6,
      maxZoom: 20,
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    map.on('load', () => {
      const tilesBaseUrl = window.location.origin + '/tiles';

      // INSPIRE parcel polygons (z16+)
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
          'fill-opacity': ['interpolate', ['linear'], ['zoom'], 16, 0.05, 18, 0.1],
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

      // Address point labels (z17+)
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
        },
        paint: {
          'text-color': '#1e293b',
          'text-halo-color': '#ffffff',
          'text-halo-width': 1.5,
        },
      });

      // Click handlers
      map.on('click', 'inspire-parcels-fill', handleFeatureClick);
      map.on('click', 'address-labels', handleFeatureClick);

      // Cursor
      map.on('mouseenter', 'inspire-parcels-fill', () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', 'inspire-parcels-fill', () => { map.getCanvas().style.cursor = ''; });
      map.on('mouseenter', 'address-labels', () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', 'address-labels', () => { map.getCanvas().style.cursor = ''; });
    });

    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, [handleFeatureClick]);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />
      {/* Zoom hint overlay */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 pointer-events-none">
        <div className="px-4 py-2 rounded-full bg-white/90 shadow-md backdrop-blur text-xs font-medium text-gray-600 border border-gray-200">
          Zoom in to see property boundaries and addresses
        </div>
      </div>
    </div>
  );
}
