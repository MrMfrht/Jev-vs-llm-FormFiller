(field, operation) => {
  // Follow the field's own popup references, even if the menu is mounted in a portal.
  const visible = el => !!el && el.checkVisibility({visibilityProperty:true}) && !!el.getClientRects().length && !el.closest('[hidden],[aria-hidden=true]');
  const roots = [field];
  for (const id of [field.getAttribute('aria-controls'),field.getAttribute('aria-owns')].filter(Boolean).join(' ').split(/\s+/)) {
    const el = field.getRootNode().getElementById(id);
    if (el && el !== field) roots.push(el);
  }
  const options = [...new Set(roots.flatMap(el => el.matches('[role=option]') ? [el] : [...el.querySelectorAll('[role=option]')]))];
  const label = el => {
    const refs = (el.getAttribute('aria-labelledby') || '').split(/\s+/);
    return refs.map(id => el.getRootNode().getElementById(id)?.textContent).filter(Boolean).join(' ') ||
      el.getAttribute('aria-label') || el.textContent.trim();
  };
  if (operation === 'open') return options.some(visible) || field.getAttribute('aria-expanded') === 'true';
  if (operation === 'search') {
    const popupIds = new Set(roots.filter(el => el !== field && el.id).map(el=>el.id));
    const relatedEditors = [...field.getRootNode().querySelectorAll('input[aria-controls],textarea[aria-controls]')]
      .filter(el => !el.readOnly && visible(el) &&
        el.getAttribute('aria-controls').split(/\s+/).some(id=>popupIds.has(id)));
    const editors = [...new Set(roots.flatMap(el => [
      ...(el.matches('input:not([readonly]),textarea:not([readonly])') ? [el] : []),
      ...el.querySelectorAll('input:not([readonly]),textarea:not([readonly])')].filter(visible)).concat(relatedEditors))];
    return editors.length === 1 ? editors[0] : null;
  }
  if (operation === 'selected') return options.filter(el=>el.getAttribute('aria-selected')==='true').map(label);
  const shown = options.filter(visible);
  if (operation === 'rows') return shown.map(el=>({label:label(el), value:el.getAttribute('value'),
    disabled:!!el.closest('[aria-disabled=true],[inert]')}));
  if (typeof operation === 'object') return shown[operation.index] || null;
  if (operation === 'scroll') {
    for (const option of shown) {
      for (let el = option.parentElement; el && el !== document.body && el !== document.documentElement; el = el.parentElement) {
        if (!['auto','scroll','overlay'].includes(getComputedStyle(el).overflowY) || el.scrollHeight <= el.clientHeight) continue;
        const before = el.scrollTop;
        el.scrollBy({top:Math.max(1, el.clientHeight - 1),behavior:'instant'});
        return before !== el.scrollTop;
      }
    }
    return false;
  }
}
