import { useRef, useEffect } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

interface Props {
  lat: number;
  lon: number;
  boundary?: GeoJSON.Feature | null;
}

export default function MapView({ lat, lon, boundary }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

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
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          },
        },
        layers: [
          { id: 'osm-tiles', type: 'raster', source: 'osm', minzoom: 0, maxzoom: 19 },
        ],
      },
      center: [lon, lat],
      zoom: 14,
      attributionControl: { compact: true },
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    new maplibregl.Marker({ color: '#2563eb' })
      .setLngLat([lon, lat])
      .addTo(map);

    map.on('load', () => {
      // Bible 6.2.4: Ward boundary polygon
      if (boundary && boundary.geometry) {
        map.addSource('ward-boundary', {
          type: 'geojson',
          data: boundary,
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

        // Fit map to boundary bounds
        const coords = getAllCoords(boundary.geometry);
        if (coords.length > 0) {
          const bounds = new maplibregl.LngLatBounds(coords[0], coords[0]);
          coords.forEach((c) => bounds.extend(c));
          map.fitBounds(bounds, { padding: 40, maxZoom: 15 });
        }
      } else {
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
    });

    mapRef.current = map;
    return () => map.remove();
  }, [lat, lon, boundary]);

  return <div ref={containerRef} className="w-full h-full" />;
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
