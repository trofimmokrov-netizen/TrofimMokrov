(() => {
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  if (navigator.clipboard?.writeText) {
    document.querySelectorAll('.payment-method').forEach(payment => {
      const copy = payment.querySelector('.wallet-copy');
      const address = payment.querySelector('.wallet-address code');
      const status = payment.querySelector('.wallet-status');
      if (!copy || !address || !status) return;
      copy.hidden = false;
      copy.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(address.textContent.trim());
          status.textContent = 'Адрес скопирован.';
        } catch {
          status.textContent = 'Выделите адрес и скопируйте его вручную.';
        }
      });
    });
  }

  const menuButton = document.querySelector('.menu-button');
  const navigation = document.querySelector('#main-nav');

  if (menuButton && navigation) {
    const mobile = matchMedia('(max-width: 800px)');
    let menuAnimation;

    const menuIsOpen = () => menuButton.getAttribute('aria-expanded') === 'true';

    function settleMenu(open) {
      menuAnimation?.cancel();
      menuAnimation = undefined;
      navigation.classList.toggle('is-open', open);
      navigation.classList.remove('is-animating');
      navigation.inert = false;
    }

    function setMenu(open) {
      if (open === menuIsOpen()) return;
      menuButton.setAttribute('aria-expanded', String(open));
      if (!mobile.matches || reducedMotion.matches || !navigation.animate) {
        settleMenu(open);
        return;
      }

      const startHeight = navigation.getBoundingClientRect().height;
      const startOpacity = startHeight ? getComputedStyle(navigation).opacity : 0;
      menuAnimation?.cancel();
      navigation.classList.add('is-open', 'is-animating');
      navigation.inert = !open;

      const endHeight = open ? navigation.getBoundingClientRect().height : 0;
      const animation = navigation.animate(
        [
          {height: startHeight + 'px', opacity: startOpacity},
          {height: endHeight + 'px', opacity: open ? 1 : 0},
        ],
        {duration: 240, easing: 'cubic-bezier(.22,.75,.25,1)', fill: 'both'}
      );
      menuAnimation = animation;
      animation.addEventListener('finish', () => {
        if (menuAnimation === animation) settleMenu(open);
      }, {once: true});
    }

    menuButton.addEventListener('click', () => setMenu(!menuIsOpen()));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && menuIsOpen()) {
        setMenu(false);
        menuButton.focus();
      }
    });
    navigation.addEventListener('click', event => {
      if (event.target.closest('a')) {
        if (menuIsOpen()) menuButton.focus();
        setMenu(false);
      }
    });
    document.addEventListener('click', event => {
      if (!event.target.closest('header')) setMenu(false);
    });
    mobile.addEventListener('change', () => {
      menuButton.setAttribute('aria-expanded', 'false');
      settleMenu(false);
    });
    reducedMotion.addEventListener('change', () => {
      if (reducedMotion.matches) settleMenu(menuIsOpen());
    });

    document.documentElement.classList.add('nav-ready');
    const header = navigation.closest('.site-header');
    if (header && 'ResizeObserver' in window) {
      let lastPadding;
      const updateScrollPadding = () => {
        if (mobile.matches) {
          const padding = header.offsetHeight + 11 + 'px';
          if (padding !== lastPadding) {
            document.documentElement.style.setProperty('--sticky-header-scroll-padding', padding);
            lastPadding = padding;
          }
        }
      };
      updateScrollPadding();
      new ResizeObserver(updateScrollPadding).observe(header);
    }
  }

  const librarySearch = document.querySelector('#library-search');
  if (librarySearch) {
    const status = document.querySelector('#library-search-status');
    const index = document.querySelector('.library-index');
    const empty = document.querySelector('.library-empty');
    const normalize = value => value.toLocaleLowerCase('ru').replaceAll('ё', 'е');
    const searchWord = word => {
      if (!/^[а-я]+$/u.test(word)) return word;
      const stem = word.replace(/(?:ами|ями|ах|ях|ов|ев|ам|ям|ой|ей|ом|ем|[аяуюеыи])$/u, '');
      return stem.length >= 4 ? stem : word;
    };
    const topics = [...document.querySelectorAll('.library-topic')].map(section => {
      const title = section.querySelector('h2').textContent + ' ' + section.dataset.libraryKeywords;
      const entries = [...section.querySelectorAll('[data-library-result]')].map(element => ({
        element,
        text: normalize(title + ' ' + element.querySelector('h3').textContent + ' ' + element.querySelector('p').textContent),
      }));
      return {section, entries};
    });
    let previousQuery;
    const filterLibrary = () => {
      const query = normalize(librarySearch.value.trim());
      if (query === previousQuery) return;
      previousQuery = query;
      const words = query ? query.split(/\s+/).map(searchWord) : [];
      let count = 0;
      for (const {section, entries} of topics) {
        let matches = 0;
        for (const {element, text} of entries) {
          const found = words.every(word => text.includes(word));
          if (element.hidden === found) element.hidden = !found;
          matches += Number(found);
        }
        if (section.hidden !== (matches === 0)) section.hidden = matches === 0;
        count += matches;
      }
      index.hidden = words.length > 0;
      empty.hidden = count > 0;
      status.textContent = words.length ? 'Найдено материалов: ' + count : '';
    };
    librarySearch.closest('.library-search').hidden = false;
    let pendingFilter = 0;
    librarySearch.addEventListener('input', () => {
      if (pendingFilter) return;
      pendingFilter = requestAnimationFrame(() => {
        pendingFilter = 0;
        filterLibrary();
      });
    });
    window.addEventListener('pageshow', filterLibrary);
    filterLibrary();
  }

  if (!('IntersectionObserver' in window) || !Element.prototype.animate) return;
  const introSelector = '.hero-copy, .page-heading';
  const sectionSelector = '[data-reveal], .section-head:not([data-reveal] *)';
  const regionSelector = `${introSelector}, ${sectionSelector}, .hero-portrait, .home-service, .project-feature-media`;
  const revealedElements = new WeakSet();
  const activeReveals = new Map();
  const easeOut = 'cubic-bezier(.18,.8,.24,1)';
  const rise = (distance, opacity) => [
    {opacity, transform: `translateY(${distance}px)`},
    {opacity: 1, transform: 'translateY(0)'},
  ];
  const headline = [
    {opacity: .46, transform: 'translateY(14px)', clipPath: 'inset(12% -.24em 63% -.24em)'},
    {opacity: 1, transform: 'translateY(0)', clipPath: 'inset(-.24em -.24em -.24em -.24em)'},
  ];

  function animateEntrance(element, region, frames, {duration, delay = 0}) {
    if (!element || revealedElements.has(element)) return;
    revealedElements.add(element);
    const animation = element.animate(frames, {duration, delay, easing: easeOut, fill: 'backwards'});
    activeReveals.set(animation, region);
    const forget = () => activeReveals.delete(animation);
    animation.addEventListener('finish', forget, {once: true});
    animation.addEventListener('cancel', forget, {once: true});
  }

  function motionSuppressed(region) {
    return document.hidden || reducedMotion.matches || region.matches(':focus-within') ||
      region.closest(':target') !== null || region.querySelector(':target') !== null;
  }

  function revealProjectMedia(frame) {
    const image = frame.querySelector(':scope > img');
    if (!image) return;
    if (!image.complete) {
      image.addEventListener('load', () => observer.observe(frame), {once: true});
      return;
    }

    const card = frame.closest('.project-feature') || frame;
    if (!image.naturalWidth || motionSuppressed(card)) return;
    animateEntrance(image, card, [
      {opacity: .72, scale: '1.05', clipPath: 'inset(7% 4% 12% 4%)'},
      {opacity: 1, scale: '1', clipPath: 'inset(0)'},
    ], {duration: 620});
  }

  function reveal(region, tileDelay) {
    if (region.matches(introSelector)) {
      animateEntrance(region.querySelector(':scope > .eyebrow'), region, rise(6, .69), {duration: 360});
      animateEntrance(region.querySelector(':scope > h1'), region, headline, {duration: 610, delay: 35});
      animateEntrance(region.querySelector(':scope > .lead'), region, rise(9, .73), {duration: 520, delay: 125});
      return;
    }
    if (region.matches('.hero-portrait')) {
      animateEntrance(region, region, rise(12, .74), {duration: 590, delay: 70});
      animateEntrance(region.querySelector('img'), region, [
        {transform: 'scale(.97)'},
        {transform: 'scale(1)'},
      ], {duration: 660, delay: 70});
      return;
    }
    if (region.matches('.home-service')) {
      animateEntrance(region.querySelector('h3, strong'), region, rise(5, .76), {duration: 360, delay: tileDelay});
      animateEntrance(region.querySelector('.home-service-summary'), region, rise(4, .8), {duration: 380, delay: tileDelay + 45});
      return;
    }
    if (region.matches('.project-feature-media')) {
      revealProjectMedia(region);
      return;
    }

    const heading = [...region.querySelectorAll('h2, h3')].find(candidate => candidate.closest(regionSelector) === region);
    if (!heading) return;
    animateEntrance(heading, region, rise(10, .62), {duration: 470});
    const description = heading.nextElementSibling;
    if (description?.matches('p')) {
      animateEntrance(description, region, rise(6, .76), {duration: 435, delay: 65});
    }
  }

  const observer = new IntersectionObserver(entries => {
    let tiles = 0;
    for (const {isIntersecting, target} of entries) {
      if (!isIntersecting) continue;
      observer.unobserve(target);
      if (motionSuppressed(target)) continue;
      let tileDelay = 0;
      if (target.matches('.home-service')) {
        tileDelay = Math.min(tiles, 2) * 45;
        tiles += 1;
      }
      reveal(target, tileDelay);
    }
  }, {threshold: .08});

  document.querySelectorAll(regionSelector).forEach(element => observer.observe(element));
  document.addEventListener('focusin', event => {
    activeReveals.forEach((region, animation) => {
      if (region.contains(event.target)) animation.cancel();
    });
  });
  reducedMotion.addEventListener('change', () => {
    if (reducedMotion.matches) {
      for (const animation of activeReveals.keys()) animation.cancel();
    }
  });
})();
