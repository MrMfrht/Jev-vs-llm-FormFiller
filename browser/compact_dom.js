(retainTargets = false) => {
  // Rebuild a small semantic tree. Never copy scripts, styles or event handlers.
  const controls = [];
  const targets = new Map();
  const capturedUrl = location.href;
  const structure = new Set(
    "main nav section article aside header footer h1 h2 h3 h4 h5 h6 ul ol li p table tr th td form label".split(" ")
  );
  const roles = new Set([
    "button", "link", "checkbox", "radio", "combobox", "textbox", "switch", "tab",
    "menuitem", "menuitemcheckbox", "menuitemradio", "option", "treeitem",
  ]);
  const pickerTypes = new Set(["date", "datetime-local", "month", "week", "time", "color", "file"]);
  const normalize = text => (text ?? "").replace(/\s+/g, " ").trim();

  function controlRole(el) {
    const explicit = el.getAttribute("role");
    if (roles.has(explicit)) return explicit;
    if (el.matches("a[href], area[href]")) return "link";
    if (el.matches("button, summary, input:is([type=button],[type=submit],[type=reset],[type=image])")) return "button";
    if (el.matches("input:is([type=checkbox],[type=radio])")) return el.type;
    if (el.matches("select")) return "combobox";
    if (el.matches("input") && pickerTypes.has(el.type)) return el.type + "-picker";
    if (el.matches("input[type=range]")) return "slider";
    if (el.matches("textarea, input, [contenteditable=true]")) return "textbox";
    if (el.hasAttribute("onclick") || typeof el.onclick === "function") return "button";
    return null;
  }

  function controlName(el) {
    const labelledBy = (el.getAttribute("aria-labelledby") || "").split(/\s+/)
      .map(id => document.getElementById(id)?.textContent || "").join(" ");
    return [labelledBy, el.getAttribute("aria-label"),
      Array.from(el.labels || [], label => label.innerText).join(" "),
      el.getAttribute("title"), el.innerText, el.getAttribute("alt"),
      el.querySelector("img[alt]")?.alt, el.getAttribute("placeholder"),
      el.matches("input[type=submit],input[type=button]") ? el.value : ""]
      .map(normalize).find(Boolean) || "";
  }

  function describeAction(node) {
    const owner = node.closest("tr,li,article,fieldset,form,[role=row],[role=listitem]");
    return JSON.stringify([
      controlRole(node), controlName(node), node.getAttribute("type"), node.href,
      node.form?.action, node.formAction, node.name, owner && normalize(owner.innerText),
    ]);
  }

  function copy(node, parent, controlsOnly = false) {
    if (node.nodeType === Node.TEXT_NODE) {
      if (!controlsOnly) parent.append(node.textContent.replace(/\s+/g, " "));
      return;
    }
    if (!(node instanceof Element) || node.matches("script,style,template,noscript,[hidden],[inert],[aria-hidden=true],input[type=hidden]")) return;
    const style = getComputedStyle(node);
    if (style.display === "none" || style.visibility === "hidden") return;
    const role = controlRole(node);
    if (role) {
      const id = "c" + (controls.length + 1);
      const name = controlName(node);
      const isSelect = node.matches("select");
      const editable = !node.readOnly && (node.matches("textarea") ||
        (node.matches("input") && ["text","search","url","email","tel","number"].includes(node.type)) ||
        node.isContentEditable);
      const options = isSelect ? Array.from(node.options, option => ({
        index: option.index, label: option.label, selected: option.selected,
        disabled: option.matches(":disabled") || !!option.closest("[hidden],[inert],[aria-disabled=true]"),
      })) : [];
      if (retainTargets) targets.set(id, {node, action: describeAction(node),
        optionNodes: isSelect ? Array.from(node.options) : [],
        optionValues: isSelect ? Array.from(node.options, option => option.value) : [], options});
      controls.push({id, role, name, disabled: node.matches(":disabled") || !!node.closest("[aria-disabled=true]"),
        href: node.matches("a[href],area[href]") ? node.href : null, options, multiple: !!node.multiple, editable});
      const marker = document.createElement("control");
      marker.setAttribute("id", id);
      marker.setAttribute("role", role);
      if (role === "checkbox" || role === "radio" || role === "switch") {
        marker.setAttribute("checked", node.getAttribute("aria-checked") ?? String(!!node.checked));
      }
      marker.textContent = name;
      if (isSelect) marker.setAttribute("selected", options.filter(o => o.selected).map(o => o.label).join(", "));
      if (editable) marker.setAttribute("value", node.value ?? node.innerText);
      parent.append(marker);
      // Tree items and custom clickable containers can contain other controls.
      for (const child of node.children) copy(child, parent, true);
      return;
    }
    const tag = node.localName;
    const target = !controlsOnly && structure.has(tag) ? document.createElement(tag) : parent;
    if (target !== parent) parent.append(target);
    for (const child of node.childNodes) copy(child, target, controlsOnly);
  }

  const root = document.createElement("main");
  copy(document.body, root);
  const scroller = document.scrollingElement;
  const snapshot = {url: capturedUrl, title: document.title, html: root.innerHTML.trim(), controls,
    scroll_y: Math.round(scrollY), scroll_max: Math.max(0, scroller.scrollHeight - scroller.clientHeight)};
  if (!retainTargets) return snapshot;
  function resolve(id) {
    const target = targets.get(id);
    if (!target || !target.node.isConnected || target.node.ownerDocument !== document ||
        location.href !== capturedUrl || describeAction(target.node) !== target.action) return null;
    if (target.node.closest("[hidden],[inert],[aria-hidden=true],[aria-disabled=true]") ||
        target.node.matches(":disabled")) return null;
    return target.node;
  }
  function resolveOption(id, index) {
    const select = resolve(id);
    const target = targets.get(id);
    const option = select?.options?.[index];
    const old = target?.options[index];
    if (!option || option !== target.optionNodes[index] || option.label !== old.label ||
        option.value !== target.optionValues[index] || option.selected !== old.selected || option.matches(":disabled") ||
        option.closest("[hidden],[inert],[aria-disabled=true]")) return null;
    return option;
  }
  return {snapshot, resolve, resolveOption};
}
