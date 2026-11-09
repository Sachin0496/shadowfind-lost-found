/* ShadowFind static build - application.
 * Same screens and workflow as the Flask app, with vision and storage running
 * in the browser so GitHub Pages can serve it as a plain static site.
 */

import { loadOpenCV, opencvAvailable, extract, rank, overlayDataURL, similarity }
  from "./vision.js";
import * as store from "./store.js";

const app = document.getElementById("app");
const flash = document.getElementById("flash");
const navLinks = document.getElementById("navlinks");
const navRight = document.getElementById("navright");
const engine = document.getElementById("engine");

const esc = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : "");
const day = (iso) => (iso || "").slice(0, 10);
const sc = (n) => Number(n || 0).toFixed(2);
const badge = (t) => `<span class="badge ${esc(t)}">${esc(cap(t))}</span>`;
const pic = (src) => (src ? `<img src="${esc(src)}" alt="" loading="lazy">` : "");

function toast(msg, kind = "info") {
  flash.innerHTML = `<div class="flash ${kind}">${esc(msg)}</div>`;
  flash.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function chrome() {
  const me = store.currentStudent();
  navLinks.innerHTML = `
    ${me ? `<a href="#/dashboard">Dashboard</a>
            <a href="#/report">Report Item</a>
            <a href="#/claims">Claims</a>` : ""}
    <a href="#/browse">Browse</a>`;
  navRight.innerHTML = me
    ? `<span class="who">${esc(me.name)} &middot; ${esc(me.department)}</span>
       <a class="btn sm light" href="#/logout">Logout</a>`
    : `<a class="btn sm light" href="#/login">Log in</a>
       <a class="btn sm" href="#/register" style="background:#fff;color:#1F3A6E">Register</a>`;
  engine.innerHTML = opencvAvailable()
    ? "shadow extraction: <b>OpenCV.js</b>, running in your browser"
    : "shadow extraction: <b>JS fallback</b> (OpenCV.js could not load)";
}

const head = (t, sub) => `<div class="page-head"><h1>${esc(t)}</h1><p>${sub}</p></div>`;

const needLogin = () => {
  if (store.currentStudent()) return true;
  toast("Please log in to continue.", "warning");
  location.hash = "#/login";
  return false;
};

/* ---------------------------------------------------------------- */
function viewIndex() {
  const st = store.stats();
  const recent = store.listItems({ limit: 6 });
  const me = store.currentStudent();

  app.innerHTML = `
  <div class="hero">
    <div>
      <h1>Find your lost item by the shape of its shadow.</h1>
      <p>Photograph a lost or found item once. ShadowFind extracts its cast shadow,
         describes the outline in 64 numbers, and ranks the reports that match it &mdash;
         so a blue bag is compared with another blue bag by shape, not by two people's
         descriptions of it.</p>
      <div class="cta">
        <a class="btn" href="#${me ? "/report" : "/register"}">Report an item</a>
        <a class="btn light" href="#/browse">Browse reports</a>
      </div>
    </div>
    <div class="hero-art">
      <svg viewBox="0 0 260 190" fill="none">
        <rect x="20" y="20" width="150" height="110" rx="10" fill="#ffffff18" stroke="#ffffff55"/>
        <circle cx="78" cy="60" r="24" fill="#fff" opacity=".92"/>
        <rect x="56" y="72" width="44" height="34" rx="4" fill="#fff" opacity=".92"/>
        <ellipse cx="172" cy="150" rx="66" ry="16" fill="#000" opacity=".22"/>
        <path d="M78 118 L150 150 L188 146 L110 108 Z" fill="#7fa8cc" opacity=".65"/>
      </svg>
    </div>
  </div>

  <div class="stats">
    <div class="stat"><div class="n">${st.lost}</div><div class="k">Lost items reported</div></div>
    <div class="stat"><div class="n">${st.found}</div><div class="k">Found items reported</div></div>
    <div class="stat"><div class="n">${st.returned}</div><div class="k">Confirmed returns</div></div>
  </div>

  <div class="card">
    <div class="card-head">
      <div><h2>Recently reported</h2><div class="sub">Newest lost and found items on campus</div></div>
      <a class="btn ghost sm" href="#/browse">Browse all</a>
    </div>
    ${recent.length ? `<div class="card-body tight"><table>
      <thead><tr><th></th><th>Item</th><th>Type</th><th>Category</th><th>Reported by</th><th>When</th></tr></thead>
      <tbody>${recent.map((it) => {
        const s = store.studentOf(it.student_id);
        return `<tr>
          <td class="thumb">${pic(it.photo)}</td>
          <td class="title-cell"><a href="#/item/${it.id}">${esc(it.title)}</a></td>
          <td>${badge(it.type)}</td>
          <td>${esc(it.category)}</td>
          <td>${esc(s.name)} <span class="muted">&middot; ${esc(s.department)}</span></td>
          <td class="muted">${day(it.created_at)}</td></tr>`;
      }).join("")}</tbody></table></div>`
      : `<div class="empty">No items reported yet.</div>`}
  </div>

  <h2 style="font-size:16px;margin:26px 0 12px">How it works</h2>
  <div class="steps">
    <div class="step"><div class="n">1</div><h3>Photograph the item</h3>
      <p>One photo on any surface. The cast shadow is what matters, so daylight works best.</p></div>
    <div class="step"><div class="n">2</div><h3>Silhouette to 64 numbers</h3>
      <p>The dark region is isolated in your browser and described as a compact shape vector.</p></div>
    <div class="step"><div class="n">3</div><h3>Ranked candidates</h3>
      <p>Cosine similarity ranks found reports. You send a claim; the finder approves it.</p></div>
  </div>`;
}

/* ---------------------------------------------------------------- */
function viewBrowse(params) {
  const me = store.currentStudent();
  const type = params.get("type");
  const cat = params.get("category");
  const items = store.listItems({ excludeStudent: me ? me.id : null, type, category: cat });

  const href = (o) => {
    const p = new URLSearchParams();
    if (o.type) p.set("type", o.type);
    if (o.category) p.set("category", o.category);
    const q = p.toString();
    return "#/browse" + (q ? "?" + q : "");
  };
  const chip = (label, h, on) => `<a class="chip ${on ? "on" : ""}" href="${h}">${esc(label)}</a>`;

  app.innerHTML = `
  ${head("Browse items", `${items.length} report${items.length === 1 ? "" : "s"}${me ? " from other students" : ""}.`)}
  <div class="card"><div class="card-body"><div class="filters">
    ${chip("All", href({ category: cat }), !type)}
    ${chip("Lost", href({ type: "lost", category: cat }), type === "lost")}
    ${chip("Found", href({ type: "found", category: cat }), type === "found")}
    <span style="width:14px"></span>
    ${chip("Any category", href({ type }), !cat)}
    ${store.CATEGORIES.map((c) => chip(c, href({ type, category: c }), cat === c)).join("")}
  </div></div></div>
  ${items.length ? `<div class="grid-cards">${items.map((it) => {
    const s = store.studentOf(it.student_id);
    return `<article class="item-card">
      <div class="ph">${pic(it.photo)}</div>
      <div class="meta">
        <div class="row">${badge(it.type)}<span class="line">${esc(it.category)}</span></div>
        <h3><a href="#/item/${it.id}">${esc(it.title)}</a></h3>
        <div class="line">${esc(it.place || "Place not given")} &middot; ${esc(s.name)} (${esc(s.department)})</div>
      </div></article>`;
  }).join("")}</div>`
  : `<div class="card"><div class="empty">Nothing here yet. Try clearing the filters.</div></div>`}`;
}

/* ---------------------------------------------------------------- */
function viewItem(id) {
  const item = store.getItem(id);
  if (!item) {
    app.innerHTML = `<div class="card" style="margin-top:30px"><div class="empty">
      <h2 style="margin:0 0 6px">Item not found</h2><a href="#/browse">Back to browse</a></div></div>`;
    return;
  }
  const me = store.currentStudent();
  const mine = !!(me && me.id === item.student_id);
  const owner = store.studentOf(item.student_id);

  let ranked = [];
  if (item.descriptor) {
    const cands = store.candidatesFor(item).filter((c) => c.descriptor);
    ranked = rank(item.descriptor, cands.map((c) => ({ id: c.id, descriptor: c.descriptor })))
      .slice(0, 10)
      .map((r) => ({ item: store.getItem(r.id), score: r.score }));
  }

  app.innerHTML = `
  <div class="page-head">
    <p style="margin-bottom:6px"><a href="#/browse">&larr; Back to browse</a></p>
    <h1>${esc(item.title)}</h1>
    <p>${badge(item.type)} &middot; ${esc(item.category)} &middot; reported by ${esc(owner.name)} (${esc(owner.department)})</p>
  </div>
  <div class="split">
    <div class="card"><div class="card-body">
      <div class="photo-frame">${pic(item.photo)}</div>
      <dl class="dl">
        <div><dt>Type</dt><dd>${badge(item.type)}</dd></div>
        <div><dt>Category</dt><dd>${esc(item.category)}</dd></div>
        <div><dt>Reported</dt><dd>${day(item.created_at)}</dd></div>
        <div><dt>Place</dt><dd>${esc(item.place || "-")}</dd></div>
        <div><dt>Date seen</dt><dd>${esc(item.seen_on || "-")}</dd></div>
        <div><dt>Department</dt><dd>${esc(owner.department)}</dd></div>
      </dl>
      ${item.description ? `<p class="desc">${esc(item.description)}</p>` : ""}
      <div class="sig-note">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style="flex:none;margin-top:1px">
          <circle cx="11" cy="9" r="6" stroke="#084298" stroke-width="2"/>
          <ellipse cx="12" cy="19" rx="8" ry="2.4" stroke="#084298" stroke-width="2"/>
        </svg>
        <div>Shadow silhouette extracted &mdash; IoU ${sc(item.shadow_iou)}, 64-value descriptor stored.
        ${item.overlay ? `<div style="margin-top:6px">
          <a class="btn ghost sm" href="${esc(item.overlay)}" target="_blank" rel="noopener">View detected shadow</a>
        </div>` : ""}</div>
      </div>
    </div></div>

    <div>
      <div class="card">
        <div class="card-head"><div><h2>Ranked candidates</h2>
          <div class="sub">Same category, opposite type, ordered by silhouette similarity</div></div></div>
        ${ranked.length ? ranked.map((r) => {
          const rs = store.studentOf(r.item.student_id);
          const lostId = item.type === "lost" ? item.id : r.item.id;
          const foundId = item.type === "lost" ? r.item.id : item.id;
          return `<div class="match">
            <img class="t" src="${esc(r.item.photo)}" alt="">
            <div class="info">
              <div class="nm"><a href="#/item/${r.item.id}">${esc(r.item.title)}</a></div>
              <div class="mt">${cap(r.item.type)} ${day(r.item.created_at)} &middot;
                 ${esc(r.item.place || "place unknown")} &middot; ${esc(rs.name)}</div>
              <div class="bar ${r.score >= 0.8 ? "strong" : ""}"><i style="width:${Math.round(r.score * 100)}%"></i></div>
            </div>
            <div class="score">${sc(r.score)}<small>similar</small></div>
            ${me && !mine ? `<button class="btn sm" data-claim="${lostId}:${foundId}">Send claim</button>` : ""}
          </div>`;
        }).join("")
        : `<div class="empty">No comparable reports yet.
             ${mine ? "As items of the opposite type are reported, candidates will appear here." : ""}</div>`}
        <div style="padding:12px 14px;color:#6c757d;font-size:12.5px;border-top:1px solid var(--line-soft)">
          Scores at or above 0.80 are shown in green. The owner confirms one candidate before a claim is sent.
        </div>
      </div>
      ${mine ? `<div class="card"><div class="card-body" style="color:#6c757d;font-size:13.5px">
        This is your own report. You cannot send a claim on it.</div></div>` : ""}
    </div>
  </div>`;

  app.querySelectorAll("[data-claim]").forEach((b) => {
    b.addEventListener("click", () => {
      if (!needLogin()) return;
      const [lostId, foundId] = b.dataset.claim.split(":").map(Number);
      const lost = store.getItem(lostId), found = store.getItem(foundId);
      if (!lost || !found) return;
      if (lost.student_id === found.student_id) {
        return toast("You cannot claim your own report.", "warning");
      }
      const m = store.saveMatch(lostId, foundId, similarity(lost.descriptor, found.descriptor));
      const { created } = store.createClaim(m.id, lost.student_id, found.student_id);
      toast(created ? "Claim sent to the finder." : "You already have an open claim on this item.",
            created ? "success" : "info");
      location.hash = "#/claims";
    });
  });
}

/* ---------------------------------------------------------------- */
function viewLogin() {
  app.innerHTML = `
  <div class="auth"><div class="card"><div class="card-body">
    <h1>ShadowFind</h1>
    <p class="sub">Lost and Found Item Matching Portal</p>
    <form id="f">
      <div class="field"><label for="email">College Email</label>
        <input id="email" name="email" type="email" required placeholder="you@college.edu"></div>
      <div class="field"><label for="password">Password</label>
        <input id="password" name="password" type="password" required></div>
      <button class="btn wide" type="submit">Sign In</button>
    </form>
    <div class="foot">Don't have an account? <a href="#/register">Register here</a></div>
    <div class="demo"><strong style="color:#444">Demo accounts</strong> (password
      <code>${store.DEMO_PASSWORD}</code>):<br>
      <code>ananya@college.edu</code> &middot; <code>rahul@college.edu</code> &middot;
      <code>priya@college.edu</code>
      <div style="margin-top:6px"><a href="#" id="fill">fill a demo account</a></div>
    </div>
  </div></div></div>`;

  app.querySelector("#fill").addEventListener("click", (e) => {
    e.preventDefault();
    app.querySelector("#email").value = "ananya@college.edu";
    app.querySelector("#password").value = store.DEMO_PASSWORD;
  });
  app.querySelector("#f").addEventListener("submit", (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const st = store.verify(fd.get("email"), fd.get("password"));
    if (!st) return toast("Wrong e-mail address or password.", "danger");
    store.login(st.id);
    toast(`Signed in as ${st.name}.`, "success");
    location.hash = "#/dashboard";
  });
}

function viewRegister() {
  app.innerHTML = `
  <div class="auth"><div class="card"><div class="card-body">
    <h1>Create an account</h1><p class="sub">Use your college e-mail address.</p>
    <form id="f">
      <div class="field"><label for="name">Full name</label><input id="name" name="name" required></div>
      <div class="field"><label for="email">College email</label>
        <input id="email" name="email" type="email" required placeholder="you@college.edu"></div>
      <div class="grid2">
        <div class="field"><label for="department">Department</label>
          <select id="department" name="department">${store.DEPARTMENTS.map((d) => `<option>${d}</option>`).join("")}</select></div>
        <div class="field"><label for="password">Password</label>
          <input id="password" name="password" type="password" required minlength="6">
          <div class="hint">At least 6 characters.</div></div>
      </div>
      <button class="btn wide" type="submit">Create account</button>
    </form>
    <div class="foot">Already registered? <a href="#/login">Sign in</a></div>
  </div></div></div>`;

  app.querySelector("#f").addEventListener("submit", (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    if (String(fd.get("password")).length < 6) return toast("Password must be at least 6 characters.", "danger");
    const r = store.createStudent({
      name: fd.get("name"), email: fd.get("email"),
      password: fd.get("password"), department: fd.get("department"),
    });
    if (r.error) return toast(r.error, "danger");
    store.login(r.student.id);
    toast("Account created. Welcome to ShadowFind.", "success");
    location.hash = "#/dashboard";
  });
}

/* ---------------------------------------------------------------- */
function claimButtons() {
  app.querySelectorAll("[data-act]").forEach((b) => {
    b.addEventListener("click", () => {
      const [action, id] = b.dataset.act.split(":");
      const status = { accept: "accepted", reject: "rejected", return: "returned" }[action];
      store.setClaimStatus(Number(id), status);
      toast({ accepted: "Claim accepted.", rejected: "Claim rejected.",
              returned: "Handover confirmed. The item is marked returned." }[status], "success");
      render();
    });
  });
}

function viewDashboard() {
  if (!needLogin()) return;
  const me = store.currentStudent();
  const mine = store.itemsOf(me.id);
  const st = store.stats();
  const incoming = store.claimsIncoming(me.id).slice(0, 5);

  app.innerHTML = `
  ${head("Student Dashboard", `Signed in as ${esc(me.name)} (${esc(me.department)})`)}
  <div class="stats">
    <div class="stat"><div class="n">${st.lost}</div><div class="k">Lost items on campus</div></div>
    <div class="stat"><div class="n">${st.found}</div><div class="k">Found items on campus</div></div>
    <div class="stat"><div class="n">${st.returned}</div><div class="k">Confirmed returns</div></div>
  </div>
  <div class="card">
    <div class="card-head"><div><h2>My reports</h2><div class="sub">Items you have reported</div></div>
      <a class="btn sm" href="#/report">Report an item</a></div>
    ${mine.length ? `<div class="card-body tight"><table>
      <thead><tr><th></th><th>Item</th><th>Type</th><th>Reported on</th><th>Shadow signature</th></tr></thead>
      <tbody>${mine.map((it) => `<tr>
        <td class="thumb">${pic(it.photo)}</td>
        <td class="title-cell"><a href="#/item/${it.id}">${esc(it.title)}</a></td>
        <td>${badge(it.type)}</td><td class="muted">${day(it.created_at)}</td>
        <td>${it.shadow_iou > 0
          ? `<span class="badge neutral">IoU ${sc(it.shadow_iou)}</span>`
          : `<span class="badge neutral">Not available</span>`}</td></tr>`).join("")}
      </tbody></table></div>`
      : `<div class="empty">You have not reported anything yet.
           <a href="#/report">Report a lost or found item</a>.</div>`}
  </div>
  <div class="card">
    <div class="card-head"><div><h2>Incoming claims</h2>
      <div class="sub">Someone believes an item you found is theirs</div></div>
      <a class="btn ghost sm" href="#/claims">All claims</a></div>
    ${incoming.length ? `<div class="card-body tight"><table>
      <thead><tr><th>Item</th><th>Claimed by</th><th>Match</th><th>Status</th><th></th></tr></thead>
      <tbody>${incoming.map((c) => `<tr>
        <td class="title-cell">${esc(c.found_title)}</td>
        <td>${esc(c.sender.name)} <span class="muted">&middot; ${esc(c.sender.department)}</span></td>
        <td>${sc(c.score)}</td>
        <td><span class="badge ${c.status}">${cap(c.status)}</span></td>
        <td style="text-align:right;white-space:nowrap">
          ${c.status === "pending" ? `
            <button class="btn sm ok" data-act="accept:${c.id}">Accept</button>
            <button class="btn sm no" data-act="reject:${c.id}">Reject</button>` : ""}</td></tr>`).join("")}
      </tbody></table></div>`
      : `<div class="empty">No incoming claims yet.</div>`}
  </div>`;
  claimButtons();
}

function viewClaims() {
  if (!needLogin()) return;
  const me = store.currentStudent();
  const incoming = store.claimsIncoming(me.id);
  const sent = store.claimsSent(me.id);

  app.innerHTML = `
  ${head("Claims", "Requests you received, and the ones you sent.")}
  <div class="card">
    <div class="card-head"><div><h2>Incoming</h2>
      <div class="sub">Someone claims an item you reported as found</div></div></div>
    ${incoming.length ? `<div class="card-body tight"><table>
      <thead><tr><th>Item</th><th>Claimed by</th><th>Match</th><th>Status</th><th></th></tr></thead>
      <tbody>${incoming.map((c) => `<tr>
        <td class="title-cell"><a href="#/item/${c.found_id}">${esc(c.found_title)}</a></td>
        <td>${esc(c.sender.name)} <span class="muted">&middot; ${esc(c.sender.department)}</span></td>
        <td>${sc(c.score)}</td>
        <td><span class="badge ${c.status}">${cap(c.status)}</span></td>
        <td style="text-align:right;white-space:nowrap">
          ${c.status === "pending" ? `
            <button class="btn sm ok" data-act="accept:${c.id}">Accept</button>
            <button class="btn sm no" data-act="reject:${c.id}">Reject</button>`
            : `<span class="muted" style="font-size:12.5px">answered</span>`}</td></tr>`).join("")}
      </tbody></table></div>`
      : `<div class="empty">No incoming claims yet.</div>`}
  </div>
  <div class="card">
    <div class="card-head"><div><h2>Sent</h2>
      <div class="sub">Claims you sent for items someone else found</div></div></div>
    ${sent.length ? `<div class="card-body tight"><table>
      <thead><tr><th>Item</th><th>Finder</th><th>Match</th><th>Status</th><th></th></tr></thead>
      <tbody>${sent.map((c) => `<tr>
        <td class="title-cell">${esc(c.found_title)}</td>
        <td>${esc(c.receiver.name)} <span class="muted">&middot; ${esc(c.receiver.department)}</span></td>
        <td>${sc(c.score)}</td>
        <td><span class="badge ${c.status}">${cap(c.status)}</span></td>
        <td style="text-align:right;white-space:nowrap">
          ${c.status === "accepted"
            ? `<button class="btn sm ok" data-act="return:${c.id}">Confirm handover</button>` : ""}</td></tr>`).join("")}
      </tbody></table></div>`
      : `<div class="empty">You have not sent any claims yet. <a href="#/browse">Browse found items</a>.</div>`}
  </div>`;
  claimButtons();
}

/* ---------------------------------------------------------------- */
function readImage(file) {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith("image/")) return reject(new Error("That file is not an image."));
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const max = 640;
      const k = Math.min(1, max / Math.max(img.width, img.height));
      const w = Math.max(1, Math.round(img.width * k));
      const h = Math.max(1, Math.round(img.height * k));
      const c = document.createElement("canvas");
      c.width = w; c.height = h;
      const ctx = c.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url);
      resolve({ imageData: ctx.getImageData(0, 0, w, h),
                dataUrl: c.toDataURL("image/jpeg", 0.7) });
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("That file is not a readable image.")); };
    img.src = url;
  });
}

