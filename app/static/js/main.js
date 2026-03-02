function syncThemeControls(theme) {
  var isDark = theme === 'dark';

  var desktopBtn = document.getElementById('themeToggle');
  var desktopIcon = document.querySelector('#themeToggle .theme-icon');
  if (desktopIcon) desktopIcon.textContent = isDark ? '☀️' : '🌙';
  if (desktopBtn) {
    desktopBtn.title = isDark ? 'Light mode' : 'Dark mode';
    desktopBtn.setAttribute('aria-label', isDark ? 'Light mode yoqish' : 'Dark mode yoqish');
  }

  var mobileBtn = document.getElementById('mobileThemeToggle');
  var mobileIcon = document.getElementById('mobileThemeIcon');
  if (mobileIcon) mobileIcon.textContent = isDark ? '☀️' : '🌙';
  if (mobileBtn) {
    mobileBtn.setAttribute('aria-label', isDark ? 'Light mode yoqish' : 'Dark mode yoqish');
  }
}

function toggleTheme() {
  var current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  var next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  try { localStorage.setItem('theme', next); } catch (e) {}
  syncThemeControls(next);
}

document.addEventListener('DOMContentLoaded', function () {
  var obs = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) { if (e.isIntersecting) e.target.classList.add('visible'); });
  }, { threshold: 0.08 });
  document.querySelectorAll('.reveal').forEach(function (el) { obs.observe(el); });

  var currentTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  syncThemeControls(currentTheme);

  var themeToggle = document.getElementById('themeToggle');
  if (themeToggle) themeToggle.addEventListener('click', toggleTheme);

  var mobileThemeToggle = document.getElementById('mobileThemeToggle');
  if (mobileThemeToggle) mobileThemeToggle.addEventListener('click', toggleTheme);

});
