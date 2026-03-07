(function () {
  var root = document.getElementById('favoritesPage');
  if (!root) return;

  function parseJson(value, fallback) {
    try {
      return value ? JSON.parse(value) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  function formatPrice(value) {
    var amount = Math.round(Number(value) || 0);
    return String(amount).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  var favoriteKeys = new Set(parseJson(root.dataset.favoriteKeys, []));
  var addUrl = root.dataset.addUrl || '';
  var removeUrl = root.dataset.removeUrl || '';

  function setFavoriteBadges(count) {
    var badge = document.getElementById('favoriteBadge');
    if (badge) {
      if (count > 0) badge.textContent = count;
      else badge.remove();
    }

    var badgeMobile = document.getElementById('favoriteBadgeMobile');
    if (badgeMobile) {
      if (count > 0) badgeMobile.textContent = count;
      else badgeMobile.remove();
    }
  }

  function setFavoriteBtnState(btn, active) {
    if (!btn) return;
    btn.classList.toggle('active', !!active);
    btn.textContent = active ? '❤' : '♡';
    btn.setAttribute('aria-label', active ? 'Sevimlida' : "Sevimliga qo'shish");
  }

  function updateCardOldPrice(cardKey, price, oldPrice) {
    var oldEl = document.getElementById('old-' + cardKey);
    var hasOld = oldPrice && oldPrice > price;
    if (!oldEl) return;

    oldEl.classList.toggle('is-hidden', !hasOld);
    if (hasOld) {
      oldEl.textContent = formatPrice(oldPrice) + " so'm";
    }
  }

  function selectVariant(btn) {
    var wrap = btn.closest('.pcard-variants');
    if (!wrap) return;

    wrap.querySelectorAll('.pcard-vbtn').forEach(function (item) {
      item.classList.remove('active');
    });
    btn.classList.add('active');

    var price = parseFloat(btn.dataset.price);
    var oldPrice = parseFloat(btn.dataset.oldPrice);
    var cardKey = btn.dataset.cardKey;
    var el = document.getElementById('price-' + cardKey);
    if (el) {
      el.textContent = formatPrice(price) + " so'm";
    }
    updateCardOldPrice(cardKey, price, oldPrice);
  }

  function removeFavorite(key) {
    fetch(removeUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: key })
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (!data.success) return;

        favoriteKeys.delete(String(key));
        var card = document.getElementById('favorite-' + key);
        if (card) card.remove();

        document.querySelectorAll('.popular-fav-btn[data-pid="' + key + '"]').forEach(function (popBtn) {
          setFavoriteBtnState(popBtn, false);
        });

        var count = data.favorites_count || 0;
        var counter = document.getElementById('favoritesCount');
        if (counter) counter.textContent = count;
        setFavoriteBadges(count);

        if (count === 0) window.location.reload();
      });
  }

  function togglePopularFavorite(btn) {
    var pid = btn && btn.dataset ? btn.dataset.pid : '';
    if (!pid) return;

    var key = String(pid);
    var isActive = favoriteKeys.has(key);
    var url = isActive ? removeUrl : addUrl;

    var vid = null;
    if (!isActive) {
      var card = btn.closest('.pcard');
      var activeVariant = card ? card.querySelector('.pcard-vbtn.active') : null;
      if (activeVariant && activeVariant.dataset.vid) vid = Number(activeVariant.dataset.vid);
    }

    var payload = isActive ? { key: key } : { product_id: Number(pid), variant_id: vid };

    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (!data.success) return;

        if (isActive) {
          favoriteKeys.delete(key);
          var favCard = document.getElementById('favorite-' + key);
          if (favCard) favCard.remove();
        } else {
          favoriteKeys.add(data.key || key);
        }

        setFavoriteBtnState(btn, !isActive);
        setFavoriteBadges(data.favorites_count || favoriteKeys.size);

        if (!isActive || (data.favorites_count || 0) === 0) {
          window.location.reload();
        }
      });
  }

  root.addEventListener('click', function (event) {
    var removeBtn = event.target.closest('[data-remove-favorite]');
    if (removeBtn && root.contains(removeBtn)) {
      removeFavorite(removeBtn.dataset.favoriteKey || '');
      return;
    }

    var popularBtn = event.target.closest('[data-toggle-popular-favorite]');
    if (popularBtn && root.contains(popularBtn)) {
      togglePopularFavorite(popularBtn);
      return;
    }

    var variantBtn = event.target.closest('[data-select-variant]');
    if (variantBtn && root.contains(variantBtn)) {
      selectVariant(variantBtn);
    }
  });
})();
