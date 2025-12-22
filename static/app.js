// static/app.js
const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");

const uploadBtn = document.getElementById("uploadBtn");
const fileInput = document.getElementById("fileInput");
const paletteList = document.getElementById("paletteList");
const meta = document.getElementById("meta");

let img = new Image();
let palette = null;

// For mapping canvas <-> image coordinates
let lastFit = null; // {x,y,w,h}

// Drag selection state (canvas coords)
let selecting = false;
let selStart = null; // {x,y}
let selRect = null;  // {x,y,w,h}
let antsOffset = 0;
let rafId = null;

function resizeCanvas() {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(canvas.clientWidth * dpr);
  canvas.height = Math.floor(canvas.clientHeight * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  draw();
}

window.addEventListener("resize", resizeCanvas);

uploadBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  const url = URL.createObjectURL(file);
  img = new Image();
  img.onload = async () => {
    resizeCanvas();
    meta.textContent = "Extracting palette…";
    palette = await fetchPalette(file);
    meta.textContent = palette?.scheme ? `Scheme: ${palette.scheme}` : (palette?.error || "");
    renderPaletteList(palette);
    selRect = null;
    draw();
  };
  img.src = url;
});

async function fetchPalette(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/api/palette", { method: "POST", body: fd });
  return await res.json();
}

async function fetchRegionPalette(rectImagePx) {
  const res = await fetch("/api/palette/region", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(rectImagePx),
  });
  return await res.json();
}

function fitRect(imgW, imgH, canvasW, canvasH) {
  const scale = Math.min(canvasW / imgW, canvasH / imgH);
  const w = imgW * scale;
  const h = imgH * scale;
  const x = (canvasW - w) / 2;
  const y = (canvasH - h) / 2;
  return { x, y, w, h, scale };
}

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

function canvasPointFromEvent(e) {
  const r = canvas.getBoundingClientRect();
  return { x: e.clientX - r.left, y: e.clientY - r.top };
}

function inImageArea(p, fit) {
  if (!fit) return false;
  return p.x >= fit.x && p.x <= fit.x + fit.w && p.y >= fit.y && p.y <= fit.y + fit.h;
}

