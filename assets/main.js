(() => {
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  if (navigator.clipboard?.writeText) {
    document.querySelectorAll('.payment-method').forEach(payment => {
      const copy = payment.querySelector('.wallet-copy');
      const address = payment.querySelector('.wallet-address code');
      const status = payment.querySelector('.wallet-status');
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
      const updateScrollPadding = () => {
        if (mobile.matches) {
          document.documentElement.style.setProperty('--sticky-header-scroll-padding', header.offsetHeight + 11 + 'px');
        }
      };
      updateScrollPadding();
      new ResizeObserver(updateScrollPadding).observe(header);
    }
  }

  if (!('IntersectionObserver' in window) || !Element.prototype.animate) return;
  const introSelector = '.hero-copy, .page-heading';
  const sectionSelector = '[data-reveal], .section-head:not([data-reveal] *)';
  const regionSelector = `${introSelector}, ${sectionSelector}, .hero-portrait, .home-service`;
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
    if (!element) return;
    const animation = element.animate(frames, {duration, delay, easing: easeOut, fill: 'backwards'});
    activeReveals.set(animation, region);
    const forget = () => activeReveals.delete(animation);
    animation.addEventListener('finish', forget, {once: true});
    animation.addEventListener('cancel', forget, {once: true});
  }

  function reveal(region) {
    if (document.hidden || reducedMotion.matches || region.matches(':focus-within') ||
        region.closest(':target') || region.querySelector(':target')) return;
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
      animateEntrance(region.querySelector('h3, strong'), region, rise(5, .76), {duration: 360});
      animateEntrance(region.querySelector('.home-service-summary'), region, rise(4, .8), {duration: 380, delay: 45});
      return;
    }

    const heading = region.querySelector('h2, h3');
    if (!heading) return;
    animateEntrance(heading, region, rise(10, .62), {duration: 470});
    const description = heading.nextElementSibling;
    if (description?.matches('p')) {
      animateEntrance(description, region, rise(6, .76), {duration: 435, delay: 65});
    }
  }

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      observer.unobserve(entry.target);
      reveal(entry.target);
    });
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
