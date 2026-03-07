(function () {
  var input = document.getElementById('collectionProductSearch');
  if (!input) return;

  var items = Array.from(document.querySelectorAll('.collection-product-item'));
  input.addEventListener('input', function () {
    var query = (input.value || '').trim().toLowerCase();
    items.forEach(function (item) {
      var haystack = item.getAttribute('data-search') || '';
      var visible = !query || haystack.indexOf(query) !== -1;
      item.classList.toggle('is-hidden', !visible);
    });
  });
})();