function viewReport() {
  if (!needLogin()) return;

  app.innerHTML = `
  ${head("Report an item", "The photograph is used to extract the item's cast shadow and store its shape descriptor.")}
  <form id="f">
  <div class="card">
    <div class="card-head"><h2>Item details</h2></div>
    <div class="card-body">
      <div class="field"><label>What happened?</label>
        <div class="radio-row">
          <label id="lab-lost"><input type="radio" name="type" value="lost" checked>
            I have <strong>lost</strong> this item</label>
          <label id="lab-found"><input type="radio" name="type" value="found">
            I have <strong>found</strong> this item</label>
        </div></div>
      <div class="grid2">
        <div class="field"><label for="title">Item title</label>
          <input id="title" name="title" required maxlength="80" placeholder="e.g. Blue Nike backpack"></div>
        <div class="field"><label for="category">Category</label>
          <select id="category" name="category">${store.CATEGORIES.map((c) => `<option>${c}</option>`).join("")}</select></div>
      </div>
      <div class="grid2">
        <div class="field"><label for="place">Place</label>
          <input id="place" name="place" maxlength="80" placeholder="e.g. Canteen, Central Library"></div>
        <div class="field"><label for="seen_on">Date</label><input id="seen_on" name="seen_on" type="date"></div>
      </div>
      <div class="field"><label for="description">Short description</label>
        <textarea id="description" name="description" maxlength="400"
          placeholder="Colour, markings, anything that helps confirm ownership."></textarea></div>
      <div class="field" style="margin-bottom:0"><label for="photo">Photograph of the item</label>
        <input id="photo" name="photo" type="file" accept="image/*" required>
        <div class="hint">JPG or PNG. Photograph the item so that its cast shadow is visible.</div>
        <div class="upload-preview" id="prev"><img alt=""></div></div>
    </div>
  </div>
  <button class="btn" type="submit" id="go">Submit report</button>
  <a class="btn ghost" href="#/dashboard">Cancel</a>
  </form>`;

  const paint = () => {
    for (const t of ["lost", "found"]) {
      app.querySelector(`#lab-${t}`).classList.toggle(
        "on", app.querySelector(`input[value="${t}"]`).checked);
    }
  };
  app.querySelectorAll("input[name=type]").forEach((r) => r.addEventListener("change", paint));
  paint();

  let file = null;
  app.querySelector("#photo").addEventListener("change", (e) => {
    file = e.target.files && e.target.files[0];
    const box = app.querySelector("#prev");
    if (!file) return box.classList.remove("on");
    box.querySelector("img").src = URL.createObjectURL(file);
    box.classList.add("on");
  });

  app.querySelector("#f").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const title = String(fd.get("title") || "").trim();
    if (title.length < 3) return toast("Give the item a short title.", "danger");
    if (!file) return toast("Attach a photograph of the item.", "danger");

    const btn = app.querySelector("#go");
    btn.disabled = true; btn.textContent = "Extracting shadow...";
    try {
      const { imageData, dataUrl } = await readImage(file);
      const sil = extract(imageData, true);
      const overlay = overlayDataURL(imageData, sil.mask);
      const item = store.createItem({
        student_id: store.currentStudent().id,
        title, type: fd.get("type"), category: fd.get("category"),
        description: fd.get("description"), place: fd.get("place"),
        seen_on: fd.get("seen_on"),
        photo: dataUrl, overlay,
        descriptor: sil.descriptor, shadow_iou: sil.iou,
      });
      toast(`Item reported. Shadow signature stored via ${sil.engine}.`, "success");
      location.hash = `#/item/${item.id}`;
    } catch (err) {
      console.error(err);
      toast(err.message || "That image could not be processed.", "danger");
      btn.disabled = false; btn.textContent = "Submit report";
    }
  });
}

function viewLogout() {
  store.logout();
  toast("You have logged out safely.", "info");
  location.hash = "#/";
}

/* ---------------------------------------------------------------- */
const routes = {
  "/": viewIndex, "/browse": viewBrowse, "/login": viewLogin,
  "/register": viewRegister, "/dashboard": viewDashboard,
  "/report": viewReport, "/claims": viewClaims, "/logout": viewLogout,
};

function render() {
  chrome();
  const raw = location.hash.replace(/^#/, "") || "/";
  const [path, qs] = raw.split("?");

  if (path.startsWith("/item/")) return viewItem(path.split("/")[2]);

  const view = routes[path];
  if (!view) {
    app.innerHTML = `<div class="card" style="margin-top:30px"><div class="empty">
      <h2 style="margin:0 0 6px">Page not found</h2>
      That page does not exist. <a href="#/">Go home</a>.</div></div>`;
    return;
  }
  return view(new URLSearchParams(qs || ""));
}

async function boot() {
  await store.seed(false);
  chrome();
  render();
  loadOpenCV().then(chrome);   // warm OpenCV so the first upload is quick
}

window.addEventListener("hashchange", render);
boot();
