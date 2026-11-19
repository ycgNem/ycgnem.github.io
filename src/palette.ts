// The >_ palette: press / (or Ctrl+K) anywhere, type a few letters, Enter.
import { $, type Row, recents, searchIndex } from './util';

const KIND: Record<Row['k'], string> = { g: 'Game', p: 'Post', l: 'Page' };

/** True when every letter of `word` appears in `text` in order ("vrd" finds "verdant"). */
function inOrder(word: string, text: string): boolean {
  let at = 0;
  for (const ch of word) {
    at = text.indexOf(ch, at) + 1;
    if (!at) return false;
  }
  return true;
}

/** How well a row matches every typed word. 0 means it doesn't. */
function score(row: Row, words: string[]): number {
  const title = row.t.toLowerCase();
  const rest = `${row.s} ${row.x}`.toLowerCase();
  let total = row.k === 'g' ? 5 : 0;
  for (const word of words) {
    let s = 0;
    if (title.startsWith(word)) s = 100;
    else if (title.split(/[^a-z0-9]+/).some((part) => part.startsWith(word))) s = 70;
    else if (title.includes(word)) s = 50;
    else if (rest.includes(word)) s = 20;
    else if (word.length > 2 && inOrder(word, title)) s = 8;
    if (!s) return 0;
    total += s;
  }
  return total;
}

export function palette(): void {
  const dialog = $<HTMLDialogElement>('[data-palette]');
  const input = $<HTMLInputElement>('[data-palette-input]');
  const list = $<HTMLUListElement>('[data-palette-list]');
  if (!dialog || !input || !list || typeof dialog.showModal !== 'function') return;
  let rows: Row[] = [];
  let shown: Row[] = [];
  let selected = 0;

  const select = (n: number): void => {
    if (!shown.length) return;
    selected = (n + shown.length) % shown.length;
    Array.from(list.children).forEach((li, i) => {
      li.setAttribute('aria-selected', String(i === selected));
      if (i === selected) li.scrollIntoView({ block: 'nearest' });
    });
  };

  const render = (): void => {
    const words = input.value.toLowerCase().split(/\s+/).filter(Boolean);
    let label: (row: Row) => string = (row) => KIND[row.k];
    if (words.length) {
      shown = rows
        .map((row, n) => ({ row, n, s: score(row, words) }))
        .filter((m) => m.s > 0)
        .sort((a, b) => b.s - a.s || a.n - b.n)
        .slice(0, 9)
        .map((m) => m.row);
    } else {
      // Nothing typed yet: games you played here first, then the rest of the cabinet, then pages.
      const played = recents().map((r) => `/games/${r.id}/`);
      const games = rows.filter((row) => row.k === 'g');
      const mine = played.flatMap((u) => games.filter((row) => row.u === u));
      shown = [...mine, ...games.filter((row) => !mine.includes(row)), ...rows.filter((row) => row.k === 'l')];
      label = (row) => (mine.includes(row) ? 'Played' : KIND[row.k]);
    }
    const items = shown.map((row) => {
      const li = document.createElement('li');
      li.setAttribute('role', 'option');
      const a = document.createElement('a');
      a.href = row.u;
      let thumb: HTMLElement;
      if (row.i) {
        const img = document.createElement('img');
        img.src = row.i;
        img.alt = '';
        img.loading = 'lazy';
        thumb = img;
      } else {
        thumb = document.createElement('span');
        thumb.className = 'pi';
        thumb.textContent = '>_';
      }
      const text = document.createElement('span');
      const title = document.createElement('b');
      title.textContent = row.t;
      const sub = document.createElement('small');
      sub.textContent = row.s;
      text.append(title, sub);
      const kind = document.createElement('em');
      kind.textContent = label(row);
      a.append(thumb, text, kind);
      li.append(a);
      return li;
    });
    if (!items.length && rows.length) {
      const none = document.createElement('li');
      none.className = 'palette-none';
      none.textContent = 'Nothing matches that. Try a genre, like "factory" or "cozy".';
      items.push(none);
    }
    list.replaceChildren(...items);
    list.scrollTop = 0;
    select(0);
  };

  const open = (): void => {
    if (dialog.open) return;
    input.value = '';
    dialog.showModal();
    input.focus();
    render();
    void searchIndex().then((r) => {
      rows = r;
      render();
    });
  };

  for (const button of document.querySelectorAll('[data-palette-open]')) button.addEventListener('click', open);
  document.addEventListener('keydown', (ev) => {
    const el = ev.target as HTMLElement | null;
    const typing = !!el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
    const slash = ev.key === '/' && !typing && !ev.ctrlKey && !ev.metaKey && !ev.altKey;
    const k = ev.key.toLowerCase() === 'k' && (ev.ctrlKey || ev.metaKey) && !ev.altKey;
    if (!slash && !k) return;
    ev.preventDefault();
    if (dialog.open) dialog.close();
    else open();
  });
  input.addEventListener('input', render);
  input.addEventListener('keydown', (ev) => {
    if (ev.key === 'ArrowDown') select(selected + 1);
    else if (ev.key === 'ArrowUp') select(selected - 1);
    else if (ev.key === 'Enter') {
      const row = shown[selected];
      if (row) location.href = row.u;
    } else return;
    ev.preventDefault();
  });
  list.addEventListener('pointermove', (ev) => {
    const li = (ev.target as Element).closest('li[role="option"]');
    const n = li ? Array.from(list.children).indexOf(li) : -1;
    if (n >= 0 && n !== selected) {
      selected = n;
      Array.from(list.children).forEach((item, i) => item.setAttribute('aria-selected', String(i === n)));
    }
  });
  // A click on the dark area around the box closes it.
  dialog.addEventListener('click', (ev) => {
    if (ev.target === dialog) dialog.close();
  });
}
