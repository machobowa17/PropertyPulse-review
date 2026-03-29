import { useRef, useEffect } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

interface Props {
  lat: number;
  lon: number;
  boundary?: GeoJSON.Feature | null;
  lsoaBoundary?: GeoJSON.Feature | null;
  pois?: GeoJSON.FeatureCollection | null;
  activeTab?: string;
}

const POI_COLOURS: Record<string, string> = {
  school: '#ea580c',
  station: '#7c3aed',
  ev_charger: '#16a34a',
};

export default function MapView({ lat, lon, boundary, lsoaBoundary, pois, activeTab }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  // Keep a ref to activeTab so the map on('load') callback can read the current value
  const activeTabRef = useRef(activeTab);
  useEffect(() => { activeTabRef.current = activeTab; }, [activeTab]);

  const ISOCHRONE_LAYERS = [
    'iso-15-fill', 'iso-15-line',
    'iso-10-fill', 'iso-10-line',
    'iso-5-fill',  'iso-5-line',
  ];
  const ISOCHRONE_SOURCES = ['iso-5', 'iso-10', 'iso-15'];

  function applyIsochronesToMap(map: maplibregl.Map, tab: string | undefined, latVal: number, lonVal: number) {
    ISOCHRONE_LAYERS.forEach((l) => { if (map.getLayer(l)) map.removeLayer(l); });
    ISOCHRONE_SOURCES.forEach((s) => { if (map.getSource(s)) map.removeSource(s); });
    if (tab !== 'Lifestyle & Connectivity') return;
    const rings = [
      { id: 'iso-15', metres: 1250, colour: '#16a34a' },
      { id: 'iso-10', metres: 833,  colour: '#ca8a04' },
      { id: 'iso-5',  metres: 417,  colour: '#dc2626' },
    ];
    rings.forEach(({ id, metres, colour }) => {
      map.addSource(id, { type: 'geojson', data: createCircle(lonVal, latVal, metres) });
      map.addLayer({ id: `${id}-fill`, type: 'fill', source: id, paint: { 'fill-color': colour, 'fill-opacity': 0.05 } });
      map.addLayer({ id: `${id}-line`, type: 'line', source: id, paint: { 'line-color': colour, 'line-width': 1.5, 'line-dasharray': [4, 3], 'line-opacity': 0.7 } });
    });
  }

  // Reactive effect: handles tab switches on an already-loaded map
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (!map.isStyleLoaded()) return; // map-creation effect handles initial render via on('load')
    applyIsochronesToMap(map, activeTab, lat, lon);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

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
          paint: { 'fill-color': '#7c3aed', 'fill-opacity': 0.07 },
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

  // Update POI markers + flood zone polygons when pois change (without recreating the map)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const renderPois = () => {
      // Remove old POI markers
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];

      // Remove old flood zone layers/source
      const FLOOD_SOURCE = 'flood-zones';
      if (map.getLayer('flood-zones-fill')) map.removeLayer('flood-zones-fill');
      if (map.getLayer('flood-zones-line')) map.removeLayer('flood-zones-line');
      if (map.getSource(FLOOD_SOURCE)) map.removeSource(FLOOD_SOURCE);

      if (pois && pois.features) {
        const pointFeatures = pois.features.filter((f) => f.geometry.type === 'Point');
        const polygonFeatures = pois.features.filter(
          (f) => f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon'
        );

        for (const feature of pointFeatures) {
          const [lng, lt] = (feature.geometry as GeoJSON.Point).coordinates as [number, number];
          const props = feature.properties || {};
          const colour = POI_COLOURS[props.category] || '#6b7280';
          const marker = new maplibregl.Marker({ color: colour, scale: 0.7 })
            .setLngLat([lng, lt])
            .setPopup(
              new maplibregl.Popup({ offset: 20, maxWidth: '200px' }).setHTML(
                `<div style="font-size:12px"><strong>${props.name || ''}</strong>${props.ofsted ? `<br>Ofsted: ${props.ofsted}` : ''}${props.phase ? `<br>${props.phase}` : ''}${props.operator ? `<br>${props.operator}` : ''}${props.connectors != null ? `<br>${props.connectors} connector${props.connectors !== 1 ? 's' : ''}` : ''}${props.max_kw != null ? ` · ${props.max_kw}kW` : ''}${props.dist_m ? `<br>${props.dist_m}m away` : ''}</div>`
              )
            )
            .addTo(map);
          markersRef.current.push(marker);
        }

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
      }
    };

    // If style not loaded yet, defer until the load event
    if (!map.isStyleLoaded()) {
      map.once('load', renderPois);
      return () => { map.off('load', renderPois); };
    }
    renderPois();
  }, [pois]);

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
      // Walking isochrones — rendered here so they appear on every fresh map instance
      applyIsochronesToMap(map, activeTabRef.current, lat, lon);

      // LSOA boundary — tighter dashed purple overlay
      if (lsoaBoundary && lsoaBoundary.geometry) {
        map.addSource('lsoa-boundary', { type: 'geojson', data: lsoaBoundary });
        map.addLayer({
          id: 'lsoa-boundary-fill',
          type: 'fill',
          source: 'lsoa-boundary',
          paint: { 'fill-color': '#7c3aed', 'fill-opacity': 0.07 },
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
    return () => { map.remove(); mapRef.current = null; };
  // lsoaBoundary handled by its own effect; exclude from deps to avoid map recreation
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
