// The game page's screen: nothing loads until you press start, then the game runs right there.
import { $, remember } from './util';

type FullscreenTarget = HTMLElement & { webkitRequestFullscreen?: () => void };

export function player(): void {
  const box = $<FullscreenTarget>('[data-player]');
  if (!box) return;
  const url = box.dataset.player ?? '';
  const frame = box.closest<HTMLElement>('.cabinet-frame');
  const restart = $<HTMLButtonElement>('[data-restart]');
  const theater = $<HTMLButtonElement>('[data-theater]');
  let game: HTMLIFrameElement | null = null;

  const start = (): void => {
    if (game || !url) return;
    const iframe = document.createElement('iframe');
    iframe.src = url;
    iframe.title = box.dataset.title ?? 'Game';
    iframe.allow = 'fullscreen; gamepad; autoplay';
    iframe.allowFullscreen = true;
    iframe.addEventListener('load', () => {
      box.classList.remove('loading');
      iframe.focus();
    });
    box.classList.add('loading');
    box.replaceChildren(iframe);
    game = iframe;
    if (restart) restart.hidden = false;
    remember(box.dataset.id ?? '');
  };

  $('.start', box)?.addEventListener('click', start);
  // "Play free" links end in #play: go straight into the game.
  const fromHash = (): void => {
    if (location.hash === '#play') start();
  };
  fromHash();
  addEventListener('hashchange', fromHash);

  $('[data-fullscreen]')?.addEventListener('click', () => {
    start();
    if (box.requestFullscreen) void box.requestFullscreen().catch(() => undefined);
    else box.webkitRequestFullscreen?.();
  });

  restart?.addEventListener('click', () => {
    if (!game) return;
    box.classList.add('loading');
    game.src = url;
  });

  const setTheater = (on: boolean): void => {
    document.body.classList.toggle('theater', on);
    theater?.setAttribute('aria-pressed', String(on));
    if (on) frame?.scrollIntoView({ block: 'start' });
  };
  theater?.addEventListener('click', () => setTheater(!document.body.classList.contains('theater')));
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && document.body.classList.contains('theater') && !document.fullscreenElement) setTheater(false);
  });
}
