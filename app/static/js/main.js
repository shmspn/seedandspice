function getThemeIconSvg(isDark) {
  if (isDark) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2.2"/><path d="M12 19.8V22"/><path d="m4.93 4.93 1.56 1.56"/><path d="m17.51 17.51 1.56 1.56"/><path d="M2 12h2.2"/><path d="M19.8 12H22"/><path d="m4.93 19.07 1.56-1.56"/><path d="m17.51 6.49 1.56-1.56"/></svg>';
  }

  return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 15.5A8.5 8.5 0 1 1 8.5 4a6.5 6.5 0 0 0 11.5 11.5z"/></svg>';
}

function syncThemeControls(theme) {
  var isDark = theme === 'dark';

  var desktopBtn = document.getElementById('themeToggle');
  var desktopIcon = document.querySelector('#themeToggle .theme-icon');
  if (desktopIcon) desktopIcon.innerHTML = getThemeIconSvg(isDark);
  if (desktopBtn) {
    desktopBtn.title = isDark ? 'Light mode' : 'Dark mode';
    desktopBtn.setAttribute('aria-label', isDark ? 'Light mode yoqish' : 'Dark mode yoqish');
  }

  var mobileBtn = document.getElementById('mobileThemeToggle');
  var mobileIcon = document.getElementById('mobileThemeIcon');
  if (mobileIcon) mobileIcon.innerHTML = getThemeIconSvg(isDark);
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

function bindRevealObserver() {
  if (!window.IntersectionObserver) {
    document.querySelectorAll('.reveal').forEach(function (el) {
      el.classList.add('visible');
    });
    return;
  }

  var obs = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) entry.target.classList.add('visible');
    });
  }, { threshold: 0.08 });

  document.querySelectorAll('.reveal').forEach(function (el) {
    obs.observe(el);
  });
}

function bindFlashDismissals() {
  document.addEventListener('click', function (event) {
    var btn = event.target.closest('[data-flash-close]');
    if (!btn) return;
    var flash = btn.closest('.flash');
    if (flash) flash.remove();
  });
}

function bindAutoSubmitControls() {
  document.addEventListener('change', function (event) {
    var field = event.target.closest('[data-auto-submit]');
    if (!field) return;

    var form = field.form || field.closest('form');
    if (!form) return;

    if (typeof form.requestSubmit === 'function') form.requestSubmit();
    else form.submit();
  });
}

document.addEventListener('DOMContentLoaded', function () {
  var currentTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  syncThemeControls(currentTheme);
  bindRevealObserver();
  bindFlashDismissals();
  bindAutoSubmitControls();

  var themeToggle = document.getElementById('themeToggle');
  if (themeToggle) themeToggle.addEventListener('click', toggleTheme);

  var mobileThemeToggle = document.getElementById('mobileThemeToggle');
  if (mobileThemeToggle) mobileThemeToggle.addEventListener('click', toggleTheme);
});
