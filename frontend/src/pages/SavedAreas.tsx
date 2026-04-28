import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Bookmark, MapPin, Trash2 } from 'lucide-react';
import type { SavedAreaEntry } from '../utils/savedAreas';
import { getSavedAreas, removeSavedArea, touchSavedArea } from '../utils/savedAreas';

export default function SavedAreas() {
  const navigate = useNavigate();
  const [items, setItems] = useState<SavedAreaEntry[]>(() => getSavedAreas());

  const handleRemove = (id: string) => {
    removeSavedArea(id);
    setItems(getSavedAreas());
  };

  return (
    <div className="min-h-dvh bg-[#0c0c0e] text-white">
      <div className="mx-auto max-w-6xl px-6 py-8 lg:px-10 lg:py-10">
        <div className="flex flex-col gap-4 border-b border-white/[0.06] pb-8">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm font-semibold text-white/58 hover:text-white transition-colors"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Back to search
          </Link>
          <div className="max-w-3xl">
            <h1 className="mt-4 text-4xl font-black tracking-tight text-white">Saved areas</h1>
            <p className="mt-3 text-base leading-relaxed text-white/54">
              Areas you've bookmarked for comparison or later review. Saved to this browser — they'll be here when you come back.
            </p>
          </div>
        </div>

        <section className="mt-8 rounded-3xl border border-white/[0.08] bg-white/[0.04] p-5 lg:p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.04] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
                <Bookmark className="h-3.5 w-3.5 text-emerald-300" aria-hidden="true" />
                Saved areas
              </div>
              <h2 className="mt-3 text-2xl font-bold tracking-tight text-white">{items.length} saved {items.length === 1 ? 'area' : 'areas'}</h2>
            </div>
          </div>

          {items.length === 0 ? (
            <div className="mt-5 rounded-3xl border border-dashed border-white/[0.08] bg-black/10 px-5 py-8 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-white/[0.08] bg-white/[0.04]">
                <Bookmark className="h-5 w-5 text-emerald-300" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-white">Nothing saved yet</h3>
              <p className="mx-auto mt-2 max-w-xl text-sm leading-relaxed text-white/48">
                Hit the "Save" button on any area results page to bookmark it here for quick access.
              </p>
              <Link
                to="/"
                className="mt-4 inline-flex items-center gap-2 rounded-xl border border-white/[0.12] bg-white/[0.06] px-4 py-2.5 text-sm font-semibold text-white hover:bg-white/[0.1] transition-colors"
              >
                Start a new search
              </Link>
            </div>
          ) : (
            <div className="mt-5 grid gap-3">
              {items.map((item) => (
                <article key={item.id} className="rounded-3xl border border-white/[0.08] bg-black/10 p-4 lg:p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.04] px-3 py-1 text-xs font-semibold text-white/75">
                          <MapPin className="h-3.5 w-3.5 text-white/45" aria-hidden="true" />
                          {item.areaName}
                        </div>
                        <span className="inline-flex items-center rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-xs text-white/55">
                          {item.parentName}
                        </span>
                        <span className="inline-flex items-center rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-xs text-white/55">
                          {item.decisionMode} mode
                        </span>
                      </div>
                      <p className="mt-3 text-sm leading-relaxed text-white/52">
                        Saved {new Date(item.savedAt).toLocaleDateString()} and last revisited {new Date(item.lastViewedAt).toLocaleDateString()}.
                      </p>
                    </div>
                    <div className="flex flex-col gap-2 sm:flex-row lg:shrink-0">
                      <button
                        type="button"
                        onClick={() => {
                          touchSavedArea(item.areaName, item.decisionMode);
                          navigate(`/results?q=${encodeURIComponent(item.query)}&mode=${item.decisionMode}`);
                        }}
                        className="inline-flex items-center justify-center rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-[#0c0c0e] hover:bg-white/90 transition-colors"
                      >
                        Open area
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRemove(item.id)}
                        className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/[0.12] bg-white/[0.04] px-4 py-2.5 text-sm font-semibold text-white hover:bg-white/[0.08] transition-colors"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                        Remove
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
