(() => {
  const root = document.documentElement;
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const scrollReadout = document.querySelector('.scroll-coordinate span');
  let pointerFrame = 0;
  let scrollFrame = 0;

  const updateScroll = () => {
    scrollFrame = 0;
    const maximum = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    const progress = Math.min(1, Math.max(0, window.scrollY / maximum));
    root.style.setProperty('--scroll-progress', progress.toFixed(4));
    if (scrollReadout) scrollReadout.textContent = progress.toFixed(3);
    document.querySelector('.proof-workbench')?.style.setProperty('--proof-turn', String(Math.round(progress * 18)));
  };

  const scheduleScroll = () => {
    if (!scrollFrame) scrollFrame = requestAnimationFrame(updateScroll);
  };

  const schedulePointer = (event) => {
    if (prefersReducedMotion.matches || pointerFrame) return;
    pointerFrame = requestAnimationFrame(() => {
      pointerFrame = 0;
      root.style.setProperty('--flow-x', `${event.clientX - window.innerWidth / 2}px`);
      root.style.setProperty('--flow-y', `${event.clientY - window.innerHeight / 2}px`);
    });
  };

  const addReveals = () => {
    const targets = document.querySelectorAll('.learning-pulse, .proof-workbench, .dashboard-grid, .graph-panel');
    targets.forEach((target) => target.classList.add('flow-reveal'));
    if (prefersReducedMotion.matches || !('IntersectionObserver' in window)) {
      targets.forEach((target) => target.classList.add('is-flow-visible'));
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-flow-visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -7% 0px' });
    targets.forEach((target) => observer.observe(target));
  };

  const bindSurfaceLight = (selector, xName, yName) => {
    const surface = document.querySelector(selector);
    if (!surface || prefersReducedMotion.matches) return;
    surface.addEventListener('pointermove', (event) => {
      const box = surface.getBoundingClientRect();
      surface.style.setProperty(xName, `${((event.clientX - box.left) / box.width) * 100}%`);
      surface.style.setProperty(yName, `${((event.clientY - box.top) / box.height) * 100}%`);
    }, { passive: true });
  };

  const start = () => {
    root.classList.add('motion-ready');
    updateScroll();
    addReveals();
    bindSurfaceLight('.chat-workbench', '--workbench-x', '--workbench-y');
    bindSurfaceLight('.graph-canvas', '--graph-x', '--graph-y');
    window.addEventListener('scroll', scheduleScroll, { passive: true });
    window.addEventListener('resize', scheduleScroll, { passive: true });
    window.addEventListener('pointermove', schedulePointer, { passive: true });
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
