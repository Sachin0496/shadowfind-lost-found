/* ShadowFind - browser build of the vision pipeline.
 *
 * A faithful port of app/vision.py: same extraction, same 64-value descriptor,
 * same cosine ranking. Runs client-side so the UI works on GitHub Pages, where
 * no Python server can run. OpenCV.js does the image work when available; a
 * pure-JS fallback keeps the demo usable if it cannot load.
 */

export const BINS = 64;
export const GRID_CELLS = 8;
export const MIN_IOU = 0.45;

let cvPromise = null;

export function opencvAvailable() {
  return !!(window.cv && window.cv.Mat);
}

export function loadOpenCV(timeoutMs = 15000) {
  if (cvPromise) return cvPromise;
  cvPromise = new Promise((resolve) => {
    let settled = false;
    const done = (ok) => { if (!settled) { settled = true; resolve(ok); } };
    if (typeof window === "undefined") return done(false);
    if (opencvAvailable()) return done(true);

    const timer = setTimeout(() => done(false), timeoutMs);
    const ready = () => { clearTimeout(timer); done(true); };

    const attach = () => {
      if (!window.cv) return done(false);
      if (window.cv.Mat) return ready();
      window.cv.onRuntimeInitialized = ready;
    };

    if (window.cv) return attach();
    const s = document.createElement("script");
    s.src = "https://docs.opencv.org/4.x/opencv.js";
    s.async = true;
    s.onload = attach;
    s.onerror = () => done(false);
    document.head.appendChild(s);
  });
  return cvPromise;
}

/* ---------------------------------------------------------------- */
/* descriptor                                                        */
/* ---------------------------------------------------------------- */

/**
 * 64-value descriptor: 8x8 occupancy grid plus aspect ratio and solidity,
 * with the mostly-empty outer ring reused for the two scalars.
 * Mirrors vision.descriptor_from_grid().
 */
export function descriptorFromMask(mask, w, h) {
  let minX = w, minY = h, maxX = -1, maxY = -1, count = 0;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (!mask[y * w + x]) continue;
      count++;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
  }
  const desc = new Float32Array(BINS);
  if (!count) return { descriptor: desc, iou: 0, areaFraction: 0 };

  const bw = maxX - minX + 1, bh = maxY - minY + 1;
  const iou = count / (bw * bh);

  const cells = new Float64Array(BINS);
  for (let y = minY; y <= maxY; y++) {
    const cy = Math.min(GRID_CELLS - 1, Math.floor(((y - minY) / bh) * GRID_CELLS));
    for (let x = minX; x <= maxX; x++) {
      if (!mask[y * w + x]) continue;
      const cx = Math.min(GRID_CELLS - 1, Math.floor(((x - minX) / bw) * GRID_CELLS));
      cells[cy * GRID_CELLS + cx] += 1;
    }
  }
  const cellArea = (bw / GRID_CELLS) * (bh / GRID_CELLS);
  for (let i = 0; i < BINS; i++) cells[i] = Math.min(1, cells[i] / cellArea);

  const aspect = bw / bh;
  const fill = count / (bw * bh);
  const ring = [0, 1, 2, 3, 4, 5, 6, 7, 15, 23, 31, 39, 47, 55,
                63, 62, 61, 60, 59, 58, 57, 56, 48, 40, 32, 24, 16, 8];
  ring.forEach((idx, i) => { cells[idx] = (i % 2 === 0 ? aspect : fill) * 0.5; });

  let norm = 0;
  for (let i = 0; i < BINS; i++) norm += cells[i] * cells[i];
  norm = Math.sqrt(norm);
  for (let i = 0; i < BINS; i++) desc[i] = norm ? cells[i] / norm : 0;

  return { descriptor: desc, iou, areaFraction: count / (w * h) };
}

export function similarity(a, b) {
  if (!a || !b || !a.length || !b.length) return 0;
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) { dot += a[i] * b[i]; na += a[i] ** 2; nb += b[i] ** 2; }
  const d = Math.sqrt(na) * Math.sqrt(nb);
  return d ? Math.max(0, Math.min(1, dot / d)) : 0;
}

export function rank(query, candidates) {
  return candidates
    .map((c) => ({ id: c.id, score: similarity(query, c.descriptor) }))
    .sort((x, y) => y.score - x.score);
}

/* ---------------------------------------------------------------- */
/* extraction                                                        */
/* ---------------------------------------------------------------- */

function fillHoles(mask, w, h) {
  const seen = new Uint8Array(w * h);
  const stack = [];
  const seed = (p) => { if (!mask[p] && !seen[p]) { seen[p] = 1; stack.push(p); } };
  for (let x = 0; x < w; x++) { seed(x); seed((h - 1) * w + x); }
  for (let y = 0; y < h; y++) { seed(y * w); seed(y * w + w - 1); }

  while (stack.length) {
    const p = stack.pop();
    const x = p % w, y = (p - x) / w;
    if (x > 0) seed(p - 1);
    if (x < w - 1) seed(p + 1);
    if (y > 0) seed(p - w);
    if (y < h - 1) seed(p + w);
  }
  for (let i = 0; i < mask.length; i++) if (!seen[i]) mask[i] = 1;
}

