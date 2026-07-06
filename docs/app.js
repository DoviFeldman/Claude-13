/* Storm Map - lightweight PWA showing offshore lightning strikes.
 *
 * Your home location is stored only in this browser (localStorage) - it is
 * never in the repo or the published data. Strike positions come from
 * data/strikes.json, committed by the GitHub Actions detector run.
 */
"use strict";

const DATA_URL = "data/strikes.json";
const RINGS_KM = [5, 15, 30, 60, 150, 250];
const SEV_COLORS = {
  danger: "#ff4d4d", caution: "#ff9f40", sweet: "#3ddc84",
  visible: "#4da3ff", far: "#9aa4c4",
};
const SRC_LABELS = { xweather: "Xweather", glm: "GOES GLM", blitzortung: "Blitzortung" };

// Regional default view (NJ/NY coast + western Atlantic) until home is set.
const map = L.map("map", { zoomControl: false }).setView([39.7, -73.6], 7);
L.control.zoom({ position: "topright" }).addTo(map);
// OSM standard tiles: includes street names and place labels for
// cross-referencing beaches with Google Maps.
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map);

const strikeLayer = L.layerGroup().addTo(map);
const ringLayer = L.layerGroup().addTo(map);
const measureLayer = L.layerGroup().addTo(map);

const statusEl = document.getElementById("status");
const readoutEl = document.getElementById("measure-readout");

let home = loadHome();
let strikesData = null;
const hiddenSources = new Set();

/* ---------- geodesy ---------- */
function haversineKm(a, b) {
  const R = 6371.0088, toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat), dLon = toRad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
function bearingDeg(a, b) {
  const toRad = (d) => (d * Math.PI) / 180;
  const y = Math.sin(toRad(b.lng - a.lng)) * Math.cos(toRad(b.lat));
  const x = Math.cos(toRad(a.lat)) * Math.sin(toRad(b.lat)) -
    Math.sin(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.cos(toRad(b.lng - a.lng));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}
const COMPASS = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
const compass = (deg) => COMPASS[Math.floor(((deg + 11.25) % 360) / 22.5)];

/* ---------- home location (device-local only) ---------- */
function loadHome() {
  try { return JSON.parse(localStorage.getItem("home")) || null; } catch { return null; }
}
function setHome(latlng, pan) {
  home = { lat: latlng.lat, lng: latlng.lng };
  localStorage.setItem("home", JSON.stringify(home));
  drawRings();
  renderStrikes();
  if (pan) map.setView(home, 9);
}
function drawRings() {
  ringLayer.clearLayers();
  if (!home) return;
  L.circleMarker(home, { radius: 6, color: "#fff", weight: 2, fillColor: "#2f6fed", fillOpacity: 1 })
    .bindPopup("Home").addTo(ringLayer);
  for (const km of RINGS_KM) {
    L.circle(home, { radius: km * 1000, color: "#5a6488", weight: 1, opacity: 0.6, fill: false, dashArray: km === 30 || km === 60 ? null : "4 6" })
      .addTo(ringLayer);
    // Label each ring due east of home.
    const lng = home.lng + (km / (111.32 * Math.cos((home.lat * Math.PI) / 180)));
    L.marker([home.lat, lng], {
      icon: L.divIcon({ className: "ring-label", html: `${km} km`, iconSize: null }),
      interactive: false,
    }).addTo(ringLayer);
  }
}

/* ---------- strikes ---------- */
async function loadStrikes() {
  statusEl.textContent = "Loading strikes…";
  try {
    const resp = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache: "no-store" });
    strikesData = await resp.json();
  } catch {
    statusEl.textContent = "Couldn't load strike data (offline?)";
    return;
  }
  buildSourceToggles();
  renderStrikes();
}

function ageMinutes(iso) {
  return Math.round((Date.now() - Date.parse(iso)) / 60000);
}