function normalizeRect(a, b) {
  const x0 = Math.min(a.x, b.x);
  const y0 = Math.min(a.y, b.y);
  const x1 = Math.max(a.x, b.x);
  const y1 = Math.max(a.y, b.y);
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

function rectCanvasToImagePx(rectCanvas, fit, imgW, imgH) {
  // Convert canvas coords -> image pixel coords, clamped
  const x0 = (rectCanvas.x - fit.x) / fit.scale;
  const y0 = (rectCanvas.y - fit.y) / fit.scale;
  const x1 = (rectCanvas.x + rectCanvas.w - fit.x) / fit.scale;
  const y1 = (rectCanvas.y + rectCanvas.h - fit.y) / fit.scale;

  const ix0 = Math.floor(clamp(x0, 0, imgW));
  const iy0 = Math.floor(clamp(y0, 0, imgH));
  const ix1 = Math.floor(clamp(x1, 0, imgW));
  const iy1 = Math.floor(clamp(y1, 0, imgH));

  return { x: ix0, y: iy0, w: Math.max(1, ix1 - ix0), h: Math.max(1, iy1 - iy0) };
}

// Mouse interactions
canvas.addEventListener("mousedown", (e) => {
  if (!img?.width || !img?.height) return;

  const p = canvasPointFromEvent(e);
  if (!inImageArea(p, lastFit)) return;

  selecting = true;
  selStart = p;
  selRect = { x: p.x, y: p.y, w: 0, h: 0 };
  startAnts();
  draw();
});

canvas.addEventListener("mousemove", (e) => {
  if (!selecting || !selStart) return;
  const p = canvasPointFromEvent(e);

  // constrain to image area
  const fit = lastFit;
  const cx = clamp(p.x, fit.x, fit.x + fit.w);
  const cy = clamp(p.y, fit.y, fit.y + fit.h);

  selRect = normalizeRect(selStart, { x: cx, y: cy });
  draw();
});

canvas.addEventListener("mouseup", async () => {
  if (!selecting) return;
  selecting = false;
  stopAnts();

  if (!selRect || selRect.w < 4 || selRect.h < 4) {
    selRect = null;
    draw();
    return;
  }

  // Convert to image pixel coordinates and request new palette
  const rectImagePx = rectCanvasToImagePx(selRect, lastFit, img.width, img.height);

  meta.textContent = "Extracting palette (selection)…";
  const p = await fetchRegionPalette(rectImagePx);
  palette = p;
  meta.textContent = palette?.scheme ? `Scheme: ${palette.scheme}` : (palette?.error || "");
  renderPaletteList(palette);

  // Keep the selection visible after release (optional). If you want it to disappear, set selRect=null.
  draw();
});

canvas.addEventListener("mouseleave", () => {
  if (!selecting) return;
  selecting = false;
  stopAnts();
  draw();
});

function startAnts() {
  if (rafId) return;
  const tick = () => {
    antsOffset = (antsOffset + 1) % 16;
    draw();
    rafId = requestAnimationFrame(tick);
  };
  rafId = requestAnimationFrame(tick);
}

function stopAnts() {
  if (rafId) cancelAnimationFrame(rafId);
  rafId = null;
}

function draw() {
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;

  ctx.clearRect(0, 0, w, h);

  if (img?.width && img?.height) {
    lastFit = fitRect(img.width, img.height, w, h);
    ctx.drawImage(img, lastFit.x, lastFit.y, lastFit.w, lastFit.h);

    if (palette) drawOverlaySwatches(lastFit);
    if (selRect) drawMarchingAnts(selRect);
  } else {
    ctx.fillStyle = "#fafafa";
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = "#777";
    ctx.font = "14px system-ui";
    ctx.fillText("Upload an image to generate a harmonized palette.", 16, 28);
  }
}

function drawMarchingAnts(r) {
  // White dashed line + black dashed line offset for classic marching-ants feel
  ctx.save();

  ctx.lineWidth = 1;

  ctx.setLineDash([6, 6]);
  ctx.lineDashOffset = -antsOffset;
  ctx.strokeStyle = "rgba(255,255,255,0.95)";
  ctx.strokeRect(r.x + 0.5, r.y + 0.5, r.w, r.h);

  ctx.setLineDash([6, 6]);
  ctx.lineDashOffset = -(antsOffset + 6);
  ctx.strokeStyle = "rgba(0,0,0,0.85)";
  ctx.strokeRect(r.x + 0.5, r.y + 0.5, r.w, r.h);

  ctx.restore();
}

function drawOverlaySwatches(imgRect) {
  const items = paletteToItems(palette);
  const swW = 160;
  const swH = 26;
  const pad = 10;

  let x = imgRect.x + pad;
  let y = imgRect.y + pad;

  ctx.save();
  ctx.globalAlpha = 0.92;
  ctx.font = "12px system-ui";

  for (const it of items) {
    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.fillRect(x, y, swW, swH);

    ctx.fillStyle = it.hex;
    ctx.fillRect(x + 6, y + 6, 14, 14);
    ctx.strokeStyle = "rgba(0,0,0,0.15)";
    ctx.strokeRect(x + 6, y + 6, 14, 14);

    ctx.fillStyle = "#111";
    ctx.fillText(`${it.role}`, x + 26, y + 16);

    ctx.fillStyle = "#333";
    ctx.fillText(it.hex, x + 92, y + 16);

    y += swH + 6;
    if (y + swH > imgRect.y + imgRect.h - pad) {
      y = imgRect.y + pad;
      x += swW + 8;
    }
  }

  ctx.restore();
}

function paletteToItems(p) {
  if (!p || p.error) return [];
  const items = [
    { role: "primary", hex: p.primary.hex },
    { role: "secondary", hex: p.secondary.hex },
    { role: "tertiary", hex: p.tertiary.hex },
  ];
  for (const s of (p.support || [])) items.push({ role: s.role, hex: s.hex });
  return items;
}

function renderPaletteList(p) {
  paletteList.innerHTML = "";
  const items = paletteToItems(p);
  for (const it of items) {
    const el = document.createElement("div");
    el.className = "swatch";
    el.innerHTML = `
      <div class="chip" style="background:${it.hex}"></div>
      <div class="label">${it.role}</div>
      <div class="hex">${it.hex}</div>
    `;
    el.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(it.hex); } catch {}
    });
    paletteList.appendChild(el);
  }
}

resizeCanvas();
