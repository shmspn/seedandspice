(function () {
  var root = document.getElementById('categoryFormPage');
  var form = document.getElementById('categoryForm');
  if (!root || !form) return;

  function parseJson(value, fallback) {
    try {
      return value ? JSON.parse(value) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  var parentSelect = document.getElementById('parentCategorySelect');
  var openParentPickerBtn = document.getElementById('openParentPickerBtn');
  var parentPickerModal = document.getElementById('parentPickerModal');
  var closeParentPickerBtn = document.getElementById('closeParentPickerBtn');
  var parentPickerLabel = document.getElementById('parentPickerLabel');
  var parentTree = document.getElementById('parentTreePreview');
  var parentTreeSearch = document.getElementById('parentTreeSearch');
  var parentTreeExpandAllBtn = document.getElementById('parentTreeExpandAllBtn');
  var parentTreeCollapseAllBtn = document.getElementById('parentTreeCollapseAllBtn');
  var wrap = document.getElementById('parentProductsWrap');
  var searchInput = document.getElementById('parentProductsSearch');
  var selectedCountEl = document.getElementById('selectedProductsCount');
  var toggleProductsScopeBtn = document.getElementById('toggleProductsScopeBtn');
  var toggleVisibleBtn = document.getElementById('toggleVisibleProductsBtn');
  var sortInput = document.getElementById('sortOrderInput');
  var sortPreviewEl = document.getElementById('sortOrderPreview');
  var autoSortBtn = document.getElementById('sortOrderAutoBtn');
  if (!parentSelect || !wrap || !searchInput || !openParentPickerBtn || !parentPickerModal || !toggleProductsScopeBtn || !toggleVisibleBtn || !parentTree) return;

  var selectedIds = new Set(parseJson(root.dataset.selectedProductIds, []));
  var endpointProducts = root.dataset.endpointProducts || '';
  var endpointSortHint = root.dataset.endpointSortHint || '';
  var imageBase = root.dataset.imageBase || '';
  var currentCatId = root.dataset.currentCatId ? Number(root.dataset.currentCatId) : null;
  var allItems = [];
  var searchText = '';
  var showAllProducts = false;
  var sortTouched = false;
  var lastSortSuggestion = null;

  var treeRows = Array.from(parentTree.querySelectorAll('.parent-tree-row[data-value]'));
  var parentTreeById = new Map();
  var parentTreeChildren = new Map();
  var parentTreeQuery = '';

  treeRows.forEach(function (row) {
    row.style.setProperty('--tree-depth', row.getAttribute('data-tree-depth') || '0');
  });

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function updatePickedCount() {
    if (selectedCountEl) {
      selectedCountEl.textContent = selectedIds.size + ' ta tanlandi';
    }
  }

  function parentTreeParentId(row) {
    return (row.getAttribute('data-parent-id') || '').trim();
  }

  function parentTreeValue(row) {
    return (row.getAttribute('data-value') || '').trim();
  }

  function setParentTreeExpanded(row, expanded) {
    if (!row || row.classList.contains('no-children')) return;
    row.classList.toggle('is-collapsed', !expanded);
  }

  function openParentTreeAncestorsByValue(value) {
    var current = String(value || '');
    while (current) {
      var row = parentTreeById.get(current);
      if (!row) break;
      var parentId = parentTreeParentId(row);
      if (!parentId) break;
      var parentRow = parentTreeById.get(parentId);
      if (!parentRow) break;
      setParentTreeExpanded(parentRow, true);
      current = parentId;
    }
  }

  function parentTreeHasCollapsedAncestor(row) {
    var parentId = parentTreeParentId(row);
    while (parentId) {
      var parentRow = parentTreeById.get(parentId);
      if (!parentRow) return false;
      if (parentRow.classList.contains('is-collapsed')) return true;
      parentId = parentTreeParentId(parentRow);
    }
    return false;
  }

  function refreshParentTreeVisibility() {
    if (parentTreeQuery) {
      var showIds = new Set();

      treeRows.forEach(function (row) {
        var value = parentTreeValue(row);
        if (!value) return;
        var nameEl = row.querySelector('.parent-tree-name');
        var hay = ((nameEl ? nameEl.textContent : row.textContent) || '').toLowerCase();
        if (hay.indexOf(parentTreeQuery) === -1) return;

        showIds.add(value);
        var current = value;
        while (current) {
          showIds.add(current);
          var currentRow = parentTreeById.get(current);
          if (!currentRow) break;
          var up = parentTreeParentId(currentRow);
          if (!up) break;
          showIds.add(up);
          current = up;
        }
      });

      treeRows.forEach(function (row) {
        var value = parentTreeValue(row);
        if (!value) {
          row.classList.remove('is-hidden');
          return;
        }
        row.classList.toggle('is-hidden', !showIds.has(value));
      });
      return;
    }

    treeRows.forEach(function (row) {
      var value = parentTreeValue(row);
      if (!value) {
        row.classList.remove('is-hidden');
        return;
      }
      row.classList.toggle('is-hidden', parentTreeHasCollapsedAncestor(row));
    });
  }

  function syncParentTreeSelection() {
    var current = parentSelect.value || '';
    treeRows.forEach(function (row) {
      row.classList.toggle('active', parentTreeValue(row) === current);
    });
    if (current) openParentTreeAncestorsByValue(current);
    refreshParentTreeVisibility();
  }

  function syncParentLabel() {
    if (!parentPickerLabel) return;
    var selected = parentSelect.options[parentSelect.selectedIndex];
    var text = selected ? (selected.getAttribute('data-title') || selected.textContent || '') : '';
    text = text.replace(/\s+/g, ' ').trim();
    parentPickerLabel.textContent = text || '— Yuqori daraja (katta tur) —';
  }

  function openParentPicker() {
    parentTreeQuery = '';
    if (parentTreeSearch) parentTreeSearch.value = '';
    parentPickerModal.classList.add('is-open');
    parentPickerModal.setAttribute('aria-hidden', 'false');
    refreshParentTreeVisibility();
    if (parentTreeSearch) {
      parentTreeSearch.focus();
      parentTreeSearch.select();
    }
  }

  function closeParentPicker() {
    parentPickerModal.classList.remove('is-open');
    parentPickerModal.setAttribute('aria-hidden', 'true');
  }

  function filteredItems() {
    if (!searchText) return allItems.slice();
    return allItems.filter(function (item) {
      var hay = (item.name || '') + ' ' + (item.cat_name || '');
      return hay.toLowerCase().indexOf(searchText) !== -1;
    });
  }

  function updateScopeButton() {
    if (!toggleProductsScopeBtn) return;
    if (showAllProducts) {
      toggleProductsScopeBtn.textContent = "Faqat bo'shlarini ko'rsatish";
      toggleProductsScopeBtn.classList.add('scope-all-active');
      return;
    }
    toggleProductsScopeBtn.textContent = "Hammasini ko'rsatish";
    toggleProductsScopeBtn.classList.remove('scope-all-active');
  }

  function visibleItemsAllSelected() {
    var list = filteredItems();
    if (!list.length) return false;
    return list.every(function (item) {
      return selectedIds.has(item.id);
    });
  }

  function updateVisibleToggleButton() {
    if (!toggleVisibleBtn) return;
    toggleVisibleBtn.textContent = visibleItemsAllSelected()
      ? "Ko'ringanini tozalash"
      : "Ko'ringanini belgilash";
  }

  function renderEmpty(message, isError) {
    var cls = isError ? 'category-products-empty error' : 'category-products-empty';
    wrap.innerHTML = '<div class="' + cls + '">' + escapeHtml(message) + '</div>';
  }

  function renderSortPreview(siblings) {
    if (!sortPreviewEl) return;
    if (!siblings || !siblings.length) {
      sortPreviewEl.innerHTML = '<span class="sort-chip empty">Bu bo\'limda hali kategoriya yo\'q.</span>';
      return;
    }
    sortPreviewEl.innerHTML = siblings.map(function (item) {
      return '<span class="sort-chip"><strong>' + escapeHtml(item.sort_order) + '</strong> ' + escapeHtml(item.name) + '</span>';
    }).join('');
  }

  function renderItems(items) {
    allItems = items || [];
    if (!allItems.length) {
      renderEmpty(
        showAllProducts
          ? 'Mahsulot topilmadi.'
          : "Bo'sh mahsulot topilmadi. Kerak bo'lsa \"Hammasini ko'rsatish\"ni bosing.",
        false
      );
      updatePickedCount();
      updateVisibleToggleButton();
      return;
    }

    var list = filteredItems();
    if (!list.length) {
      renderEmpty("Qidiruv bo'yicha mos mahsulot topilmadi.", false);
      updatePickedCount();
      updateVisibleToggleButton();
      return;
    }

    wrap.innerHTML = list.map(function (product) {
      var checked = selectedIds.has(product.id) ? ' checked' : '';
      var statusCls = product.is_active ? 'active' : 'inactive';
      var statusText = product.is_active ? 'Faol' : 'Nofaol';
      var meta = product.assigned_categories_text ? '<small>' + escapeHtml(product.assigned_categories_text) + '</small>' : '';
      var media = product.image
        ? '<img src="' + imageBase + encodeURIComponent(product.image) + '" alt="' + escapeHtml(product.name) + '">'
        : '<span class="category-product-fallback">' + escapeHtml(product.cat_icon || '🌿') + '</span>';

      return '<label class="category-product-card" data-id="' + product.id + '">'
        + '<input type="checkbox" name="product_ids" value="' + product.id + '"' + checked + '>'
        + media
        + '<span class="category-product-main"><strong>' + escapeHtml(product.name) + '</strong>' + meta + '</span>'
        + '<span class="category-product-status ' + statusCls + '">' + statusText + '</span>'
        + '</label>';
    }).join('');

    updatePickedCount();
    updateVisibleToggleButton();
  }

  function setActionState(enabled) {
    searchInput.disabled = !enabled;
    toggleProductsScopeBtn.disabled = !enabled;
    toggleVisibleBtn.disabled = !enabled;
    updateVisibleToggleButton();
  }

  function loadProducts(parentId) {
    if (!parentId) {
      allItems = [];
      setActionState(false);
      renderEmpty("Ota tur tanlang, mahsulotlar shu yerda chiqadi.", false);
      updatePickedCount();
      updateScopeButton();
      updateVisibleToggleButton();
      return;
    }

    setActionState(true);
    var query = '?parent_id=' + encodeURIComponent(parentId) + '&show=' + (showAllProducts ? 'all' : 'available');
    if (currentCatId) query += '&current_category_id=' + encodeURIComponent(currentCatId);

    fetch(endpointProducts + query)
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (!data || !data.success) {
          allItems = [];
          renderEmpty('Mahsulotlarni yuklashda xatolik.', true);
          updateVisibleToggleButton();
          return;
        }
        renderItems(data.items || []);
        updateScopeButton();
      })
      .catch(function () {
        allItems = [];
        renderEmpty('Mahsulotlarni yuklashda xatolik.', true);
        updateVisibleToggleButton();
      });
  }

  function loadSortHint(parentId) {
    var query = '?parent_id=' + encodeURIComponent(parentId || '');
    if (currentCatId) query += '&exclude_id=' + encodeURIComponent(currentCatId);

    fetch(endpointSortHint + query)
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (!data || !data.success) return;
        var siblings = data.siblings || [];
        var nextSort = Number(data.next_sort || 1);
        lastSortSuggestion = nextSort;
        renderSortPreview(siblings);
        if (!sortTouched && sortInput && !currentCatId) {
          sortInput.value = String(nextSort);
        }
      })
      .catch(function () {});
  }

  wrap.addEventListener('change', function (event) {
    var target = event.target;
    if (!target || target.name !== 'product_ids') return;

    var id = parseInt(target.value, 10);
    if (!id) return;

    if (target.checked) selectedIds.add(id);
    else selectedIds.delete(id);
    updatePickedCount();
    updateVisibleToggleButton();
  });

  searchInput.addEventListener('input', function () {
    searchText = (searchInput.value || '').trim().toLowerCase();
    renderItems(allItems);
  });

  toggleVisibleBtn.addEventListener('click', function () {
    var list = filteredItems();
    var shouldClear = visibleItemsAllSelected();
    list.forEach(function (item) {
      if (shouldClear) selectedIds.delete(item.id);
      else selectedIds.add(item.id);
    });
    renderItems(allItems);
  });

  toggleProductsScopeBtn.addEventListener('click', function () {
    showAllProducts = !showAllProducts;
    loadProducts(parentSelect.value || '');
  });

  parentSelect.addEventListener('change', function () {
    selectedIds.clear();
    searchText = '';
    searchInput.value = '';
    if (!currentCatId) sortTouched = false;
    loadProducts(this.value || '');
    loadSortHint(this.value || '');
    syncParentTreeSelection();
    syncParentLabel();
  });

  treeRows.forEach(function (row) {
    var value = parentTreeValue(row);
    var id = (row.getAttribute('data-cat-id') || '').trim();
    var parentId = parentTreeParentId(row);

    if (id) {
      parentTreeById.set(id, row);
      if (!parentTreeChildren.has(parentId)) parentTreeChildren.set(parentId, []);
      parentTreeChildren.get(parentId).push(row);
    }

    row.addEventListener('click', function (event) {
      var toggleEl = event.target && event.target.closest ? event.target.closest('.parent-tree-toggle') : null;
      if (toggleEl) {
        event.preventDefault();
        event.stopPropagation();
        if (row.classList.contains('no-children')) return;
        setParentTreeExpanded(row, row.classList.contains('is-collapsed'));
        refreshParentTreeVisibility();
        return;
      }

      if (parentSelect.value === value) {
        syncParentTreeSelection();
        return;
      }

      parentSelect.value = value;
      parentSelect.dispatchEvent(new Event('change'));
      closeParentPicker();
    });
  });

  treeRows.forEach(function (row) {
    var id = (row.getAttribute('data-cat-id') || '').trim();
    var hasChildren = !!(id && parentTreeChildren.get(id) && parentTreeChildren.get(id).length);
    if (!hasChildren) {
      row.classList.add('no-children');
      return;
    }
    row.classList.remove('no-children');
    row.classList.remove('is-collapsed');
  });

  if (parentTreeExpandAllBtn) {
    parentTreeExpandAllBtn.addEventListener('click', function () {
      treeRows.forEach(function (row) {
        if (!row.classList.contains('no-children')) row.classList.remove('is-collapsed');
      });
      refreshParentTreeVisibility();
    });
  }

  if (parentTreeCollapseAllBtn) {
    parentTreeCollapseAllBtn.addEventListener('click', function () {
      treeRows.forEach(function (row) {
        if (!row.classList.contains('no-children')) row.classList.add('is-collapsed');
      });
      openParentTreeAncestorsByValue(parentSelect.value || '');
      refreshParentTreeVisibility();
    });
  }

  if (parentTreeSearch) {
    parentTreeSearch.addEventListener('input', function () {
      parentTreeQuery = (parentTreeSearch.value || '').trim().toLowerCase();
      if (parentTreeQuery) {
        treeRows.forEach(function (row) {
          if (!row.classList.contains('no-children')) row.classList.remove('is-collapsed');
        });
      }
      refreshParentTreeVisibility();
    });
  }

  openParentPickerBtn.addEventListener('click', openParentPicker);
  if (closeParentPickerBtn) closeParentPickerBtn.addEventListener('click', closeParentPicker);

  parentPickerModal.addEventListener('click', function (event) {
    var target = event.target;
    if (target && target.hasAttribute('data-close-parent-picker')) closeParentPicker();
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && parentPickerModal.classList.contains('is-open')) {
      closeParentPicker();
    }
  });

  if (sortInput) {
    sortInput.addEventListener('input', function () {
      sortTouched = true;
    });
  }

  if (autoSortBtn) {
    autoSortBtn.addEventListener('click', function () {
      if (!sortInput) return;
      if (lastSortSuggestion !== null) sortInput.value = String(lastSortSuggestion);
      sortTouched = true;
      sortInput.focus();
    });
  }

  updatePickedCount();
  updateScopeButton();
  updateVisibleToggleButton();
  syncParentTreeSelection();
  syncParentLabel();
  loadProducts(parentSelect.value || '');
  loadSortHint(parentSelect.value || '');
})();
