// Small shared helpers for the site script.

export const $ = <T extends Element = HTMLElement>(sel: string, root: ParentNode = document): T | null =>
  root.querySelector<T>(sel);

export const $$ = <T extends Element = HTMLElement>(sel: string, root: ParentNode = document): T[] =>
  Array.from(root.querySelectorAll<T>(sel));

export const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

/** A plain left click, with no key held to open a new tab or window. */
export const plainClick = (ev: MouseEvent): boolean =>
  ev.button === 0 && !ev.metaKey && !ev.ctrlKey && !ev.shiftKey && !ev.altKey;

// localStorage can throw (private windows, blocked site data), so every use goes through these.
export function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function save(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Nowhere to save to. The site works the same without it.
  }
}

/** One row of /search.json.  k: g game, p post, l link. */
export interface Row {
  k: 'g' | 'p' | 'l';
  t: string;
  s: string;
  u: string;
  i?: string;
  x: string;
  play?: boolean;
}

let index: Promise<Row[]> | null = null;

/** Every game, post and page, fetched once and shared by the palette and "Surprise me". */
export function searchIndex(): Promise<Row[]> {
  index ??= fetch('/search.json')
    .then((r) => (r.ok ? (r.json() as Promise<Row[]>) : []))
    .catch(() => []);
  return index;
}

/** Games played on this device, newest first. */
export interface Recent {
  id: string;
  t: number;
}

const RECENT = 'ycg.recent';

export const recents = (): Recent[] => load<Recent[]>(RECENT, []).filter((r) => typeof r?.id === 'string');

export function remember(id: string): void {
  if (!id) return;
  save(RECENT, [{ id, t: Date.now() }, ...recents().filter((r) => r.id !== id)].slice(0, 8));
}

export const clearRecents = (): void => save(RECENT, []);

/** "2026-11-17" as "2 days ago", or null when the plain date reads better. */
export function relative(iso: string): string | null {
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m || !d) return null;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const days = Math.round((today - new Date(y, m - 1, d).getTime()) / 864e5);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 14) return `${days} days ago`;
  if (days < 56) return `${Math.round(days / 7)} weeks ago`;
  return null;
}
