(frameHidden, retainNodes = false) => {
  const fields = [];
  const nodes = [];
  const radioGroups = new Map();
  const roles = new Set(["textbox", "searchbox", "combobox", "listbox", "checkbox", "radio",
    "switch", "slider", "spinbutton"]);
  const clean = value => (value || "").replace(/\s+/g, " ").trim();
  const attr = (el, key) => el.getAttribute(key) || "";
  const parent = el => el.parentElement || el.getRootNode().host;

  function ancestor(el, selector) {
    for (let current = el; current; current = parent(current)) {
      if (current.matches(selector)) return current;
    }
    return null;
  }

  function referenced(el, attribute) {
    return attr(el, attribute).split(/\s+/).filter(Boolean)
      .map(id => el.getRootNode().getElementById(id)).filter(Boolean);
  }

  function label(el) {
    return clean(referenced(el, "aria-labelledby").map(node => node.textContent).join(" ")) ||
      clean(attr(el, "aria-label")) || clean(Array.from(el.labels || [], item => {
        const copy = item.cloneNode(true);
        for (const child of copy.querySelectorAll("select,input,textarea,button")) child.remove();
        return copy.textContent;
      }).join(" ")) || clean(attr(el, "title")) || clean(attr(el, "placeholder"));
  }

  function section(el) {
    const group = ancestor(el, 'fieldset,[role=group],[role=radiogroup],section,article');
    if (!group) return "";
    const heading = group.querySelector(":scope > legend,:scope > h1,:scope > h2,:scope > h3,:scope > h4");
    return label(group) || clean(heading?.textContent) || group.id ||
      "section " + (Array.from(group.getRootNode().querySelectorAll('fieldset,[role=group],[role=radiogroup],section,article')).indexOf(group) + 1);
  }

  function kind(el) {
    if (el.matches("select,textarea")) return el.localName;
    if (el.matches("input") && ["hidden","password","file"].includes(el.type)) return el.type;
    const role = attr(el, "role").split(/\s+/).find(r => roles.has(r));
    if (role) return role;
    if (el.matches("input")) return ["button","image","submit","reset"].includes(el.type) ? "" : el.type;
    if (el.isContentEditable && !parent(el)?.isContentEditable) return "editable";
    return "";
  }

  function hidden(el) {
    if (frameHidden || ancestor(el, "[hidden],[aria-hidden=true]")) return true;
    return !el.checkVisibility({visibilityProperty: true}) || !el.getClientRects().length;
  }

  function disabled(el) {
    return el.matches(":disabled") || !!ancestor(el, "[inert],[aria-disabled=true]");
  }

  function option(el) {
    const native = el.matches("option");
    return {
      label: native ? el.label : label(el) || clean(el.textContent),
      value: native ? el.value : el.getAttribute("value"),
      selected: native ? el.selected : attr(el,"aria-selected") === "true",
      disabled: disabled(el),
      hidden: native ? !!ancestor(el,"[hidden],[aria-hidden=true]") : hidden(el),
      group: el.closest("optgroup")?.label || "",
    };
  }

  function choices(el, type) {
    if (el.matches("select")) return ["native", Array.from(el.options, option)];
    if (el.matches("input") && el.list) return ["suggestions", Array.from(el.list.options, option)];
    if (!["combobox","listbox"].includes(type)) return ["none", []];
    const roots = [el, ...referenced(el,"aria-controls"), ...referenced(el,"aria-owns")];
    const items = new Set(roots.flatMap(root => [ ...(root.matches('[role=option]') ? [root] : []),
      ...root.querySelectorAll('[role=option]') ]));
    return [items.size ? "mounted" : "not_exposed", Array.from(items, option)];
  }

  function value(el, type) {
    if (["password","file","hidden"].includes(type)) return null;
    if (el.matches("select")) return Array.from(el.selectedOptions, opt => opt.value);
    if (["radio","checkbox","switch"].includes(type)) return el.matches("input") ? el.checked : el.getAttribute("aria-checked");
    if (el.matches("input,textarea")) return el.value;
    if (el.isContentEditable) return el.innerText;
    return el.getAttribute("aria-valuetext") ?? el.getAttribute("aria-valuenow");
  }

  function visitField(el, type) {
    const [options_source, options] = choices(el,type);
    const form = el.form || ancestor(el, "form");
    const formName = form && (form.id || form.name || label(form) ||
      "form " + (Array.from(form.getRootNode().querySelectorAll("form")).indexOf(form) + 1));
    const field = {kind:type, label:label(el), name:attr(el,"name"),
      html_id:el.id, placeholder:attr(el,"placeholder"), form:formName || "",
      nearby_label: el.previousElementSibling?.matches("label:not([for])")
        ? clean(el.previousElementSibling.textContent) : "",
      help_text: clean(referenced(el, "aria-describedby").map(n => n.textContent).join(" ")),
      section:section(el), required:!!el.required || attr(el,"aria-required")==="true",
      multiple:!!el.multiple || attr(el,"aria-multiselectable")==="true",
      hidden:hidden(el), disabled:disabled(el), read_only:!!el.readOnly || attr(el,"aria-readonly")==="true",
      value:value(el,type), options, options_source};
    field.fillable_now = !field.hidden && !field.disabled && !field.read_only;
    if (type !== "radio") { fields.push(field); if (retainNodes) nodes.push(el); return; }

    // Native groups are scoped by DOM root, form owner and name. Custom radios
    // are grouped only when the document supplies an explicit radio group.
    const native = el.matches("input");
    const owner = native && el.name ? el.form || el.getRootNode() : ancestor(el,'[role=radiogroup]') || el;
    const key = native ? el.name || el : owner;
    if (!radioGroups.has(owner)) radioGroups.set(owner, new Map());
    const groups = radioGroups.get(owner);
    if (!groups.has(key)) {
      const group = {...field, label:field.section || field.name || field.label,
        options_source:"radio_group", options:[], value:null};
      groups.set(key,group); fields.push(group);
      if (retainNodes) nodes.push(el);
    }
    const group = groups.get(key);
    const selected = field.value === true || field.value === "true";
    const choice = {label:field.label || clean(el.textContent), value:native ? el.value : el.getAttribute("value"),
      selected, hidden:field.hidden, disabled:field.disabled || field.read_only, group:""};
    group.options.push(choice);
    group.fillable_now ||= field.fillable_now;
    group.required ||= field.required;
    group.hidden &&= field.hidden;
    group.disabled &&= field.disabled;
    group.read_only &&= field.read_only;
    if (selected) group.value = choice.value ?? choice.label;
  }

  function walk(root) {
    for (const el of root.querySelectorAll("*")) {
      const type = kind(el);
      if (type) visitField(el,type);
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  }
  walk(document);
  return {url:location.href, fields, ...(retainNodes ? {nodes} : {})};
}
