(() => {
  const root = document.documentElement;
  const key = 'trofim-site-theme';
  const modes = new Set(['auto', 'light', 'dark']);
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  const themeColor = document.querySelector('meta[name="theme-color"]');
  const control = document.querySelector('.theme-control');
  const button = control?.querySelector('.theme-toggle');
  const panel = control?.querySelector('.theme-options');
  const inputs = panel?.querySelectorAll('input[name="v5-site-theme"]') || [];
  let mode = 'auto';

  function storedMode(fallback) {
    for (const name of ['sessionStorage', 'localStorage']) {
      try {
        const value = window[name].getItem(key);
        if (modes.has(value)) return value;
      } catch {
        // The browser may restrict a storage area in embedded or private contexts.
      }
    }
    return fallback;
  }

  function saveMode(value) {
    try {
      window.localStorage.setItem(key, value);
    } catch {
      try {
        window.sessionStorage.setItem(key, value);
      } catch {
        // The selection still applies to the current page.
      }
      return;
    }
    try {
      window.sessionStorage.removeItem(key);
    } catch {
      // Local storage is enough when session storage is unavailable.
    }
  }

  function apply(value) {
    mode = modes.has(value) ? value : 'auto';
    const dark = mode === 'dark' || (mode === 'auto' && system.matches);
    root.dataset.themeMode = mode;
    root.dataset.theme = dark ? 'dark' : 'light';
    themeColor?.setAttribute('content', dark ? '#101b15' : '#f4f5ee');
    for (const input of inputs) input.checked = input.value === mode;
  }

  apply(modes.has(root.dataset.themeMode) ? root.dataset.themeMode : storedMode('auto'));
  system.addEventListener('change', () => {
    if (mode === 'auto') apply(mode);
  });
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) apply(storedMode('auto'));
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted) apply(storedMode(mode));
  });

  if (!control || !button || !panel) return;

  function close() {
    panel.hidden = true;
    button.setAttribute('aria-expanded', 'false');
  }

  button.addEventListener('click', () => {
    if (!panel.hidden) {
      close();
      return;
    }
    control.closest('header')?.querySelector('.menu-button[aria-expanded="true"]')?.click();
    panel.hidden = false;
    button.setAttribute('aria-expanded', 'true');
    panel.querySelector('input:checked')?.focus();
  });

  control.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !panel.hidden) {
      event.preventDefault();
      close();
      button.focus();
    }
  });
  control.addEventListener('focusout', event => {
    if (!control.contains(event.relatedTarget)) close();
  });
  document.addEventListener('click', event => {
    if (!control.contains(event.target)) close();
  });
  for (const input of inputs) {
    input.addEventListener('change', () => {
      if (!input.checked) return;
      apply(input.value);
      saveMode(mode);
    });
  }

  control.hidden = false;
})();
