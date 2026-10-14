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

  // Edit page: release time (plugins/cyberpaw/release.py). A hidden challenge becomes visible at that time.
  // The picker is local time; the server gets and returns UTC epoch seconds.
  async function setupRelease() {
    const container = document.getElementById("challenge-update-container");
    const form = container && container.querySelector("form");
    if (!form || typeof CHALLENGE_ID === "undefined" || form.querySelector(".cp-release-field")) return;
    const url = `${init.urlRoot}/admin/cyberpaw/challenges/${CHALLENGE_ID}/release`;
    const group = document.createElement("div");
    group.className = "form-group mb-3 cp-release-field";
    group.innerHTML = `
      <label for="cp-release-edit">Release time<br>
        <small class="form-text text-muted">A hidden challenge becomes visible to players at this time (your local time)</small>
      </label>
      <div class="d-flex">
        <input class="form-control" type="datetime-local" id="cp-release-edit">
        <button type="button" class="btn btn-outline-secondary ml-2 cp-release-save">Set</button>
        <button type="button" class="btn btn-link text-muted cp-release-clear">Clear</button>
      </div>
      <small class="cp-release-status text-muted"></small>`;
    const anchor = form.querySelector(".cp-difficulty-field") || form.querySelector('input[name="category"]')?.closest(".form-group");
    if (anchor) anchor.after(group);
    else form.prepend(group);
    const input = group.querySelector("input");
    const status = group.querySelector(".cp-release-status");

    const show = (at) => {
      // Epoch seconds to the picker's local "YYYY-MM-DDTHH:MM".
      const d = at ? new Date(at * 1000) : null;
      input.value = d ? new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16) : "";
    };
    const send = async (at) => {
      try {
        const res = await fetch(url, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "CSRF-Token": init.csrfNonce },
          body: JSON.stringify({ at }),
        });
        const body = await res.json();
        if (!res.ok) {
          status.textContent = body.message || "Could not save release time";
          return;
        }
        show(body.at);
        status.textContent = body.at ? "Saved" : "No release time set";
      } catch (e) {
        status.textContent = "Could not save release time";
      }
    };
    group.querySelector(".cp-release-save").addEventListener("click", () => {
      if (!input.value) status.textContent = "Pick a date and time first";
      else send(Math.floor(new Date(input.value).getTime() / 1000));
    });
    group.querySelector(".cp-release-clear").addEventListener("click", () => send(null));

    const res = await fetch(url, { credentials: "same-origin" });
    if (res.ok) show((await res.json()).at);
  }

  // Edit page: bonus flag (plugins/cyberpaw/bonus_flag.py). A second flag worth its own points.
  async function setupBonus() {
    const container = document.getElementById("challenge-update-container");
    const form = container && container.querySelector("form");
    if (!form || typeof CHALLENGE_ID === "undefined" || form.querySelector(".cp-bonus-field")) return;
    const url = `${init.urlRoot}/admin/cyberpaw/challenges/${CHALLENGE_ID}/bonus`;
    const group = document.createElement("div");
    group.className = "form-group mb-3 cp-bonus-field";
    group.innerHTML = `
      <label for="cp-bonus-edit">Bonus flag<br>
        <small class="form-text text-muted">Optional second flag worth extra points. Players enter it in the normal flag box. Changing it clears who has found it.</small>
      </label>
      <div class="d-flex">
        <input class="form-control text-monospace" id="cp-bonus-edit" maxlength="255" placeholder="CyberPaw{...}">
        <input class="form-control ml-2" type="number" min="1" id="cp-bonus-points-edit" aria-label="Bonus points" title="Bonus points" style="max-width: 7rem">
        <button type="button" class="btn btn-outline-secondary ml-2 cp-bonus-save">Set</button>
        <button type="button" class="btn btn-link text-muted cp-bonus-clear">Clear</button>
      </div>
      <small class="cp-bonus-status text-muted"></small>`;
    const anchor = form.querySelector(".cp-release-field, .cp-difficulty-field") || form.querySelector('input[name="category"]')?.closest(".form-group");
    if (anchor) anchor.after(group);
    else form.prepend(group);
    const flag = group.querySelector("#cp-bonus-edit");
    const points = group.querySelector("#cp-bonus-points-edit");
    const status = group.querySelector(".cp-bonus-status");

    const show = (data) => {
      flag.value = data.flag || "";
      points.value = data.points || 50;
    };
    const send = async (body) => {
      try {
        const res = await fetch(url, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "CSRF-Token": init.csrfNonce },
          body: JSON.stringify(body),
        });
        const data = await res.json();
        if (!res.ok) {
          status.textContent = data.message || "Could not save bonus flag";
          return;
        }
        show(data);
        status.textContent = data.flag ? "Saved" : "No bonus flag set";
      } catch (e) {
        status.textContent = "Could not save bonus flag";
      }
    };
    group.querySelector(".cp-bonus-save").addEventListener("click", () => {
      if (!flag.value.trim()) status.textContent = "Type a bonus flag first";
      else send({ flag: flag.value, points: points.value });
    });
    group.querySelector(".cp-bonus-clear").addEventListener("click", () => send({ flag: null }));

    const res = await fetch(url, { credentials: "same-origin" });
    if (res.ok) show(await res.json());
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

  // Referral columns on the admin Users page (plugins/cyberpaw/referral.py). The data comes from
  // /admin/cyberpaw/referrals, which says whether the setting in Config -> Accounts is on.
  async function fetchReferrals() {
    try {
      const res = await fetch(`${init.urlRoot}/admin/cyberpaw/referrals`, { credentials: "same-origin" });
      return res.ok ? await res.json() : null;
    } catch (e) {
      return null;
    }
  }

  // Config -> Accounts: on/off for the referral columns. Saved by the tab's own Update button, like the
  // First solve bonus.
  async function adminReferralsSetting() {
    const form = document.querySelector("#accounts form");
    if (!form || !location.pathname.startsWith(`${init.urlRoot}/admin/config`)) return;
    const data = await fetchReferrals();
    const group = document.createElement("div");
    group.className = "form-group";
    const label = document.createElement("label");
    label.htmlFor = "cp-admin-referrals";
    label.textContent = "Referral columns on the Users page";
    const select = document.createElement("select");
    select.id = "cp-admin-referrals";
    select.name = "cyberpaw_admin_referrals";
    select.className = "form-control custom-select";
    [["true", "On"], ["false", "Off"]].forEach(([value, text]) => select.append(new Option(text, value)));
    select.value = data && data.enabled ? "true" : "false";
    const help = document.createElement("small");
    help.className = "form-text text-muted";
    help.textContent =
      "Adds \"Referred by\" (the player whose invite link they signed up with) and \"Referrals\" (invite " +
      "bonuses used out of the maximum) to Admin -> Users. Only admins see them.";
    group.append(label, select, help);
    form.querySelector("button[type=submit]").before(group);
  }

  async function userReferralColumns() {
    if (location.pathname.replace(/\/$/, "") !== `${init.urlRoot}/admin/users`) return;
    const table = document.querySelector("#teamsboard");
    if (!table) return;
    const data = await fetchReferrals();
    if (!data || !data.enabled) return;
    const headerRow = table.querySelector("thead tr");
    [["Referred by", ""], ["Referrals", `Invite bonuses used out of ${data.max}`]].forEach(([text, title]) => {
      const th = document.createElement("th");
      th.className = "text-center";
      th.title = title;
      const b = document.createElement("b");
      b.textContent = text;
      th.append(b);
      headerRow.append(th);
    });
    table.querySelectorAll("tbody tr[name]").forEach((row) => {
      const id = row.getAttribute("name");
      const by = document.createElement("td");
      by.className = "text-center";
      const referrer = data.referred_by[id];
      if (referrer) {
        const a = document.createElement("a");
        a.href = `${init.urlRoot}/admin/users/${referrer.id}`;
        a.textContent = referrer.name;
        // The row itself links to the referred player; this link goes to the referrer instead.
        a.addEventListener("click", (e) => e.stopPropagation());
        by.append(a);
      }
      const used = document.createElement("td");
      used.className = "text-center text-nowrap";
      const stats = data.referrers[id] || { used: 0, counted: 0, total: 0 };
      used.textContent = `${stats.used}/${data.max}`;
      const waiting = stats.total - stats.counted;
      used.title = `${stats.total} signed up with their link` + (waiting ? `, ${waiting} not counted yet (no solve or not confirmed)` : "");
      row.append(by, used);
    });
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
    adminReferralsSetting();
    userReferralColumns();
    submissionFilters();
    hideLanguageAndCountry();
    new MutationObserver(hideLanguageAndCountry).observe(document.body, { childList: true, subtree: true });
    setupEdit().finally(setupRelease).finally(setupBonus);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
