import { useState, useMemo } from 'react';
import { ChevronDown, Map, Maximize2, Minimize2 } from 'lucide-react';
import MapView from '../MapView';
import MapLayerControl from '../MapLayerControl';
import { useResults } from '../../context/ResultsContext';

/** Mobile map toggle button + animated collapse + map content */
export function ResultsMobileMap() {
  const [expanded, setExpanded] = useState(false);
  const {
    isDesktop,
    showMap,
    setShowMap,
    resolved,
    effectiveBoundary,
    effectiveLsoaBoundary,
    mapPois,
    mapPoisLoading,
    activeTab,
    visibleLayers,
    lsoa,
    mapViewportRef,
    handleViewportChange,
    choroplethData,
    choroplethUrl,
    activeChoropleth,
    mapFocusMode,
    focusLabel,
    focusReason,
    handleLayerToggle,
    mapFlyToRef,
    mapHighlightRef,
    selectProperty,
    propertyData,
  } = useResults();

  const selectedParcelFeature = useMemo<GeoJSON.Feature | null>(() => {
    if (!propertyData?.parcel?.geojson) return null;
    return { type: 'Feature', properties: {}, geometry: propertyData.parcel.geojson };
  }, [propertyData?.parcel?.geojson]);

  if (isDesktop) return null;

  return (
    <>
      {/* Map toggle button */}
      <div className="mb-4">
        <button
          onClick={() => setShowMap(!showMap)}
          aria-label={showMap ? 'Hide map' : 'Show map'}
          aria-expanded={showMap}
          className="flex items-center gap-2 text-sm text-brand-600 font-medium"
        >
          <Map className="w-4 h-4" aria-hidden="true" />
          {showMap ? 'Hide Map' : 'View Map'}
          <ChevronDown className={`w-4 h-4 transition-transform ${showMap ? 'rotate-180' : ''}`} aria-hidden="true" />
        </button>
      </div>

      {/* Mobile map — animated grid collapse */}
      <div
        className="grid transition-[grid-template-rows,opacity] duration-300 ease-out mb-4"
        style={{
          gridTemplateRows: !isDesktop && showMap && resolved?.coordinates?.lat ? '1fr' : '0fr',
          opacity: !isDesktop && showMap && resolved?.coordinates?.lat ? 1 : 0,
          visibility: !isDesktop && showMap && resolved?.coordinates?.lat ? 'visible' : 'hidden',
        }}
      >
        <div className="overflow-hidden">
          <div className="rounded-2xl overflow-hidden shadow-sm relative transition-[height] duration-300 ease-out" style={{ height: expanded ? '70vh' : '280px' }}>
            <MapView
              lat={resolved?.coordinates?.lat ?? 0}
              lon={resolved?.coordinates?.lon ?? 0}
              boundary={effectiveBoundary}
              lsoaBoundary={effectiveLsoaBoundary}
              pois={mapPois}
              activeTab={activeTab}
              visibleLayers={visibleLayers}
              searchLsoa={lsoa !== '_' ? lsoa : undefined}
              initialViewport={mapViewportRef.current}
              onViewportChange={handleViewportChange}
              choroplethData={activeChoropleth ? choroplethData : null}
              choroplethUrl={activeChoropleth ? choroplethUrl : null}
              onMapReady={(flyTo) => { mapFlyToRef.current = flyTo; }}
              onHighlightReady={(cb) => { mapHighlightRef.current = cb; }}
              onPropertySelect={selectProperty}
              selectedPropertyParcel={selectedParcelFeature}
            />
            <MapLayerControl
              activeTab={activeTab}
              visibleLayers={visibleLayers}
              onToggle={handleLayerToggle}
              soldPricesSince={mapPois?.sold_prices_since}
              focusMode={mapFocusMode}
              focusLabel={focusLabel}
              focusReason={focusReason}
            />
            {/* Expand/collapse button */}
            <button
              onClick={() => setExpanded((v) => !v)}
              aria-label={expanded ? 'Collapse map' : 'Expand map'}
              className="absolute bottom-2 right-2 z-10 flex h-8 w-8 items-center justify-center rounded-lg bg-white/90 shadow-md backdrop-blur hover:bg-gray-50 transition-colors border border-divider/60"
            >
              {expanded ? <Minimize2 className="w-4 h-4 text-ink" /> : <Maximize2 className="w-4 h-4 text-ink" />}
            </button>
            {(mapPoisLoading || (activeChoropleth && !choroplethData)) && (
              <div className="absolute inset-0 z-[5] flex items-center justify-center bg-white/20 backdrop-blur-[1px] rounded-2xl pointer-events-none">
                <div className="px-3 py-1.5 rounded-full bg-white/90 text-xs font-medium text-ink-muted shadow-sm">
                  {activeChoropleth && !choroplethData ? 'Loading heatmap…' : 'Loading…'}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

/** Desktop map aside panel — sticky sidebar */
export function ResultsDesktopMap() {
  const {
    isDesktop,
    resolved,
    effectiveBoundary,
    effectiveLsoaBoundary,
    mapPois,
    mapPoisLoading,
    activeTab,
    visibleLayers,
    lsoa,
    mapViewportRef,
    handleViewportChange,
    choroplethData,
    choroplethUrl,
    activeChoropleth,
    mapFocusMode,
    focusLabel,
    focusReason,
    handleLayerToggle,
    autoFollowEnabled,
    setAutoFollowEnabled,
    mapFlyToRef,
    mapHighlightRef,
    selectProperty,
    propertyData,
  } = useResults();

  const selectedParcelFeature = useMemo<GeoJSON.Feature | null>(() => {
    if (!propertyData?.parcel?.geojson) return null;
    return { type: 'Feature', properties: {}, geometry: propertyData.parcel.geojson };
  }, [propertyData?.parcel?.geojson]);

  if (!isDesktop || !resolved?.coordinates?.lat) return null;

  return (
    <aside className="w-[40%] shrink-0 sticky top-[105px] h-[calc(100vh-105px)] p-4 pl-0">
      <div className="rounded-2xl overflow-hidden shadow-sm h-full relative">
        <MapView
          lat={resolved.coordinates.lat}
          lon={resolved.coordinates.lon!}
          boundary={effectiveBoundary}
          lsoaBoundary={effectiveLsoaBoundary}
          pois={mapPois}
          activeTab={activeTab}
          visibleLayers={visibleLayers}
          searchLsoa={lsoa !== '_' ? lsoa : undefined}
          initialViewport={mapViewportRef.current}
          onViewportChange={handleViewportChange}
          choroplethData={activeChoropleth ? choroplethData : null}
          choroplethUrl={activeChoropleth ? choroplethUrl : null}
          onMapReady={(flyTo) => { mapFlyToRef.current = flyTo; }}
          onHighlightReady={(cb) => { mapHighlightRef.current = cb; }}
          onPropertySelect={selectProperty}
          selectedPropertyParcel={selectedParcelFeature}
        />
        <MapLayerControl
          activeTab={activeTab}
          visibleLayers={visibleLayers}
          onToggle={handleLayerToggle}
          soldPricesSince={mapPois?.sold_prices_since}
          focusMode={mapFocusMode}
          focusLabel={focusLabel}
          focusReason={focusReason}
          autoFollowEnabled={autoFollowEnabled}
          onAutoFollowToggle={() => setAutoFollowEnabled((v) => !v)}
        />
        {(mapPoisLoading || (activeChoropleth && !choroplethData)) && (
          <div className="absolute inset-0 z-[5] flex items-center justify-center bg-white/20 backdrop-blur-[1px] rounded-2xl pointer-events-none">
            <div className="px-3 py-1.5 rounded-full bg-white/90 text-xs font-medium text-ink-muted shadow-sm">
              {activeChoropleth && !choroplethData ? 'Loading heatmap…' : 'Loading…'}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
