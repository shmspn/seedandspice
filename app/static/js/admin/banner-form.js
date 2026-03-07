(function () {
  var select = document.getElementById('collectionSelect');
  var linkInput = document.getElementById('manualLinkInput');
  if (!select || !linkInput) return;

  function sync() {
    var hasCollection = !!select.value;
    linkInput.disabled = hasCollection;
    linkInput.placeholder = hasCollection
      ? "Kolleksiya tanlangan — avtomatik link ishlaydi"
      : '/katalog yoki https://...';
  }

  select.addEventListener('change', sync);
  sync();
})();
