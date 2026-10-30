(function () {
  // Altersabfrage – nur einmal pro Browser
  var gate = document.getElementById('gate');
  if (gate) {
    var KEY = 'videothek18';
    var ok = false;
    try { ok = localStorage.getItem(KEY) === '1'; } catch (e) {}
    gate.hidden = ok;
    var go = gate.querySelector('[data-confirm]');
    if (go) go.addEventListener('click', function () {
      try { localStorage.setItem(KEY, '1'); } catch (e) {}
      gate.hidden = true;
      var input = document.querySelector('[data-search]');
      if (input) input.focus();
    });
  }

  // Suche
  var input = document.querySelector('[data-search]');
  var items = Array.prototype.slice.call(document.querySelectorAll('[data-term]'));
  var empty = document.querySelector('[data-empty]');
  if (input && items.length) {
    var filter = function () {
      var q = input.value.trim().toLowerCase();
      var shown = 0;
      items.forEach(function (el) {
        var hit = !q || el.getAttribute('data-term').indexOf(q) !== -1;
        el.hidden = !hit;
        if (hit) shown++;
      });
      if (empty) empty.hidden = shown !== 0;
    };
    input.addEventListener('input', filter);
    input.addEventListener('search', filter);
    document.addEventListener('keydown', function (e) {
      if (e.key === '/' && document.activeElement !== input) {
        e.preventDefault();
        input.focus();
        input.select();
      }
    });
  }

  // Ein-Datei-Variante: Gruppen ausblenden, wenn nichts passt
  var groups = Array.prototype.slice.call(document.querySelectorAll('section.grp'));
  if (input && groups.length) {
    input.addEventListener('input', function () {
      var q = input.value.trim().toLowerCase();
      groups.forEach(function (g) {
        var nameHit = !q || g.getAttribute('data-term').indexOf(q) !== -1;
        var hits = 0;
        Array.prototype.slice.call(g.querySelectorAll('li[data-term]')).forEach(function (li) {
          var hit = nameHit || li.getAttribute('data-term').indexOf(q) !== -1;
          li.hidden = !hit;
          if (hit) hits++;
        });
        g.hidden = !nameHit && hits === 0;
      });
    });
  }

  // Sortierung (nur Startseite): A–Z oder meiste Links
  var grid = document.querySelector('[data-grid]');
  var sortBtn = document.querySelector('[data-sort]');
  if (grid && sortBtn) {
    var mode = 'az';
    var apply = function () {
      var cards = Array.prototype.slice.call(grid.children);
      cards.sort(function (a, b) {
        if (mode === 'count') {
          return Number(b.dataset.count) - Number(a.dataset.count) ||
                 a.dataset.name.localeCompare(b.dataset.name, 'de');
        }
        return a.dataset.name.localeCompare(b.dataset.name, 'de');
      });
      cards.forEach(function (c) { grid.appendChild(c); });
      sortBtn.setAttribute('aria-pressed', mode === 'count');
      sortBtn.textContent = mode === 'count' ? 'Sortierung: meiste Links' : 'Sortierung: A–Z';
    };
    sortBtn.addEventListener('click', function () {
      mode = mode === 'az' ? 'count' : 'az';
      apply();
    });
  }
})();
