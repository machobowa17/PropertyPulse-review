import { ExternalLink } from 'lucide-react';

interface Props {
  postcode?: string | null;   // e.g. "SW1A 1AA"
  ladCode?: string | null;
}

interface ResourceLink {
  label: string;
  desc: string;
  url: string;
  colour: string;
}

function pcNorm(pc: string | null | undefined) {
  return pc ? pc.replace(/\s+/g, '').toUpperCase() : '';
}

export default function UsefulResourcesPanel({ postcode, ladCode: _ladCode }: Props) {
  const pc = pcNorm(postcode);
  const pcSpace = pc.length > 3 ? pc.slice(0, -3) + ' ' + pc.slice(-3) : pc;

  const links: ResourceLink[] = [
    {
      label: 'Planning Portal',
      desc: 'Search local planning applications',
      url: pc
        ? `https://www.planningportal.co.uk/planning/planning-applications/how-to-apply`
        : 'https://www.planningportal.co.uk',
      colour: '#2563eb',
    },
    {
      label: 'Find Planning Apps',
      desc: 'Local authority planning search',
      url: pc
        ? `https://www.gov.uk/search-register-planning-decisions`
        : 'https://www.gov.uk/search-register-planning-decisions',
      colour: '#1d4ed8',
    },
    {
      label: 'Land Registry',
      desc: 'Title register, ownership & charges',
      url: pc
        ? `https://search-property-information.service.gov.uk/search/results?postcode=${encodeURIComponent(pcSpace)}`
        : 'https://search-property-information.service.gov.uk',
      colour: '#7c3aed',
    },
    {
      label: 'EA Flood Map',
      desc: 'Check flood risk zones',
      url: pc
        ? `https://check-long-term-flood-risk.service.gov.uk/postcode?postcode=${encodeURIComponent(pcSpace)}`
        : 'https://check-long-term-flood-risk.service.gov.uk',
      colour: '#0891b2',
    },
    {
      label: 'Ofsted',
      desc: 'School inspection reports',
      url: pc
        ? `https://www.ofsted.gov.uk/education-and-skills/find-an-inspection-report/find-an-inspection-report/?view=Provider&searchtype=POSTCODE&postcode=${encodeURIComponent(pcSpace)}`
        : 'https://www.ofsted.gov.uk',
      colour: '#059669',
    },
    {
      label: 'Ofcom Checker',
      desc: 'Broadband & mobile coverage',
      url: pc
        ? `https://checker.ofcom.org.uk/?postcode=${encodeURIComponent(pcSpace)}`
        : 'https://checker.ofcom.org.uk',
      colour: '#7c3aed',
    },
    {
      label: 'NHS Find Services',
      desc: 'GPs, dentists & pharmacies',
      url: pc
        ? `https://www.nhs.uk/service-search/find-a-gp/results/${encodeURIComponent(pcSpace)}`
        : 'https://www.nhs.uk/service-search',
      colour: '#dc2626',
    },
    {
      label: 'Police Crime Map',
      desc: 'Crime stats & local policing',
      url: pc
        ? `https://www.police.uk/pu/your-area/search-results/?postcode=${encodeURIComponent(pcSpace)}`
        : 'https://www.police.uk',
      colour: '#1f2937',
    },
    {
      label: 'VOA Band Lookup',
      desc: 'Check or challenge council tax band',
      url: pc
        ? `https://www.tax.service.gov.uk/check-council-tax-band/search?postcode=${encodeURIComponent(pcSpace)}`
        : 'https://www.tax.service.gov.uk/check-council-tax-band/search',
      colour: '#b45309',
    },
    {
      label: 'ONS Area Profile',
      desc: 'Census & socio-economic data',
      url: pc
        ? `https://www.ons.gov.uk/visualisations/areas/${pc}`
        : 'https://www.ons.gov.uk/visualisations/areas',
      colour: '#0f172a',
    },
  ];

  return (
    <div className="mt-2">
      {pc && (
        <div className="flex items-center gap-1.5 mb-2">
          <ExternalLink className="w-3 h-3 text-ink-faint" />
          <span className="text-[10px] text-ink-faint">Pre-filled for postcode</span>
          <span className="text-[10px] text-ink-faint bg-surface border border-divider px-2 py-0.5 rounded-full font-medium">
            {pcSpace}
          </span>
        </div>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
        {links.map((link) => (
          <a
            key={link.label}
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex flex-col gap-1 p-2.5 rounded-xl border border-divider hover:border-brand-300 hover:bg-brand-50 transition-all"
          >
            <div className="flex items-center justify-between">
              <span
                className="text-xs font-semibold leading-tight"
                style={{ color: link.colour }}
              >
                {link.label}
              </span>
              <ExternalLink className="w-3 h-3 text-ink-faint opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
            </div>
            <span className="text-[10px] text-ink-faint leading-tight">{link.desc}</span>
          </a>
        ))}
      </div>
    </div>
  );
}
