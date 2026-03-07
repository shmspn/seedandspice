(function () {
  function fallbackCopy(text) {
    var area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'absolute';
    area.style.left = '-9999px';
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    document.body.removeChild(area);
  }

  document.querySelectorAll('.copy-collection-link').forEach(function (btn) {
    btn.addEventListener('click', async function () {
      var link = btn.getAttribute('data-link') || '';
      if (!link) return;

      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(link);
        } else {
          fallbackCopy(link);
        }
      } catch (e) {
        fallbackCopy(link);
      }

      var original = btn.textContent;
      btn.textContent = 'Nusxalandi';
      setTimeout(function () {
        btn.textContent = original;
      }, 1200);
    });
  });
})();
