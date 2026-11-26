(() => {
  const ecosystem = document.querySelector('[data-eco]');
  if (!ecosystem) return;

  const controls = ecosystem.querySelector('[data-eco-controls]');
  const buttons = [...controls.querySelectorAll('[data-eco-node]')];
  const panels = new Map([...ecosystem.querySelectorAll('[data-eco-panel]')].map(panel => [
    panel.dataset.ecoPanel, panel,
  ]));
  const status = controls.querySelector('[data-eco-status]');

  function select(node, announce = false) {
    const selected = panels.get(node);
    if (!selected) return;
    for (const [key, panel] of panels) panel.hidden = key !== node;
    for (const button of buttons) {
      button.setAttribute('aria-pressed', String(button.dataset.ecoNode === node));
    }
    if (announce) status.textContent = 'Показано описание инструмента ' + selected.querySelector('h2').textContent;
  }

  function hashNode() {
    return location.hash.startsWith('#eco-') ? location.hash.slice(5) : '';
  }

  for (const button of buttons) {
    button.addEventListener('click', () => select(button.dataset.ecoNode, true));
  }
  window.addEventListener('hashchange', () => {
    const node = hashNode();
    if (!panels.has(node)) return;
    const panel = panels.get(node);
    const wasHidden = panel.hidden;
    select(node);
    if (wasHidden) panel.scrollIntoView({block: 'start'});
  });
  const initial = hashNode();
  select(panels.has(initial) ? initial : 'sites');
  ecosystem.classList.add('eco-interactive');
  controls.hidden = false;
})();
