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
  }

  if (!('IntersectionObserver' in window) || !Element.prototype.animate) return;
  const introSelector = '.hero-copy, .page-heading';
  const sectionSelector = '[data-reveal], .section-head:not([data-reveal] *)';
  const regionSelector = `${introSelector}, ${sectionSelector}, .hero-portrait`;
  const activeReveals = new Map();

  function animateEntrance(element, region, {distance, opacity, duration, delay = 0}) {
    if (!element) return;
    const animation = element.animate(
      [
        {opacity, transform: `translateY(${distance}px)`},
        {opacity: 1, transform: 'translateY(0)'},
      ],
      {duration, delay, easing: 'cubic-bezier(.2,.7,.25,1)', fill: 'backwards'}
    );
    activeReveals.set(animation, region);
    const forget = () => activeReveals.delete(animation);
    animation.addEventListener('finish', forget, {once: true});
    animation.addEventListener('cancel', forget, {once: true});
  }

  function reveal(region) {
    if (document.hidden || reducedMotion.matches || region.matches(':focus-within') ||
        region.closest(':target') || region.querySelector(':target')) return;
    if (region.matches(introSelector)) {
      animateEntrance(region.querySelector(':scope > .eyebrow'), region, {distance: 7, opacity: .65, duration: 410});
      animateEntrance(region.querySelector(':scope > h1'), region, {distance: 16, opacity: .48, duration: 620, delay: 45});
      animateEntrance(region.querySelector(':scope > .lead'), region, {distance: 10, opacity: .64, duration: 560, delay: 125});
      return;
    }
    if (region.matches('.hero-portrait')) {
      animateEntrance(region, region, {distance: 9, opacity: .73, duration: 550, delay: 70});
      return;
    }

    const heading = region.querySelector('h2, h3');
    if (!heading) return;
    animateEntrance(heading, region, {distance: 10, opacity: .55, duration: 510});
    const description = heading.nextElementSibling;
    if (description?.matches('p')) {
      animateEntrance(description, region, {distance: 7, opacity: .72, duration: 475, delay: 65});
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
