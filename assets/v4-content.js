(() => {
  const portfolio = document.querySelector('[data-portfolio]');
  if (portfolio) {
    const controls = document.querySelector('[data-portfolio-controls]');
    const buttons = [...controls.querySelectorAll('[data-project-filter]')];
    const groups = [...portfolio.querySelectorAll('[data-project-group]')];
    const status = controls.querySelector('.work-count');
    const total = portfolio.querySelectorAll('[data-project-card]').length;

    function showProjects(filter) {
      let visible = 0;
      for (const group of groups) {
        group.hidden = filter !== 'all' && group.dataset.projectGroup !== filter;
        if (!group.hidden) visible += group.querySelectorAll('[data-project-card]').length;
      }
      buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.projectFilter === filter)));
      status.textContent = 'Показано ' + visible + ' из ' + total;
    }

    function projectTarget() {
      try {
        const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
        return portfolio.contains(target) ? target : null;
      } catch {
        return null;
      }
    }

    function showProjectTarget() {
      const target = projectTarget();
      if (!target) return;
      const group = target.closest('[data-project-group]');
      const wasHidden = Boolean(group?.hidden);
      if (wasHidden) showProjects(group.dataset.projectGroup);
      const disclosure = target.querySelector('.work-disclosure');
      if (disclosure) disclosure.open = true;
      if (wasHidden) target.scrollIntoView({block: 'start'});
    }

    for (const button of buttons) {
      button.addEventListener('click', () => {
        const filter = button.dataset.projectFilter;
        showProjects(filter);
        if (projectTarget()?.closest('[hidden]')) {
          history.replaceState(history.state, '', location.pathname + location.search);
        }
      });
    }
    controls.hidden = false;
    showProjects('all');
    showProjectTarget();
    window.addEventListener('hashchange', showProjectTarget);
  }

  const librarySearch = document.querySelector('#library-search');
  if (librarySearch) {
    const status = document.querySelector('#library-search-status');
    const index = document.querySelector('.library-index');
    const empty = document.querySelector('.library-empty');
    const results = document.querySelector('.library-results');
    const searchField = document.createElement('div');
    const clear = document.createElement('button');
    searchField.className = 'library-search-field';
    clear.className = 'library-search-clear';
    clear.type = 'button';
    clear.textContent = 'Очистить';
    librarySearch.before(searchField);
    searchField.append(librarySearch, clear);
    librarySearch.maxLength = 120;

    const aliases = {
      websites: 'лендинг веб фронтенд ui ux',
      telegram: 'Телеграм телеграмм mini app miniapp чатбот',
      crm: 'Bitrix24 bitrix CRM лид воронка',
      content: 'искусственный интеллект нейросеть ИИ публикация',
      automation: 'webhook вебхук API отказоустойчивость',
      practice: 'бриф ТЗ документация чеклист',
    };
    const normalize = value => value.toLocaleLowerCase('ru').replaceAll('ё', 'е');
    const searchWord = word => {
      if (!/^[а-я]+$/u.test(word)) return word;
      const stem = word.replace(/(?:ами|ями|ах|ях|ов|ев|ам|ям|ой|ей|ом|ем|[аяуюеыи])$/u, '');
      return stem.length >= 4 ? stem : word;
    };
    const wordsIn = value => (normalize(value).match(/[\p{L}\p{N}]+/gu) || []).map(searchWord);
    const hasWord = (words, query) => words.some(word => word === query || (query.length >= 3 && word.startsWith(query)));
    const topics = [...document.querySelectorAll('.library-topic')].map(section => {
      const key = section.id.replace(/^topic-/, '');
      const topicWords = wordsIn([section.querySelector('h2').textContent, section.dataset.libraryKeywords, aliases[key]].join(' '));
      const list = section.querySelector('.library-list');
      const entries = [...list.querySelectorAll('[data-library-result]')].map(element => ({
        element,
        title: wordsIn(element.querySelector('h3').textContent),
        description: wordsIn(element.querySelector('p').textContent),
      }));
      return {section, list, entries, topicWords};
    });

    function scoreEntry(entry, topicWords, query) {
      let score = 0;
      for (const word of query) {
        if (hasWord(entry.title, word)) score += 8;
        else if (hasWord(entry.description, word)) score += 4;
        else if (hasWord(topicWords, word)) score += 1;
        else return -1;
      }
      return score;
    }

    let previousQuery;
    const filterLibrary = () => {
      const query = [...new Set(wordsIn(librarySearch.value))];
      const queryKey = query.join(' ');
      clear.hidden = !librarySearch.value;
      if (queryKey === previousQuery) return;
      previousQuery = queryKey;
      let count = 0;
      const rankedTopics = topics.map(({section, list, entries, topicWords}) => {
        const ranked = entries.map(entry => ({entry, score: scoreEntry(entry, topicWords, query)}));
        ranked.sort((left, right) => right.score - left.score);
        for (const {entry, score} of ranked) {
          entry.element.hidden = score < 0;
          count += Number(score >= 0);
        }
        list.append(...ranked.map(({entry}) => entry.element));
        section.hidden = ranked[0].score < 0;
        return {section, score: ranked[0].score};
      });
      rankedTopics.sort((left, right) => right.score - left.score);
      results.append(...rankedTopics.map(({section}) => section));
      index.hidden = query.length > 0;
      empty.hidden = count > 0;
      status.textContent = query.length ? 'Найдено материалов: ' + count : '';
    };
    const clearSearch = () => {
      librarySearch.value = '';
      filterLibrary();
      librarySearch.focus();
    };
    clear.addEventListener('click', clearSearch);
    librarySearch.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !event.isComposing && librarySearch.value) {
        event.preventDefault();
        clearSearch();
      }
    });
    librarySearch.closest('.library-search').hidden = false;
    librarySearch.addEventListener('input', filterLibrary);
    window.addEventListener('pageshow', filterLibrary);
    filterLibrary();
  }
})();
