// ycgNem site behaviour: attract-mode screen, click-to-load game player, fullscreen.
(function () {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Attract mode: cycle the cabinet screen through every game's cover.
  const screen = document.querySelector('[data-attract]');
  if (screen) {
    const imgs = [...screen.querySelectorAll('img')];
    const label = document.querySelector('[data-attract-label]');
    let i = 0;
    const show = (n) => {
      imgs.forEach((im, k) => im.classList.toggle('on', k === n));
      if (label) {
        const im = imgs[n];
        label.innerHTML = '';
        const a = document.createElement('a');
        a.href = im.dataset.href;
        a.textContent = '▶ ' + im.alt;
        label.appendChild(a);
      }
    };
    show(0);
    if (!reduce && imgs.length > 1) {
      let timer = setInterval(() => { i = (i + 1) % imgs.length; show(i); }, 3200);
      screen.addEventListener('mouseenter', () => clearInterval(timer));
      screen.addEventListener('mouseleave', () => {
        timer = setInterval(() => { i = (i + 1) % imgs.length; show(i); }, 3200);
      });
    }
    screen.addEventListener('click', () => { location.href = imgs[i].dataset.href; });
  }

  // Player: load the game only when asked, so pages stay light.
  const player = document.querySelector('[data-player]');
  if (player) {
    const start = player.querySelector('.start');
    const load = () => {
      const f = document.createElement('iframe');
      f.src = player.dataset.player;
      f.title = player.dataset.title;
      f.allow = 'autoplay; fullscreen; gamepad';
      f.allowFullscreen = true;
      player.replaceChildren(f);
      f.focus();
    };
    start && start.addEventListener('click', load);
    if (location.hash === '#play' && start) load();

    const fs = document.querySelector('[data-fullscreen]');
    fs && fs.addEventListener('click', () => {
      if (!player.querySelector('iframe')) load();
      const el = player;
      const req = el.requestFullscreen || el.webkitRequestFullscreen;
      if (req) req.call(el).catch(() => {});
    });
  }

  const y = document.querySelector('[data-year]');
  if (y) y.textContent = new Date().getFullYear();
})();
