/* ShadowFind static build - data layer.
 *
 * The Flask app keeps state in SQLite; the static build keeps the same records
 * in localStorage, so report -> rank -> claim -> accept -> return all behave
 * the same without a server.
 */

const KEY = "shadowfind.v1";

export const CATEGORIES = ["Bag", "Bottle", "Watch", "Umbrella", "Helmet",
  "Electronics", "Books", "Keys", "ID card", "Other"];
export const DEPARTMENTS = ["CSE", "ECE", "EEE", "MECH", "CIVIL", "IT", "AI&DS", "Other"];
export const DEMO_PASSWORD = "shadow123";

const blank = () => ({
  students: [], items: [], matches: [], claims: [], session: null,
  nextId: { student: 1, item: 1, match: 1, claim: 1 },
});

let state = null;

export function load() {
  if (state) return state;
  try {
    const raw = localStorage.getItem(KEY);
    state = raw ? JSON.parse(raw) : blank();
  } catch { state = blank(); }
  state.nextId = state.nextId || { student: 1, item: 1, match: 1, claim: 1 };
  return state;
}

export function save() {
  try { localStorage.setItem(KEY, JSON.stringify(load())); }
  catch (e) { console.warn("state not persisted:", e); }
}

export function reset() {
  state = blank();
  try { localStorage.removeItem(KEY); } catch {}
  return state;
}

export const seeded = () => load().students.length > 0;

/* ---------------- students + session ---------------- */
function hash(password) {
  let h = 5381;
  for (let i = 0; i < password.length; i++) h = ((h << 5) + h + password.charCodeAt(i)) | 0;
  return "h" + (h >>> 0).toString(16);
}

export function createStudent({ name, email, password, department }) {
  const s = load();
  const e = String(email).trim().toLowerCase();
  if (s.students.some((x) => x.email === e)) {
    return { error: "That e-mail address is already registered." };
  }
  const student = { id: s.nextId.student++, name: String(name).trim(), email: e,
                    password: hash(password), department,
                    created_at: new Date().toISOString() };
  s.students.push(student);
  save();
  return { student };
}

export function verify(email, password) {
  const e = String(email).trim().toLowerCase();
  const st = load().students.find((x) => x.email === e);
  return st && st.password === hash(password) ? st : null;
}

export function login(id) { const s = load(); s.session = id; save(); }
export function logout() { const s = load(); s.session = null; save(); }

export function currentStudent() {
  const s = load();
  return s.session ? s.students.find((x) => x.id === s.session) || null : null;
}

/* ---------------- items ---------------- */
export function createItem(d) {
  const s = load();
  const item = {
    id: s.nextId.item++,
    student_id: d.student_id,
    title: d.title, type: d.type, category: d.category,
    description: d.description || "", place: d.place || "",
    seen_on: d.seen_on || "",
    photo: d.photo || "", overlay: d.overlay || "",
    descriptor: d.descriptor ? Array.from(d.descriptor) : null,
    shadow_iou: d.shadow_iou || 0,
    created_at: new Date().toISOString(),
  };
  s.items.push(item);
  save();
  return item;
}

export const getItem = (id) => load().items.find((i) => i.id === Number(id)) || null;

export function listItems({ excludeStudent = null, type = null, category = null, limit = 200 } = {}) {
  return load().items
    .filter((i) => excludeStudent == null || i.student_id !== excludeStudent)
    .filter((i) => !type || i.type === type)
    .filter((i) => !category || i.category === category)
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
    .slice(0, limit);
}

export const itemsOf = (sid) => load().items.filter((i) => i.student_id === sid)
  .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));

export const studentOf = (id) =>
  load().students.find((x) => x.id === id) || { name: "Unknown", department: "-" };

/** Same category, opposite type - mirrors db.candidates_for(). */
export function candidatesFor(item) {
  const opposite = item.type === "lost" ? "found" : "lost";
  const pool = load().items.filter((i) => i.type === opposite && i.descriptor && i.id !== item.id);
  const same = pool.filter((i) => i.category === item.category);
  return same.length ? same : pool;
}

/* ---------------- matches + claims ---------------- */
export function saveMatch(lostId, foundId, score) {
  const s = load();
  let m = s.matches.find((x) => x.lost_item_id === lostId && x.found_item_id === foundId);
  if (m) { m.score = score; } else {
    m = { id: s.nextId.match++, lost_item_id: lostId, found_item_id: foundId,
          score, created_at: new Date().toISOString() };
    s.matches.push(m);
  }
  save();
  return m;
}

export function createClaim(matchId, senderId, receiverId) {
  const s = load();
  const open = s.claims.find((c) => c.match_id === matchId && c.sender_id === senderId
    && (c.status === "pending" || c.status === "accepted"));
  if (open) return { claim: open, created: false };
  const claim = { id: s.nextId.claim++, match_id: matchId, sender_id: senderId,
                  receiver_id: receiverId, status: "pending",
                  created_at: new Date().toISOString() };
  s.claims.push(claim);
  save();
  return { claim, created: true };
}

