// The attract screen at the top of the home page.  It cycles on its own, driven by the CSS
// animation on the active tab's progress bar: when the bar finishes filling, the next game shows.
// That keeps the bar and the switch in step, and pausing is one class.
import { $, $$, plainClick, reducedMotion } from './util';

export function hero(): void {
  const root = $('[data-hero]');
  if (!root) return;
  const tabs = $$<HTMLAnchorElement>('.hero-tab', root);
  if (tabs.length < 2) return;
  const tabBar = $('.hero-tabs', root);
  const screen = $('[data-screen]', root);
  const channel = $('[data-hero-ch]', root);
  const layers = [$$('.hero-panel', root), $$('.screen img', root), $$('.hero-amb img', root), tabs];
  let at = 0;

  const show = (i: number): void => {
    at = (i + tabs.length) % tabs.length;
    for (const layer of layers) layer.forEach((el, n) => el.classList.toggle('on', n === at));
    if (channel) channel.textContent = `CH ${at + 1}`;
    if (screen && !reducedMotion) {
      screen.classList.remove('flick');
      void screen.offsetWidth; // restart the flicker
      screen.classList.add('flick');
    }
    // On a phone the tabs scroll sideways: keep the active one in view without moving the page.
    const tab = tabs[at];
    if (tabBar && tab && tabBar.scrollWidth > tabBar.clientWidth) {
      tabBar.scrollTo({ left: tab.offsetLeft - (tabBar.clientWidth - tab.clientWidth) / 2, behavior: 'smooth' });
    }
  };

  // Reasons to pause: the pointer is over it, focus is inside it, it's off screen, the tab is hidden.
  const holds = new Set<string>();
  const hold = (why: string, on: boolean): void => {
    if (on) holds.add(why);
    else holds.delete(why);
    root.classList.toggle('hold', holds.size > 0);
  };

  tabs.forEach((tab, n) => {
    tab.addEventListener('click', (ev) => {
      // The first click on a tab shows that game here. A click on the showing tab opens its page.
      if (n === at || !plainClick(ev)) return;
      ev.preventDefault();
      show(n);
    });
  });
  tabBar?.addEventListener('keydown', (ev) => {
    if (ev.key !== 'ArrowRight' && ev.key !== 'ArrowLeft') return;
    ev.preventDefault();
    show(at + (ev.key === 'ArrowRight' ? 1 : -1));
    tabs[at]?.focus();
  });

  if (reducedMotion) return; // the tabs still work; nothing moves on its own
  root.classList.add('run');
  root.addEventListener('animationend', (ev) => {
    if (ev.animationName === 'fill') show(at + 1);
  });
  root.addEventListener('pointerenter', (ev) => {
    if (ev.pointerType === 'mouse') hold('hover', true);
  });
  root.addEventListener('pointerleave', () => hold('hover', false));
  root.addEventListener('focusin', () => hold('focus', true));
  root.addEventListener('focusout', () => hold('focus', false));
  document.addEventListener('visibilitychange', () => hold('hidden', document.hidden));
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(([entry]) => hold('offscreen', !entry?.isIntersecting), { threshold: 0.25 }).observe(root);
  }
}
