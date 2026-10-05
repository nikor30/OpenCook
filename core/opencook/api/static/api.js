// Small helpers shared by the pages.
const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const init = { cache: "no-store", ...options };
  if (options.json !== undefined) {
    init.body = JSON.stringify(options.json);
    init.headers = { "Content-Type": "application/json" };
  }
  const response = await fetch(path, init);
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    const message = Array.isArray(detail)
      ? detail
          .map((d) => String(d.msg ?? d).replace(/^Value error, /, ""))
          .join(" ")
      : detail;
    throw new Error(message || `Fehler ${response.status}`);
  }
  return data;
}

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value === true) node.setAttribute(key, "");
    else if (value !== false && value != null) node.setAttribute(key, value);
  }
  node.append(...children.flat().filter((c) => c != null));
  return node;
}

const duration = (s) => {
  const m = Math.floor(s / 60);
  const rest = s % 60;
  return rest ? `${m}:${String(rest).padStart(2, "0")} min` : `${m} min`;
};
const clock = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

function ingredientText(ingredient) {
  const amount = ingredient.amount ?? "";
  const unit =
    ingredient.unit && ingredient.unit !== "pcs" ? ` ${ingredient.unit}` : "";
  return `${amount}${unit} ${ingredient.name}`.trim();
}

// Replaces {i1} in a step text with "20 g Butter" (as text nodes, never HTML).
function stepText(text, ingredients) {
  const byId = Object.fromEntries(ingredients.map((i) => [i.id, i]));
  return (text ?? "").split(/(\{[A-Za-z0-9_-]+\})/).map((part) => {
    const id = part.match(/^\{(.+)\}$/)?.[1];
    return byId[id] ? el("strong", {}, ingredientText(byId[id])) : part;
  });
}
