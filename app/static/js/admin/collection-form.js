(function () {
  var input = document.getElementById('collectionProductSearch');
  var openPickerBtn = document.getElementById('openCollectionCategoryPickerBtn');
  var pickerModal = document.getElementById('collectionCategoryPickerModal');
  var closePickerBtn = document.getElementById('closeCollectionCategoryPickerBtn');
  var pickerLabel = document.getElementById('collectionCategoryPickerLabel');
  var tree = document.getElementById('collectionCategoryTree');
  var treeSearch = document.getElementById('collectionCategoryTreeSearch');
  var toggleAllBtn = document.getElementById('collectionCategoryToggleAllBtn');
  if (!input) return;

  var items = Array.from(document.querySelectorAll('.collection-product-item'));
  var selectedCategory = '';
  var treeQuery = '';
  var treeRows = tree ? Array.from(tree.querySelectorAll('.parent-tree-row[data-value]')) : [];
  var treeById = new Map();
  var treeChildren = new Map();

  function valueOf(row) {
    return (row.getAttribute('data-value') || '').trim();
  }

  function parentIdOf(row) {
    return (row.getAttribute('data-parent-id') || '').trim();
  }

  function itemCategoryIds(item) {
    return (item.getAttribute('data-category-ids') || '')
      .split(',')
      .map(function (value) { return value.trim(); })
      .filter(Boolean);
  }

  function setExpanded(row, expanded) {
    if (!row || row.classList.contains('no-children')) return;
    row.classList.toggle('is-collapsed', !expanded);
  }

  function expandableRows() {
    return treeRows.filter(function (row) {
      return !row.classList.contains('no-children');
    });
  }

  function areAllExpanded() {
    var rows = expandableRows();
    if (!rows.length) return true;
    return rows.every(function (row) {
      return !row.classList.contains('is-collapsed');
    });
  }

  function updateToggleAllButton() {
    if (!toggleAllBtn) return;
    var rows = expandableRows();
    var expandLabel = toggleAllBtn.dataset.expandLabel || 'Barchasini ochish';
    var collapseLabel = toggleAllBtn.dataset.collapseLabel || 'Barchasini yopish';
    if (!rows.length) {
      toggleAllBtn.disabled = true;
      toggleAllBtn.textContent = expandLabel;
      toggleAllBtn.setAttribute('aria-pressed', 'false');
      return;
    }
    var expanded = rows.every(function (row) {
      return !row.classList.contains('is-collapsed');
    });
    toggleAllBtn.disabled = false;
    toggleAllBtn.textContent = expanded ? collapseLabel : expandLabel;
    toggleAllBtn.setAttribute('aria-pressed', expanded ? 'true' : 'false');
  }

  function openAncestorsByValue(value) {
    var current = String(value || '');
    while (current) {
      var row = treeById.get(current);
      if (!row) break;
      var parentId = parentIdOf(row);
      if (!parentId) break;
      var parentRow = treeById.get(parentId);
      if (!parentRow) break;
      setExpanded(parentRow, true);
      current = parentId;
    }
  }

  function hasCollapsedAncestor(row) {
    var parentId = parentIdOf(row);
    while (parentId) {
      var parentRow = treeById.get(parentId);
      if (!parentRow) return false;
      if (parentRow.classList.contains('is-collapsed')) return true;
      parentId = parentIdOf(parentRow);
    }
    return false;
  }

  function refreshTreeVisibility() {
    if (!tree) return;

    if (treeQuery) {
      var showIds = new Set();
      treeRows.forEach(function (row) {
        var value = valueOf(row);
        if (!value) return;
        var nameEl = row.querySelector('.parent-tree-name');
        var haystack = ((nameEl ? nameEl.textContent : row.textContent) || '').toLowerCase();
        if (haystack.indexOf(treeQuery) === -1) return;

        showIds.add(value);
        var current = value;
        while (current) {
          showIds.add(current);
          var currentRow = treeById.get(current);
          if (!currentRow) break;
          var up = parentIdOf(currentRow);
          if (!up) break;
          showIds.add(up);
          current = up;
        }
      });

      treeRows.forEach(function (row) {
        var value = valueOf(row);
        if (!value) {
          row.classList.remove('is-hidden');
          return;
        }
        row.classList.toggle('is-hidden', !showIds.has(value));
      });
      return;
    }

    treeRows.forEach(function (row) {
      var value = valueOf(row);
      if (!value) {
        row.classList.remove('is-hidden');
        return;
      }
      row.classList.toggle('is-hidden', hasCollapsedAncestor(row));
    });
  }

  function syncTreeSelection() {
    if (!tree) return;
    treeRows.forEach(function (row) {
      row.classList.toggle('active', valueOf(row) === selectedCategory);
    });
    if (selectedCategory) openAncestorsByValue(selectedCategory);
    refreshTreeVisibility();
    updateToggleAllButton();
  }

  function selectedCategoryLabel() {
    if (!selectedCategory) return 'Barcha kategoriyalar';
    var row = treeById.get(selectedCategory);
    if (!row) return 'Barcha kategoriyalar';
    var nameEl = row.querySelector('.parent-tree-name');
    return ((nameEl ? nameEl.textContent : row.textContent) || 'Barcha kategoriyalar').replace(/\s+/g, ' ').trim();
  }

  function syncPickerLabel() {
    if (pickerLabel) pickerLabel.textContent = selectedCategoryLabel();
  }

  function matchesCategory(item) {
    if (!selectedCategory) return true;

    return itemCategoryIds(item).some(function (categoryId) {
      var current = categoryId;
      while (current) {
        if (current === selectedCategory) return true;
        var row = treeById.get(current);
        current = row ? parentIdOf(row) : '';
      }
      return false;
    });
  }

  function applyFilters() {
    var query = (input.value || '').trim().toLowerCase();
    items.forEach(function (item) {
      var haystack = item.getAttribute('data-search') || '';
      var matchesSearch = !query || haystack.indexOf(query) !== -1;
      var visible = matchesSearch && matchesCategory(item);
      item.classList.toggle('is-hidden', !visible);
    });
  }

  function openPicker() {
    if (!pickerModal) return;
    treeQuery = '';
    if (treeSearch) treeSearch.value = '';
    pickerModal.classList.add('is-open');
    pickerModal.setAttribute('aria-hidden', 'false');
    refreshTreeVisibility();
    updateToggleAllButton();
    if (treeSearch) {
      treeSearch.focus();
      treeSearch.select();
    }
  }

  function closePicker() {
    if (!pickerModal) return;
    pickerModal.classList.remove('is-open');
    pickerModal.setAttribute('aria-hidden', 'true');
  }

  if (tree) {
    treeRows.forEach(function (row) {
      row.style.setProperty('--tree-depth', row.getAttribute('data-tree-depth') || '0');

      var id = (row.getAttribute('data-cat-id') || '').trim();
      var parentId = parentIdOf(row);
      if (id) {
        treeById.set(id, row);
        if (!treeChildren.has(parentId)) treeChildren.set(parentId, []);
        treeChildren.get(parentId).push(row);
      }

      row.addEventListener('click', function (event) {
        var toggleEl = event.target && event.target.closest ? event.target.closest('.parent-tree-toggle') : null;
        if (toggleEl) {
          event.preventDefault();
          event.stopPropagation();
          if (row.classList.contains('no-children')) return;
          setExpanded(row, row.classList.contains('is-collapsed'));
          refreshTreeVisibility();
          updateToggleAllButton();
          return;
        }

        selectedCategory = valueOf(row);
        syncTreeSelection();
        syncPickerLabel();
        applyFilters();
        closePicker();
      });
    });

    treeRows.forEach(function (row) {
      var id = (row.getAttribute('data-cat-id') || '').trim();
      var hasChildren = !!(id && treeChildren.get(id) && treeChildren.get(id).length);
      if (!hasChildren) {
        row.classList.add('no-children');
        return;
      }
      row.classList.remove('no-children');
      row.classList.remove('is-collapsed');
    });
  }

  input.addEventListener('input', applyFilters);

  if (toggleAllBtn) {
    toggleAllBtn.addEventListener('click', function () {
      var shouldCollapse = areAllExpanded();
      treeRows.forEach(function (row) {
        if (row.classList.contains('no-children')) return;
        row.classList.toggle('is-collapsed', shouldCollapse);
      });
      if (shouldCollapse) openAncestorsByValue(selectedCategory);
      refreshTreeVisibility();
      updateToggleAllButton();
    });
  }

  if (treeSearch) {
    treeSearch.addEventListener('input', function () {
      treeQuery = (treeSearch.value || '').trim().toLowerCase();
      if (treeQuery) {
        treeRows.forEach(function (row) {
          if (!row.classList.contains('no-children')) row.classList.remove('is-collapsed');
        });
      }
      refreshTreeVisibility();
      updateToggleAllButton();
    });
  }

  if (openPickerBtn) openPickerBtn.addEventListener('click', openPicker);
  if (closePickerBtn) closePickerBtn.addEventListener('click', closePicker);

  if (pickerModal) {
    pickerModal.addEventListener('click', function (event) {
      var target = event.target;
      if (target && target.hasAttribute('data-close-parent-picker')) closePicker();
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && pickerModal && pickerModal.classList.contains('is-open')) {
      closePicker();
    }
  });

  syncTreeSelection();
  syncPickerLabel();
  applyFilters();
})();
