// Shared tab navigation. Each page has <nav id="tabs"></nav> and loads this script.
(() => {
  const ICONS = {
    recipes:
      '<path d="M5 5a2 2 0 0 1 2-2h11v15H7a2 2 0 0 0-2 2z"/><path d="M5 20a2 2 0 0 0 2 1h11v-3"/><path d="M9 7h5M9 10.5h5"/>',
    live: '<path d="M4 10h16v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"/><path d="M2 10h2M20 10h2"/><path d="M9 6.5c0-1.2 1.2-1.3 1.2-2.5M13.8 6.5c0-1.2 1.2-1.3 1.2-2.5"/>',
    stats:
      '<path d="M4 20h16"/><rect x="5" y="12" width="3.2" height="5" rx="1"/><rect x="10.4" y="8" width="3.2" height="9" rx="1"/><rect x="15.8" y="4" width="3.2" height="13" rx="1"/>',
    settings:
      '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
  };
  const TABS = [
    { href: "/", icon: "live", label: "Live" },
    {
      href: "/recipes",
      icon: "recipes",
      label: "Rezepte",
      also: ["/recipes/edit", "/cook"],
    },
    { href: "/stats", icon: "stats", label: "Statistik" },
    { href: "/settings", icon: "settings", label: "Einstellungen" },
  ];
  const nav = document.getElementById("tabs");
  nav.className = "tabs";
  nav.setAttribute("aria-label", "Bereiche");
  nav.innerHTML = TABS.map(
    (t) =>
      `<a class="tab" href="${t.href}"${location.pathname === t.href || (t.also ?? []).includes(location.pathname) ? ' aria-current="page"' : ""}>` +
      `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" ` +
      `stroke-linecap="round" stroke-linejoin="round">${ICONS[t.icon]}</svg>` +
      `<span>${t.label}</span></a>`,
  ).join("");
})();
