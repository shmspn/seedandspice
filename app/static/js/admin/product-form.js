(function () {
  var page = document.getElementById('productFormPage');
  var form = document.getElementById('mainForm');
  if (!page || !form) return;

  var variantRows = document.getElementById('variantRows');
  var unitTypeSelect = document.getElementById('unitTypeSelect');
  var unitTypeHint = document.getElementById('unitTypeHint');
  var varIdx = Number(form.dataset.initialVariantCount || 1);

  function buildVariantRow(index) {
    var row = document.createElement('div');
    row.className = 'variant-row';
    row.innerHTML =
      '<input type="text" name="v_label_' + index + '" placeholder="Variant (100g, 1kg, 250ml)">' +
      '<input type="number" name="v_price_' + index + '" placeholder="Narx (so\'m)" min="1" step="any">' +
      '<input type="number" name="v_old_price_' + index + '" placeholder="Eski narx" min="1" step="any">' +
      '<input type="date" name="v_promo_start_' + index + '" title="Aksiya boshlanish sanasi">' +
      '<input type="date" name="v_promo_end_' + index + '" title="Aksiya tugash sanasi">' +
      '<button type="button" class="btn-remove-var" data-remove-variant>✕</button>';
    return row;
  }

  function addVariant() {
    if (!variantRows) return;
    variantRows.appendChild(buildVariantRow(varIdx));
    varIdx += 1;
  }

  function removeVariant(btn) {
    var row = btn.closest('.variant-row');
    if (row) row.remove();
  }

  function setImageAsPrimary(imageId) {
    fetch('/admin/mahsulot-rasm/' + imageId + '/asosiy', { method: 'POST' })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data.success) refreshPrimaryState(data.primary_id || imageId);
      })
      .catch(function () {
        alert('Xatolik yuz berdi!');
      });
  }

  function deleteImage(imageId) {
    if (!confirm("Rasmni o'chirasizmi?")) return;

    fetch('/admin/mahsulot-rasm/' + imageId + '/ochirish', { method: 'POST' })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (!data.success) {
          alert("O'chirishda xatolik!");
          return;
        }
        var thumb = document.getElementById('imgthumb-' + imageId);
        if (thumb) thumb.remove();
        refreshPrimaryState(data.primary_id || null);
      })
      .catch(function () {
        alert("O'chirishda xatolik!");
      });
  }

  function ensureSetPrimaryBtn(thumb, imageId) {
    var actions = thumb.querySelector('.img-actions');
    if (!actions || actions.querySelector('.img-set-primary')) return;

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'img-btn img-set-primary';
    btn.title = 'Asosiy qilish';
    btn.textContent = '⭐';
    btn.setAttribute('data-set-primary-image', String(imageId));
    actions.insertBefore(btn, actions.firstChild);
  }

  function refreshPrimaryState(primaryId) {
    var thumbs = document.querySelectorAll('.img-thumb');
    thumbs.forEach(function (thumb) {
      var id = parseInt((thumb.id || '').replace('imgthumb-', ''), 10);
      var isPrimary = primaryId && id === parseInt(primaryId, 10);
      var badge = thumb.querySelector('.img-primary-badge');
      var setBtn = thumb.querySelector('.img-set-primary');

      thumb.classList.toggle('primary', !!isPrimary);

      if (isPrimary) {
        if (!badge) {
          badge = document.createElement('div');
          badge.className = 'img-primary-badge';
          badge.textContent = '⭐ ASOSIY';
          thumb.insertBefore(badge, thumb.firstChild.nextSibling);
        }
        if (setBtn) setBtn.remove();
      } else {
        if (badge) badge.remove();
        ensureSetPrimaryBtn(thumb, id);
      }
    });
  }

  function updateUnitHint() {
    if (!unitTypeSelect || !unitTypeHint) return;
    unitTypeHint.textContent = unitTypeSelect.value === 'kg'
      ? 'Kilogramm rejimida variant narxlari 1kg uchun kiritiladi.'
      : "Dona rejimida variant narxlari dona bo'yicha yuritiladi.";
  }

  function setupCategoryTree() {
    var items = Array.from(page.querySelectorAll('.cat-tree-item'));
    if (!items.length) return;

    var byId = new Map();
    var childrenByParent = new Map();
    var treeActions = page.querySelector('.cat-tree-actions');
    var expandBtn = document.getElementById('catExpandAllBtn');
    var collapseBtn = document.getElementById('catCollapseAllBtn');

    items.forEach(function (item) {
      item.style.setProperty('--depth', item.getAttribute('data-depth') || '0');
      var id = item.getAttribute('data-cat-id') || '';
      var parentId = item.getAttribute('data-parent-id') || '';
      if (!id) return;

      byId.set(id, item);
      if (!childrenByParent.has(parentId)) childrenByParent.set(parentId, []);
      childrenByParent.get(parentId).push(item);
    });

    function syncCheckedState(item) {
      var checkbox = item.querySelector('input[type="checkbox"]');
      item.classList.toggle('is-selected', !!(checkbox && checkbox.checked));
    }

    function setExpandedState(item, expanded) {
      if (!item || item.classList.contains('no-children')) return;
      item.classList.toggle('is-collapsed', !expanded);
      var toggle = item.querySelector('.cat-tree-toggle');
      if (toggle) toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    }

    function isAncestorCollapsed(item) {
      var parentId = item.getAttribute('data-parent-id') || '';
      while (parentId) {
        var parent = byId.get(parentId);
        if (!parent) return false;
        if (parent.classList.contains('is-collapsed')) return true;
        parentId = parent.getAttribute('data-parent-id') || '';
      }
      return false;
    }

    function refreshTreeVisibility() {
      items.forEach(function (item) {
        item.classList.toggle('is-hidden', isAncestorCollapsed(item));
      });
    }

    function openAncestors(item) {
      var parentId = item.getAttribute('data-parent-id') || '';
      while (parentId) {
        var parent = byId.get(parentId);
        if (!parent) break;
        setExpandedState(parent, true);
        parentId = parent.getAttribute('data-parent-id') || '';
      }
    }

    items.forEach(function (item) {
      var id = item.getAttribute('data-cat-id') || '';
      var children = childrenByParent.get(id) || [];
      var hasChildren = children.length > 0;
      item.classList.toggle('no-children', !hasChildren);
      if (hasChildren) setExpandedState(item, false);
      syncCheckedState(item);
    });

    var hasNested = items.some(function (item) {
      var id = item.getAttribute('data-cat-id') || '';
      return (childrenByParent.get(id) || []).length > 0;
    });
    if (treeActions) treeActions.classList.toggle('is-hidden', !hasNested);

    page.addEventListener('click', function (event) {
      var toggle = event.target.closest('[data-toggle-cat-tree]');
      if (!toggle || !page.contains(toggle)) return;

      event.preventDefault();
      event.stopPropagation();

      var item = toggle.closest('.cat-tree-item');
      if (!item || item.classList.contains('no-children')) return;

      setExpandedState(item, item.classList.contains('is-collapsed'));
      refreshTreeVisibility();
    });

    page.addEventListener('change', function (event) {
      var checkbox = event.target.closest('.cat-tree-item input[type="checkbox"]');
      if (!checkbox || !page.contains(checkbox)) return;

      var item = checkbox.closest('.cat-tree-item');
      if (!item) return;

      syncCheckedState(item);
      if (checkbox.checked) {
        openAncestors(item);
        refreshTreeVisibility();
      }
    });

    if (expandBtn) {
      expandBtn.addEventListener('click', function () {
        items.forEach(function (item) {
          if (!item.classList.contains('no-children')) setExpandedState(item, true);
        });
        refreshTreeVisibility();
      });
    }

    if (collapseBtn) {
      collapseBtn.addEventListener('click', function () {
        items.forEach(function (item) {
          if (!item.classList.contains('no-children')) setExpandedState(item, false);
        });
        refreshTreeVisibility();
      });
    }

    items.forEach(function (item) {
      var checkbox = item.querySelector('input[type="checkbox"]');
      if (checkbox && checkbox.checked) openAncestors(item);
    });

    refreshTreeVisibility();
  }

  page.addEventListener('click', function (event) {
    var addBtn = event.target.closest('[data-add-variant]');
    if (addBtn && page.contains(addBtn)) {
      addVariant();
      return;
    }

    var removeBtn = event.target.closest('[data-remove-variant]');
    if (removeBtn && page.contains(removeBtn)) {
      removeVariant(removeBtn);
      return;
    }

    var primaryBtn = event.target.closest('[data-set-primary-image]');
    if (primaryBtn && page.contains(primaryBtn)) {
      setImageAsPrimary(primaryBtn.getAttribute('data-set-primary-image'));
      return;
    }

    var deleteBtn = event.target.closest('[data-delete-image]');
    if (deleteBtn && page.contains(deleteBtn)) {
      deleteImage(deleteBtn.getAttribute('data-delete-image'));
    }
  });

  if (unitTypeSelect) unitTypeSelect.addEventListener('change', updateUnitHint);
  updateUnitHint();
  setupCategoryTree();
})();
