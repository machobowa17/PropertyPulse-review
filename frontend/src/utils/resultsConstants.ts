/* ── Static configuration for the Results page ──
 * Extracted from Results.tsx to keep the component focused on behaviour.
 */

/* ── Map layer priority per tab ── */
export const MAP_LAYER_PRIORITY: Record<string, string[]> = {
  'Property & Market': [
    'sold_price', 'choropleth_avg_price', 'choropleth_median_price', 'choropleth_price_per_sqft', 'choropleth_median_rent', 'choropleth_epc_score',
    'choropleth_housing_tenure', 'choropleth_housing_type',
  ],
  'Lifestyle & Connectivity': [
    'station', 'amenity', 'park', 'sports_recreation', 'ev_charger',
    'choropleth_broadband', 'choropleth_mobile_coverage',
  ],
  'Environment & Safety': ['flood_zone', 'choropleth_air_quality_no2', 'choropleth_air_quality_pm25'],
  'Community & Education': [
    'school', 'nhs_facility',
    'choropleth_median_earnings', 'choropleth_population_density', 'choropleth_median_age', 'choropleth_household_composition',
    'choropleth_good_health', 'choropleth_economically_active', 'choropleth_degree_educated',
    'choropleth_no_car', 'choropleth_born_abroad', 'choropleth_household_size',
    'choropleth_deprivation', 'choropleth_deprivation_income', 'choropleth_deprivation_employment',
    'choropleth_deprivation_education', 'choropleth_deprivation_health', 'choropleth_deprivation_crime',
    'choropleth_deprivation_barriers', 'choropleth_deprivation_living_environment',
  ],
  'Local Governance': ['choropleth_council_tax'],
};

/* ── Metric → map layer bindings (metric-follow system) ── */
export type MetricMapBinding = {
  mode: 'layer' | 'context';
  layerKey?: string;
  label: string;
  reason: string;
};