function keepLargest(mask, w, h) {
  const seen = new Uint8Array(w * h);
  let best = null, bestSize = 0;
  for (let i = 0; i < mask.length; i++) {
    if (!mask[i] || seen[i]) continue;
    const comp = [], stack = [i];
    seen[i] = 1;
    while (stack.length) {
      const p = stack.pop();
      comp.push(p);
      const x = p % w, y = (p - x) / w;
      const push = (q) => { if (!seen[q] && mask[q]) { seen[q] = 1; stack.push(q); } };
      if (x > 0) push(p - 1);
      if (x < w - 1) push(p + 1);
      if (y > 0) push(p - w);
      if (y < h - 1) push(p + w);
    }
    if (comp.length > bestSize) { bestSize = comp.length; best = comp; }
  }
  mask.fill(0);
  if (best) for (const p of best) mask[p] = 1;
}

function extractOpenCV(imageData) {
  const cv = window.cv;
  const w = imageData.width, h = imageData.height;
  const src = cv.matFromImageData(imageData);
  const grey = new cv.Mat(), mask = new cv.Mat(), k = cv.Mat.ones(3, 3, cv.CV_8U);
  try {
    cv.cvtColor(src, grey, cv.COLOR_RGBA2GRAY, 0);
    let block = Math.max(15, (Math.floor(Math.min(w, h) / 12) | 1));
    if (block >= Math.min(w, h)) block = 15;
    cv.adaptiveThreshold(grey, mask, 255, cv.ADAPTIVE_THRESH_MEAN_C,
                        cv.THRESH_BINARY_INV, block, 10);
    cv.morphologyEx(mask, mask, cv.MORPH_OPEN, k);

    const labels = new cv.Mat(), stats = new cv.Mat(), cents = new cv.Mat();
    cv.connectedComponentsWithStats(mask, labels, stats, cents, 8, cv.CV_32S);
    let best = -1, bestArea = 0;
    for (let i = 1; i < stats.rows; i++) {
      const a = stats.intAt(i, cv.CC_STAT_AREA);
      if (a > bestArea) { bestArea = a; best = i; }
    }
    const out = new Uint8Array(w * h);
    if (best > 0) {
      const ld = labels.data32S;
      for (let i = 0; i < w * h; i++) if (ld[i] === best) out[i] = 1;
    }
    labels.delete(); stats.delete(); cents.delete();
    fillHoles(out, w, h);
    return out;
  } finally {
    src.delete(); grey.delete(); mask.delete(); k.delete();
  }
}

function extractFallback(imageData) {
  const { width: w, height: h, data } = imageData;
  const grey = new Uint8Array(w * h);
  let sum = 0;
  for (let i = 0, p = 0; i < data.length; i += 4, p++) {
    const g = (data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114) | 0;
    grey[p] = g; sum += g;
  }
  const thresh = Math.max(40, (sum / (w * h)) * 0.72);
  const mask = new Uint8Array(w * h);
  for (let i = 0; i < grey.length; i++) mask[i] = grey[i] < thresh ? 1 : 0;
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++)
      if (x < 2 || y < 2 || x >= w - 2 || y >= h - 2) mask[y * w + x] = 0;
  keepLargest(mask, w, h);
  fillHoles(mask, w, h);
  return mask;
}

export function extract(imageData, preferOpenCV = true) {
  const use = preferOpenCV && opencvAvailable();
  const { width: w, height: h } = imageData;
  const mask = use ? extractOpenCV(imageData) : extractFallback(imageData);
  const { descriptor, iou, areaFraction } = descriptorFromMask(mask, w, h);
  return { mask, width: w, height: h, descriptor, iou, areaFraction,
           reliable: iou >= MIN_IOU && areaFraction >= 0.01,
           engine: use ? "OpenCV.js" : "JS fallback" };
}

export function overlayDataURL(imageData, mask, tint = [40, 90, 170]) {
  const { width: w, height: h, data } = imageData;
  const out = new Uint8ClampedArray(data);
  for (let i = 0, p = 0; p < mask.length; i += 4, p++) {
    if (!mask[p]) continue;
    out[i]     = out[i]     * 0.45 + tint[0] * 0.55;
    out[i + 1] = out[i + 1] * 0.45 + tint[1] * 0.55;
    out[i + 2] = out[i + 2] * 0.45 + tint[2] * 0.55;
  }
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  c.getContext("2d").putImageData(new ImageData(out, w, h), 0, 0);
  return c.toDataURL("image/jpeg", 0.86);
}
