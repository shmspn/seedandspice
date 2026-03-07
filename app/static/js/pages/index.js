(function () {
  var root = document.getElementById('homePage');
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

  function setupHomeBanner() {
    var bannerRoot = document.getElementById('homeBanner');
    if (!bannerRoot) return;

    var slides = Array.from(bannerRoot.querySelectorAll('.home-banner-slide'));
    var count = slides.length;
    if (count <= 1) return;

    var dots = Array.from(bannerRoot.querySelectorAll('.home-banner-dot'));
    var idx = 0;
    var timer = null;
    var touchStartX = 0;
    var touchStartY = 0;
    var swipeMoved = false;

    function sync() {
      slides.forEach(function (slide, slideIndex) {
        slide.classList.toggle('active', slideIndex === idx);
      });
      dots.forEach(function (dot, dotIndex) {
        dot.classList.toggle('active', dotIndex === idx);
      });
    }

    function go(next) {
      idx = (next + count) % count;
      sync();
    }

    function start() {
      if (timer) clearInterval(timer);
      timer = setInterval(function () { go(idx + 1); }, 5000);
    }

    function stop() {
      if (timer) clearInterval(timer);
      timer = null;
    }

    var prev = bannerRoot.querySelector('[data-banner-action="prev"]');
    var next = bannerRoot.querySelector('[data-banner-action="next"]');
    if (prev) prev.addEventListener('click', function () { go(idx - 1); start(); });
    if (next) next.addEventListener('click', function () { go(idx + 1); start(); });

    dots.forEach(function (dot) {
      dot.addEventListener('click', function () {
        go(parseInt(dot.dataset.bannerDot || '0', 10));
        start();
      });
    });

    bannerRoot.addEventListener('touchstart', function (event) {
      var touch = event.touches && event.touches[0];
      if (!touch) return;
      touchStartX = touch.clientX;
      touchStartY = touch.clientY;
      swipeMoved = false;
      stop();
    }, { passive: true });

    bannerRoot.addEventListener('touchend', function (event) {
      var touch = event.changedTouches && event.changedTouches[0];
      if (!touch) {
        start();
        return;
      }

      var dx = touch.clientX - touchStartX;
      var dy = touch.clientY - touchStartY;
      if (Math.abs(dx) > 36 && Math.abs(dx) > Math.abs(dy)) {
        swipeMoved = true;
        if (dx < 0) go(idx + 1);
        else go(idx - 1);
      } else {
        sync();
      }
      start();
    }, { passive: true });

    bannerRoot.addEventListener('touchcancel', start, { passive: true });

    slides.forEach(function (slide) {
      slide.addEventListener('click', function (event) {
        if (!swipeMoved) return;
        event.preventDefault();
        swipeMoved = false;
      });
    });

    document.addEventListener('visibilitychange', function () {
      if (document.hidden) stop();
      else start();
    });
    window.addEventListener('focus', start);

    go(0);
    start();
  }

  root.addEventListener('click', function (event) {
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

  setupHomeBanner();
})();
