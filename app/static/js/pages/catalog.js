(function () {
  window.setupCatalogAccordion = function setupCatalogAccordion() {};

  var root = document.getElementById('catalogPage');
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

  function currentCardKey(pid) {
    return String(pid);
  }

  function setFavoriteBtnState(btn, isActive) {
    if (!btn) return;
    btn.classList.toggle('active', !!isActive);
    btn.textContent = isActive ? '❤' : '♡';
    btn.setAttribute('aria-label', isActive ? 'Sevimlida' : "Sevimliga qo'shish");
  }

  function setFavoriteBadges(count) {
    var badge = document.getElementById('favoriteBadge');
    if (!badge && count > 0) {
      var icon = document.querySelector('.favorite-icon');
      if (icon) {
        badge = document.createElement('span');
        badge.id = 'favoriteBadge';
        badge.className = 'favorite-badge';
        icon.appendChild(badge);
      }
    }
    if (badge) {
      if (count > 0) badge.textContent = count;
      else badge.remove();
    }

    var badgeMobile = document.getElementById('favoriteBadgeMobile');
    if (!badgeMobile && count > 0) {
      var mobileIcon = document.querySelector('.favorite-mobile-item');
      if (mobileIcon) {
        badgeMobile = document.createElement('span');
        badgeMobile.id = 'favoriteBadgeMobile';
        badgeMobile.className = 'favorite-badge-mobile';
        mobileIcon.appendChild(badgeMobile);
      }
    }
    if (badgeMobile) {
      if (count > 0) badgeMobile.textContent = count;
      else badgeMobile.remove();
    }
  }

  function updateCardOldPrice(pid, price, oldPrice) {
    var oldEl = document.getElementById('old-' + pid);
    var badge = document.getElementById('badge-' + pid);
    var hasOld = oldPrice && oldPrice > price;

    if (oldEl) {
      oldEl.classList.toggle('is-hidden', !hasOld);
      if (hasOld) {
        oldEl.textContent = formatPrice(oldPrice) + " so'm";
      }
    }

    if (badge) badge.classList.toggle('is-hidden', !hasOld);
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
    var el = document.getElementById('price-' + btn.dataset.pid);
    if (el) {
      el.textContent = formatPrice(price) + " so'm";
    }
    updateCardOldPrice(btn.dataset.pid, price, oldPrice);
  }

  function addToFavorites(pid, vid, btn) {
    if (!pid) return;

    if (!vid && btn) {
      var card = btn.closest('.pcard');
      var active = card ? card.querySelector('.pcard-vbtn.active') : null;
      if (active && active.dataset.vid) vid = parseInt(active.dataset.vid, 10);
    }

    var key = currentCardKey(pid);
    var isActive = favoriteKeys.has(key);
    var url = isActive ? removeUrl : addUrl;
    var payload = isActive ? { key: key } : { product_id: pid, variant_id: vid };

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
          setFavoriteBtnState(btn, false);
        } else {
          favoriteKeys.add(data.key || key);
          setFavoriteBtnState(btn, true);
        }
        setFavoriteBadges(data.favorites_count || 0);
      });
  }

  function markBranchOpening(branch) {
    if (!branch) return;
    if (branch._openingTimer) clearTimeout(branch._openingTimer);
    branch.classList.add('is-opening');
    branch._openingTimer = setTimeout(function () {
      branch.classList.remove('is-opening');
    }, 220);
  }

  function toggleBranch(btn) {
    var targetId = btn.getAttribute('data-target');
    if (!targetId) return;

    var branch = document.getElementById(targetId);
    if (!branch) return;

    var willOpen = branch.classList.contains('is-collapsed');
    branch.classList.toggle('is-collapsed', !willOpen);
    if (willOpen) markBranchOpening(branch);

    btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    btn.classList.toggle('active', willOpen);

    if (btn.classList.contains('catalog-tree-top')) {
      var group = btn.closest('.catalog-tree-group');
      if (group) group.classList.toggle('open', willOpen);
    }
  }

  root.addEventListener('click', function (event) {
    var treeToggle = event.target.closest('.catalog-tree-toggle[data-target]');
    if (treeToggle && root.contains(treeToggle)) {
      toggleBranch(treeToggle);
      return;
    }

    var favoriteBtn = event.target.closest('[data-toggle-favorite]');
    if (favoriteBtn && root.contains(favoriteBtn)) {
      addToFavorites(parseInt(favoriteBtn.dataset.productId, 10), null, favoriteBtn);
      return;
    }

    var variantBtn = event.target.closest('[data-select-variant]');
    if (variantBtn && root.contains(variantBtn)) {
      selectVariant(variantBtn);
    }
  });
})();