function decorate(c) {
  const s = load();
  const m = s.matches.find((x) => x.id === c.match_id) || {};
  const lost = s.items.find((i) => i.id === m.lost_item_id) || {};
  const found = s.items.find((i) => i.id === m.found_item_id) || {};
  return { ...c, score: m.score || 0, lost_title: lost.title || "-",
           found_title: found.title || "-", lost_id: lost.id, found_id: found.id,
           sender: studentOf(c.sender_id), receiver: studentOf(c.receiver_id) };
}

export const claimsIncoming = (sid) => load().claims
  .filter((c) => c.receiver_id === sid).map(decorate)
  .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));

export const claimsSent = (sid) => load().claims
  .filter((c) => c.sender_id === sid).map(decorate)
  .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));

export function setClaimStatus(id, status) {
  const s = load();
  const c = s.claims.find((x) => x.id === id);
  if (!c) return;
  c.status = status;
  if (status === "accepted") {
    for (const o of s.claims) {
      if (o.match_id === c.match_id && o.id !== c.id && o.status === "pending") o.status = "rejected";
    }
  }
  save();
}

export function stats() {
  const s = load();
  return {
    lost: s.items.filter((i) => i.type === "lost").length,
    found: s.items.filter((i) => i.type === "found").length,
    returned: s.claims.filter((c) => c.status === "returned").length,
  };
}

/* ---------------- seed ---------------- */
const SEED_STUDENTS = [
  ["Ananya R", "ananya@college.edu", "CSE"],
  ["Rahul M", "rahul@college.edu", "ECE"],
  ["Priya K", "priya@college.edu", "IT"],
  ["Karthik S", "karthik@college.edu", "MECH"],
];

const SEED_ITEMS = [
  [0, "lost",  "Blue Nike backpack", "Bag",      "seed_bag_blue_0.jpg",    "Canteen",          "2026-10-12",
   "Blue Nike backpack with a white swoosh, a broken left zip and a small green dinosaur keychain."],
  [1, "found", "Blue backpack",      "Bag",      "seed_bag_blue_1.jpg",    "Physics Lab 2",    "2026-10-14",
   "Found a blue backpack after the lab session. Slightly worn, white logo on the front."],
  [2, "found", "Laptop bag",         "Bag",      "seed_bag_grey_2.jpg",    "Central Library",  "2026-10-15",
   "Dark laptop bag left near the reading room. Has a side pocket with a padlock."],
  [0, "lost",  "Casio F-91W watch",  "Watch",    "seed_watch_black_3.jpg", "Sports ground",    "2026-10-09",
   "Black Casio digital watch, resin strap, small scratch on the glass."],
  [3, "found", "Digital watch",      "Watch",    "seed_watch_black_4.jpg", "Sports ground",    "2026-10-10",
   "Found a black digital watch near the basketball court."],
  [1, "lost",  "Steel water bottle", "Bottle",   "seed_bottle_grey_5.jpg", "Mechanical Block", "2026-10-11",
   "One litre steel bottle with a blue cap and a dent near the base."],
  [2, "found", "Water bottle",       "Bottle",   "seed_bottle_grey_6.jpg", "Canteen",          "2026-10-14",
   "Steel bottle with a coloured cap, found on a canteen table."],
  [3, "lost",  "Black umbrella",     "Umbrella", "seed_umbrella_black_7.jpg", "Bus stop",      "2026-10-06",
   "Compact black umbrella with a wooden handle."],
  [1, "found", "Umbrella",           "Umbrella", "seed_umbrella_black_8.jpg", "Main gate",     "2026-10-07",
   "Black folding umbrella left at the main gate."],
  [2, "lost",  "White helmet",       "Helmet",   "seed_helmet_white_9.jpg", "Parking area",    "2026-10-05",
   "White full-face helmet with a clear visor and a red stripe."],
  [3, "found", "Helmet",             "Helmet",   "seed_helmet_white_10.jpg", "Parking area",   "2026-10-06",
   "White helmet found beside the two-wheeler parking."],
];

export async function seed(force = false) {
  if (!force && seeded()) return false;
  if (force) reset();
  const s = load();

  const ids = SEED_STUDENTS.map(([name, email, department]) => {
    const st = { id: s.nextId.student++, name, email,
                 password: hash(DEMO_PASSWORD), department,
                 created_at: new Date().toISOString() };
    s.students.push(st);
    return st.id;
  });

  let descriptors = {};
  try {
    const res = await fetch("seed/descriptors.json", { cache: "no-cache" });
    if (res.ok) descriptors = await res.json();
  } catch { /* matching degrades gracefully without precomputed descriptors */ }

  // spread the sample reports over a couple of weeks so the lists look real
  const t0 = new Date("2026-10-06T09:00:00Z").getTime();
  SEED_ITEMS.forEach(([owner, type, title, category, photo, place, seen_on, desc], i) => {
    const d = descriptors[photo];
    s.items.push({
      id: s.nextId.item++, student_id: ids[owner],
      title, type, category, place, description: desc, seen_on,
      photo: `seed/${photo}`,
      overlay: d ? `seed/${d.overlay}` : "",
      descriptor: d ? d.descriptor : null,
      shadow_iou: d ? d.iou : 0,
      created_at: new Date(t0 + i * 26 * 36e5).toISOString(),
    });
  });
  save();
  return true;
}
