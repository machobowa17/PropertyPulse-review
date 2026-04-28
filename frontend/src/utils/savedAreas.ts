export type SavedAreaCollection = 'saved';

export interface SavedAreaEntry {
  id: string;
  collection: SavedAreaCollection;
  query: string;
  areaName: string;
  parentName: string;
  sessionKey: string | null;
  decisionMode: 'buy' | 'rent' | 'invest';
  persona: string;
  notes: string[];
  savedAt: string;
  lastViewedAt: string;
}

const STORAGE_KEY = 'propertypulse_saved_areas_v2';
const STORAGE_KEY_V1 = 'propertypulse_saved_areas_v1';
const MAX_ITEMS = 48;

function canUseStorage(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

function readRaw(): SavedAreaEntry[] {
  if (!canUseStorage()) return [];
  try {
    // Try v2 first
    let raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      // Migrate from v1 if present
      raw = window.localStorage.getItem(STORAGE_KEY_V1);
      if (raw) {
        // Migrate: normalize all entries to collection='saved', deduplicate by area+mode
        const v1 = JSON.parse(raw) as Array<Record<string, unknown>>;
        if (Array.isArray(v1)) {
          const seen = new Set<string>();
          const migrated: SavedAreaEntry[] = [];
          for (const item of v1) {
            if (!item || typeof item !== 'object') continue;
            const areaName = String(item.areaName ?? '');
            const decisionMode = String(item.decisionMode ?? 'buy');
            const dedup = `${decisionMode}::${areaName.trim().toLowerCase()}`;
            if (seen.has(dedup)) continue;
            seen.add(dedup);
            migrated.push({
              id: buildSavedAreaId(areaName, decisionMode),
              collection: 'saved',
              query: String(item.query ?? ''),
              areaName,
              parentName: String(item.parentName ?? ''),
              sessionKey: typeof item.sessionKey === 'string' ? item.sessionKey : null,
              decisionMode: decisionMode as 'buy' | 'rent' | 'invest',
              persona: String(item.persona ?? ''),
              notes: Array.isArray(item.notes) ? item.notes as string[] : [],
              savedAt: String(item.savedAt ?? new Date().toISOString()),
              lastViewedAt: String(item.lastViewedAt ?? new Date().toISOString()),
            });
          }
          writeRaw(migrated);
          // Clean up v1 key
          try { window.localStorage.removeItem(STORAGE_KEY_V1); } catch { /* ignore */ }
          return migrated;
        }
      }
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is SavedAreaEntry => {
      return !!item
        && typeof item === 'object'
        && typeof item.id === 'string'
        && item.collection === 'saved'
        && typeof item.query === 'string'
        && typeof item.areaName === 'string'
        && typeof item.parentName === 'string'
        && (typeof item.sessionKey === 'string' || item.sessionKey === null)
        && typeof item.decisionMode === 'string'
        && typeof item.persona === 'string'
        && Array.isArray(item.notes)
        && typeof item.savedAt === 'string'
        && typeof item.lastViewedAt === 'string';
    });
  } catch {
    return [];
  }
}

function writeRaw(entries: SavedAreaEntry[]): void {
  if (!canUseStorage()) return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch { /* Safari private browsing or quota exceeded — safe to ignore */ }
}

export function buildSavedAreaId(areaName: string, decisionMode: string): string {
  return `saved::${decisionMode}::${areaName.trim().toLowerCase()}`;
}

export function getSavedAreas(): SavedAreaEntry[] {
  return readRaw().sort((a, b) => new Date(b.lastViewedAt).getTime() - new Date(a.lastViewedAt).getTime());
}

export function saveArea(entry: Omit<SavedAreaEntry, 'id' | 'collection' | 'savedAt' | 'lastViewedAt'>): SavedAreaEntry {
  const now = new Date().toISOString();
  const id = buildSavedAreaId(entry.areaName, entry.decisionMode);
  const existing = readRaw();
  const nextEntry: SavedAreaEntry = {
    ...entry,
    id,
    collection: 'saved',
    savedAt: existing.find((item) => item.id === id)?.savedAt || now,
    lastViewedAt: now,
  };

  const filtered = existing.filter((item) => item.id !== id);
  const all = [nextEntry, ...filtered]
    .sort((a, b) => new Date(b.lastViewedAt).getTime() - new Date(a.lastViewedAt).getTime())
    .slice(0, MAX_ITEMS);

  writeRaw(all);
  return nextEntry;
}

export function removeSavedArea(id: string): void {
  const existing = readRaw();
  writeRaw(existing.filter((item) => item.id !== id));
}

export function isAreaSaved(areaName: string, decisionMode: string): boolean {
  const id = buildSavedAreaId(areaName, decisionMode);
  return readRaw().some((item) => item.id === id);
}

export function touchSavedArea(areaName: string, decisionMode: string): void {
  const id = buildSavedAreaId(areaName, decisionMode);
  const existing = readRaw();
  const index = existing.findIndex((item) => item.id === id);
  if (index === -1) return;
  existing[index] = {
    ...existing[index],
    lastViewedAt: new Date().toISOString(),
  };
  writeRaw(existing);
}
