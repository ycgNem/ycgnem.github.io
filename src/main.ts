// ycgNem site script.  Every page works without it: this adds the moving parts.
// Bundled to assets/js/site.js by `npm run build:js`.
import { cabinet } from './cabinet';
import { hero } from './hero';
import { palette } from './palette';
import { player } from './player';
import { $, $$, clearRecents, plainClick, recents, reducedMotion, relative, searchIndex } from './util';
import { zoom } from './zoom';

/** The boot screen plays once a session; any key or click skips it. */
function boot(): void {
  const screen = $('.boot');
  if (!screen) return;
  const done = (): void => document.documentElement.classList.add('booted');
  screen.addEventListener('animationend', (ev) => {
    if (ev.animationName === 'boot-out') done();
  });
  screen.addEventListener('pointerdown', done);
  addEventListener('keydown', done, { once: true });
}

/** Recent dates read as "3 days ago"; the full date stays in the tooltip. */
function dates(): void {
  for (const el of $$<HTMLTimeElement>('time[data-rel]')) {
    const ago = relative(el.dateTime);
    if (!ago) continue;
    el.title = el.textContent ?? '';
    el.textContent = ago;
  }
  for (const el of $$('[data-year]')) el.textContent = String(new Date().getFullYear());
}

/** "Jump back in": the games played on this device, on the home page. */
function recentRail(): void {
  const rail = $('[data-recent]');
  const list = $('[data-recent-list]');
  if (!rail || !list) return;
  const cards = recents()
    .map((r) => $<HTMLAnchorElement>(`[data-shelves] .gcard[data-id="${CSS.escape(r.id)}"]`))
    .filter((card): card is HTMLAnchorElement => !!card)
    .slice(0, 4)
    .map((card) => {
      const copy = card.cloneNode(true) as HTMLAnchorElement;
      copy.className = 'gcard gcard-md';
      copy.hash = 'play';
      return copy;
    });
  if (!cards.length) return;
  list.append(...cards);
  rail.hidden = false;
  $('[data-recent-clear]', rail)?.addEventListener('click', () => {
    clearRecents();
    rail.hidden = true;
  });
}

/** "Surprise me" opens a random playable game, never the one you're on. */
function surprise(): void {
  document.addEventListener('click', (ev) => {
    const el = (ev.target as Element).closest<HTMLElement>('[data-random]');
    if (!el || !plainClick(ev)) return;
    ev.preventDefault();
    void searchIndex().then((rows) => {
      const games = rows.filter((row) => row.k === 'g' && row.play && row.u !== location.pathname);
      const pick = games[Math.floor(Math.random() * games.length)];
      if (pick) location.href = `${pick.u}#play`;
      else if (el instanceof HTMLAnchorElement) location.href = el.href;
    });
  });
}

/** A clicked cover grows into the game page's screen (browsers with cross-page view transitions). */
function coverMorph(): void {
  document.addEventListener('click', (ev) => {
    const target = ev.target as Element;
    const card = target.closest('.gcard');
    const heroLink = target.closest('.hero-actions .btn-primary, .hero-tab.on');
    const img = card ? $('.gcard-art img', card) : heroLink ? $('.screen img.on') : null;
    if (!img) return;
    for (const old of $$('[data-morph]')) {
      old.style.removeProperty('view-transition-name');
      delete old.dataset.morph;
    }
    img.style.setProperty('view-transition-name', 'cover');
    img.dataset.morph = '';
  });
}

/** Sections lift into place the first time they scroll into view. */
function reveal(): void {
  if (reducedMotion || !('IntersectionObserver' in window)) return;
  const seen = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const el = entry.target as HTMLElement;
        seen.unobserve(el);
        el.classList.add('in');
        el.addEventListener('transitionend', (ev) => {
          if (ev.target === el) el.classList.remove('rv', 'in');
        });
      }
    },
    { rootMargin: '0px 0px -6% 0px' },
  );
  const targets = $$('.shelf, .band-head, .promises li, .nums li, .pcard, .term, .join, .split > .panel, .toolbox li, .month > h2');
  for (const el of targets) {
    if (el.getBoundingClientRect().top < innerHeight) continue; // already on screen: leave it be
    const nth = el.parentElement ? Array.from(el.parentElement.children).indexOf(el) : 0;
    el.style.setProperty('--d', `${Math.min(nth, 5) * 60}ms`);
    el.classList.add('rv');
    seen.observe(el);
  }
}

/** The 404 page counts down like a continue screen, then sends you home. */
function gameOver(): void {
  const digit = $('[data-over-n]');
  if (!digit) return;
  let n = Number(digit.textContent) || 9;
  const tick = setInterval(() => {
    n -= 1;
    digit.textContent = String(Math.max(n, 0));
    if (n > 0) return;
    clearInterval(tick);
    location.replace('/');
  }, 1000);
  // Reaching for a button stops the clock.
  $('[data-over]')?.addEventListener('focusin', () => clearInterval(tick));
}

boot();
dates();
hero();
recentRail();
cabinet();
palette();
player();
zoom();
surprise();
coverMorph();
reveal();
gameOver();