export const METRIC_MAP_BINDINGS: Record<string, MetricMapBinding> = {
  avg_price: { mode: 'layer', layerKey: 'choropleth_avg_price', label: 'Average price heatmap', reason: 'This metric has nearby spatial evidence, so the map follows it with the average-price heatmap.' },
  median_price: { mode: 'layer', layerKey: 'choropleth_median_price', label: 'Median price heatmap', reason: 'This metric has a dedicated spatial layer showing median transaction prices per LSOA.' },
  transaction_volume: { mode: 'layer', layerKey: 'sold_price', label: 'Recent sold-price points', reason: 'Transaction volume is best read against nearby sold-price evidence.' },
  price_per_sqft: { mode: 'layer', layerKey: 'choropleth_price_per_sqft', label: 'Price per sqft heatmap', reason: 'This metric has a dedicated spatial layer.' },
  affordability: { mode: 'layer', layerKey: 'choropleth_avg_price', label: 'Average price heatmap', reason: 'Price geography is the most honest spatial context for affordability.' },
  price_trend_yoy: { mode: 'layer', layerKey: 'sold_price', label: 'Recent sold-price points', reason: 'Price trend is grounded in transaction evidence.' },
  new_build_proportion: { mode: 'layer', layerKey: 'sold_price', label: 'Recent sold-price points', reason: 'New-build share is best interpreted against recent transaction evidence.' },
  epc_energy_score: { mode: 'layer', layerKey: 'choropleth_epc_score', label: 'EPC score heatmap', reason: 'This metric has a dedicated spatial layer.' },
  epc_rating: { mode: 'layer', layerKey: 'choropleth_epc_score', label: 'EPC score heatmap', reason: 'Best read with nearby EPC performance.' },
  nearest_station: { mode: 'layer', layerKey: 'station', label: 'Nearby stations', reason: 'This metric has direct spatial evidence.' },
  ptal: { mode: 'layer', layerKey: 'station', label: 'Nearby stations', reason: 'Nearby stations are the clearest honest spatial evidence.' },
  ptal_score: { mode: 'layer', layerKey: 'station', label: 'Nearby stations', reason: 'Nearby stations are the clearest honest spatial evidence.' },
  commute_distance: { mode: 'layer', layerKey: 'station', label: 'Nearby stations', reason: 'Commute distance is interpreted through nearby transport access.' },
  cycling: { mode: 'layer', layerKey: 'station', label: 'Nearby stations', reason: 'No dedicated route layer yet; map uses transport nodes as best current anchor.' },
  ev_chargers: { mode: 'layer', layerKey: 'ev_charger', label: 'Nearby EV chargers', reason: 'This metric has direct spatial evidence.' },
  no_car: { mode: 'layer', layerKey: 'choropleth_no_car', label: 'No-car households heatmap', reason: 'LSOA-level census evidence available.' },
  flood_risk: { mode: 'layer', layerKey: 'flood_zone', label: 'Flood-risk zones', reason: 'This metric has direct spatial evidence.' },
  primary_schools: { mode: 'layer', layerKey: 'school', label: 'Nearby schools', reason: 'This metric has direct spatial evidence.' },
  secondary_schools: { mode: 'layer', layerKey: 'school', label: 'Nearby schools', reason: 'This metric has direct spatial evidence.' },
  freehold_leasehold: { mode: 'context', label: 'Local analysis boundary', reason: 'Tenure mix does not yet have a direct spatial layer.' },
  median_rent: { mode: 'layer', layerKey: 'choropleth_median_rent', label: 'Median rent heatmap', reason: 'Honest local-authority proxy layer available.' },
  gross_yield: { mode: 'context', label: 'Local analysis boundary', reason: 'Computed from numeric evidence rather than a rent surface.' },
  investment_grade: { mode: 'context', label: 'Local analysis boundary', reason: 'Composite decision metric without a standalone spatial layer.' },
  amenities_15min: { mode: 'layer', layerKey: 'amenity', label: 'Nearby amenities', reason: 'Mapped place evidence available.' },
  mobile_coverage: { mode: 'layer', layerKey: 'choropleth_mobile_coverage', label: '4G outdoor coverage heatmap', reason: 'Postcode-level spatial evidence available.' },
  broadband: { mode: 'layer', layerKey: 'choropleth_broadband', label: 'Gigabit broadband heatmap', reason: 'Postcode-level spatial evidence available.' },
  air_quality_no2: { mode: 'layer', layerKey: 'choropleth_air_quality_no2', label: 'NO2 heatmap', reason: 'DEFRA air-quality grid cells aggregated to LSOAs.' },
  air_quality_pm25: { mode: 'layer', layerKey: 'choropleth_air_quality_pm25', label: 'PM2.5 heatmap', reason: 'DEFRA air-quality grid cells aggregated to LSOAs.' },
  noise: { mode: 'context', label: 'Local analysis boundary', reason: 'Currently numeric-only.' },
  nearest_park: { mode: 'layer', layerKey: 'park', label: 'Parks and green spaces', reason: 'Mapped green-space evidence available.' },
  green_cover: { mode: 'layer', layerKey: 'park', label: 'Parks and green spaces', reason: 'Anchored to mapped green-space sites.' },
  green_spaces: { mode: 'layer', layerKey: 'park', label: 'Parks and green spaces', reason: 'Mapped polygon evidence available.' },
  parks_1km: { mode: 'layer', layerKey: 'park', label: 'Parks and green spaces', reason: 'Mapped park locations available.' },
  sports_recreation: { mode: 'layer', layerKey: 'sports_recreation', label: 'Sports and recreation places', reason: 'Mapped place evidence available.' },
  nhs_facilities: { mode: 'layer', layerKey: 'nhs_facility', label: 'Nearby NHS facilities', reason: 'Mapped place evidence available.' },
  demographics_overview: { mode: 'layer', layerKey: 'choropleth_population_density', label: 'Population density heatmap', reason: 'Defaults to the broadest demographic surface.' },
  population_density: { mode: 'layer', layerKey: 'choropleth_population_density', label: 'Population density heatmap', reason: 'Direct LSOA-level census evidence.' },
  median_age: { mode: 'layer', layerKey: 'choropleth_median_age', label: 'Median age heatmap', reason: 'Direct LSOA-level census evidence.' },
  household_composition: { mode: 'layer', layerKey: 'choropleth_household_composition', label: 'Household composition heatmap', reason: 'LSOA-level census evidence.' },
  housing_tenure: { mode: 'layer', layerKey: 'choropleth_housing_tenure', label: 'Housing tenure heatmap', reason: 'LSOA-level census evidence.' },
  housing_type: { mode: 'layer', layerKey: 'choropleth_housing_type', label: 'Housing stock heatmap', reason: 'LSOA-level census evidence.' },
  deprivation: { mode: 'layer', layerKey: 'choropleth_deprivation', label: 'Deprivation heatmap', reason: 'LSOA-level spatial evidence.' },
  deprivation_income: { mode: 'layer', layerKey: 'choropleth_deprivation_income', label: 'Income deprivation heatmap', reason: 'LSOA-level spatial evidence.' },
  deprivation_employment: { mode: 'layer', layerKey: 'choropleth_deprivation_employment', label: 'Employment deprivation heatmap', reason: 'LSOA-level spatial evidence.' },
  deprivation_education: { mode: 'layer', layerKey: 'choropleth_deprivation_education', label: 'Education deprivation heatmap', reason: 'LSOA-level spatial evidence.' },
  deprivation_health: { mode: 'layer', layerKey: 'choropleth_deprivation_health', label: 'Health deprivation heatmap', reason: 'LSOA-level spatial evidence.' },
  deprivation_crime: { mode: 'layer', layerKey: 'choropleth_deprivation_crime', label: 'Crime deprivation heatmap', reason: 'LSOA-level spatial evidence.' },
  deprivation_barriers: { mode: 'layer', layerKey: 'choropleth_deprivation_barriers', label: 'Housing and services barriers heatmap', reason: 'LSOA-level spatial evidence.' },
  deprivation_living_environment: { mode: 'layer', layerKey: 'choropleth_deprivation_living_environment', label: 'Living environment heatmap', reason: 'LSOA-level spatial evidence.' },
  good_health: { mode: 'layer', layerKey: 'choropleth_good_health', label: 'Good health heatmap', reason: 'Direct LSOA-level census evidence.' },
  economically_active: { mode: 'layer', layerKey: 'choropleth_economically_active', label: 'Economic activity heatmap', reason: 'Direct LSOA-level census evidence.' },
  degree_educated: { mode: 'layer', layerKey: 'choropleth_degree_educated', label: 'Degree education heatmap', reason: 'Direct LSOA-level census evidence.' },
  born_abroad: { mode: 'layer', layerKey: 'choropleth_born_abroad', label: 'Born abroad heatmap', reason: 'Direct LSOA-level census evidence.' },
  household_size: { mode: 'layer', layerKey: 'choropleth_household_size', label: 'Household size heatmap', reason: 'LSOA-level census evidence.' },
  council_tax: { mode: 'layer', layerKey: 'choropleth_council_tax', label: 'Council tax heatmap', reason: 'Honest local-authority proxy layer available.' },
  local_authority: { mode: 'context', label: 'Local analysis boundary', reason: 'Already reflected by the search boundary.' },
  controlling_party: { mode: 'context', label: 'Local analysis boundary', reason: 'Governance metric without a direct map layer.' },
  water_company: { mode: 'context', label: 'Local analysis boundary', reason: 'Service-region metric without a direct rendered layer.' },
  financial_health: { mode: 'context', label: 'Local analysis boundary', reason: 'Aggregate governance metric.' },
  median_earnings: { mode: 'layer', layerKey: 'choropleth_median_earnings', label: 'Median earnings heatmap', reason: 'Honest local-authority proxy layer available.' },
};

/* Derived from MAP_LAYER_PRIORITY — single source of truth for all choropleth keys. */
export const ALL_CHOROPLETH_KEYS = [
  ...new Set(
    Object.values(MAP_LAYER_PRIORITY)
      .flat()
      .filter((k) => k.startsWith('choropleth_')),
  ),
];

export const LSOA_SUFFIX = 'LSOAs are small geographic units for statistical analysis in England and Wales, designed by the Office for National Statistics (ONS) to have 1,000–3,000 residents or 400–1,200 households. As of 2021, there are 33,755 LSOAs in England and 1,917 in Wales. The results below use LSOA-level data at their lowest level of granularity.';
