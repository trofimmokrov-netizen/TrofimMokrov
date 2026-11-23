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
  const activeReveals = new Map();

  function reveal(element) {
    if (document.hidden || reducedMotion.matches || element.matches(':focus-within, :target') || element.querySelector(':target')) return;
    const intro = element.matches('.hero-copy, .hero-portrait');
    const animation = element.animate(
      [
        {opacity: intro ? .65 : .82, transform: `translateY(${intro ? 10 : 6}px)`},
        {opacity: 1, transform: 'translateY(0)'},
      ],
      {
        duration: intro ? 470 : 390,
        delay: element.matches('.hero-portrait') ? 55 : 0,
        easing: 'cubic-bezier(.2,.7,.25,1)',
        fill: 'backwards',
      }
    );
    activeReveals.set(element, animation);
    const forget = () => activeReveals.delete(element);
    animation.addEventListener('finish', forget, {once: true});
    animation.addEventListener('cancel', forget, {once: true});
  }

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      observer.unobserve(entry.target);
      reveal(entry.target);
    });
  }, {threshold: .08});

  document.querySelectorAll('.hero-copy, .hero-portrait, .page-heading, [data-reveal]').forEach(element => observer.observe(element));
  document.addEventListener('focusin', event => {
    activeReveals.forEach((animation, element) => {
      if (element.contains(event.target)) animation.cancel();
    });
  });
  reducedMotion.addEventListener('change', () => {
    if (reducedMotion.matches) activeReveals.forEach(animation => animation.cancel());
  });
})();
