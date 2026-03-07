(function () {
  var body = document.body;
  var openBtn = document.getElementById('adminMenuOpen');
  var closeBtn = document.getElementById('adminMenuClose');
  var backdrop = document.getElementById('sidebarBackdrop');

  function closeMenu() {
    if (!openBtn) return;
    body.classList.remove('sidebar-open');
    openBtn.setAttribute('aria-expanded', 'false');
  }

  function openMenu() {
    if (!openBtn) return;
    body.classList.add('sidebar-open');
    openBtn.setAttribute('aria-expanded', 'true');
  }

  if (openBtn && backdrop) {
    openBtn.addEventListener('click', openMenu);
    if (closeBtn) closeBtn.addEventListener('click', closeMenu);
    backdrop.addEventListener('click', closeMenu);

    document.querySelectorAll('.sidebar .nav-link, .sidebar-footer a').forEach(function (el) {
      el.addEventListener('click', function () {
        if (window.matchMedia('(max-width: 1100px)').matches) closeMenu();
      });
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') closeMenu();
    });

    window.addEventListener('resize', function () {
      if (window.innerWidth > 1100) closeMenu();
    });
  }

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement)) return;

    var message = form.getAttribute('data-confirm');
    if (message && !window.confirm(message)) {
      event.preventDefault();
    }
  });
})();
