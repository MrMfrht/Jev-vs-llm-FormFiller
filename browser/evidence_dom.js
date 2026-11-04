() => {
  const blocks = [];
  const clean = value => (value ?? "").replace(/\s+/g, " ").trim();
  const omitted = "script,style,template,noscript,[hidden],[inert],[aria-hidden=true],input[type=hidden],input[type=password]";
  const headings = "h1,h2,h3,h4,h5,h6";
  const scopes = "main,nav,article,section,aside,header,footer,li,dialog";

  function visible(el) {
    const style = getComputedStyle(el);
    return !el.matches(omitted) && style.display !== "none" && style.visibility !== "hidden";
  }

  // Read inline prose as one unit. Exclude nested hidden content, even when
  // aria-hidden does not change the browser's visible layout.
  function inlineText(node) {
    if (node.nodeType === Node.TEXT_NODE) return node.data;
    if (!(node instanceof Element) || !visible(node)) return "";
    if (node.matches("br")) return " ";
    if (node.matches("img")) return node.alt;
    return Array.from(node.childNodes, inlineText).join("");
  }

  function emit(kind, value, context) {
    const text = clean(value);
    if (text) blocks.push({kind, text, context: context.filter(Boolean)});
  }

  function fieldLabel(el) {
    const ids = (el.getAttribute("aria-labelledby") || "").split(/\s+/);
    return clean(ids.map(id => document.getElementById(id)?.textContent).join(" ")) ||
      el.getAttribute("aria-label") || clean(Array.from(el.labels || [], inlineText).join(" ")) ||
      el.getAttribute("placeholder") || el.name;
  }

  function cellContext(cell) {
    const table = cell.closest("table");
    const row = cell.parentElement;
    if (!table || !row.matches("tr")) return [];
    const context = [table.caption && clean(inlineText(table.caption)), "Row " + (row.rowIndex + 1)];
    const explicit = (cell.getAttribute("headers") || "").split(/\s+/)
      .map(id => document.getElementById(id))
      .filter(el => el?.matches("th") && el.closest("table") === table);
    if (explicit.length) return context.concat(explicit.map(el => clean(inlineText(el))));
    const rowHeaders = Array.from(row.cells).filter(el => el !== cell && el.scope === "row");
    context.push(...rowHeaders.map(el => clean(inlineText(el))));
    // Only infer positional headers for a simple rectangular table.
    const first = table.rows[0];
    if (first && first !== row && !table.querySelector("[colspan],[rowspan]") &&
        Array.from(first.cells).every(el => el.matches("th")) && first.cells.length === row.cells.length) {
      context.push(clean(inlineText(first.cells[cell.cellIndex])));
    }
    return context;
  }

  function visit(node, trail, labels) {
    if (node.nodeType === Node.TEXT_NODE) {
      emit("text", node.data, [...trail, ...labels]);
      return;
    }
    if (!(node instanceof Element) || !visible(node)) return;
    if (node.matches(scopes)) trail = [...trail];
    if (node.matches(headings)) {
      const title = clean(inlineText(node));
      const level = Number(node.localName[1]);
      trail.length = Math.min(trail.length, level - 1);
      emit("heading", title, [...trail, ...labels]);
      trail[level - 1] = title;
      return;
    }
    if (node.matches("td,th")) labels = [...labels, ...cellContext(node)];
    const context = [...trail, ...labels];
    if (node.matches("input,textarea,select")) {
      let value = node.value;
      if (node.matches("select")) value = Array.from(node.selectedOptions, o => o.text).join(", ");
      if (node.matches("input[type=checkbox],input[type=radio]")) value = node.checked ? "checked" : "unchecked";
      if (node.matches("input[type=file]")) return;
      emit("field", value, [...context, fieldLabel(node)]);
      return;
    }
    const splitParagraph = node.matches("p") && node.querySelectorAll("span").length > 1;
    if (!splitParagraph && node.matches("p,a,button,dt,summary") && !node.querySelector("input,textarea,select,button,a,br")) {
      emit(node.localName, inlineText(node) || node.getAttribute("aria-label"), context);
      return;
    }
    if (node.matches("img")) {
      emit("image-description", node.alt, context);
      return;
    }
    for (const child of node.childNodes) visit(child, trail, labels);
  }

  visit(document.body, [], []);
  return {url: location.href, blocks};
}
