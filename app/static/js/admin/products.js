(function () {
  var form = document.getElementById('filterForm');
  var tipSelect = document.getElementById('tipSelect');
  var catSelect = document.getElementById('catSelect');
  if (!form || !tipSelect || !catSelect) return;

  function parseJson(value, fallback) {
    try {
      return value ? JSON.parse(value) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  var allCategories = parseJson(form.dataset.allCategories, []);
  var typesMap = parseJson(form.dataset.typesMap, {});
  typesMap[''] = allCategories;

  function renderCategories(tip) {
    catSelect.innerHTML = '<option value="">Barcha kategoriyalar</option>';
    var list = tip ? (typesMap[tip] || []) : (typesMap[''] || []);
    list.forEach(function (category) {
      var option = document.createElement('option');
      option.value = category.id;
      option.textContent = (category.icon || '') + ' ' + category.name;
      catSelect.appendChild(option);
    });
  }

  tipSelect.addEventListener('change', function () {
    renderCategories(tipSelect.value);
    if (typeof form.requestSubmit === 'function') form.requestSubmit();
    else form.submit();
  });
})();
