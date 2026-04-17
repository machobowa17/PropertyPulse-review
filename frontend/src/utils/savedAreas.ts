export type SavedAreaCollection = 'shortlist' | 'watchlist';

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

const STORAGE_KEY = 'propertypulse_saved_areas_v1';
const MAX_ITEMS_PER_COLLECTION = 24;

function canUseStorage(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

function readRaw(): SavedAreaEntry[] {
  if (!canUseStorage()) return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is SavedAreaEntry => {
      return !!item
        && typeof item === 'object'
        && typeof item.id === 'string'
        && (item.collection === 'shortlist' || item.collection === 'watchlist')
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

export function buildSavedAreaId(areaName: string, collection: SavedAreaCollection, decisionMode: string): string {
  return `${collection}::${decisionMode}::${areaName.trim().toLowerCase()}`;
}

export function getSavedAreas(): SavedAreaEntry[] {
  return readRaw().sort((a, b) => new Date(b.lastViewedAt).getTime() - new Date(a.lastViewedAt).getTime());
}

export function getSavedAreasByCollection(collection: SavedAreaCollection): SavedAreaEntry[] {
  return getSavedAreas().filter((item) => item.collection === collection);
}

export function saveArea(entry: Omit<SavedAreaEntry, 'id' | 'savedAt' | 'lastViewedAt'>): SavedAreaEntry {
  const now = new Date().toISOString();
  const id = buildSavedAreaId(entry.areaName, entry.collection, entry.decisionMode);
  const existing = readRaw();
  const nextEntry: SavedAreaEntry = {
    ...entry,
    id,
    savedAt: existing.find((item) => item.id === id)?.savedAt || now,
    lastViewedAt: now,
  };

  const filtered = existing.filter((item) => item.id !== id);
  const sameCollection = filtered.filter((item) => item.collection === entry.collection);
  const otherCollections = filtered.filter((item) => item.collection !== entry.collection);
  const trimmedCollection = [nextEntry, ...sameCollection]
    .sort((a, b) => new Date(b.lastViewedAt).getTime() - new Date(a.lastViewedAt).getTime())
    .slice(0, MAX_ITEMS_PER_COLLECTION);

  writeRaw([...trimmedCollection, ...otherCollections]);
  return nextEntry;
}

export function removeSavedArea(id: string): void {
  const existing = readRaw();
  writeRaw(existing.filter((item) => item.id !== id));
}

export function isAreaSaved(areaName: string, collection: SavedAreaCollection, decisionMode: string): boolean {
  const id = buildSavedAreaId(areaName, collection, decisionMode);
  return readRaw().some((item) => item.id === id);
}

export function touchSavedArea(areaName: string, collection: SavedAreaCollection, decisionMode: string): void {
  const id = buildSavedAreaId(areaName, collection, decisionMode);
  const existing = readRaw();
  const index = existing.findIndex((item) => item.id === id);
  if (index === -1) return;
  existing[index] = {
    ...existing[index],
    lastViewedAt: new Date().toISOString(),
  };
  writeRaw(existing);
}
