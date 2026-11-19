// Screenshots open in a full-window viewer, with arrow keys to step through the set.
import { $$, plainClick } from './util';

export function zoom(): void {
  const links = $$<HTMLAnchorElement>('a[data-zoom]');
  if (!links.length || typeof HTMLDialogElement === 'undefined') return;
  let dialog: HTMLDialogElement | null = null;
  let image: HTMLImageElement;
  let label: HTMLElement;
  let group: HTMLAnchorElement[] = [];
  let at = 0;

  const show = (i: number): void => {
    at = (i + group.length) % group.length;
    const link = group[at];
    if (!link) return;
    image.src = link.href;
    image.alt = link.querySelector('img')?.alt ?? '';
    label.textContent = group.length > 1 ? `${at + 1} / ${group.length}` : image.alt;
  };

  const button = (text: string, name: string, act: () => void): HTMLButtonElement => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'btn btn-ghost btn-sm';
    b.textContent = text;
    b.setAttribute('aria-label', name);
    b.addEventListener('click', act);
    return b;
  };

  // Built on first use, so pages nobody zooms on pay nothing.
  const build = (): HTMLDialogElement => {
    const d = document.createElement('dialog');
    d.className = 'zoom';
    d.setAttribute('aria-label', 'Screenshot');
    image = document.createElement('img');
    image.addEventListener('click', () => d.close());
    label = document.createElement('span');
    const bar = document.createElement('p');
    bar.className = 'zoom-bar';
    const prev = button('<-', 'Previous screenshot', () => show(at - 1));
    const next = button('->', 'Next screenshot', () => show(at + 1));
    prev.dataset.step = next.dataset.step = '';
    bar.append(prev, label, next, button('Close', 'Close', () => d.close()));
    d.append(image, bar);
    d.addEventListener('click', (ev) => {
      if (ev.target === d) d.close();
    });
    d.addEventListener('keydown', (ev) => {
      if (ev.key === 'ArrowRight') show(at + 1);
      else if (ev.key === 'ArrowLeft') show(at - 1);
    });
    document.body.append(d);
    return d;
  };

  for (const link of links) {
    link.addEventListener('click', (ev) => {
      if (!plainClick(ev)) return;
      ev.preventDefault();
      dialog ??= build();
      // The set is the gallery this shot sits in, or every figure in the same post.
      const home = link.closest('.gallery, .prose');
      group = links.filter((other) => other.closest('.gallery, .prose') === home);
      for (const step of $$('[data-step]', dialog)) step.hidden = group.length < 2;
      show(group.indexOf(link));
      dialog.showModal();
    });
  }
}
