function Shimmer({ className }: { className: string }) {
  return (
    <div
      className={`relative overflow-hidden rounded-lg bg-divider ${className}`}
    >
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.4s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent" />
    </div>
  );
}

/** Single metric card skeleton */
function MetricCardSkeleton() {
  return (
    <div className="rounded-2xl border border-divider bg-white p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Shimmer className="w-8 h-8 rounded-xl" />
          <Shimmer className="w-32 h-4" />
        </div>
        <Shimmer className="w-16 h-5 rounded-full" />
      </div>
      <div className="flex items-end justify-between">
        <Shimmer className="w-24 h-7" />
        <Shimmer className="w-20 h-3" />
      </div>
      <Shimmer className="w-full h-1.5 rounded-full" />
    </div>
  );
}

/** Persona score card skeleton — wider banner at the top */
function PersonaCardSkeleton() {
  return (
    <div className="rounded-2xl border border-divider bg-white p-5 space-y-3">
      <div className="flex items-center gap-3">
        <Shimmer className="w-10 h-10 rounded-xl" />
        <div className="space-y-1.5 flex-1">
          <Shimmer className="w-40 h-4" />
          <Shimmer className="w-24 h-3" />
        </div>
        <Shimmer className="w-14 h-8 rounded-xl" />
      </div>
      <Shimmer className="w-full h-2 rounded-full" />
    </div>
  );
}

interface Props {
  /** How many metric card skeletons to show */
  count?: number;
  /** Show the persona score banner skeleton too */
  showPersona?: boolean;
}

export default function SkeletonCard({ count = 8, showPersona = true }: Props) {
  return (
    <div className="grid gap-3">
      {showPersona && <PersonaCardSkeleton />}
      {Array.from({ length: count }).map((_, i) => (
        <MetricCardSkeleton key={i} />
      ))}
    </div>
  );
}

/** Resolving skeleton — shown while the postcode/place is being looked up.
 *  Renders the area banner as shimmer + a full tab skeleton beneath. */
export function ResolvingSkeleton() {
  return (
    <div className="max-w-7xl mx-auto w-full px-4">
      {/* Fake area banner */}
      <div className="pt-5 pb-2 space-y-2">
        <Shimmer className="w-64 h-8 rounded-xl" />
        <div className="flex gap-2">
          <Shimmer className="w-24 h-5 rounded" />
          <Shimmer className="w-20 h-5 rounded" />
          <Shimmer className="w-28 h-5 rounded" />
        </div>
      </div>
      {/* Fake tab bar */}
      <div className="flex gap-2 py-3 border-b border-divider mb-6">
        {Array.from({ length: 5 }).map((_, i) => (
          <Shimmer key={i} className="w-28 h-8 rounded-lg" />
        ))}
      </div>
      <SkeletonCard count={6} showPersona={false} />
    </div>
  );
}
