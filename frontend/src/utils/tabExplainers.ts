import type { TabName } from '../types';

interface TabExplainer {
  title: string;
  summary: string;
  decision: string;
}

export const TAB_EXPLAINERS: Record<TabName, TabExplainer> = {
  'Property & Market': {
    title: 'Property & Market',
    summary: 'Transaction prices, rental costs, yields, and energy efficiency across the local area.',
    decision: 'What does it cost to buy or rent here, and how does that compare?',
  },
  'Lifestyle & Connectivity': {
    title: 'Lifestyle & Connectivity',
    summary: 'Transport links, broadband, amenities, and commuting patterns for the local area.',
    decision: 'How well connected is daily life here?',
  },
  'Environment & Safety': {
    title: 'Environment & Safety',
    summary: 'Crime rates, air quality, flood risk, green spaces, and environmental quality.',
    decision: 'How safe and pleasant is the local environment?',
  },
  'Community & Education': {
    title: 'Community & Education',
    summary: 'Demographics, schools, deprivation, healthcare access, and neighbourhood character.',
    decision: 'What kind of community lives here and what services are available?',
  },
  'Local Governance': {
    title: 'Local Governance',
    summary: 'Council tax, political control, water provider, and local authority context.',
    decision: 'Who governs this area and what are the running costs?',
  },
};
