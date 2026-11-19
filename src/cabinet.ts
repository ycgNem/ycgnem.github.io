// The cabinet: filter by status, 2D or 3D and a typed word, and switch between the curated
// shelves and one flat list sorted by latest update.
import { $, $$ } from './util';

/** Which game statuses each filter button covers. */
const GROUPS: Record<string, string[]> = {
  released: ['released', 'playable'],
  playtest: ['playtest'],
  prototype: ['prototype', 'indev'],
};

export function cabinet(): void {
  const root = $('[data-cab]');
  if (!root) return;
  const shelves = $('[data-shelves]', root);
  const flat = $('[data-flat]', root);
  if (!shelves || !flat) return;
  const count = $('[data-cab-count]', root);
  const empty = $('[data-cab-empty]', root);
  const search = $<HTMLInputElement>('[data-cab-search]', root);
  const cards = $$<HTMLAnchorElement>('.gcard', shelves);
  let flatCards: HTMLAnchorElement[] = [];
  const state = { status: 'all', dim: '', q: '', order: 'shelves' };

  const matches = (card: HTMLElement): boolean => {
    const d = card.dataset;
    if (state.status !== 'all' && !(GROUPS[state.status] ?? []).includes(d.status ?? '')) return false;
    if (state.dim && d.dim !== state.dim) return false;
    const text = d.text ?? '';
    return state.q.split(/\s+/).every((word) => text.includes(word));
  };

  // The "Latest" list is built the first time it's asked for: a copy of every card, newest first.
  const buildFlat = (): void => {
    if (flatCards.length) return;
    flatCards = cards
      .map((card) => {
        const copy = card.cloneNode(true) as HTMLAnchorElement;
        copy.className = 'gcard gcard-md';
        return copy;
      })
      .sort((a, b) => (b.dataset.updated ?? '').localeCompare(a.dataset.updated ?? ''));
    flat.append(...flatCards);
  };

  const press = (attr: 'status' | 'dim' | 'order', value: string): void => {
    for (const b of $$<HTMLButtonElement>(`button[data-${attr}]`, root)) {
      b.setAttribute('aria-pressed', String(b.dataset[attr] === value));
    }
  };

  const apply = (animate = false): void => {
    const latest = state.order === 'latest';
    if (latest) buildFlat();
    let n = 0;
    for (const card of cards) {
      const ok = matches(card);
      card.hidden = !ok;
      if (ok) n++;
    }
    for (const card of flatCards) card.hidden = !matches(card);
    for (const shelf of $$('[data-shelf]', shelves)) {
      const shown = $$('.gcard:not([hidden])', shelf).length;
      shelf.hidden = shown === 0;
      const badge = $('[data-shelf-n]', shelf);
      if (badge) badge.textContent = String(shown).padStart(2, '0');
    }
    shelves.hidden = latest || n === 0;
    flat.hidden = !latest || n === 0;
    if (empty) empty.hidden = n > 0;
    if (count) count.textContent = String(n);
    press('status', state.status);
    press('dim', state.dim);
    press('order', state.order);
    if (animate) {
      const grid = latest ? flat : shelves;
      grid.classList.remove('swap');
      void grid.offsetWidth; // restart the animation
      grid.classList.add('swap');
    }
  };

  root.addEventListener('click', (ev) => {
    const button = (ev.target as Element).closest<HTMLButtonElement>('button');
    if (!button) return;
    const d = button.dataset;
    if (d.status) state.status = d.status;
    else if (d.dim) state.dim = state.dim === d.dim ? '' : d.dim;
    else if (d.order) state.order = d.order;
    else if ('cabClear' in d) {
      Object.assign(state, { status: 'all', dim: '', q: '' });
      if (search) search.value = '';
    } else return;
    apply(true);
  });
  search?.addEventListener('input', () => {
    state.q = search.value.trim().toLowerCase();
    apply();
  });
  search?.addEventListener('keydown', (ev) => {
    if (ev.key !== 'Escape' || !search.value) return;
    search.value = '';
    state.q = '';
    apply();
  });
}
