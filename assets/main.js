(() => {
 const button = document.querySelector('.menu-button');
 const nav = document.querySelector('#main-nav');
 if (button && nav) {
  const close = () => {button.setAttribute('aria-expanded', 'false');nav.classList.remove('is-open');};
  button.addEventListener('click', () => {
   const open = button.getAttribute('aria-expanded') !== 'true';
   button.setAttribute('aria-expanded', String(open));nav.classList.toggle('is-open', open);
  });
  document.addEventListener('keydown', event => {if(event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true'){close();button.focus();}});
  nav.addEventListener('click', event => {if(event.target.closest('a')) close();});
  document.addEventListener('click', event => {if(!event.target.closest('header')) close();});
  document.documentElement.classList.add('nav-ready');
 }
 if ('IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
   if (entry.isIntersecting) {entry.target.classList.add('reveal-play');observer.unobserve(entry.target);}
  }), {threshold: 0.08});
  document.querySelectorAll('[data-reveal]').forEach(element => observer.observe(element));
 }
})();