function renderStrikes() {
  strikeLayer.clearLayers();
  if (!strikesData) return;
  let shown = 0;
  for (const s of strikesData.strikes || []) {
    if (hiddenSources.has(s.src)) continue;
    shown++;
    const color = SEV_COLORS[s.sev] || "#9aa4c4";
    const m = L.circleMarker([s.lat, s.lon], {
      radius: 5, color, weight: 1.5, fillColor: color, fillOpacity: 0.7,
    });
    let info = `<b>${s.band || "strike"}</b><br>${SRC_LABELS[s.src] || s.src}`;
    const ref = home || null;
    if (ref) {
      const d = haversineKm(ref, { lat: s.lat, lng: s.lon });
      const b = bearingDeg(ref, { lat: s.lat, lng: s.lon });
      info += `<br>${d.toFixed(1)} km ${compass(b)} (${Math.round(b)}°) from home`;
    } else if (s.km) {
      info += `<br>${s.km} km from target`;
    }
    if (s.t) info += `<br>${new Date(s.t).toLocaleTimeString()}`;
    m.bindPopup(info);
    m.addTo(strikeLayer);
  }
  const gen = strikesData.generated;
  const counts = Object.entries(strikesData.sources || {})
    .map(([k, v]) => `${SRC_LABELS[k] || k}: ${v.ok ? v.count : "✗"}`).join(" · ");
  statusEl.textContent = gen
    ? `${shown} strikes · ${ageMinutes(gen)} min old · ${counts}`
    : `${shown} strikes`;
}

function buildSourceToggles() {
  const holder = document.getElementById("src-toggles");
  holder.innerHTML = "";
  for (const name of Object.keys(strikesData.sources || {})) {
    const chip = document.createElement("button");
    chip.className = "src-chip" + (hiddenSources.has(name) ? " off" : "");
    chip.textContent = SRC_LABELS[name] || name;
    chip.onclick = () => {
      hiddenSources.has(name) ? hiddenSources.delete(name) : hiddenSources.add(name);
      chip.classList.toggle("off");
      renderStrikes();
    };
    holder.appendChild(chip);
  }
}

/* ---------- measure tool ---------- */
let measuring = false;
let measurePts = [];
const measureBtn = document.getElementById("btn-measure");

measureBtn.onclick = () => {
  measuring = !measuring;
  measureBtn.classList.toggle("active", measuring);
  measurePts = [];
  measureLayer.clearLayers();
  readoutEl.hidden = !measuring;
  readoutEl.textContent = measuring ? "Tap two points to measure" : "";
};

map.on("click", (e) => {
  if (settingHome) {
    setHome(e.latlng, false);
    endHomeMode();
    return;
  }
  if (!measuring) return;
  if (measurePts.length >= 2) { measurePts = []; measureLayer.clearLayers(); }
  measurePts.push(e.latlng);
  L.circleMarker(e.latlng, { radius: 5, color: "#ffd75e", fillColor: "#ffd75e", fillOpacity: 1 })
    .addTo(measureLayer);
  if (measurePts.length === 2) {
    L.polyline(measurePts, { color: "#ffd75e", weight: 2, dashArray: "6 6" }).addTo(measureLayer);
    const km = haversineKm(measurePts[0], measurePts[1]);
    const brg = bearingDeg(measurePts[0], measurePts[1]);
    readoutEl.textContent = `${km.toFixed(1)} km · ${(km * 0.621371).toFixed(1)} mi · ${compass(brg)}`;
  } else {
    readoutEl.textContent = "Tap the second point…";
  }
});

/* ---------- home button ---------- */
let settingHome = false;
const homeBtn = document.getElementById("btn-home");
function endHomeMode() {
  settingHome = false;
  homeBtn.classList.remove("active");
}
homeBtn.onclick = () => {
  if (settingHome) { endHomeMode(); return; }
  if (navigator.geolocation) {
    statusEl.textContent = "Getting your location…";
    navigator.geolocation.getCurrentPosition(
      (pos) => { setHome({ lat: pos.coords.latitude, lng: pos.coords.longitude }, true); },
      () => {
        settingHome = true;
        homeBtn.classList.add("active");
        statusEl.textContent = "Location denied - tap the map to set home";
      },
      { enableHighAccuracy: true, timeout: 8000 },
    );
  } else {
    settingHome = true;
    homeBtn.classList.add("active");
    statusEl.textContent = "Tap the map to set home";
  }
};

/* ---------- boot ---------- */
document.getElementById("refresh").onclick = loadStrikes;
setInterval(loadStrikes, 60000);
drawRings();
if (home) map.setView(home, 9);
loadStrikes();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js");
}
