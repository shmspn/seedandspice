(function () {
  var galleries = Array.from(document.querySelectorAll('[data-pcard-gallery]'));
  if (!galleries.length) return;

  var mobileTabletMedia = window.matchMedia('(max-width: 1100px)');

  function setActiveDot(gallery, index) {
    var dots = Array.from(gallery.querySelectorAll('.pcard-gallery-dot'));
    if (!dots.length) return;

    var safeIndex = Math.max(0, Math.min(index, dots.length - 1));
    dots.forEach(function (dot, dotIndex) {
      dot.classList.toggle('active', dotIndex === safeIndex);
    });
  }

  function syncGallery(gallery) {
    var track = gallery.querySelector('[data-pcard-track]');
    if (!track) return;

    if (!mobileTabletMedia.matches) {
      track.scrollLeft = 0;
      setActiveDot(gallery, 0);
      return;
    }

    var width = track.clientWidth || gallery.clientWidth || 1;
    var index = Math.round(track.scrollLeft / width);
    setActiveDot(gallery, index);
  }

  function bindGallery(gallery) {
    var track = gallery.querySelector('[data-pcard-track]');
    if (!track || track.dataset.galleryBound === '1') return;
    track.dataset.galleryBound = '1';

    var startX = 0;
    var startY = 0;
    var suppressClick = false;

    track.addEventListener('scroll', function () {
      if (!mobileTabletMedia.matches) return;
      window.requestAnimationFrame(function () {
        syncGallery(gallery);
      });
    }, { passive: true });

    track.addEventListener('touchstart', function (event) {
      if (!mobileTabletMedia.matches) return;
      var touch = event.touches && event.touches[0];
      if (!touch) return;
      startX = touch.clientX;
      startY = touch.clientY;
      suppressClick = false;
    }, { passive: true });

    track.addEventListener('touchmove', function (event) {
      if (!mobileTabletMedia.matches) return;
      var touch = event.touches && event.touches[0];
      if (!touch) return;

      var dx = touch.clientX - startX;
      var dy = touch.clientY - startY;
      if (Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy)) {
        suppressClick = true;
      }
    }, { passive: true });

    track.addEventListener('touchend', function () {
      if (!mobileTabletMedia.matches) return;
      window.requestAnimationFrame(function () {
        syncGallery(gallery);
      });
    }, { passive: true });

    track.addEventListener('click', function (event) {
      if (!suppressClick) return;
      event.preventDefault();
      event.stopPropagation();
      suppressClick = false;
    }, true);

    syncGallery(gallery);
  }

  function refreshGalleries() {
    galleries.forEach(function (gallery) {
      bindGallery(gallery);
      syncGallery(gallery);
    });
  }

  refreshGalleries();
  if (mobileTabletMedia.addEventListener) {
    mobileTabletMedia.addEventListener('change', refreshGalleries);
  } else if (mobileTabletMedia.addListener) {
    mobileTabletMedia.addListener(refreshGalleries);
  }
  window.addEventListener('resize', refreshGalleries);
})();
