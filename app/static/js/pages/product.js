(function () {
  var root = document.getElementById('productPage');
  if (!root) return;

  function parseJson(value, fallback) {
    try {
      return value ? JSON.parse(value) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  function setHidden(el, hidden) {
    if (el) el.classList.toggle('is-hidden', !!hidden);
  }

  function formatPrice(value) {
    var amount = Math.round(Number(value) || 0);
    return String(amount).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  var productId = Number(root.dataset.productId || 0);
  var currentVid = root.dataset.currentVid ? Number(root.dataset.currentVid) : null;
  var currentPrice = Number(root.dataset.currentPrice || 0);
  var currentOldPrice = Number(root.dataset.currentOldPrice || 0);
  var currentPromoEnd = root.dataset.currentPromoEnd || '';
  var favoriteKeys = new Set(parseJson(root.dataset.favoriteKeys, []));
  var addUrl = root.dataset.addUrl || '';
  var removeUrl = root.dataset.removeUrl || '';
  var galleryTrack = document.getElementById('galleryTrack');
  var galleryIndex = 0;

  function currentFavoriteKey() {
    return String(productId);
  }

  function setFavoriteBtnState(btn, active) {
    if (!btn) return;
    btn.classList.toggle('active', !!active);
    btn.textContent = active ? '❤' : '♡';
    btn.setAttribute('aria-label', active ? 'Sevimlida' : "Sevimliga qo'shish");
  }

  function syncFavoriteBtn() {
    setFavoriteBtnState(document.getElementById('detailFavoriteBtn'), favoriteKeys.has(currentFavoriteKey()));
  }

  function syncRelatedFavoriteBtns() {
    document.querySelectorAll('.related-favorite-btn').forEach(function (btn) {
      var pid = btn.dataset ? String(btn.dataset.pid || '') : '';
      if (!pid) return;
      setFavoriteBtnState(btn, favoriteKeys.has(pid));
    });
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

  function parsePromoEndDate(raw) {
    if (!raw) return null;
    var text = String(raw).trim();
    if (!text) return null;
    if (text.indexOf(' ') !== -1 && text.indexOf('T') === -1) {
      text = text.replace(' ', 'T');
    }
    if (text.indexOf('T') === -1) {
      text += 'T23:59:59';
    }
    var date = new Date(text);
    return isNaN(date.getTime()) ? null : date;
  }

  function updateDiscount(oldPrice, promoEnd) {
    var badge = document.getElementById('discountBadge');
    var daysEl = document.getElementById('discountDays');
    var wrap = document.getElementById('oldPriceWrap');
    var value = document.getElementById('oldPriceValue');
    var endAt = parsePromoEndDate(promoEnd);
    var now = new Date();
    var promoExpired = !!(endAt && endAt.getTime() <= now.getTime());
    var hasDiscount = oldPrice && oldPrice > currentPrice && !promoExpired;

    if (value && hasDiscount) {
      value.textContent = formatPrice(oldPrice);
    }
    setHidden(wrap, !hasDiscount);
    setHidden(badge, !hasDiscount);

    if (badge && hasDiscount) {
      badge.textContent = '-' + Math.round((oldPrice - currentPrice) / oldPrice * 100) + '%';
    }

    if (!daysEl) return;
    if (hasDiscount && endAt && endAt.getTime() > now.getTime()) {
      var daysLeft = Math.ceil((endAt.getTime() - now.getTime()) / 86400000);
      if (daysLeft < 1) daysLeft = 1;
      daysEl.textContent = daysLeft === 1
        ? 'Aksiyaning oxirgi kuni!'
        : 'Aksiya tugashiga ' + daysLeft + ' kun qoldi';
      setHidden(daysEl, false);
      return;
    }

    daysEl.textContent = '';
    setHidden(daysEl, true);
  }

  function updateUnitPriceView(price) {
    var priceEl = document.getElementById('unitPriceValue');
    if (priceEl) {
      priceEl.textContent = formatPrice(price) + " so'm";
    }
  }

  function updateGalleryState(index) {
    document.querySelectorAll('.thumb-btn').forEach(function (btn, btnIndex) {
      btn.classList.toggle('active', btnIndex === index);
    });
    document.querySelectorAll('.gallery-dot').forEach(function (dot, dotIndex) {
      dot.classList.toggle('active', dotIndex === index);
    });
  }

  function selectGalleryImage(index) {
    if (!galleryTrack) return;
    galleryIndex = index;
    galleryTrack.scrollTo({ left: galleryTrack.clientWidth * index, behavior: 'smooth' });
    updateGalleryState(index);
  }

  function onGalleryScroll() {
    if (!galleryTrack || !galleryTrack.clientWidth) return;
    var index = Math.round(galleryTrack.scrollLeft / galleryTrack.clientWidth);
    if (index !== galleryIndex) {
      galleryIndex = index;
      updateGalleryState(index);
    }
  }

  function selectVariant(btn) {
    document.querySelectorAll('.v-btn').forEach(function (item) {
      item.classList.remove('active');
    });
    btn.classList.add('active');
    currentVid = parseInt(btn.dataset.vid, 10);
    currentPrice = parseFloat(btn.dataset.price);
    currentOldPrice = parseFloat(btn.dataset.oldPrice) || 0;
    currentPromoEnd = btn.dataset.promoEnd || '';
    updateUnitPriceView(currentPrice);
    updateDiscount(currentOldPrice, currentPromoEnd);
    syncFavoriteBtn();
  }

  function addToFavoritesDetail() {
    var key = currentFavoriteKey();
    var isActive = favoriteKeys.has(key);
    var url = isActive ? removeUrl : addUrl;
    var payload = isActive ? { key: key } : { product_id: productId, variant_id: currentVid };

    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (!data.success) {
          alert(data.error || 'Xatolik yuz berdi');
          return;
        }

        if (isActive) favoriteKeys.delete(key);
        else favoriteKeys.add(data.key || key);

        syncFavoriteBtn();
        syncRelatedFavoriteBtns();
        setFavoriteBadges(data.favorites_count || 0);
      })
      .catch(function () {
        alert("Tarmoq xatosi, qayta urinib ko'ring");
      });
  }

  function toggleRelatedFavorite(btn) {
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
        if (!data.success) {
          alert(data.error || 'Xatolik yuz berdi');
          return;
        }

        if (isActive) favoriteKeys.delete(key);
        else favoriteKeys.add(data.key || key);

        syncFavoriteBtn();
        syncRelatedFavoriteBtns();
        setFavoriteBadges(data.favorites_count || 0);
      })
      .catch(function () {
        alert("Tarmoq xatosi, qayta urinib ko'ring");
      });
  }

  function updateRelatedOldPrice(cardKey, price, oldPrice) {
    var oldEl = document.getElementById('related-old-' + cardKey);
    var hasOld = oldPrice && oldPrice > price;
    if (!oldEl) return;

    oldEl.classList.toggle('is-hidden', !hasOld);
    if (hasOld) {
      oldEl.textContent = formatPrice(oldPrice) + " so'm";
    }
  }

  function updateTabExpandBtn(tab) {
    var toggleBtn = tab ? tab.querySelector('[data-toggle-tab-content]') : null;
    if (!toggleBtn) return;

    var expandLabel = toggleBtn.dataset.expandLabel || "To'liq ko'rish";
    var collapseLabel = toggleBtn.dataset.collapseLabel || 'Qisqartirish';
    toggleBtn.textContent = tab.classList.contains('is-expanded') ? collapseLabel : expandLabel;
  }

  function refreshCollapsibleTab(tab) {
    var body = tab ? tab.querySelector('.tab-content-body') : null;
    var toggleBtn = tab ? tab.querySelector('[data-toggle-tab-content]') : null;
    if (!tab || !body || !toggleBtn) return;

    var wasExpanded = tab.classList.contains('is-expanded');

    tab.classList.remove('has-overflow', 'is-expanded');
    tab.classList.add('is-collapsed');
    toggleBtn.classList.add('is-hidden');

    var hasOverflow = body.scrollHeight > body.clientHeight + 4;
    if (!hasOverflow) {
      tab.classList.remove('is-collapsed');
      updateTabExpandBtn(tab);
      return;
    }

    tab.classList.add('has-overflow');
    toggleBtn.classList.remove('is-hidden');

    if (wasExpanded) {
      tab.classList.remove('is-collapsed');
      tab.classList.add('is-expanded');
    }

    updateTabExpandBtn(tab);
  }

  function refreshActiveCollapsibleTab() {
    var activeTab = document.querySelector('.tab-content.active[data-collapsible-tab]');
    if (activeTab) refreshCollapsibleTab(activeTab);
  }

  function toggleTabContent(btn) {
    var tab = btn ? btn.closest('.tab-content[data-collapsible-tab]') : null;
    if (!tab || !tab.classList.contains('has-overflow')) return;

    var expanded = !tab.classList.contains('is-expanded');
    tab.classList.toggle('is-expanded', expanded);
    tab.classList.toggle('is-collapsed', !expanded);
    updateTabExpandBtn(tab);
  }

  function selectRelatedVariant(btn) {
    var wrap = btn.closest('.pcard-variants');
    if (!wrap) return;

    wrap.querySelectorAll('.pcard-vbtn').forEach(function (item) {
      item.classList.remove('active');
    });
    btn.classList.add('active');

    var price = parseFloat(btn.dataset.price);
    var oldPrice = parseFloat(btn.dataset.oldPrice);
    var cardKey = btn.dataset.cardKey;
    var priceEl = document.getElementById('related-price-' + cardKey);
    if (priceEl) {
      priceEl.textContent = formatPrice(price) + " so'm";
    }
    updateRelatedOldPrice(cardKey, price, oldPrice);
  }

  function showTab(id, btn) {
    document.querySelectorAll('.tab-content').forEach(function (tab) {
      tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(function (item) {
      item.classList.remove('active');
    });

    var target = document.getElementById('tab-' + id);
    if (target) {
      target.classList.add('active');
      refreshCollapsibleTab(target);
    }
    btn.classList.add('active');
  }

  root.addEventListener('click', function (event) {
    var galleryBtn = event.target.closest('[data-gallery-index]');
    if (galleryBtn && root.contains(galleryBtn)) {
      selectGalleryImage(parseInt(galleryBtn.dataset.galleryIndex, 10));
      return;
    }

    var detailFavoriteBtn = event.target.closest('[data-toggle-detail-favorite]');
    if (detailFavoriteBtn && root.contains(detailFavoriteBtn)) {
      addToFavoritesDetail();
      return;
    }

    var variantBtn = event.target.closest('[data-select-variant]');
    if (variantBtn && root.contains(variantBtn)) {
      selectVariant(variantBtn);
      return;
    }

    var tabBtn = event.target.closest('[data-tab-id]');
    if (tabBtn && root.contains(tabBtn)) {
      showTab(tabBtn.dataset.tabId || '', tabBtn);
      return;
    }

    var tabToggleBtn = event.target.closest('[data-toggle-tab-content]');
    if (tabToggleBtn && root.contains(tabToggleBtn)) {
      toggleTabContent(tabToggleBtn);
      return;
    }

    var relatedFavoriteBtn = event.target.closest('[data-related-favorite]');
    if (relatedFavoriteBtn && root.contains(relatedFavoriteBtn)) {
      event.preventDefault();
      event.stopPropagation();
      toggleRelatedFavorite(relatedFavoriteBtn);
      return;
    }

    var relatedVariantBtn = event.target.closest('[data-select-related-variant]');
    if (relatedVariantBtn && root.contains(relatedVariantBtn)) {
      selectRelatedVariant(relatedVariantBtn);
    }
  });

  if (galleryTrack) {
    galleryTrack.addEventListener('scroll', onGalleryScroll, { passive: true });
    updateGalleryState(0);
    window.addEventListener('resize', function () {
      if (!galleryTrack) return;
      galleryTrack.scrollLeft = galleryTrack.clientWidth * galleryIndex;
    });
  }

  window.addEventListener('resize', refreshActiveCollapsibleTab);

  updateUnitPriceView(currentPrice);
  updateDiscount(currentOldPrice, currentPromoEnd);
  syncFavoriteBtn();
  syncRelatedFavoriteBtns();
  refreshActiveCollapsibleTab();
})();
