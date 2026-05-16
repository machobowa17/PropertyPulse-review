import { useState } from 'react';
import type { WikiSummaryResponse } from '../../api/client';

interface Props {
  data: WikiSummaryResponse;
}

export default function WikiSummaryCard({ data }: Props) {
  const [expanded, setExpanded] = useState(false);
  const summary = data.summary;
  if (!summary) return null;

  const paragraphs = summary.extract.split('\n\n');
  const firstPara = paragraphs[0] || '';
  const hasMore = paragraphs.length > 1;
  const displayText = expanded ? summary.extract : firstPara;

  return (
    <div className="rounded-xl border border-brand-100/60 bg-white overflow-hidden">
      {/* Image banner */}
      {summary.image?.url && (
        <div className="relative w-full h-40 overflow-hidden bg-ink-50">
          <img
            src={summary.image.url}
            alt={summary.title}
            className="w-full h-full object-cover"
            loading="lazy"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" />
          <h3 className="absolute bottom-3 left-4 text-white font-semibold text-base drop-shadow-sm">
            About {summary.title}
          </h3>
        </div>
      )}

      <div className="px-4 py-3">
        {/* Title (only if no image banner) */}
        {!summary.image?.url && (
          <h3 className="text-sm font-semibold text-ink-900 mb-1.5">About {summary.title}</h3>
        )}

        {/* Extract text */}
        <p className="text-xs leading-relaxed text-ink-600 whitespace-pre-line">
          {displayText}
        </p>

        {/* Expand / collapse */}
        {hasMore && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-1.5 text-[11px] font-medium text-brand-600 hover:text-brand-700 transition-colors cursor-pointer"
          >
            {expanded ? 'Show less' : 'Read more'}
          </button>
        )}

        {/* Attribution */}
        <p className="mt-2 text-[10px] text-ink-400">
          Source:{' '}
          <a
            href={summary.url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-brand-600 transition-colors"
          >
            Wikipedia
          </a>
          {' '}· CC BY-SA 3.0
        </p>
      </div>
    </div>
  );
}
