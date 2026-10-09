// Adds a Difficulty (1-5) dropdown to the admin challenge edit page (new challenges get theirs from the
// Add challenge form on the CyberPaw admin home).
// The dropdown has no `name`, so the platform's own form code ignores it; this script saves it through
// the cyberpaw plugin API instead.
(() => {
  const API = `${init.urlRoot}/plugins/cyberpaw/api/difficulty`;
  const LABELS = ["Not set", "1 - Easy", "2", "3 - Medium", "4", "5 - Hard"];

  function buildField(id) {
    const group = document.createElement("div");
    group.className = "form-group mb-3 cp-difficulty-field";
    group.innerHTML = `
      <label for="${id}">Difficulty<br>
        <small class="form-text text-muted">Shown to players as 1-5 warning triangles</small>
      </label>
      <select class="form-control" id="${id}">
        ${LABELS.map((label, i) => `<option value="${i}">${label}</option>`).join("")}
      </select>
      <small class="cp-difficulty-status text-muted"></small>`;
    return group;
  }

  async function save(challengeId, value, status) {
    const res = await fetch(`${API}/${challengeId}`, {
      method: "PUT",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "CSRF-Token": init.csrfNonce },
      body: JSON.stringify({ difficulty: Number(value) || null }),
    });
    if (status) status.textContent = res.ok ? "Saved" : "Could not save difficulty";
    return res.ok;
  }

  // Put the field right after the Category input of a challenge form.
  function insertInto(form, id) {
    if (!form || form.querySelector(".cp-difficulty-field")) return null;
    const category = form.querySelector('input[name="category"]');
    const field = buildField(id);
    const anchor = category ? category.closest(".form-group") : null;
    if (anchor) anchor.after(field);
    else form.prepend(field);
    return field;
  }

  // Edit page: /admin/challenges/<id>. Saves as soon as the value changes.
  async function setupEdit() {
    const container = document.getElementById("challenge-update-container");
    if (!container || typeof CHALLENGE_ID === "undefined") return;
    const field = insertInto(container.querySelector("form"), "cp-difficulty-edit");
    if (!field) return;
    const select = field.querySelector("select");
    const status = field.querySelector(".cp-difficulty-status");

    const res = await fetch(API, { credentials: "same-origin" });
    if (res.ok) {
      const { data } = await res.json();
      select.value = String(data[String(CHALLENGE_ID)] || 0);
    }
    select.addEventListener("change", () => save(CHALLENGE_ID, select.value, status));
  }

  // Admin settings CyberPaw doesn't use: brackets, custom fields, languages, MLC, and
  // teams (the site is individual players only).
  const HIDDEN_CONFIG_SECTIONS = ["#brackets", "#fields", "#mlc", "#localization", "#usermode"];

  // CyberPaw assumes English, the US and JWU: hide language, country and affiliation inputs and columns
  // in admin forms and tables (they are loaded into modals later, so keep watching).
  function hideLanguageAndCountry() {
    document.querySelectorAll('select[name="country"], select[name="language"], input[name="affiliation"]').forEach((select) => {
      const group = select.closest(".form-group, .mb-3, .col-md-6, .col-md-4") || select;
      group.style.display = "none";
    });
    document.querySelectorAll("table").forEach((table) => {
      const headers = [...table.querySelectorAll("thead th")];
      headers.forEach((th, index) => {
        if (!["country", "affiliation"].includes(th.textContent.trim().toLowerCase())) return;
        table.querySelectorAll("tr").forEach((row) => {
          const cell = row.children[index];
          if (cell) cell.style.display = "none";
        });
      });
    });
  }

  function hideConfigSections() {
    if (!location.pathname.startsWith(`${init.urlRoot}/admin/config`)) return;
    HIDDEN_CONFIG_SECTIONS.forEach((hash) => {
      document.querySelectorAll(`a[href="${hash}"]`).forEach((a) => {
        (a.closest("li") || a).style.display = "none";
      });
    });
    // Unused fields inside visible tabs: team account options, the deprecated Mailgun settings, and the
    // CTF description (not shown anywhere on the site).
    document.querySelectorAll('#accounts a[href="#team-accounts"]').forEach((a) => {
      (a.closest(".nav") || a).style.display = "none";
    });
    document.querySelectorAll('[name="mailgun_base_url"], [name="mailgun_api_key"], #ctf_description').forEach((input) => {
      (input.closest(".form-group") || input).style.display = "none";
    });
    document.querySelectorAll("#email .alert-warning").forEach((alert) => {
      if (/mailgun/i.test(alert.textContent)) alert.style.display = "none";
    });
    // Drop a sidebar heading when every item under it is hidden.
    document.querySelectorAll("#config-sidebar .section-title").forEach((title) => {
      let item = title.nextElementSibling;
      let visible = false;
      while (item && !item.classList.contains("section-title")) {
        if (item.style.display !== "none") visible = true;
        item = item.nextElementSibling;
      }
      if (!visible) title.style.display = "none";
    });
  }

  // The Terms of Service and Privacy Policy links point at the Rules and Privacy Notice pages, so their text
  // is edited there. Replace the unused text boxes in the Legal tab with buttons to those page editors.
  async function legalPageLinks() {
    if (!location.pathname.startsWith(`${init.urlRoot}/admin/config`)) return;
    const boxes = [
      ["tos_text", "rules", "Rules"],
      ["privacy_text", "privacy-notice", "Privacy Notice"],
    ];
    let pages = [];
    try {
      const res = await fetch(`${init.urlRoot}/api/v1/pages`, { credentials: "same-origin", headers: { "CSRF-Token": init.csrfNonce } });
      pages = res.ok ? (await res.json()).data || [] : [];
    } catch (e) {
      /* buttons fall back to the page list */
    }
    boxes.forEach(([name, route, title]) => {
      const textarea = document.querySelector(`#legal textarea[name="${name}"]`);
      if (!textarea || textarea.value.trim()) return;
      const group = textarea.closest(".form-group") || textarea.parentElement;
      const page = pages.find((p) => p.route === route);
      const note = document.createElement("div");
      note.className = "form-group";
      const text = document.createElement("p");
      text.className = "text-muted mb-2";
      text.textContent = `This text is the ${title} page on the site. Edit it there:`;
      const link = document.createElement("a");
      link.className = "btn btn-outline-primary btn-sm";
      link.href = page ? `${init.urlRoot}/admin/pages/${page.id}` : `${init.urlRoot}/admin/pages`;
      link.textContent = `Edit ${title} page`;
      note.append(text, link);
      group.style.display = "none";
      group.after(note);
    });
  }

  // Config -> Challenges: First solve bonus (plugins/cyberpaw/first_paw.py). The tab's own Update button
  // saves it with the other settings, since the platform stores any setting the form sends.
  async function firstSolveBonusSetting() {
    const form = document.querySelector("#challenges form");
    if (!form || !location.pathname.startsWith(`${init.urlRoot}/admin/config`)) return;
    let value = "0";
    try {
      const res = await fetch(`${init.urlRoot}/api/v1/configs/cyberpaw_first_solve_bonus`, {
        credentials: "same-origin",
        headers: { "CSRF-Token": init.csrfNonce },
      });
      const json = res.ok ? await res.json() : null;
      if (json && json.data && json.data.value !== null && json.data.value !== undefined) value = String(json.data.value);
    } catch (e) {
      /* shows 0 */
    }
    const group = document.createElement("div");
    group.className = "form-group";
    const label = document.createElement("label");
    label.htmlFor = "cp-first-solve-bonus";
    label.textContent = "First solve bonus (points)";
    const input = document.createElement("input");
    input.type = "number";
    input.min = "0";
    input.step = "1";
    input.id = "cp-first-solve-bonus";
    input.name = "cyberpaw_first_solve_bonus";
    input.className = "form-control";
    input.value = value;
    const help = document.createElement("small");
    help.className = "form-text text-muted";
    help.textContent =
      "Extra points for the first player to solve each challenge (the First Paw). Given as an award, so it " +
      "shows on their profile. Moves to the next solver if the first solve is removed. 0 turns it off.";
    group.append(label, input, help);
    form.querySelector("button[type=submit]").before(group);
  }

  // One Submissions page: All / Correct / Incorrect filter buttons instead of three menu entries.
  function submissionFilters() {
    const base = `${init.urlRoot}/admin/submissions`;
    if (!location.pathname.startsWith(base)) return;
    const heading = document.querySelector(".jumbotron h1");
    if (!heading) return;
    const current = location.pathname.slice(base.length).replace(/^\/|\/$/g, "");
    const group = document.createElement("div");
    group.className = "btn-group mt-3";
    group.setAttribute("role", "group");
    [["", "All"], ["correct", "Correct"], ["incorrect", "Incorrect"]].forEach(([type, label]) => {
      const a = document.createElement("a");
      a.className = `btn ${type === current ? "btn-primary" : "btn-outline-primary"}`;
      a.href = type ? `${base}/${type}` : base;
      a.textContent = label;
      group.append(a);
    });
    heading.after(group);
  }

  const start = () => {
    hideConfigSections();
    legalPageLinks();
    firstSolveBonusSetting();
    submissionFilters();
    hideLanguageAndCountry();
    new MutationObserver(hideLanguageAndCountry).observe(document.body, { childList: true, subtree: true });
    setupEdit();
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
