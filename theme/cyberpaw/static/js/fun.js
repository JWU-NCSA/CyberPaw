// CyberPaw extras for players: confetti, playful messages, rank in the navbar, First Paw badges,
// typing tagline, paw rain and a couple of easter eggs. Visual only; nothing here affects scoring.
(() => {
  const root = (window.init && window.init.urlRoot) || "";
  const loggedIn = Boolean(window.init && window.init.userId);
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const pick = (list) => list[Math.floor(Math.random() * list.length)];
  const BLUE = "#2664A2";
  const GOLD = "#F5B021";

  // ---------------------------------------------------------------- easter egg: console greeting
  console.log("%c🐾 CyberPaw", `font-size:28px;font-weight:700;color:${BLUE}`);
  console.log(
    "%cOpening dev tools already? Good instincts, wildcat.\nNo flags hiding in here though. Go hack some challenges!",
    `font-size:13px;color:${GOLD}`
  );

  // ---------------------------------------------------------------- confetti and paw rain
  function burst({ count = 140, emoji = null, duration = 2600, fromTop = false } = {}) {
    if (calm) return;
    const canvas = document.createElement("canvas");
    canvas.className = "cp-fx";
    document.body.append(canvas);
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const resize = () => {
      canvas.width = innerWidth * dpr;
      canvas.height = innerHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const colors = [BLUE, GOLD, "#0D4B89", "#ffffff", "#67c23a"];
    const parts = Array.from({ length: count }, () => ({
      x: fromTop ? Math.random() * innerWidth : innerWidth / 2 + (Math.random() - 0.5) * 120,
      y: fromTop ? -20 - Math.random() * innerHeight * 0.5 : innerHeight * 0.45,
      vx: fromTop ? (Math.random() - 0.5) * 1.5 : (Math.random() - 0.5) * 16,
      vy: fromTop ? 2 + Math.random() * 3 : -6 - Math.random() * 10,
      size: emoji ? 18 + Math.random() * 14 : 6 + Math.random() * 6,
      spin: Math.random() * Math.PI,
      vspin: (Math.random() - 0.5) * 0.3,
      color: pick(colors),
    }));
    const start = performance.now();
    const frame = (now) => {
      const t = now - start;
      ctx.clearRect(0, 0, innerWidth, innerHeight);
      ctx.globalAlpha = Math.max(0, 1 - Math.max(0, t - duration * 0.7) / (duration * 0.3));
      parts.forEach((p) => {
        p.vy += fromTop ? 0.02 : 0.32;
        p.x += p.vx;
        p.y += p.vy;
        p.spin += p.vspin;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.spin);
        if (emoji) {
          ctx.font = `${p.size}px serif`;
          ctx.fillText(emoji, -p.size / 2, p.size / 2);
        } else {
          ctx.fillStyle = p.color;
          ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
        }
        ctx.restore();
      });
      if (t < duration) requestAnimationFrame(frame);
      else canvas.remove();
    };
    requestAnimationFrame(frame);
  }
  const pawRain = () => burst({ count: 60, emoji: "🐾", duration: 4500, fromTop: true });

  // ---------------------------------------------------------------- toasts
  function toast(text) {
    const el = document.createElement("div");
    el.className = "cp-toast";
    el.setAttribute("role", "status");
    el.textContent = text;
    document.body.append(el);
    requestAnimationFrame(() => el.classList.add("show"));
    setTimeout(() => {
      el.classList.remove("show");
      setTimeout(() => el.remove(), 400);
    }, 3200);
  }

  // ---------------------------------------------------------------- flag submissions
  const NOPES = [
    "Nope. The paw slipped. 🐾",
    "Not quite, wildcat.",
    "The firewall says no.",
    "Close? Maybe. Correct? No.",
    "Access denied. Try again!",
    "That flag smells a little fishy. 🐟",
    "Hmm, the server isn't buying it.",
    "So close you can almost taste the bytes.",
  ];
  const YAYS = ["Pawsome! 🐾", "Flag captured!", "Nailed it, wildcat!", "Clean hack. Respect.", "Go Wildcats! 🐾"];

  // The challenge window can report the same response more than once; react to each one once.
  const seenResponses = new WeakSet();

  window.addEventListener("cp-flag-result", (event) => {
    const ref = event.detail && event.detail.ref;
    if (ref && typeof ref === "object") {
      if (seenResponses.has(ref)) return;
      seenResponses.add(ref);
    }
    const status = event.detail && event.detail.status;
    const alert = event.target instanceof Element ? event.target : null;
    const quip = alert && alert.querySelector(".cp-flag-quip");
    if (status === "correct") {
      if (quip) quip.textContent = pick(YAYS);
      burst();
      refreshRank(true);
    } else if (status === "incorrect") {
      if (quip) quip.textContent = pick(NOPES);
      const modal = alert && alert.closest(".modal-content, .modal-dialog, #challenge-window");
      const input = modal && modal.querySelector('input[x-model="submission"], #challenge-input');
      if (input && !calm) {
        input.classList.remove("cp-shake");
        void input.offsetWidth; // restart the animation
        input.classList.add("cp-shake");
        input.addEventListener("animationend", () => input.classList.remove("cp-shake"), { once: true });
      }
    } else if (quip) {
      quip.textContent = "";
    }
  });

  window.addEventListener("cp-category-cleared", (event) => {
    burst({ count: 260, duration: 3500 });
    setTimeout(() => burst({ count: 40, emoji: "🐾", duration: 3500 }), 400);
    const name = String(event.detail || "");
    toast(`${name.charAt(0).toUpperCase()}${name.slice(1)} cleared! Every challenge solved. 🐾`);
  });

  // ---------------------------------------------------------------- rank in the navbar
  async function refreshRank(afterSolve = false) {
    if (!loggedIn) return;
    try {
      const res = await fetch(`${root}/api/v1/users/me`, { credentials: "same-origin" });
      if (!res.ok) return;
      const { data } = await res.json();
      if (!data || data.score === undefined) return;
      let chip = document.getElementById("cp-rank");
      if (!chip) {
        const nav = document.querySelector("nav .navbar-nav.ms-md-auto, nav .navbar-nav:last-of-type");
        if (!nav) return;
        const li = document.createElement("li");
        li.className = "nav-item d-flex align-items-center";
        chip = document.createElement("a");
        chip.id = "cp-rank";
        chip.className = "cp-rank";
        chip.href = `${root}/scoreboard`;
        chip.title = "Your place and score";
        li.append(chip);
        nav.prepend(li);
      }
      const text = `${data.place ? `${data.place} · ` : ""}${Number(data.score).toLocaleString()} pts`;
      let previous = null;
      try { previous = sessionStorage.getItem("cp-rank"); } catch (e) { /* storage blocked */ }
      chip.textContent = text;
      if ((afterSolve || previous) && previous !== text) {
        chip.classList.remove("cp-bump");
        void chip.offsetWidth;
        chip.classList.add("cp-bump");
      }
      try { sessionStorage.setItem("cp-rank", text); } catch (e) { /* storage blocked */ }
    } catch (e) {
      /* rank is a nice-to-have */
    }
  }

  // ---------------------------------------------------------------- First Paw badges on profiles
  async function showFirstPaws() {
    const match = location.pathname.match(/\/users\/(\d+)\/?$/);
    const isOwn = /\/user\/?$/.test(location.pathname);
    if (!match && !isOwn) return;
    const id = match ? match[1] : window.init && window.init.userId;
    if (!id) return;
    try {
      const res = await fetch(`${root}/plugins/cyberpaw/api/first-paws?user_id=${id}`, { credentials: "same-origin" });
      if (!res.ok) return;
      const { data } = await res.json();
      if (!data || !data.length) return;
      const box = document.createElement("div");
      box.className = "cp-paw-shelf text-center";
      const title = document.createElement("div");
      title.className = "cp-paw-shelf-title";
      title.textContent = `🐾 First Paw × ${data.length}`;
      box.append(title);
      data.forEach((c) => {
        const badge = document.createElement("span");
        badge.className = "badge cp-first-paw me-1 mb-1";
        badge.textContent = c.name;
        badge.title = `First to solve ${c.name} (${c.category})`;
        box.append(badge);
      });
      const anchor = document.querySelector(".jumbotron .container") || document.querySelector("main");
      if (anchor) anchor.append(box);
    } catch (e) {
      /* optional */
    }
  }

  // ---------------------------------------------------------------- typing tagline
  function typing(el) {
    let lines;
    try { lines = JSON.parse(el.dataset.cpTyping); } catch (e) { return; }
    if (!Array.isArray(lines) || !lines.length) return;
    if (calm) { el.textContent = lines[0]; return; }
    let line = 0;
    let pos = 0;
    let deleting = false;
    const tick = () => {
      const full = lines[line];
      pos += deleting ? -1 : 1;
      el.textContent = full.slice(0, pos);
      let wait = deleting ? 35 : 70;
      if (!deleting && pos === full.length) { deleting = true; wait = 1800; }
      else if (deleting && pos === 0) { deleting = false; line = (line + 1) % lines.length; wait = 300; }
      setTimeout(tick, wait);
    };
    tick();
  }

  // ---------------------------------------------------------------- easter egg: Konami code
  const KONAMI = ["ArrowUp", "ArrowUp", "ArrowDown", "ArrowDown", "ArrowLeft", "ArrowRight", "ArrowLeft", "ArrowRight", "b", "a"];
  let progress = 0;
  document.addEventListener("keydown", (e) => {
    const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    progress = key === KONAMI[progress] ? progress + 1 : key === KONAMI[0] ? 1 : 0;
    if (progress === KONAMI.length) {
      progress = 0;
      pawRain();
      toast("↑↑↓↓←→←→BA · Old-school wildcat detected. 🐾");
    }
  });

  // ---------------------------------------------------------------- message of the day
  // Players must accept the rules once per MOTD version (theme/motd.html, injected by
  // apply-config.sh). Not shown on the rules pages themselves so they can be read first.
  function showMotd() {
    const template = document.getElementById("cp-motd");
    if (!loggedIn || !template) return;
    if (/\/(rules|privacy-notice|how-to-play)\/?$/.test(location.pathname)) return;
    const key = `cp-motd-${window.init.userId}`;
    const version = template.dataset.version || "1";
    try { if (localStorage.getItem(key) === version) return; } catch (e) { /* storage blocked */ }

    const backdrop = document.createElement("div");
    backdrop.className = "cp-motd-backdrop";
    const dialog = document.createElement("div");
    dialog.className = "cp-motd";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.append(template.content.cloneNode(true));
    const button = document.createElement("button");
    button.className = "btn btn-primary w-100 mt-3";
    button.textContent = "I understand and agree";
    button.addEventListener("click", () => {
      try { localStorage.setItem(key, version); } catch (e) { /* storage blocked */ }
      backdrop.remove();
    });
    dialog.append(button);
    backdrop.append(dialog);
    document.body.append(backdrop);
    button.focus();
  }

  // ---------------------------------------------------------------- home page
  // Guests see Register / Log in; players see their invite link (templates/page.html puts it after the page
  // HTML, so it is moved into the home block here). Register is hidden
  // when the navbar has no Register link (registration closed). The page HTML is sanitized (no "hidden"
  // attribute), so fun.css hides the guest block until it gets the cp-show class.
  function homeActions() {
    const invite = document.querySelector("#cp-referral[hidden]");
    const home = document.querySelector(".cp-home");
    if (invite && home) {
      home.append(invite);
      invite.hidden = false;
    }
    if (loggedIn) return;
    document.querySelectorAll("[data-cp-guest]").forEach((el) => el.classList.add("cp-show"));
    if (!document.querySelector('nav a[href$="/register"]')) {
      document.querySelectorAll("[data-cp-register]").forEach((el) => el.remove());
    }
    document.querySelectorAll(".cp-home-actions a[href^='/']").forEach((a) => {
      a.setAttribute("href", root + a.getAttribute("href"));
    });
  }

  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  // Competition status from the start and end times in the admin config: a ticking countdown to the start
  // or the end, or "Competition ended". Once it has started with no end time set, the card is removed.
  function competitionStatus() {
    const box = document.querySelector("[data-cp-status]");
    if (!box) return;
    const start = Number(window.init && window.init.start) || 0;
    const end = Number(window.init && window.init.end) || 0;
    const label = el("div", "cp-countdown-label");
    const units = ["Days", "Hours", "Minutes", "Seconds"].map((name) => {
      const unit = el("div", "cp-unit");
      const value = el("div", "cp-unit-value", "00");
      unit.append(value, el("div", "cp-unit-name", name));
      return { unit, value };
    });
    const clock = el("div", "cp-clock");
    units.forEach(({ unit }) => clock.append(unit));
    const panel = el("div", "cp-countdown");
    panel.append(label, clock);
    box.replaceChildren(panel);

    let timer = null;
    let counting = false; // counted down to the start on this page view
    const render = () => {
      const now = Date.now() / 1000;
      let target = 0;
      // The countdown page on /challenges (templates/countdown.html) reloads into the challenges at the start.
      if (counting && now >= start && box.hasAttribute("data-cp-reload")) {
        clearInterval(timer);
        window.location.reload();
        return;
      }
      if (start && now < start) {
        panel.dataset.state = "soon";
        counting = true;
        label.textContent = "Competition starts in";
        target = start;
      } else if (end && now < end) {
        panel.dataset.state = "live";
        label.replaceChildren(el("span", "cp-live-dot"), document.createTextNode("Live now · ends in"));
        target = end;
      } else {
        if (timer) clearInterval(timer);
        // Started with no end time: no card at all.
        if (!end) {
          box.remove();
          return;
        }
        panel.dataset.state = "over";
        label.replaceChildren(document.createTextNode("Competition ended. Thanks for playing! 🐾"));
        clock.hidden = true;
        return;
      }
      clock.hidden = false;
      let left = Math.max(0, Math.floor(target - now));
      const parts = [Math.floor(left / 86400), Math.floor((left % 86400) / 3600), Math.floor((left % 3600) / 60), left % 60];
      units.forEach(({ value }, i) => {
        const text = String(parts[i]).padStart(2, "0");
        if (value.textContent !== text) {
          value.textContent = text;
          if (!calm) {
            value.classList.remove("cp-tick");
            void value.offsetWidth;
            value.classList.add("cp-tick");
          }
        }
      });
      // Hide the days box once it is down to 0.
      units[0].unit.hidden = parts[0] === 0;
    };
    render();
    if (start || end) timer = setInterval(render, 1000);
  }

  // ---------------------------------------------------------------- email confirmation, one tab
  // The confirm link in the email opens a new tab. The tab that was waiting on /confirm marks itself;
  // when the new tab arrives confirmed, it tells the waiting tab (storage event), which moves on to
  // the challenges, and then the new tab closes itself if the browser allows it. If the link was opened
  // in another browser or on a phone, the waiting tab notices by checking /confirm every few seconds.
  const WAITING = "cp-awaiting-confirm";
  const CONFIRMED = "cp-confirmed";
  const goToChallenges = () => (window.location.href = root + "/challenges");

  function oneTabConfirm() {
    if (!loggedIn) return;
    const store = (() => { try { return window.localStorage; } catch (e) { return null; } })();
    if (window.location.pathname === root + "/confirm") {
      if (store) {
        try { store.setItem(WAITING, String(Date.now())); } catch (e) { /* storage blocked */ }
        window.addEventListener("storage", (e) => {
          if (e.key === CONFIRMED && e.newValue) goToChallenges();
        });
      }
      // A verified account gets redirected away from /confirm.
      setInterval(async () => {
        try {
          const res = await fetch(root + "/confirm", { credentials: "same-origin", redirect: "manual" });
          if (res.type === "opaqueredirect") goToChallenges();
        } catch (e) { /* offline, try again */ }
      }, 5000);
      return;
    }
    if (!store || !window.init.userVerified) return;
    let waiting = null;
    try { waiting = store.getItem(WAITING); } catch (e) { return; }
    if (!waiting) return;
    try {
      store.removeItem(WAITING);
      store.setItem(CONFIRMED, String(Date.now()));
      store.removeItem(CONFIRMED);
    } catch (e) { /* storage blocked */ }
    // Only an hour-old waiting tab could still be open; older marks are just cleared.
    if (Date.now() - Number(waiting) > 3600 * 1000) return;
    window.close();
    setTimeout(() => toast("Email confirmed! 🐾 You can close your other CyberPaw tab."), 300);
  }

  // ---------------------------------------------------------------- hints
  // The platform's "unlock this hint?" popup doesn't open in this theme, so hints are unlocked here. Free hints
  // (cost 0) open straight away; paid hints ask first. Used by templates/challenge.html as x-data="cpHint(id, cost)".
  window.cpHint = (id, cost) => ({
    html: null,
    error: "",
    async toggle(event) {
      const details = event.target;
      if (!details.open || this.html) return;
      this.error = "";
      const headers = { "Content-Type": "application/json", "CSRF-Token": window.init.csrfNonce };
      const getHint = async () => (await (await fetch(`${root}/api/v1/hints/${id}`, { credentials: "same-origin" })).json()).data || {};
      try {
        let hint = await getHint();
        if (!hint.content) {
          if (cost > 0 && !window.confirm(`Unlock this hint for ${cost} point${cost === 1 ? "" : "s"}?`)) {
            details.open = false;
            return;
          }
          const res = await fetch(`${root}/api/v1/unlocks`, {
            method: "POST",
            credentials: "same-origin",
            headers,
            body: JSON.stringify({ target: id, type: "hints" }),
          });
          const json = await res.json().catch(() => ({}));
          if (!res.ok || !json.success) {
            const errors = json.errors ? Object.values(json.errors).flat() : [];
            this.error = errors[0] || json.message || "Couldn't open this hint.";
            return;
          }
          hint = await getHint();
        }
        this.html = hint.html || "";
      } catch (e) {
        this.error = "Couldn't open this hint. Try again.";
      }
    },
  });

  // ---------------------------------------------------------------- profile settings
  // Avatar, bio, GitHub and LinkedIn are stored by the cyberpaw plugin, not the platform, so they are saved
  // with their own request when the settings form is submitted.
  function profileSettings() {
    const box = document.querySelector("[data-cp-profile-form]");
    if (!box) return;
    const form = box.closest("form");
    const save = async (body) => {
      const res = await fetch(`${root}/plugins/cyberpaw/api/profile`, {
        method: "PATCH",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "CSRF-Token": window.init.csrfNonce },
        body: JSON.stringify(body),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        const errors = (json.errors && json.errors.profile) || ["Couldn't save your profile. Try again."];
        throw new Error(errors[0]);
      }
      return json.data;
    };
    const showError = (message) => {
      const alert = el("div", "alert alert-danger", message);
      document.getElementById("results").prepend(alert);
      setTimeout(() => alert.remove(), 6000);
    };
    document.getElementById("cp-new-avatar").addEventListener("click", async () => {
      try {
        const data = await save({ new_avatar: true });
        document.getElementById("cp-avatar-preview").src = root + data.avatar_url;
      } catch (e) {
        showError(e.message);
      }
    });
    form.addEventListener("submit", async () => {
      try {
        await save({
          bio: document.getElementById("cp-bio").value,
          github: document.getElementById("cp-github").value,
          linkedin: document.getElementById("cp-linkedin").value,
        });
      } catch (e) {
        showError(e.message);
      }
    });
  }

  // ---------------------------------------------------------------- referral link copy button
  function referralCopy() {
    const button = document.getElementById("cp-referral-copy");
    if (!button) return;
    const input = document.getElementById("cp-referral-link");
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(input.value);
      } catch (e) {
        input.select();
        document.execCommand("copy");
      }
      button.innerHTML = '<i class="fas fa-check"></i> Copied';
      setTimeout(() => (button.innerHTML = '<i class="fas fa-copy"></i> Copy'), 2000);
    });
  }

  // ---------------------------------------------------------------- solve card and share buttons
  // After a solve, the challenge window shows a square "challenge solved" image to share, like the
  // certificates on Hack The Box. It is drawn on a canvas from the data-* attributes of [data-cp-solve]
  // (templates/challenge.html), shown in the panel and used by the Download and Instagram buttons. The
  // panel is created later by the challenge window, so everything here listens on the document.
  const CARD_SIZE = 1080;
  const cards = new WeakMap(); // [data-cp-solve] element -> Promise of the PNG blob

  function loadImage(src) {
    return new Promise((resolve) => {
      if (!src) return resolve(null);
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = src;
    });
  }

  // The largest font size (down to `min`) at which `text` fits in `maxLines` lines. If it still doesn't fit,
  // lines that are too wide and the last line (when text is left over) end in an ellipsis.
  function fitLines(ctx, text, font, maxWidth, maxLines, max, min) {
    let size = max;
    let lines = [];
    for (; size >= min; size -= 4) {
      ctx.font = font(size);
      lines = [];
      let line = "";
      for (const word of text.split(/\s+/)) {
        const next = line ? line + " " + word : word;
        if (line && ctx.measureText(next).width > maxWidth) {
          lines.push(line);
          line = word;
        } else {
          line = next;
        }
      }
      lines.push(line);
      if (lines.length <= maxLines && lines.every((l) => ctx.measureText(l).width <= maxWidth)) return { size, lines };
    }
    size = min;
    ctx.font = font(size);
    const more = lines.length > maxLines;
    lines = lines.slice(0, maxLines).map((line, i) => {
      if (!(more && i === maxLines - 1) && ctx.measureText(line).width <= maxWidth) return line;
      while (line && ctx.measureText(line + "…").width > maxWidth) line = line.slice(0, -1);
      return line + "…";
    });
    return { size, lines };
  }

  function paw(ctx, x, y, scale, angle) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle);
    ctx.scale(scale, scale);
    ctx.beginPath();
    ctx.ellipse(0, 18, 30, 25, 0, 0, Math.PI * 2);
    [[-34, -14, -0.4], [-13, -34, -0.15], [13, -34, 0.15], [34, -14, 0.4]].forEach(([tx, ty, r]) => {
      ctx.moveTo(tx + 11, ty);
      ctx.ellipse(tx, ty, 11, 15, r, 0, Math.PI * 2);
    });
    ctx.fill();
    ctx.restore();
  }

  async function drawSolveCard(data) {
    const S = CARD_SIZE;
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = S;
    const ctx = canvas.getContext("2d");
    const css = getComputedStyle(document.documentElement);
    const blue = css.getPropertyValue("--cp-blue").trim() || "#2664A2";
    const dark = css.getPropertyValue("--cp-blue-dark").trim() || "#0D4B89";
    const family = getComputedStyle(document.body).fontFamily || "sans-serif";
    const font = (weight) => (size) => `${weight} ${size}px ${family}`;
    const logo = await loadImage(data.logo);

    // Blue background with faint binary and paw prints, white header with the logo.
    const bg = ctx.createLinearGradient(0, 0, S, S);
    bg.addColorStop(0, blue);
    bg.addColorStop(1, dark);
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, S, S);
    ctx.fillStyle = "rgba(255, 255, 255, 0.035)";
    ctx.font = `600 22px ui-monospace, monospace`;
    for (let row = 0, y = 330; y < S; row++, y += 34) {
      let bits = "";
      for (let i = 0; i < 80; i++) bits += (i * 7 + row * 13 + ((i * row) % 5)) % 3 ? "1" : "0";
      ctx.fillText(bits, -((row * 17) % 40), y);
    }
    ctx.fillStyle = "rgba(255, 255, 255, 0.07)";
    paw(ctx, 140, 980, 1.6, -0.5);
    paw(ctx, 950, 430, 1.3, 0.45);
    paw(ctx, 980, 900, 0.9, 0.2);

    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, S, 280);
    if (logo) {
      const h = 200;
      const w = (logo.width / logo.height) * h;
      ctx.drawImage(logo, (S - w) / 2, 40, w, h);
    } else {
      ctx.fillStyle = blue;
      ctx.textAlign = "center";
      ctx.font = font(800)(90);
      ctx.fillText(data.ctf, S / 2, 175);
    }

    // Check mark badge and "challenge solved".
    ctx.textAlign = "center";
    ctx.fillStyle = "#fff";
    ctx.beginPath();
    ctx.arc(S / 2, 370, 46, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = blue;
    ctx.lineWidth = 12;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(S / 2 - 22, 372);
    ctx.lineTo(S / 2 - 6, 388);
    ctx.lineTo(S / 2 + 24, 354);
    ctx.stroke();
    ctx.fillStyle = "rgba(255, 255, 255, 0.85)";
    ctx.font = font(700)(34);
    if ("letterSpacing" in ctx) ctx.letterSpacing = "8px";
    ctx.fillText("CHALLENGE SOLVED", S / 2 + 4, 470);
    if ("letterSpacing" in ctx) ctx.letterSpacing = "0px";

    // Challenge name, category and points, and the player, stacked and centered between the heading
    // and the footer.
    const pill = [data.category, data.points ? `${data.points} pts` : ""].filter(Boolean).join("  ·  ");
    const who = data.player && fitLines(ctx, data.player, font(700), 860, 1, 48, 30);
    const rest = (pill ? 40 + 60 : 0) + (who ? 56 + 34 + 10 + who.size : 0);
    // Shrink the title until the whole stack fits.
    let title;
    for (let max = 96; ; max -= 4) {
      title = fitLines(ctx, data.challenge, font(800), 900, 3, max, 44);
      if (max <= 44 || title.lines.length * Math.round(title.size * 1.15) + rest <= 980 - 510) break;
    }
    const lineHeight = Math.round(title.size * 1.15);
    const height = title.lines.length * lineHeight + rest;
    let y = 510 + Math.max(0, (980 - 510 - height) / 2);
    ctx.textBaseline = "top";
    ctx.fillStyle = "#fff";
    ctx.font = font(800)(title.size);
    title.lines.forEach((line) => {
      ctx.fillText(line, S / 2, y + (lineHeight - title.size) / 2);
      y += lineHeight;
    });
    if (pill) {
      y += 40;
      ctx.font = font(600)(32);
      const w = ctx.measureText(pill).width + 64;
      ctx.fillStyle = "rgba(255, 255, 255, 0.16)";
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect((S - w) / 2, y, w, 60, 30);
      else ctx.rect((S - w) / 2, y, w, 60);
      ctx.fill();
      ctx.fillStyle = "#fff";
      ctx.fillText(pill, S / 2, y + 13);
      y += 60;
    }
    if (who) {
      y += 56;
      ctx.fillStyle = "rgba(255, 255, 255, 0.75)";
      ctx.font = font(500)(34);
      ctx.fillText("Solved by", S / 2, y);
      y += 34 + 10;
      ctx.fillStyle = "#fff";
      ctx.font = font(700)(who.size);
      ctx.fillText(who.lines[0], S / 2, y);
    }
    ctx.textBaseline = "alphabetic";

    // Footer.
    ctx.fillStyle = "rgba(255, 255, 255, 0.65)";
    ctx.font = font(500)(26);
    const date = new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
    ctx.fillText([data.ctf, data.site, date].filter(Boolean).join("  ·  "), S / 2, 1035);

    return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
  }

  function solveCard(section) {
    if (!cards.has(section)) cards.set(section, drawSolveCard({ ...section.dataset }));
    return cards.get(section);
  }

  function cardFileName(section) {
    const slug = (section.dataset.challenge || "challenge").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    return `cyberpaw-${slug || "challenge"}.png`;
  }

  function downloadCard(blob, name) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
  }

  function solvePanel() {
    window.addEventListener("cp-flag-result", async (event) => {
      const status = event.detail && event.detail.status;
      if (status !== "correct" && status !== "already_solved") return;
      const section = event.target instanceof Element && event.target.querySelector("[data-cp-solve]");
      if (!section) return;
      const img = section.querySelector(".cp-solve-card");
      if (!img || !img.hidden) return;
      const blob = await solveCard(section);
      if (!blob) return;
      img.src = URL.createObjectURL(blob);
      img.hidden = false;
    });

    document.addEventListener("click", async (event) => {
      const download = event.target.closest("[data-cp-card-download]");
      const instagram = event.target.closest("[data-cp-instagram]");
      if (!download && !instagram) return;
      const section = event.target.closest("[data-cp-solve]");
      if (!section) return;
      const blob = await solveCard(section);
      const name = cardFileName(section);
      if (download) {
        if (blob) downloadCard(blob, name);
        return;
      }

      // Instagram has no web share link. Phones get the system share sheet with the image and caption
      // (Instagram is listed there); elsewhere the image is downloaded, the caption copied and Instagram
      // opened in a new tab.
      const caption = instagram.dataset.cpInstagram;
      const file = blob && new File([blob], name, { type: "image/png" });
      if (matchMedia("(pointer: coarse)").matches && navigator.share) {
        const shareData = file && navigator.canShare && navigator.canShare({ files: [file] })
          ? { files: [file], text: caption }
          : { text: caption };
        try {
          await navigator.share(shareData);
          return;
        } catch (e) {
          if (e.name === "AbortError") return;
        }
      }
      // Copy before opening the tab: the clipboard only works while this page has focus.
      try {
        await navigator.clipboard.writeText(caption);
        toast(blob ? "Image saved and caption copied. Post them on Instagram." : "Caption copied. Paste it into your Instagram post.");
      } catch (e) {
        toast(caption);
      }
      if (blob) downloadCard(blob, name);
      window.open("https://www.instagram.com/", "_blank", "noopener");
    });
  }

  const start = () => {
    profileSettings();
    referralCopy();
    solvePanel();
    oneTabConfirm();
    showMotd();
    homeActions();
    competitionStatus();
    document.querySelectorAll("[data-cp-typing]").forEach(typing);
    refreshRank();
    showFirstPaws();
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
