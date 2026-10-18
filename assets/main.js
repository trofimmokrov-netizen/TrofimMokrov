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

// Editorial text motion. Web Animations never hide the underlying content.
(() => {
 const reduced = matchMedia('(prefers-reduced-motion: reduce)');
 const active = new Set();
 const play = (element, frames, options) => {
  if (reduced.matches || !element.animate) return null;
  const animation = element.animate(frames, options);
  active.add(animation);
  animation.finished.then(() => active.delete(animation), () => active.delete(animation));
  return animation;
 };
 const headings = document.querySelectorAll('main h1, .section-head h2, .contact-banner h2, .dark > h2, .visual-copy h2, .split > div > h2, .ai-spotlight h2');
 const revealHeading = heading => {
  if (reduced.matches || !heading.animate) return;
  const walker = document.createTreeWalker(heading, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  const words = [];
  nodes.forEach(node => {
   const fragment = document.createDocumentFragment();
   node.textContent.split(/(\s+)/).filter(Boolean).forEach(part => {
    if (/^\s+$/.test(part)) fragment.append(document.createTextNode(part));
    else {const word = document.createElement('span');word.className = 'text-word';word.textContent = part;fragment.append(word);words.push(word);}
   });
   node.replaceWith(fragment);
  });
  words.forEach((word, index) => play(word,
   [{opacity:0.15,transform:'translateY(18px) rotate(1deg)'},{opacity:1,transform:'translateY(0) rotate(0)'}],
   {duration:850,delay:Math.min(index*65,520),easing:'cubic-bezier(.16,1,.3,1)',fill:'backwards'}));
 };
 if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
   if(entry.isIntersecting){revealHeading(entry.target);observer.unobserve(entry.target);}
  }), {threshold:0.15});
  headings.forEach(heading => observer.observe(heading));
 }
 const note = document.querySelector('.living-note');
 const control = document.querySelector('.motion-toggle');
 if (!note || !control) {
  reduced.addEventListener('change',event=>{if(event.matches)active.forEach(animation=>animation.cancel());});
  return;
 }
 const phrases = [...note.querySelectorAll('.living-phrase')];
 let index=0, timer=null, paused=false, inView=false, transition=null;
 const clear = () => {clearTimeout(timer);timer=null;};
 const schedule = () => {
  clear();
  if(reduced.matches || paused || document.hidden || !inView || !note.animate)return;
  timer=setTimeout(advance,5200);
 };
 const advance = async () => {
  const previous=phrases[index];
  transition=play(previous,[{opacity:1,transform:'translateY(0)'},{opacity:0,transform:'translateY(-7px)'}],{duration:280,easing:'ease-in'});
  try {if(transition)await transition.finished;}catch{return;}
  if(reduced.matches || paused || document.hidden || !inView){schedule();return;}
  previous.classList.remove('is-current');index=(index+1)%phrases.length;
  phrases[index].classList.add('is-current');
  transition=play(phrases[index],[{opacity:0,transform:'translateY(9px)'},{opacity:1,transform:'translateY(0)'}],{duration:650,easing:'cubic-bezier(.16,1,.3,1)'});
  schedule();
 };
 const stop = () => {clear();if(transition)transition.cancel();transition=null;};
 control.addEventListener('click',()=>{
  paused=!paused;control.setAttribute('aria-pressed',String(paused));
  control.setAttribute('aria-label',paused?'Продолжить смену фраз':'Остановить смену фраз');
  control.textContent=paused?'Продолжить':'Пауза';
  if(paused)stop();else schedule();
 });
 document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();else schedule();});
 reduced.addEventListener('change',()=>{
  if(reduced.matches){stop();active.forEach(animation=>animation.cancel());}
  control.hidden=reduced.matches || !note.animate;
  schedule();
 });
 if('IntersectionObserver' in window){
  new IntersectionObserver(entries=>{inView=entries[0].isIntersecting;if(inView)schedule();else stop();},{threshold:.25}).observe(note);
 }
 control.hidden=reduced.matches || !note.animate;
})();
