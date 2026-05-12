// Minimal client-side simulator UI: posts to /simulate and plots one trace.

const form = document.getElementById("sim-form");
const analysisSelect = document.getElementById("analysis");
const tracePick = document.getElementById("trace-pick");
const statusEl = document.getElementById("status");
const canvas = document.getElementById("scope");
const ctx = canvas.getContext("2d");
let lastResult = null;

function showAnalysisFieldset() {
  const which = analysisSelect.value;
  document.querySelectorAll("fieldset.ana").forEach(fs => {
    fs.classList.toggle("hidden", !fs.classList.contains("ana-" + which));
  });
}
analysisSelect.addEventListener("change", showAnalysisFieldset);
showAnalysisFieldset();

form.addEventListener("submit", async ev => {
  ev.preventDefault();
  statusEl.textContent = "Running…";
  const data = new FormData(form);
  try {
    const res = await fetch("/simulate", { method: "POST", body: data });
    const j = await res.json();
    if (j.error) { statusEl.textContent = "Error: " + j.error; return; }
    lastResult = j;
    tracePick.innerHTML = "";
    if (j.analysis === "op") {
      statusEl.textContent = "DC operating point";
      drawOpPoint(j.operating_point);
      return;
    }
    (j.nets || Object.keys(j.waveforms || {})).forEach(n => {
      const opt = document.createElement("option");
      opt.value = n; opt.textContent = n;
      tracePick.appendChild(opt);
    });
    statusEl.textContent = `${j.analysis} — ${(j.x || []).length} pts`;
    drawTrace();
  } catch (e) {
    statusEl.textContent = "Network error: " + e;
  }
});

tracePick.addEventListener("change", drawTrace);

function drawTrace() {
  if (!lastResult || !lastResult.x) return;
  const net = tracePick.value;
  if (!net) return;
  const xs = lastResult.x;
  const ys = lastResult.waveforms[net];
  if (!ys) return;
  const w = canvas.width, h = canvas.height;
  ctx.fillStyle = "#06080f"; ctx.fillRect(0, 0, w, h);
  const isAC = lastResult.analysis === "ac";
  const xv = isAC ? xs.map(x => Math.log10(Math.max(x, 1e-12))) : xs;
  const yv = isAC ? ys.map(y => 20 * Math.log10(Math.max(Math.abs(y), 1e-12))) : ys;
  const xmin = Math.min(...xv), xmax = Math.max(...xv);
  const ymin = Math.min(...yv), ymax = Math.max(...yv);
  const pad = 30;
  function px(i) {
    return pad + (xv[i] - xmin) / Math.max(xmax - xmin, 1e-12) * (w - 2 * pad);
  }
  function py(i) {
    return h - pad - (yv[i] - ymin) / Math.max(ymax - ymin, 1e-12) * (h - 2 * pad);
  }
  // axes
  ctx.strokeStyle = "#25324a"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad, pad); ctx.lineTo(pad, h - pad);
  ctx.lineTo(w - pad, h - pad); ctx.stroke();
  // trace
  ctx.strokeStyle = "#4ed1c5"; ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let i = 0; i < xv.length; i++) {
    if (i === 0) ctx.moveTo(px(i), py(i)); else ctx.lineTo(px(i), py(i));
  }
  ctx.stroke();
  // labels
  ctx.fillStyle = "#98a2b3"; ctx.font = "11px ui-monospace, monospace";
  ctx.fillText(net, pad + 6, pad + 14);
  ctx.fillText(isAC ? "log10(f)" : "x", w - pad - 30, h - pad + 14);
  ctx.fillText(isAC ? "dB" : "V", 4, pad + 4);
}

function drawOpPoint(op) {
  const w = canvas.width, h = canvas.height;
  ctx.fillStyle = "#06080f"; ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = "#e6edf3"; ctx.font = "14px ui-monospace, monospace";
  let y = 30;
  for (const k of Object.keys(op).sort()) {
    ctx.fillText(`V(${k}) = ${op[k].toFixed(4)} V`, 20, y);
    y += 22;
    if (y > h - 10) break;
  }
}
