/** Bible Part 5 — Persona × Takeaway Matrix (Full Coverage) */
import type { Persona, PersonaId, Metric } from '../types';

export const PERSONAS: Persona[] = [
  { id: 'family', label: 'Family Buyer', icon: '🏠', description: 'Schools, safety, gardens' },
  { id: 'young_professional', label: 'Young Professional', icon: '💼', description: 'Commute, nightlife, broadband' },
  { id: 'investor', label: 'Investor (BTL)', icon: '📈', description: 'Yield, capital growth, demand' },
  { id: 'retired', label: 'Retired Buyer', icon: '🌿', description: 'Peace, healthcare, green space' },
  { id: 'student', label: 'Student Renter', icon: '🎓', description: 'Affordability, transport, social' },
  { id: 'expat', label: 'Expat Relocating', icon: '✈️', description: 'Schools, connectivity, community' },
];

type Colour = 'green' | 'amber' | 'red' | 'neutral';

interface Takeaway {
  soWhat: string;
  watchOut: string;
  colour: Colour;
}

/** Bible Part 5.2 — Full takeaway matrix for all 42 metrics × 6 personas. */
export function getTakeaway(metric: Metric, persona: PersonaId): Takeaway {
  const { id, comparison_flag, local_value } = metric;
  const isHigher = comparison_flag === 'higher_than_parent';
  const isLower = comparison_flag === 'lower_than_parent';
  const val = typeof local_value === 'number' ? local_value : 0;
  const strVal = String(local_value ?? '');

  // ═══════════════════════════════════════════
  // TAB 1: PROPERTY & MARKET
  // ═══════════════════════════════════════════

  // --- Average / Median Price ---
  if (id === 'avg_price' || id === 'median_price') {
    if (isLower) {
      if (persona === 'family') return { soWhat: 'More affordable', watchOut: 'Check reasons why', colour: 'green' };
      if (persona === 'young_professional') return { soWhat: 'Cheaper to buy later', watchOut: 'Growth potential?', colour: 'green' };
      if (persona === 'investor') return { soWhat: 'Entry point', watchOut: 'Growth potential?', colour: 'green' };
      if (persona === 'retired') return { soWhat: 'Better value', watchOut: 'Area quality', colour: 'green' };
      if (persona === 'student') return { soWhat: 'Cheaper area', watchOut: 'Check amenities', colour: 'green' };
      if (persona === 'expat') return { soWhat: 'Affordable entry', watchOut: 'Research the area', colour: 'green' };
    }
    if (isHigher) {
      if (persona === 'family') return { soWhat: 'Premium area', watchOut: 'Stretching budget', colour: 'amber' };
      if (persona === 'young_professional') return { soWhat: 'Expensive area', watchOut: 'Save longer', colour: 'amber' };
      if (persona === 'investor') return { soWhat: 'Capital preservation', watchOut: 'Lower yields', colour: 'amber' };
      if (persona === 'retired') return { soWhat: 'Established area', watchOut: 'Premium pricing', colour: 'amber' };
      if (persona === 'student') return { soWhat: 'Pricey area', watchOut: 'Rents likely high too', colour: 'red' };
      if (persona === 'expat') return { soWhat: 'Desirable location', watchOut: 'High entry cost', colour: 'amber' };
    }
  }

  // --- Price per Sqft ---
  if (id === 'price_per_sqft') {
    if (isLower) {
      if (persona === 'family') return { soWhat: 'More space for money', watchOut: 'Check build quality', colour: 'green' };
      if (persona === 'investor') return { soWhat: 'Value per sqft', watchOut: 'Appreciation pace', colour: 'green' };
      return { soWhat: 'Good value per sqft', watchOut: 'Compare local stock', colour: 'green' };
    }
    if (isHigher) {
      if (persona === 'family') return { soWhat: 'Premium per sqft', watchOut: 'Smaller rooms', colour: 'amber' };
      if (persona === 'investor') return { soWhat: 'High entry £/sqft', watchOut: 'Margin squeeze', colour: 'amber' };
      return { soWhat: 'Above average £/sqft', watchOut: 'Premium pricing', colour: 'amber' };
    }
  }

  // --- Transaction Volume ---
  if (id === 'transaction_volume') {
    if (isLower) {
      if (persona === 'investor') return { soWhat: 'Low liquidity', watchOut: 'Hard to sell', colour: 'red' };
      if (persona === 'family') return { soWhat: 'Quiet market', watchOut: 'Less choice', colour: 'amber' };
      return { soWhat: 'Low activity', watchOut: 'Limited options', colour: 'amber' };
    }
    if (isHigher) {
      if (persona === 'investor') return { soWhat: 'Liquid market', watchOut: 'Competition', colour: 'green' };
      if (persona === 'family') return { soWhat: 'Active market', watchOut: 'Act fast', colour: 'green' };
      return { soWhat: 'Busy market', watchOut: 'Competitive bidding', colour: 'green' };
    }
  }

  // --- Freehold vs Leasehold ---
  if (id === 'freehold_leasehold') {
    const fhPct = val;
    if (fhPct > 70) {
      if (persona === 'family') return { soWhat: 'Mostly freehold', watchOut: 'None', colour: 'green' };
      if (persona === 'investor') return { soWhat: 'Freehold stock', watchOut: 'Higher entry price', colour: 'green' };
      return { soWhat: 'Freehold dominant', watchOut: 'None', colour: 'green' };
    }
    if (fhPct < 30) {
      if (persona === 'family') return { soWhat: 'Mostly leasehold', watchOut: 'Ground rent + service', colour: 'amber' };
      if (persona === 'investor') return { soWhat: 'Leasehold area', watchOut: 'Lease length check', colour: 'amber' };
      return { soWhat: 'Leasehold dominant', watchOut: 'Check lease terms', colour: 'amber' };
    }
    return { soWhat: 'Mixed tenure', watchOut: 'Check individual titles', colour: 'neutral' };
  }

  // --- New Build Proportion ---
  if (id === 'new_build_proportion') {
    if (val > 15) {
      if (persona === 'family') return { soWhat: 'New homes available', watchOut: 'Premium pricing', colour: 'green' };
      if (persona === 'investor') return { soWhat: 'New stock for BTL', watchOut: 'Stamp duty surcharge', colour: 'green' };
      return { soWhat: 'Development active', watchOut: 'Construction disruption', colour: 'green' };
    }
    return { soWhat: 'Established stock', watchOut: 'Renovation costs', colour: 'neutral' };
  }

  // --- Price Trend YoY ---
  if (id === 'price_trend_yoy') {
    if (isHigher) {
      if (persona === 'family') return { soWhat: 'Prices rising fast', watchOut: 'Act now or wait?', colour: 'amber' };
      if (persona === 'investor') return { soWhat: 'Strong capital growth', watchOut: 'Peak risk', colour: 'green' };
      if (persona === 'retired') return { soWhat: 'Appreciating area', watchOut: 'Buying at top?', colour: 'amber' };
      return { soWhat: 'Above-avg growth', watchOut: 'Cycle risk', colour: 'amber' };
    }
    if (isLower) {
      if (persona === 'family') return { soWhat: 'Slower growth', watchOut: 'Equity risk', colour: 'amber' };
      if (persona === 'investor') return { soWhat: 'Weak capital growth', watchOut: 'Total return check', colour: 'red' };
      return { soWhat: 'Below-avg growth', watchOut: 'Monitor trend', colour: 'amber' };
    }
  }

  // --- Median Rent ---
  if (id === 'median_rent') {
    if (isHigher) {
      if (persona === 'investor') return { soWhat: 'Strong rental income', watchOut: 'Void periods', colour: 'green' };
      if (persona === 'young_professional' || persona === 'student') return { soWhat: 'Pricey rents', watchOut: 'Budget pressure', colour: 'red' };
      if (persona === 'expat') return { soWhat: 'High rents', watchOut: 'Budget carefully', colour: 'red' };
      return { soWhat: 'High rents', watchOut: 'Cost of living', colour: 'amber' };
    }
    if (isLower) {
      if (persona === 'investor') return { soWhat: 'Weaker income', watchOut: 'Low demand?', colour: 'red' };
      if (persona === 'young_professional' || persona === 'student') return { soWhat: 'Affordable', watchOut: 'Check quality', colour: 'green' };
      if (persona === 'expat') return { soWhat: 'Affordable rents', watchOut: 'Check connectivity', colour: 'green' };
      return { soWhat: 'Affordable rents', watchOut: 'Demand factors', colour: 'green' };
    }
  }

  // --- Gross Yield ---
  if (id === 'gross_yield') {
    if (isHigher) {
      if (persona === 'investor') return { soWhat: 'Strong yield', watchOut: 'Sustainability', colour: 'green' };
      return { soWhat: 'Good returns here', watchOut: 'Higher risk?', colour: 'neutral' };
    }
    if (isLower) {
      if (persona === 'investor') return { soWhat: 'Weak yield', watchOut: 'Capital play only', colour: 'red' };
      return { soWhat: 'Low rental yield', watchOut: 'Owner-occupier area', colour: 'neutral' };
    }
  }

  // --- Affordability (rent as % of income) ---
  if (id === 'affordability') {
    if (val > 40) {
      if (persona === 'young_professional') return { soWhat: 'Rent is a stretch', watchOut: 'Over 40% of income', colour: 'red' };
      if (persona === 'student') return { soWhat: 'Very expensive', watchOut: 'Shared housing needed', colour: 'red' };
      if (persona === 'investor') return { soWhat: 'Tenants squeezed', watchOut: 'Default risk', colour: 'amber' };
      if (persona === 'expat') return { soWhat: 'High cost of living', watchOut: 'Budget impact', colour: 'red' };
      return { soWhat: 'Low affordability', watchOut: 'High housing costs', colour: 'amber' };
    }
    if (val < 25) {
      if (persona === 'young_professional') return { soWhat: 'Very affordable', watchOut: 'None', colour: 'green' };
      if (persona === 'student') return { soWhat: 'Affordable area', watchOut: 'None', colour: 'green' };
      if (persona === 'investor') return { soWhat: 'Tenants can pay', watchOut: 'Low yield area?', colour: 'green' };
      return { soWhat: 'Affordable area', watchOut: 'None', colour: 'green' };
    }
    return { soWhat: 'Moderate affordability', watchOut: 'Budget check', colour: 'amber' };
  }

  // --- Investment Grade ---
  if (id === 'investment_grade') {
    const grade = strVal;
    if (grade === 'A' || grade === 'B') {
      if (persona === 'investor') return { soWhat: 'Strong investment area', watchOut: 'Entry timing', colour: 'green' };
      return { soWhat: 'High-rated area', watchOut: 'Premium prices', colour: 'green' };
    }
    if (grade === 'C' || grade === 'D') {
      if (persona === 'investor') return { soWhat: 'Average prospects', watchOut: 'Selectivity needed', colour: 'amber' };
      return { soWhat: 'Mid-range outlook', watchOut: 'Research further', colour: 'neutral' };
    }
    if (persona === 'investor') return { soWhat: 'Weak fundamentals', watchOut: 'Avoid or speculate', colour: 'red' };
    return { soWhat: 'Below average rating', watchOut: 'Check outlook', colour: 'amber' };
  }

  // ═══════════════════════════════════════════
  // TAB 2: LIFESTYLE & CONNECTIVITY
  // ═══════════════════════════════════════════

  // --- 15-Min Score ---
  if (id === 'fifteen_min_score') {
    if (val >= 70) {
      if (persona === 'retired') return { soWhat: 'Walk to everything', watchOut: 'Can be busy', colour: 'green' };
      if (persona === 'young_professional') return { soWhat: 'Vibrant neighbourhood', watchOut: 'None', colour: 'green' };
      return { soWhat: 'Great walkability', watchOut: 'None', colour: 'green' };
    }
    if (val >= 40) {
      return { soWhat: 'Decent amenities', watchOut: 'Some car trips', colour: 'amber' };
    }
    if (persona === 'retired') return { soWhat: 'Car dependent', watchOut: 'Isolation risk', colour: 'red' };
    if (persona === 'student') return { soWhat: 'Far from shops', watchOut: 'Transport needed', colour: 'red' };
    return { soWhat: 'Limited walkability', watchOut: 'Car essential', colour: 'red' };
  }

  // --- Amenities count ---
  if (id === 'amenities_15min') {
    if (isHigher) {
      if (persona === 'young_professional') return { soWhat: 'Plenty of options', watchOut: 'Can be noisy', colour: 'green' };
      if (persona === 'retired') return { soWhat: 'Well-served area', watchOut: 'Busy streets', colour: 'green' };
      return { soWhat: 'Well-served area', watchOut: 'Can be noisy', colour: 'green' };
    }
    if (isLower) {
      if (persona === 'retired') return { soWhat: 'Quieter area', watchOut: 'Car dependency', colour: 'amber' };
      if (persona === 'young_professional') return { soWhat: 'Limited nightlife', watchOut: 'Social scene', colour: 'red' };
      if (persona === 'student') return { soWhat: 'Few options nearby', watchOut: 'Transport costs', colour: 'red' };
      return { soWhat: 'Fewer amenities', watchOut: 'Car needed', colour: 'amber' };
    }
  }

  // --- Nearest Station ---
  if (id === 'nearest_station') {
    const distM = val;
    if (distM <= 800) {
      if (persona === 'young_professional') return { soWhat: 'Easy commute', watchOut: 'Train noise', colour: 'green' };
      if (persona === 'student') return { soWhat: 'Great for transport', watchOut: 'None', colour: 'green' };
      if (persona === 'expat') return { soWhat: 'Well-connected', watchOut: 'None', colour: 'green' };
      return { soWhat: 'Station nearby', watchOut: 'Potential noise', colour: 'green' };
    }
    if (distM <= 1600) {
      return { soWhat: 'Walkable to station', watchOut: 'Longer walk', colour: 'amber' };
    }
    if (persona === 'young_professional') return { soWhat: 'Far from station', watchOut: 'Commute impact', colour: 'red' };
    return { soWhat: 'Station quite far', watchOut: 'Bus/car needed', colour: 'amber' };
  }

  // --- EV Chargers ---
  if (id === 'ev_chargers') {
    if (isHigher) return { soWhat: 'Good EV coverage', watchOut: 'None', colour: 'green' };
    if (isLower) return { soWhat: 'Fewer EV chargers', watchOut: 'If you drive electric', colour: 'amber' };
  }

  // --- PTAL ---
  if (id === 'ptal') {
    if (isHigher) {
      if (persona === 'young_professional') return { soWhat: 'Excellent connections', watchOut: 'Premium rents', colour: 'green' };
      if (persona === 'student') return { soWhat: 'Great transport links', watchOut: 'None', colour: 'green' };
      return { soWhat: 'Well-connected', watchOut: 'None', colour: 'green' };
    }
    if (isLower) {
      if (persona === 'young_professional') return { soWhat: 'Weaker links', watchOut: 'Commute time', colour: 'amber' };
      return { soWhat: 'Less connected', watchOut: 'Car may be needed', colour: 'amber' };
    }
  }

  // --- Cycling ---
  if (id === 'cycling') {
    if (isHigher) {
      if (persona === 'young_professional') return { soWhat: 'Cycling-friendly', watchOut: 'Road safety', colour: 'green' };
      return { soWhat: 'Active cycling area', watchOut: 'None', colour: 'green' };
    }
    if (isLower) return { soWhat: 'Low cycling uptake', watchOut: 'Less infrastructure', colour: 'neutral' };
  }

  // --- Broadband ---
  if (id === 'broadband') {
    if (isHigher) {
      if (persona === 'young_professional') return { soWhat: 'Excellent connectivity', watchOut: 'None', colour: 'green' };
      if (persona === 'expat') return { soWhat: 'Fast internet', watchOut: 'None', colour: 'green' };
      return { soWhat: 'Good broadband', watchOut: 'Check your provider', colour: 'green' };
    }
    if (isLower) {
      if (persona === 'young_professional') return { soWhat: 'Connectivity gap', watchOut: 'WFH issues', colour: 'red' };
      if (persona === 'investor') return { soWhat: 'Broadband gap', watchOut: 'Tenant complaints', colour: 'amber' };
      return { soWhat: 'Below average', watchOut: 'Remote work risk', colour: 'amber' };
    }
  }

  // --- Mobile Coverage ---
  if (id === 'mobile_coverage') {
    if (val >= 95) return { soWhat: 'Full coverage', watchOut: 'None', colour: 'green' };
    if (val >= 80) return { soWhat: 'Good coverage', watchOut: 'Indoor spots', colour: 'amber' };
    if (persona === 'young_professional') return { soWhat: 'Coverage gaps', watchOut: 'Connectivity issues', colour: 'red' };
    return { soWhat: 'Patchy coverage', watchOut: 'Check your network', colour: 'amber' };
  }

  // ═══════════════════════════════════════════
  // TAB 3: ENVIRONMENT & SAFETY
  // ═══════════════════════════════════════════

  // --- Crime Rate ---
  if (id === 'crime_rate') {
    if (isHigher) {
      if (persona === 'family') return { soWhat: 'Think carefully', watchOut: 'School run safety', colour: 'red' };
      if (persona === 'young_professional') return { soWhat: 'Worth knowing', watchOut: 'Night-time safety', colour: 'amber' };
      if (persona === 'investor') return { soWhat: 'Price opportunity', watchOut: 'Tenant quality risk', colour: 'amber' };
      if (persona === 'retired') return { soWhat: 'Caution advised', watchOut: 'Personal safety', colour: 'red' };
      if (persona === 'student') return { soWhat: 'Fairly typical', watchOut: 'Bike theft risk', colour: 'amber' };
      if (persona === 'expat') return { soWhat: 'Above average crime', watchOut: 'Research streets', colour: 'red' };
    }
    if (isLower) {
      if (persona === 'family') return { soWhat: 'Safer than average', watchOut: 'None', colour: 'green' };
      if (persona === 'retired') return { soWhat: 'Safe area', watchOut: 'None', colour: 'green' };
      return { soWhat: 'Lower crime', watchOut: 'None', colour: 'green' };
    }
  }

  // --- Crime Trend ---
  if (id === 'crime_trend') {
    if (val > 10) {
      if (persona === 'family') return { soWhat: 'Crime rising', watchOut: 'Deteriorating safety', colour: 'red' };
      if (persona === 'investor') return { soWhat: 'Crime increasing', watchOut: 'Tenant turnover', colour: 'amber' };
      return { soWhat: 'Crime trending up', watchOut: 'Monitor closely', colour: 'amber' };
    }
    if (val < -10) {
      if (persona === 'family') return { soWhat: 'Crime falling', watchOut: 'None', colour: 'green' };
      if (persona === 'investor') return { soWhat: 'Improving safety', watchOut: 'Prices may follow', colour: 'green' };
      return { soWhat: 'Crime declining', watchOut: 'None', colour: 'green' };
    }
    return { soWhat: 'Stable crime levels', watchOut: 'None', colour: 'neutral' };
  }

  // --- Flood Risk ---
  if (id === 'flood_risk') {
    const level = strVal;
    if (level === 'High' || level === 'Medium') {
      if (persona === 'investor') return { soWhat: 'Insurance costs', watchOut: 'Resale risk', colour: 'red' };
      if (persona === 'family') return { soWhat: 'Flood risk area', watchOut: 'Safety + insurance', colour: 'red' };
      return { soWhat: 'Flood risk present', watchOut: 'Insurance + damage', colour: 'red' };
    }
    if (level === 'Low') return { soWhat: 'Some flood risk', watchOut: 'Check insurance', colour: 'amber' };
    return { soWhat: 'Low flood risk', watchOut: 'None', colour: 'green' };
  }

  // --- Air Quality ---
  if (id === 'air_quality_no2' || id === 'air_quality_pm25') {
    if (isLower) {
      if (persona === 'family') return { soWhat: 'Clean air', watchOut: 'None', colour: 'green' };
      if (persona === 'retired') return { soWhat: 'Healthy air', watchOut: 'None', colour: 'green' };
      return { soWhat: 'Better than average', watchOut: 'None', colour: 'green' };
    }
    if (isHigher) {
      if (persona === 'family') return { soWhat: 'Pollution concern', watchOut: "Children's health", colour: 'red' };
      if (persona === 'retired') return { soWhat: 'Health risk', watchOut: 'Respiratory issues', colour: 'red' };
      if (persona === 'expat') return { soWhat: 'Air quality issue', watchOut: 'Health impact', colour: 'amber' };
      return { soWhat: 'Above average pollution', watchOut: 'Health impact', colour: 'amber' };
    }
  }

  // --- Nearest Park ---
  if (id === 'nearest_park') {
    const distM = val;
    if (distM <= 400) {
      if (persona === 'family') return { soWhat: 'Park on doorstep', watchOut: 'None', colour: 'green' };
      if (persona === 'retired') return { soWhat: 'Green space nearby', watchOut: 'None', colour: 'green' };
      return { soWhat: 'Close to green space', watchOut: 'None', colour: 'green' };
    }
    if (distM <= 800) return { soWhat: 'Park walkable', watchOut: 'Short walk', colour: 'green' };
    if (persona === 'family') return { soWhat: 'Park further away', watchOut: 'Less outdoor play', colour: 'amber' };
    return { soWhat: 'Limited green space', watchOut: 'Quality of life', colour: 'amber' };
  }

  // --- EPC Rating ---
  if (id === 'epc_rating') {
    if (isHigher) {
      if (persona === 'investor') return { soWhat: 'Good EPC stock', watchOut: 'None', colour: 'green' };
      return { soWhat: 'Energy efficient', watchOut: 'None', colour: 'green' };
    }
    if (isLower) {
      if (persona === 'investor') return { soWhat: 'EPC upgrade needed', watchOut: 'MEES compliance', colour: 'red' };
      if (persona === 'family') return { soWhat: 'Higher energy bills', watchOut: 'Insulation costs', colour: 'amber' };
      return { soWhat: 'Low efficiency', watchOut: 'Energy costs', colour: 'amber' };
    }
  }

  // --- ESG Score ---
  if (id === 'esg_score') {
    if (val >= 70) {
      if (persona === 'family') return { soWhat: 'Sustainable area', watchOut: 'None', colour: 'green' };
      if (persona === 'investor') return { soWhat: 'Future-proofed', watchOut: 'None', colour: 'green' };
      return { soWhat: 'High ESG rating', watchOut: 'None', colour: 'green' };
    }
    if (val >= 45) return { soWhat: 'Moderate ESG', watchOut: 'Room for improvement', colour: 'amber' };
    if (persona === 'investor') return { soWhat: 'ESG risk', watchOut: 'Regulatory risk', colour: 'red' };
    return { soWhat: 'Low ESG score', watchOut: 'Environmental concerns', colour: 'red' };
  }

  // ═══════════════════════════════════════════
  // TAB 4: COMMUNITY & EDUCATION
  // ═══════════════════════════════════════════

  // --- Population Density ---
  if (id === 'population_density') {
    if (isHigher) {
      if (persona === 'family') return { soWhat: 'Densely populated', watchOut: 'Less space', colour: 'amber' };
      if (persona === 'young_professional') return { soWhat: 'Urban buzz', watchOut: 'Crowding', colour: 'green' };
      if (persona === 'retired') return { soWhat: 'Busy area', watchOut: 'Noise + crowds', colour: 'red' };
      if (persona === 'investor') return { soWhat: 'High demand area', watchOut: 'Competition', colour: 'green' };
      return { soWhat: 'High density', watchOut: 'Crowding', colour: 'amber' };
    }
    if (isLower) {
      if (persona === 'family') return { soWhat: 'More space', watchOut: 'Fewer services', colour: 'green' };
      if (persona === 'retired') return { soWhat: 'Peaceful density', watchOut: 'Car needed', colour: 'green' };
      return { soWhat: 'Spacious area', watchOut: 'Less urban', colour: 'neutral' };
    }
  }

  // --- Median Age ---
  if (id === 'median_age') {
    if (isHigher) {
      if (persona === 'retired') return { soWhat: 'Mature community', watchOut: 'None', colour: 'green' };
      if (persona === 'young_professional') return { soWhat: 'Older demographic', watchOut: 'Quieter nightlife', colour: 'amber' };
      if (persona === 'student') return { soWhat: 'Older area', watchOut: 'Few peers', colour: 'red' };
      return { soWhat: 'Older population', watchOut: 'Different vibe', colour: 'neutral' };
    }
    if (isLower) {
      if (persona === 'young_professional') return { soWhat: 'Young community', watchOut: 'None', colour: 'green' };
      if (persona === 'student') return { soWhat: 'Age-match area', watchOut: 'None', colour: 'green' };
      if (persona === 'retired') return { soWhat: 'Younger area', watchOut: 'May feel out of place', colour: 'amber' };
      return { soWhat: 'Younger demographic', watchOut: 'Consider fit', colour: 'neutral' };
    }
  }

  // --- Household Composition ---
  if (id === 'household_composition') {
    if (isHigher) {
      // Higher = more families
      if (persona === 'family') return { soWhat: 'Family-oriented area', watchOut: 'None', colour: 'green' };
      if (persona === 'young_professional') return { soWhat: 'Family area', watchOut: 'Quieter social scene', colour: 'amber' };
      if (persona === 'student') return { soWhat: 'Family-heavy area', watchOut: 'Less student life', colour: 'amber' };
      return { soWhat: 'Family area', watchOut: 'None', colour: 'neutral' };
    }
    if (isLower) {
      if (persona === 'family') return { soWhat: 'Fewer families', watchOut: 'Playdate options', colour: 'amber' };
      if (persona === 'young_professional') return { soWhat: 'Singles/sharers area', watchOut: 'None', colour: 'green' };
      if (persona === 'student') return { soWhat: 'Sharing-friendly', watchOut: 'None', colour: 'green' };
      return { soWhat: 'Mixed households', watchOut: 'None', colour: 'neutral' };
    }
  }

  // --- Housing Tenure ---
  if (id === 'housing_tenure') {
    if (isHigher) {
      // Higher = more owner-occupied
      if (persona === 'family') return { soWhat: 'Settled community', watchOut: 'Less rental stock', colour: 'green' };
      if (persona === 'investor') return { soWhat: 'Owner-occupier area', watchOut: 'Less BTL demand?', colour: 'amber' };
      if (persona === 'young_professional') return { soWhat: 'Ownership-heavy', watchOut: 'Fewer rentals', colour: 'amber' };
      return { soWhat: 'Stable community', watchOut: 'None', colour: 'green' };
    }
    if (isLower) {
      if (persona === 'investor') return { soWhat: 'Strong rental demand', watchOut: 'Competition', colour: 'green' };
      if (persona === 'young_professional' || persona === 'student') return { soWhat: 'Renter-friendly area', watchOut: 'Turnover', colour: 'green' };
      if (persona === 'family') return { soWhat: 'Transient area', watchOut: 'Community stability', colour: 'amber' };
      return { soWhat: 'Renter-heavy', watchOut: 'Turnover', colour: 'neutral' };
    }
  }

  // --- Housing Type (% detached) ---
  if (id === 'housing_type') {
    const detPct = val;
    if (detPct > 40) {
      if (persona === 'family') return { soWhat: 'Spacious homes', watchOut: 'Premium prices', colour: 'green' };
      if (persona === 'retired') return { soWhat: 'Detached living', watchOut: 'Maintenance costs', colour: 'green' };
      return { soWhat: 'Houses dominate', watchOut: 'Higher prices', colour: 'neutral' };
    }
    if (detPct < 15) {
      if (persona === 'family') return { soWhat: 'Limited family homes', watchOut: 'Lack of gardens', colour: 'red' };
      if (persona === 'young_professional') return { soWhat: 'High availability', watchOut: 'Service charges', colour: 'green' };
      if (persona === 'investor') return { soWhat: 'Strong rental demand', watchOut: 'Leasehold restrictions', colour: 'green' };
      if (persona === 'retired') return { soWhat: 'Flat-heavy area', watchOut: 'Mobility access', colour: 'amber' };
      return { soWhat: 'Mostly flats', watchOut: 'Limited houses', colour: 'amber' };
    }
    return { soWhat: 'Mixed housing stock', watchOut: 'Check specific property', colour: 'neutral' };
  }

  // --- Primary Schools ---
  if (id === 'primary_schools') {
    if (val >= 3) {
      if (persona === 'family') return { soWhat: 'Good school choice', watchOut: 'Catchment competition', colour: 'green' };
      if (persona === 'expat') return { soWhat: 'Schools nearby', watchOut: 'Admissions process', colour: 'green' };
      return { soWhat: 'Good primary schools', watchOut: 'None', colour: 'green' };
    }
    if (val >= 1) {
      if (persona === 'family') return { soWhat: 'Limited school options', watchOut: 'Check catchments', colour: 'amber' };
      return { soWhat: 'Some good primaries', watchOut: 'Limited choice', colour: 'amber' };
    }
    if (persona === 'family') return { soWhat: 'No Good/Outstanding nearby', watchOut: 'School quality issue', colour: 'red' };
    return { soWhat: 'Few rated primaries', watchOut: 'School access', colour: 'neutral' };
  }

  // --- Secondary Schools ---
  if (id === 'secondary_schools') {
    if (val >= 3) {
      if (persona === 'family') return { soWhat: 'Strong secondaries', watchOut: 'Check Progress 8', colour: 'green' };
      if (persona === 'expat') return { soWhat: 'Good school access', watchOut: 'UK school system differs', colour: 'green' };
      return { soWhat: 'Good secondary schools', watchOut: 'None', colour: 'green' };
    }
    if (persona === 'family') return { soWhat: 'Fewer top secondaries', watchOut: 'Travel to school', colour: 'amber' };
    return { soWhat: 'Limited secondaries', watchOut: 'Check coverage', colour: 'neutral' };
  }

  // --- IMD Deprivation ---
  if (id === 'deprivation') {
    if (isLower) {
      if (persona === 'family') return { soWhat: 'Low deprivation', watchOut: 'Premium pricing', colour: 'green' };
      if (persona === 'investor') return { soWhat: 'Affluent area', watchOut: 'Lower yields', colour: 'amber' };
      if (persona === 'retired') return { soWhat: 'Quality of life', watchOut: 'Cost of living', colour: 'green' };
      return { soWhat: 'Desirable area', watchOut: 'Higher costs', colour: 'green' };
    }
    if (isHigher) {
      if (persona === 'family') return { soWhat: 'Think carefully', watchOut: 'School quality risk', colour: 'red' };
      if (persona === 'investor') return { soWhat: 'Price opportunity', watchOut: 'Tenant risk', colour: 'amber' };
      if (persona === 'retired') return { soWhat: 'Caution advised', watchOut: 'Personal safety', colour: 'red' };
      return { soWhat: 'Worth knowing', watchOut: 'Area challenges', colour: 'amber' };
    }
  }

  // --- NHS Facilities ---
  if (id === 'nhs_facilities') {
    if (val >= 5) {
      if (persona === 'retired') return { soWhat: 'Healthcare access', watchOut: 'None', colour: 'green' };
      if (persona === 'family') return { soWhat: 'GPs nearby', watchOut: 'None', colour: 'green' };
      return { soWhat: 'Good NHS coverage', watchOut: 'None', colour: 'green' };
    }
    if (val >= 1) return { soWhat: 'Some NHS facilities', watchOut: 'May be busy', colour: 'amber' };
    if (persona === 'retired') return { soWhat: 'Few facilities', watchOut: 'GP access concern', colour: 'red' };
    return { soWhat: 'Limited NHS nearby', watchOut: 'Register early', colour: 'amber' };
  }

  // --- Area Persona ---
  if (id === 'area_persona') {
    const p = strVal;
    if (p === 'Family Suburb') {
      if (persona === 'family') return { soWhat: 'Your kind of area', watchOut: 'None', colour: 'green' };
      if (persona === 'young_professional') return { soWhat: 'Suburban feel', watchOut: 'Quieter lifestyle', colour: 'amber' };
      if (persona === 'student') return { soWhat: 'Family-oriented', watchOut: 'Few peers', colour: 'amber' };
      return { soWhat: 'Family suburb', watchOut: 'None', colour: 'neutral' };
    }
    if (p === 'Urban Professional Hub') {
      if (persona === 'young_professional') return { soWhat: 'Perfect match', watchOut: 'None', colour: 'green' };
      if (persona === 'family') return { soWhat: 'Urban area', watchOut: 'Less family-friendly', colour: 'amber' };
      if (persona === 'retired') return { soWhat: 'Busy urban area', watchOut: 'Noise + pace', colour: 'amber' };
      return { soWhat: 'Urban professional area', watchOut: 'None', colour: 'neutral' };
    }
    if (p === 'Retirement Haven') {
      if (persona === 'retired') return { soWhat: 'Ideal for you', watchOut: 'None', colour: 'green' };
      if (persona === 'young_professional') return { soWhat: 'Quiet area', watchOut: 'Limited social', colour: 'amber' };
      if (persona === 'student') return { soWhat: 'Very quiet', watchOut: 'No nightlife', colour: 'red' };
      return { soWhat: 'Retirement area', watchOut: 'Quiet lifestyle', colour: 'neutral' };
    }
    if (p === 'Student Quarter') {
      if (persona === 'student') return { soWhat: 'Student area', watchOut: 'None', colour: 'green' };
      if (persona === 'family') return { soWhat: 'Student area', watchOut: 'Noise + turnover', colour: 'red' };
      if (persona === 'retired') return { soWhat: 'Student area', watchOut: 'Noise concerns', colour: 'red' };
      if (persona === 'investor') return { soWhat: 'Student demand', watchOut: 'Seasonal voids', colour: 'green' };
      return { soWhat: 'Student quarter', watchOut: 'Transient population', colour: 'amber' };
    }
    return { soWhat: 'Mixed community', watchOut: 'Check fit', colour: 'neutral' };
  }

  // ═══════════════════════════════════════════
  // TAB 5: LOCAL GOVERNANCE
  // ═══════════════════════════════════════════

  // --- Council Tax ---
  if (id === 'council_tax') {
    if (isHigher) {
      if (persona === 'investor') return { soWhat: 'Higher running costs', watchOut: 'Tenant cost factor', colour: 'amber' };
      return { soWhat: 'Higher tax', watchOut: 'Ongoing cost', colour: 'amber' };
    }
    if (isLower) {
      if (persona === 'investor') return { soWhat: 'Lower running costs', watchOut: 'Check services', colour: 'green' };
      return { soWhat: 'Lower tax', watchOut: 'Check service quality', colour: 'green' };
    }
  }

  // --- Local Authority ---
  if (id === 'local_authority') {
    return { soWhat: '', watchOut: '', colour: 'neutral' };
  }

  // --- Controlling Party ---
  if (id === 'controlling_party') {
    return { soWhat: 'Local governance', watchOut: 'Policy impacts', colour: 'neutral' };
  }

  // --- Water Company ---
  if (id === 'water_company') {
    return { soWhat: 'Utility provider', watchOut: 'Check bills + service', colour: 'neutral' };
  }

  // --- Financial Health (S114) ---
  if (id === 'financial_health') {
    if (strVal.includes('S114')) {
      if (persona === 'investor') return { soWhat: 'Council distress', watchOut: 'Service cuts', colour: 'red' };
      if (persona === 'family') return { soWhat: 'Council in trouble', watchOut: 'Service reductions', colour: 'red' };
      return { soWhat: 'S114 notice issued', watchOut: 'Service quality risk', colour: 'red' };
    }
    return { soWhat: 'Council solvent', watchOut: 'None', colour: 'green' };
  }

  // ═══════════════════════════════════════════
  // DEFAULT FALLBACK
  // ═══════════════════════════════════════════
  if (comparison_flag === null) return { soWhat: '', watchOut: '', colour: 'neutral' };
  if (isHigher) return { soWhat: 'Above parent average', watchOut: 'Worth investigating', colour: 'amber' };
  if (isLower) return { soWhat: 'Below parent average', watchOut: 'Worth investigating', colour: 'amber' };
  return { soWhat: 'In line with average', watchOut: 'None', colour: 'neutral' };
}
