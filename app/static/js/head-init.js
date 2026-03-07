(function () {
  'use strict';

  var savedTheme = null;
  try {
    savedTheme = localStorage.getItem('theme');
  } catch (e) {
    savedTheme = null;
  }

  var theme = savedTheme;
  if (theme !== 'light' && theme !== 'dark') {
    theme = (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
  }

  document.documentElement.setAttribute('data-theme', theme);
})();
