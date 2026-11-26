"""Render the theme switch and ecosystem links shared by v5 pages."""
from html import escape
from posixpath import dirname, relpath


def _icon(path, css_class):
    return (
        f'<svg class="{css_class}" viewBox="0 0 24 24" width="20" height="20" '
        f'aria-hidden="true" focusable="false"><path d="{path}"/></svg>'
    )


def theme_bootstrap():
    """Apply the first paint theme before the site styles load."""
    return """<script>
(() => {
  const key = 'trofim-site-theme';
  let mode = 'auto';
  for (const name of ['sessionStorage', 'localStorage']) {
    try {
      const value = window[name].getItem(key);
      if (value === 'auto' || value === 'light' || value === 'dark') { mode = value; break; }
    } catch {}
  }
  const dark = mode === 'dark' || (mode === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.themeMode = mode;
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#101b15' : '#f4f5ee');
})();
</script>"""


def theme_button():
    sun = _icon('M12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10zM12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4', 'theme-sun')
    moon = _icon('M20.5 14.5A8.8 8.8 0 0 1 9.5 3.5a8.9 8.9 0 1 0 11 11z', 'theme-moon')
    return f'''
<div class="theme-control" hidden>
  <button type="button" class="theme-toggle" aria-label="Оформление сайта" title="Оформление сайта"
    aria-expanded="false" aria-controls="v5-theme-options">{sun}{moon}</button>
  <div class="theme-options" id="v5-theme-options" hidden>
    <fieldset>
      <legend>Тема оформления</legend>
      <label><input type="radio" name="v5-site-theme" value="auto" checked>Как в системе</label>
      <label><input type="radio" name="v5-site-theme" value="light">Светлая</label>
      <label><input type="radio" name="v5-site-theme" value="dark">Тёмная</label>
    </fieldset>
  </div>
</div>'''


def bento(current):
    cards = (
        ('project', 'project.html', 'Собрать проект', 'Подберите услуги и подготовьте описание задачи.', 'assets/v5-art/project-map.svg', ''),
        ('tools', 'tools.html', 'Инструменты', 'Расчёты и материалы для подготовки проекта.', 'assets/v5-art/toolkit.svg', ''),
        ('ecosystem', 'ecosystem.html', 'Экосистема', 'Как связаны сайт, Telegram, CRM и автоматизация.', 'assets/service-art/ecosystem.svg', ''),
        ('portfolio', 'portfolio.html', 'Портфолио', 'Сайты, боты и мини-приложения в работе.', '', 'M4 6h16v12H4zM4 9h16m-12 5h4m3 0h2'),
        ('articles', 'articles.html', 'Библиотека', 'Практические статьи о цифровых инструментах.', '', 'M3 5c4-1 7 0 9 2 2-2 5-3 9-2v13c-4-1-7 0-9 2-2-2-5-3-9-2zM12 7v13'),
    )
    arrow = _icon('M5 19 19 5M5 5h14v14', 'bento-arrow-icon')
    folder = dirname(current) or '.'
    markup = []
    for key, page, heading, description, image, icon in cards:
        visuals = ''
        if image:
            source = escape(relpath(image, folder), quote=True)
            visuals = f'<img class="bento-art" src="{source}" width="288" height="160" alt="" loading="lazy" decoding="async">'
        elif icon:
            visuals = _icon(icon, 'bento-symbol')
        destination = escape(relpath(page, folder), quote=True)
        markup.append(f'''
<a class="bento-card bento-card--{key}" href="{destination}">
  <div class="bento-card-copy"><h3>{escape(heading)}</h3><p>{escape(description)}</p></div>
  {visuals}<span class="bento-arrow" aria-hidden="true">{arrow}</span>
</a>''')
    return f'''
<section class="section ecosystem-bento" aria-labelledby="ecosystem-bento-title" data-reveal>
  <div class="section-head"><h2 id="ecosystem-bento-title">Проекты и инструменты</h2></div>
  <div class="bento-grid">{''.join(markup)}
  </div>
</section>'''
