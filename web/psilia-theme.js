/* Psilia theme toggle — persist choice in localStorage */
(function () {
  var key = 'psilia-theme';
  var cycle = [null, 'mono', 'light', 'light-mono'];
  var saved = localStorage.getItem(key);
  if (saved) document.documentElement.setAttribute('data-theme', saved);

  window.psiliaToggleTheme = function () {
    var current = document.documentElement.getAttribute('data-theme') || null;
    var idx = cycle.indexOf(current);
    var next = cycle[(idx + 1) % cycle.length];
    if (next) {
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem(key, next);
    } else {
      document.documentElement.removeAttribute('data-theme');
      localStorage.removeItem(key);
    }
  };
})();
