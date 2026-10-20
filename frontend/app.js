/**
 * FarmaSigap Client Application
 * Supports:
 * - Dual Mode: Dark Mode & Light Mode (White Mode)
 * - Connected Indonesian Logistics Network & District Focus Map
 * - Progressive Disclosure: Mode Ringkas (Simpel) vs Mode Lengkap (Detail)
 * - Interactive WHO IEHK Posko Kit & Donation Matcher
 */

// Adapt API_BASE_URL to current domain (Railway deployment or localhost)
const API_BASE_URL = (typeof window !== "undefined" && window.location.origin && !window.location.origin.startsWith("file:") && !window.location.origin.includes("localhost") && !window.location.origin.includes("127.0.0.1"))
  ? `${window.location.origin}/api`
  : "http://localhost:8000/api";

// Fallback Mock Data
const FALLBACK_DATA = {
  telemetry: {
    pm25: 184.5,
    ispu: "Sangat Tidak Sehat",
    hotspots: 48
  },
  // 7 Puskesmas Kubu Raya (Fokus Bencana Karhutla)
  puskesmas: [
    { id: "PKM-A", name: "Puskesmas Sungai Raya", lat: -0.0682, lng: 109.3871, status: "merah", stockDays: 3.1, leadTime: 4 },
    { id: "PKM-B", name: "Puskesmas Rasau Jaya", lat: -0.2141, lng: 109.3512, status: "hijau", stockDays: 45.0, leadTime: 3 },
    { id: "PKM-C", name: "Puskesmas Sungai Kakap", lat: -0.0821, lng: 109.1824, status: "kuning", stockDays: 10.2, leadTime: 4 },
    { id: "PKM-D", name: "Puskesmas Sungai Ambawang", lat: -0.0125, lng: 109.4312, status: "merah", stockDays: 4.8, leadTime: 3 },
    { id: "PKM-E", name: "Puskesmas Kuala Mandor B", lat: 0.0531, lng: 109.4128, status: "kuning", stockDays: 8.5, leadTime: 5 },
    { id: "PKM-F", name: "Puskesmas Teluk Pakedai", lat: -0.3218, lng: 109.2814, status: "hijau", stockDays: 32.0, leadTime: 5 },
    { id: "PKM-G", name: "Puskesmas Terentang", lat: -0.4120, lng: 109.5210, status: "hijau", stockDays: 28.4, leadTime: 6 }
  ],
  // Jaringan Logistik Nasional Indonesia Terhubung
  nationalHubs: [
    { id: "HUB-JKT", name: "Depo Pusat Kemenkes & HEOC", city: "DKI Jakarta", lat: -6.2088, lng: 106.8456, type: "pusat", status: "Depo Cadangan Nasional" },
    { id: "HUB-PNK", name: "Instalasi Farmasi Kubu Raya / Pontianak", city: "Kalimantan Barat", lat: -0.0682, lng: 109.3871, type: "bencana", status: "SIAGA 1 (Karhutla Aktif)" },
    { id: "HUB-PKU", name: "Instalasi Farmasi Pekanbaru", city: "Riau", lat: 0.5071, lng: 101.4478, type: "waspada", status: "SIAGA 2 (Kabut Asap Ringan)" },
    { id: "HUB-PLM", name: "Instalasi Farmasi Palembang", city: "Sumatera Selatan", lat: -2.9761, lng: 104.7754, type: "waspada", status: "SIAGA 2 (Hotspot Lahan Gambut)" },
    { id: "HUB-BDJ", name: "Instalasi Farmasi Banjarmasin", city: "Kalimantan Selatan", lat: -3.3194, lng: 114.5908, type: "waspada", status: "SIAGA 2 (Pantauan Udara)" },
    { id: "HUB-SUB", name: "Depo Logistik Buffer Regional", city: "Surabaya, Jawa Timur", lat: -7.2575, lng: 112.7521, type: "buffer", status: "Buffer Stok Siap Mobilisasi" },
    { id: "HUB-MKS", name: "Depo Farmasi Terpadu", city: "Makassar, Sulawesi Selatan", lat: -5.1477, lng: 119.4327, type: "buffer", status: "Depo Penyangga Wilayah Timur" }
  ],
  hotspots: [
    { lat: -0.092, lng: 109.412, name: "Titik Panas Gambut Parit Baru" },
    { lat: -0.051, lng: 109.438, name: "Titik Panas Semak Ambawang" },
    { lat: -0.185, lng: 109.382, name: "Titik Panas Lahan Rasau Jaya" }
  ],
  medicines: [
    { name: "Salbutamol Inhaler 100 mcg", form: "Canister 200 dosis", need14: 180, stock: 40, days: 3.1, status: "merah", action: "Mutasi segera dari Puskesmas Rasau Jaya (Surplus)" },
    { name: "Parasetamol Tablet 500 mg", form: "Strip 10 tablet", need14: 2400, stock: 1100, days: 6.4, status: "merah", action: "Pengadaan darurat / redistribusi faskes terdekat" },
    { name: "Air Mata Buatan (Tetes 5 ml)", form: "Botol tetes", need14: 150, stock: 120, days: 11.2, status: "kuning", action: "Pantau harian, kebutuhan iritasi asap meningkat" },
    { name: "Tabung Oksigen Medis 1 m³", form: "Tabung regulator", need14: 12, stock: 9, days: 10.5, status: "kuning", action: "Siagakan di UGD 24 Jam Puskesmas" },
    { name: "Masker Respirator N95", form: "Pcs", need14: 900, stock: 1600, days: 24.9, status: "hijau", action: "Stok aman untuk kelompok rentan & balita" },
    { name: "Oralit Sachet 200 ml", form: "Sachet bubuk", need14: 300, stock: 650, days: 30.3, status: "hijau", action: "Pemantauan rutin posko" }
  ],
  ispaTrend: {
    labels: ["W-4 (21 Sep)", "W-3 (28 Sep)", "W-2 (05 Okt)", "W-1 (12 Okt)", "Hari Ini (20 Okt)", "+1 W (27 Okt)", "+2 W (03 Nov)", "+3 W (10 Nov)"],
    actual: [420, 510, 680, 740, 810, null, null, null],
    p50:    [null, null, null, null, 810, 940, 1050, 860],
    p90:    [null, null, null, null, 870, 1180, 1390, 1150],
    p10:    [null, null, null, null, 760, 720, 780, 610]
  }
};

let mapInstance = null;
let heroGlobe = null;
let mapMarkers = [];
let mapIntroPlayed = false;
let liveMapData = null; // data Puskesmas & titik panas dari FastAPI bila backend aktif
let currentMapViewMode = "globe"; // "globe", "indonesia", atau "local"
let ispaChartInstance = null;
let currentDetailMode = "simple"; // "simple" or "detail"

// Initialize on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  initCyberWavesCanvas();
  initTheme();
  initMap();
  initHeroGlobe();
  loadMedicineTable(FALLBACK_DATA.medicines);
  initISPAChart(FALLBACK_DATA.ispaTrend);
  calculatePoskoKit();
  initDonationRows();
  checkBackendHealth();
});

// ==========================================================================
// 1. THEME SWITCHER (Dark Mode & White / Light Mode)
// ==========================================================================
function initTheme() {
  const savedTheme = localStorage.getItem("farmasigap_theme") || "dark";
  applyTheme(savedTheme);
}

window.toggleTheme = function() {
  const currentTheme = document.body.getAttribute("data-theme") || "dark";
  const newTheme = currentTheme === "dark" ? "light" : "dark";
  applyTheme(newTheme);
};

function applyTheme(theme) {
  document.body.setAttribute("data-theme", theme);
  localStorage.setItem("farmasigap_theme", theme);

  const iconEl = document.getElementById("theme-icon");
  const labelEl = document.getElementById("theme-label");

  if (theme === "light") {
    if (iconEl) iconEl.innerText = "☀️";
    if (labelEl) labelEl.innerText = "Mode Terang";
  } else {
    if (iconEl) iconEl.innerText = "🌙";
    if (labelEl) labelEl.innerText = "Mode Gelap";
  }

  // Ganti basemap peta dasbor (gelap / terang)
  if (mapInstance) {
    updateMapTileTheme(theme);
  }

  // Update Chart.js colors
  if (ispaChartInstance) {
    updateChartTheme(theme);
  }
}

function updateMapTileTheme(theme) {
  if (!mapInstance || !mapInstance.isStyleLoaded()) return;
  ["dark-base", "dark-ref"].forEach(id => mapInstance.setLayoutProperty(id, "visibility", theme === "light" ? "none" : "visible"));
  ["light-base", "light-ref"].forEach(id => mapInstance.setLayoutProperty(id, "visibility", theme === "light" ? "visible" : "none"));
}

function updateChartTheme(theme) {
  const isDark = theme === "dark";
  const gridColor = isDark ? "rgba(255, 255, 255, 0.05)" : "rgba(15, 23, 42, 0.06)";
  const textColor = isDark ? "rgba(255, 255, 255, 0.55)" : "rgba(15, 23, 42, 0.65)";

  ispaChartInstance.options.scales.x.grid.color = gridColor;
  ispaChartInstance.options.scales.x.ticks.color = textColor;
  ispaChartInstance.options.scales.y.grid.color = gridColor;
  ispaChartInstance.options.scales.y.ticks.color = textColor;
  ispaChartInstance.update();
}

// ==========================================================================
// 2. PROGRESSIVE DISCLOSURE (Mode Ringkas vs Mode Lengkap)
// ==========================================================================
window.setDetailMode = function(mode) {
  currentDetailMode = mode;
  document.body.setAttribute("data-detail-mode", mode);

  const btnSimple = document.getElementById("btn-mode-simple");
  const btnDetail = document.getElementById("btn-mode-detail");
  const chartDetails = document.getElementById("chart-extended-details");
  const rationaleExtended = document.getElementById("rationale-extended");
  const detailToggleLabel = document.getElementById("detail-toggle-label");

  if (mode === "detail") {
    if (btnSimple) btnSimple.classList.remove("active");
    if (btnDetail) btnDetail.classList.add("active");
    if (chartDetails) chartDetails.style.display = "block";
    if (rationaleExtended) rationaleExtended.style.display = "block";
    if (detailToggleLabel) detailToggleLabel.innerText = "Tutup Rincian Lengkap ▴";
  } else {
    if (btnSimple) btnSimple.classList.add("active");
    if (btnDetail) btnDetail.classList.remove("active");
    if (chartDetails) chartDetails.style.display = "none";
    if (rationaleExtended) rationaleExtended.style.display = "none";
    if (detailToggleLabel) detailToggleLabel.innerText = "Buka Rincian Lengkap ▾";
  }
};

window.toggleDetailMode = function() {
  const nextMode = currentDetailMode === "simple" ? "detail" : "simple";
  setDetailMode(nextMode);
};

// ==========================================================================
// 3. PETA: GLOBE BUMI -> INDONESIA TERHUBUNG -> FOKUS KUBU RAYA (MapLibre GL)
// ==========================================================================
const ESRI_TILES = "https://server.arcgisonline.com/ArcGIS/rest/services";
const INDONESIA_VIEW = { center: [118, -2.5], spanLng: 50, spanLat: 20 }; // Sabang–Merauke + margin
const KUBU_RAYA_VIEW = { center: [109.33, -0.17], zoom: 9.6 };
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
// Citra satelit tampil saat zoom jauh (globe), memudar ke basemap operasional saat zoom dekat
const SATELLITE_FADE = ["interpolate", ["linear"], ["zoom"], 3, 1, 5.5, 0];
const BASEMAP_FADE = ["interpolate", ["linear"], ["zoom"], 3, 0, 5.5, 1];

const LOGISTICS_CORRIDORS = [
  { from: [106.8456, -6.2088], to: [109.3871, -0.0682], color: "#ff4d4f", name: "Koridor Darurat: Jakarta ➜ Pontianak (Karhutla)" },
  { from: [106.8456, -6.2088], to: [101.4478, 0.5071], color: "#ffa940", name: "Koridor Siaga: Jakarta ➜ Pekanbaru (Riau)" },
  { from: [106.8456, -6.2088], to: [104.7754, -2.9761], color: "#ffa940", name: "Koridor Siaga: Jakarta ➜ Palembang (Sumsel)" },
  { from: [106.8456, -6.2088], to: [114.5908, -3.3194], color: "#355ff3", name: "Koridor Buffer: Jakarta ➜ Banjarmasin" },
  { from: [106.8456, -6.2088], to: [112.7521, -7.2575], color: "#61dd99", name: "Depo Penyangga: Jakarta ➜ Surabaya" },
  { from: [112.7521, -7.2575], to: [119.4327, -5.1477], color: "#355ff3", name: "Depo Regional: Surabaya ➜ Makassar" }
];

const STATUS_PIN = { merah: "#ff4d4f", kuning: "#ffa940", hijau: "#61dd99" };
const HUB_PIN = { bencana: "#ff4d4f", waspada: "#ffa940", buffer: "#61dd99", pusat: "#355ff3" };

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
}

function esriSource(service, attribution) {
  return {
    type: "raster",
    tiles: [`${ESRI_TILES}/${service}/MapServer/tile/{z}/{y}/{x}`],
    tileSize: 256,
    maxzoom: 16,
    attribution
  };
}

function buildMapStyle(theme, { satelliteOnly = false } = {}) {
  const style = {
    version: 8,
    projection: { type: "globe" },
    sources: { satellite: esriSource("World_Imagery", "Citra © Esri, Maxar, Earthstar Geographics") },
    layers: [{ id: "satellite", type: "raster", source: "satellite", paint: { "raster-opacity": satelliteOnly ? 1 : SATELLITE_FADE } }]
  };
  if (satelliteOnly) return style;

  const basemaps = {
    "dark-base": "Canvas/World_Dark_Gray_Base",
    "dark-ref": "Canvas/World_Dark_Gray_Reference",
    "light-base": "Canvas/World_Light_Gray_Base",
    "light-ref": "Canvas/World_Light_Gray_Reference"
  };
  Object.entries(basemaps).forEach(([id, service]) => {
    style.sources[id] = esriSource(service, "Basemap © Esri");
    const visible = id.startsWith("light") === (theme === "light");
    style.layers.push({
      id,
      type: "raster",
      source: id,
      layout: { visibility: visible ? "visible" : "none" },
      paint: { "raster-opacity": BASEMAP_FADE }
    });
  });
  return style;
}

// Zoom agar seluruh globe muat di dalam elemen. Diameter teoretis = 512 × 2^zoom / π piksel,
// tetapi siluet bola tampak ±80% karena perspektif kamera 3D.
const GLOBE_PERSPECTIVE = 0.8;
function globeZoomFor(el, fill = 0.86) {
  const size = Math.max(Math.min(el.clientWidth, el.clientHeight), 120) * fill;
  return Math.log2((size * Math.PI) / (512 * GLOBE_PERSPECTIVE));
}

// Zoom agar rentang bujur/lintang tertentu muat (dihitung manual; fitBounds kurang akurat di proyeksi globe)
function zoomForSpan(el, spanLng, spanLat) {
  const zx = Math.log2(el.clientWidth / ((spanLng / 360) * 512));
  const zy = Math.log2(el.clientHeight / ((spanLat / 360) * 512));
  return Math.min(zx, zy);
}

// Atribusi ringkas MapLibre terbuka saat awal; tutup agar tidak menutupi peta (tetap bisa dibuka lewat ikon "i")
function collapseAttribution(map) {
  const attrib = map.getContainer().querySelector(".maplibregl-ctrl-attrib");
  if (attrib) {
    attrib.classList.remove("maplibregl-compact-show");
    attrib.removeAttribute("open");
  }
}

function showMapError(el, err) {
  console.warn("Peta tidak dapat dimuat:", err);
  el.innerHTML = `<div class="map-error">Peta interaktif tidak dapat dimuat (butuh WebGL & koneksi internet ke CDN).</div>`;
}

function initMap() {
  const el = document.getElementById("district-map");
  if (!el) return;
  try {
    mapInstance = new maplibregl.Map({
      container: el,
      style: buildMapStyle(document.body.getAttribute("data-theme") || "dark"),
      center: [117, -2],
      zoom: 1.2,
      minZoom: 0.5,
      maxZoom: 16,
      attributionControl: false
    });
  } catch (err) {
    mapInstance = null;
    showMapError(el, err);
    return;
  }

  mapInstance.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  mapInstance.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
  // Peta dibuat saat view dasbor masih tersembunyi; sesuaikan ukuran setiap kali kontainer berubah
  new ResizeObserver(() => mapInstance.resize()).observe(el);

  mapInstance.on("load", () => {
    mapInstance.addSource("corridors", {
      type: "geojson",
      data: {
        type: "FeatureCollection",
        features: LOGISTICS_CORRIDORS.map(c => ({
          type: "Feature",
          properties: { name: c.name, color: c.color },
          geometry: { type: "LineString", coordinates: [c.from, c.to] }
        }))
      }
    });
    mapInstance.addLayer({
      id: "corridors",
      type: "line",
      source: "corridors",
      layout: { "line-cap": "round" },
      paint: { "line-color": ["get", "color"], "line-width": 2.5, "line-opacity": 0.9, "line-dasharray": [2, 2] }
    });
    mapInstance.on("click", "corridors", e => {
      new maplibregl.Popup()
        .setLngLat(e.lngLat)
        .setHTML(`<b>${escapeHtml(e.features[0].properties.name)}</b><br><small>Jalur distribusi logistik bencana aktif</small>`)
        .addTo(mapInstance);
    });
    mapInstance.on("mouseenter", "corridors", () => (mapInstance.getCanvas().style.cursor = "pointer"));
    mapInstance.on("mouseleave", "corridors", () => (mapInstance.getCanvas().style.cursor = ""));

    setMapViewMode(currentMapViewMode, { animate: false });
    collapseAttribution(mapInstance);
  });
}

function addMapMarker(lngLat, element, popupHtml) {
  const marker = new maplibregl.Marker({ element })
    .setLngLat(lngLat)
    .setPopup(new maplibregl.Popup({ offset: 12, maxWidth: "260px" }).setHTML(popupHtml))
    .addTo(mapInstance);
  mapMarkers.push(marker);
}

function dotElement(color, size = 14) {
  const el = document.createElement("div");
  el.className = "map-dot-marker";
  el.style.cssText = `width:${size}px;height:${size}px;background:${color};box-shadow:0 0 12px ${color};`;
  return el;
}

function renderNetworkMarkers() {
  FALLBACK_DATA.nationalHubs.forEach(hub => {
    const color = HUB_PIN[hub.type] || HUB_PIN.pusat;
    addMapMarker([hub.lng, hub.lat], dotElement(color), `
      <div class="map-popup">
        <strong style="color:${color};">${escapeHtml(hub.name)}</strong>
        <span>Wilayah: <b>${escapeHtml(hub.city)}</b></span>
        <span>Status: <b>${escapeHtml(hub.status)}</b></span>
      </div>`);
  });
}

function renderDistrictMarkers() {
  const puskesmas = (liveMapData && liveMapData.puskesmas) || FALLBACK_DATA.puskesmas;
  const hotspots = (liveMapData && liveMapData.hotspots) || FALLBACK_DATA.hotspots;

  puskesmas.forEach(pkm => {
    const color = STATUS_PIN[pkm.status] || STATUS_PIN.hijau;
    const days = pkm.stockDays === null || pkm.stockDays === undefined || pkm.stockDays >= 999 ? "–" : `${pkm.stockDays} Hari`;
    addMapMarker([pkm.lng, pkm.lat], dotElement(color), `
      <div class="map-popup">
        <strong>${escapeHtml(pkm.name)}</strong>
        <span>Hari Stok: <b style="color:${color};">${days}</b> (${escapeHtml((pkm.status || "").toUpperCase())})</span>
        <span>Lead Time: <b>${pkm.leadTime} Hari</b></span>
      </div>`);
  });

  hotspots.forEach(spot => {
    const el = document.createElement("div");
    el.className = "map-fire-marker";
    el.textContent = "🔥";
    addMapMarker([spot.lng, spot.lat], el, `
      <div class="map-popup">
        <strong style="color:#ff7a45;">${escapeHtml(spot.name)}</strong>
        <small>NASA FIRMS Thermal Hotspot${spot.confidence ? ` · keyakinan ${escapeHtml(spot.confidence)}` : ""}</small>
      </div>`);
  });
}

function moveCamera(mode, animate) {
  const el = mapInstance.getContainer();
  const motion = animate && !REDUCED_MOTION;
  if (mode === "globe") {
    const view = { center: [117, -2], zoom: globeZoomFor(el), bearing: 0, pitch: 0 };
    motion ? mapInstance.flyTo({ ...view, duration: 2200 }) : mapInstance.jumpTo(view);
  } else if (mode === "indonesia") {
    const view = { center: INDONESIA_VIEW.center, zoom: zoomForSpan(el, INDONESIA_VIEW.spanLng, INDONESIA_VIEW.spanLat), bearing: 0, pitch: 0 };
    motion ? mapInstance.flyTo({ ...view, duration: 2600 }) : mapInstance.jumpTo(view);
  } else {
    motion ? mapInstance.flyTo({ ...KUBU_RAYA_VIEW, duration: 3200, essential: true }) : mapInstance.jumpTo(KUBU_RAYA_VIEW);
  }
}

window.setMapViewMode = function(mode, { animate = true } = {}) {
  currentMapViewMode = mode;

  document.querySelectorAll(".map-toggle-btn[data-map-mode]").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.mapMode === mode);
  });
  const headerTitle = document.getElementById("map-header-title");
  const hudTitle = document.getElementById("hud-mode-title");
  const hudDesc = document.getElementById("hud-network-desc");
  const local = mode === "local";
  if (headerTitle) {
    headerTitle.innerText = local
      ? "Peta Hari Stok Tersisa · Kubu Raya (Kalbar)"
      : mode === "globe" ? "Globe Jaringan Logistik Obat Bencana" : "Peta Jaringan Logistik Obat Bencana Indonesia";
  }
  if (hudTitle) hudTitle.innerText = local ? "Fokus Bencana:" : "Jaringan Nasional:";
  if (hudDesc) hudDesc.innerText = local ? "7 Puskesmas & 48 Titik Panas Karhutla" : "6 Koridor Suplai Antar-Pulau Terhubung";

  if (!mapInstance) return;
  if (!mapInstance.isStyleLoaded() || !mapInstance.getLayer("corridors")) {
    mapInstance.once("load", () => setMapViewMode(mode, { animate }));
    return;
  }

  mapMarkers.forEach(m => m.remove());
  mapMarkers = [];
  mapInstance.setLayoutProperty("corridors", "visibility", local ? "none" : "visible");
  local ? renderDistrictMarkers() : renderNetworkMarkers();
  moveCamera(mode, animate);
};

// Animasi pembuka dasbor: globe bumi -> kepulauan Indonesia
function playMapIntro() {
  if (!mapInstance || mapIntroPlayed) return;
  mapIntroPlayed = true;
  setMapViewMode("globe", { animate: false });
  setTimeout(() => {
    if (currentMapViewMode === "globe") setMapViewMode("indonesia");
  }, REDUCED_MOTION ? 0 : 900);
}

async function loadLiveMapData() {
  try {
    const [pkmRes, telRes] = await Promise.all([
      fetch(`${API_BASE_URL}/hazard/puskesmas`),
      fetch(`${API_BASE_URL}/hazard/telemetry`)
    ]);
    if (!pkmRes.ok || !telRes.ok) return;
    const pkm = await pkmRes.json();
    const tel = await telRes.json();
    liveMapData = {
      puskesmas: pkm.data.map(p => ({
        id: p.id, name: p.name, lat: p.lat, lng: p.lng, status: p.overall_status,
        stockDays: p.min_days_remaining, leadTime: p.lead_time_days
      })),
      hotspots: tel.data.active_fire_clusters
    };
    if (currentMapViewMode === "local") setMapViewMode("local", { animate: false });
  } catch (err) {
    // tetap memakai data bawaan
  }
}

// --------------------------------------------------------------------------
// Globe bumi di beranda (berputar pelan, bisa diputar dengan mouse)
// --------------------------------------------------------------------------
// Posisi label diatur agar tidak bertumpuk (Kubu Raya & Jakarta hanya ±6° terpisah)
const HERO_BEACONS = [
  { lngLat: [109.3871, -0.0682], tone: "red", label: "Kubu Raya [Kritis]", place: "label-up" },
  { lngLat: [106.8456, -6.2088], tone: "blue", label: "Hub Pusat (Jakarta)", place: "label-left" },
  { lngLat: [119.4327, -5.1477], tone: "mint", label: "Depo Makassar [Buffer]", place: "label-down" }
];

function initHeroGlobe() {
  const el = document.getElementById("hero-globe");
  if (!el) return;
  const touch = window.matchMedia("(pointer: coarse)").matches;
  try {
    heroGlobe = new maplibregl.Map({
      container: el,
      style: buildMapStyle("dark", { satelliteOnly: true }),
      center: [112, -2],
      zoom: globeZoomFor(el),
      attributionControl: false,
      scrollZoom: false,
      boxZoom: false,
      doubleClickZoom: false,
      keyboard: false,
      touchZoomRotate: false,
      dragRotate: false,
      dragPan: !touch // di layar sentuh, geser tetap untuk scroll halaman
    });
  } catch (err) {
    heroGlobe = null;
    el.classList.add("hologram-sphere"); // fallback ke hologram CSS
    return;
  }
  heroGlobe.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
  new ResizeObserver(() => {
    if (!el.clientWidth) return; // beranda sedang tersembunyi
    heroGlobe.resize();
    heroGlobe.setZoom(globeZoomFor(el));
  }).observe(el);

  heroGlobe.on("load", () => {
    HERO_BEACONS.forEach(b => {
      const node = document.createElement("div");
      node.className = `geo-beacon ${b.place}`;
      node.innerHTML = `<span class="beacon-wave ${b.tone}"></span><span class="beacon-dot ${b.tone}"></span><span class="beacon-label">${escapeHtml(b.label)}</span>`;
      new maplibregl.Marker({ element: node }).setLngLat(b.lngLat).addTo(heroGlobe);
    });
    collapseAttribution(heroGlobe);
    spinHeroGlobe();
  });

  let interacting = false;
  heroGlobe.on("mousedown", () => (interacting = true));
  heroGlobe.on("dragend", () => { interacting = false; spinHeroGlobe(); });
  heroGlobe.on("mouseup", () => { interacting = false; spinHeroGlobe(); });
  heroGlobe.on("moveend", () => spinHeroGlobe());

  function spinHeroGlobe() {
    if (REDUCED_MOTION || interacting || heroGlobe.isMoving()) return;
    const homeVisible = document.getElementById("view-home").classList.contains("active");
    if (!homeVisible || document.hidden) {
      setTimeout(spinHeroGlobe, 1000); // jeda saat beranda tidak terlihat
      return;
    }
    const center = heroGlobe.getCenter();
    center.lng -= 4; // ±90 detik per putaran, searah rotasi bumi
    heroGlobe.easeTo({ center, duration: 1000, easing: n => n });
  }
}

// ==========================================================================
// 4. MAIN VIEWS SWITCHER
// ==========================================================================
window.switchMainView = function(viewKey) {
  const views = {
    'home': 'view-home',
    'command-center': 'view-command-center',
    'posko': 'view-posko',
    'donation': 'view-donation'
  };

  const targetId = views[viewKey] || 'view-home';

  document.querySelectorAll('.page-view').forEach(v => v.classList.remove('active'));
  document.getElementById(targetId).classList.add('active');

  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.remove('active');
  });

  const activeNav = document.querySelector(`.nav-item[onclick*="${viewKey}"]`);
  if (activeNav) activeNav.classList.add('active');

  if (viewKey === 'command-center' && mapInstance) {
    setTimeout(() => {
      mapInstance.resize();
      playMapIntro();
    }, 200);
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
};

// ==========================================================================
// 5. MEDICINE TABLE & PREDICTION CHART
// ==========================================================================
function loadMedicineTable(medicines) {
  const tbody = document.getElementById("medicine-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  medicines.forEach(m => {
    const tr = document.createElement("tr");

    let statusBadgeClass = "hijau";
    let statusText = "AMAN";
    if (m.status === "merah") {
      statusBadgeClass = "merah";
      statusText = "KRITIS";
    } else if (m.status === "kuning") {
      statusBadgeClass = "kuning";
      statusText = "WASPADA";
    }

    tr.innerHTML = `
      <td class="drug-title">
        <strong>${m.name}</strong>
        <span>${m.form}</span>
      </td>
      <td class="text-right" style="font-family: var(--font-mono); font-weight: 700;">${m.need14.toLocaleString()}</td>
      <td class="text-right" style="font-family: var(--font-mono); font-weight: 700;">${m.stock.toLocaleString()}</td>
      <td class="text-center">
        <span class="days-val ${m.status === 'merah' ? 'text-red' : m.status === 'kuning' ? 'text-orange' : 'text-mint'}">
          ${m.days} hr
        </span>
      </td>
      <td class="text-center">
        <span class="badge-status ${statusBadgeClass}">${statusText}</span>
      </td>
      <td class="col-detail-only" style="font-size: 11px; color: var(--color-white-dim);">${m.action}</td>
    `;
    tbody.appendChild(tr);
  });
}

function initISPAChart(trendData) {
  const chartEl = document.getElementById("ispa-chart");
  if (!chartEl) return;
  const ctx = chartEl.getContext("2d");

  ispaChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: trendData.labels,
      datasets: [
        {
          label: "Kasus Aktual Riil",
          data: trendData.actual,
          borderColor: "#61dd99",
          backgroundColor: "#61dd99",
          borderWidth: 3,
          pointRadius: 4,
          pointHoverRadius: 6,
          tension: 0.25
        },
        {
          label: "Prediksi Median P50",
          data: trendData.p50,
          borderColor: "#355ff3",
          borderDash: [5, 5],
          borderWidth: 2,
          pointRadius: 3,
          tension: 0.25
        },
        {
          label: "Batas Atas P90 (Safety Stock)",
          data: trendData.p90,
          borderColor: "rgba(53, 95, 243, 0.4)",
          backgroundColor: "rgba(53, 95, 243, 0.15)",
          fill: "+1",
          borderWidth: 1,
          pointRadius: 0,
          tension: 0.25
        },
        {
          label: "Batas Bawah P10",
          data: trendData.p10,
          borderColor: "rgba(53, 95, 243, 0.4)",
          fill: false,
          borderWidth: 1,
          pointRadius: 0,
          tension: 0.25
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "rgba(255, 255, 255, 0.55)", font: { family: "JetBrains Mono", size: 10 } }
        },
        y: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "rgba(255, 255, 255, 0.55)", font: { family: "JetBrains Mono", size: 10 } },
          title: { display: true, text: "Kasus ISPA / Minggu", color: "rgba(255, 255, 255, 0.4)", font: { size: 10 } }
        }
      }
    }
  });
}

// Handle Mutation Approval
window.handleRedistributionAction = async function(id, action) {
  const btnApprove = document.getElementById("btn-approve-mutation");
  const btnReject = document.getElementById("btn-reject-mutation");

  try {
    await fetch(`${API_BASE_URL}/redistribution/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        suggestion_id: id,
        action: action,
        pharmacist_name: "Apt. Mohammad Rifqi Faiz"
      })
    });
  } catch (e) {
    // Client-side simulation
  }

  if (action === "approve") {
    btnApprove.disabled = true;
    btnApprove.innerHTML = "✓ Mutasi Resmi Disetujui (Surat Terbit)";
    btnApprove.style.background = "#61dd99";
    btnApprove.style.color = "#060b18";
    btnReject.style.display = "none";
    showToast("Surat Mutasi Terbit: 60 Canister Salbutamol dikirim ke Puskesmas Sungai Raya.");
  } else {
    btnReject.disabled = true;
    btnReject.innerText = "Ditolak oleh Apoteker";
    btnApprove.style.display = "none";
    showToast("Usulan mutasi obat ditolak untuk disesuaikan.");
  }
};

// Calculate Posko Kit
window.calculatePoskoKit = function() {
  const disasterEl = document.getElementById("posko-disaster");
  if (!disasterEl) return;
  const disaster = disasterEl.value;
  const total = parseInt(document.getElementById("posko-total").value) || 500;
  const days = parseInt(document.getElementById("posko-days").value) || 14;
  const balitaPct = parseFloat(document.getElementById("posko-balita").value) || 15;
  const elderlyPct = parseFloat(document.getElementById("posko-elderly").value) || 12;

  const balitaCount = Math.round(total * (balitaPct / 100));
  const elderlyCount = Math.round(total * (elderlyPct / 100));
  const adultCount = Math.max(0, total - balitaCount - elderlyCount);

  const tbody = document.getElementById("posko-kit-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  const items = [];

  if (disaster === "karhutla") {
    items.push({
      name: "Salbutamol Inhaler 100 mcg",
      cat: "Respiratorik & Asma Akut",
      qty: Math.max(8, Math.round((balitaCount * 0.08 + elderlyCount * 0.12) * (days / 7))),
      unit: "Canister 200 dosis",
      note: "Pelega bronkospasme akut akibat asap partikulat PM2.5."
    });
    items.push({
      name: "Parasetamol Sirup 120 mg/5 ml",
      cat: "Pediatrik (Balita)",
      qty: Math.max(12, Math.round(balitaCount * 0.35 * (days / 7))),
      unit: "Botol 60 ml",
      note: "Demam & nyeri balita posko. Dosis 10-15 mg/kgBB."
    });
    items.push({
      name: "Parasetamol Tablet 500 mg",
      cat: "Dewasa & Geriatri",
      qty: Math.max(200, Math.round((adultCount + elderlyCount) * 2.5 * days)),
      unit: "Tablet",
      note: "Antipiretik/analgesik lini pertama penanganan gejala ISPA."
    });
    items.push({
      name: "Air Mata Buatan (Artificial Tears)",
      cat: "Oftalmologi",
      qty: Math.max(15, Math.round(total * 0.18 * (days / 7))),
      unit: "Botol 5 ml",
      note: "Mengatasi iritasi konjungtiva dan mata perih akibat jelaga asap."
    });
    items.push({
      name: "Masker Respirator N95",
      cat: "Alat Pelindung Diri",
      qty: Math.round(total * 2 * (days / 7)),
      unit: "Pcs",
      note: "Filtrasi partikel berbahaya bagi balita, lansia & komorbid."
    });
  } else if (disaster === "banjir") {
    items.push({
      name: "Oralit Sachet 200 ml",
      cat: "Rehidrasi Oral",
      qty: Math.round(total * 3 * (days / 5)),
      unit: "Sachet",
      note: "Pencegahan & koreksi dehidrasi diare posko banjir."
    });
    items.push({
      name: "Zinc Tablet Dispersibel 20 mg",
      cat: "Pediatrik Diare",
      qty: balitaCount * 10,
      unit: "Tablet",
      note: "Suplementasi wajib diare anak selama 10 hari berturut-turut."
    });
    items.push({
      name: "Krim Mikonazol Nitrat 2%",
      cat: "Dermatologi",
      qty: Math.round(total * 0.2 * (days / 7)),
      unit: "Tube 10 g",
      note: "Mengatasi infeksi jamur kulit akibat kontak genangan banjir."
    });
  } else {
    items.push({
      name: "Kassa Steril & Perban Elastis",
      cat: "Trauma & Luka",
      qty: Math.round(total * 0.8),
      unit: "Roll / Box",
      note: "Balut luka & fiksasi fraktur darurat korban gempa."
    });
    items.push({
      name: "Povidone Iodine 10%",
      cat: "Antiseptik",
      qty: Math.round(total * 0.1),
      unit: "Botol 300 ml",
      note: "Antiseptik desinfeksi luka robek & lecet."
    });
  }

  items.forEach(it => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${it.name}</strong></td>
      <td><span class="badge-tech" style="color:var(--color-primary); background:var(--color-primary-dim); padding:2px 6px; border-radius:4px; font-size:10px;">${it.cat}</span></td>
      <td class="text-right" style="font-family: var(--font-mono); font-size: 14px; font-weight: 700;">${it.qty.toLocaleString()}</td>
      <td style="font-family: var(--font-mono); color: var(--color-white-dim);">${it.unit}</td>
      <td style="font-size: 11px; color: var(--color-white-dim);">${it.note}</td>
    `;
    tbody.appendChild(tr);
  });
};

// Initialize Donation Sample Rows
function initDonationRows() {
  const tbody = document.getElementById("donation-tbody");
  if (!tbody) return;
  tbody.innerHTML = `
    <tr>
      <td><strong>Salbutamol Inhaler 100 mcg</strong></td>
      <td style="font-family: var(--font-mono); font-weight:700;">120</td>
      <td>Canister</td>
      <td style="font-family: var(--font-mono);">2027-11-30</td>
      <td>NGO Peduli Sehat</td>
      <td><span class="badge-status hijau">AMAN (&gt; 12 Bln)</span></td>
      <td><span class="badge-status hijau">PRIORITAS TINGGI</span></td>
      <td style="color: var(--color-mint); font-weight: 600;">DITERIMA (Masuk Stok Posko)</td>
    </tr>
    <tr>
      <td><strong>Amoksisilin Kapsul 500 mg</strong></td>
      <td style="font-family: var(--font-mono); font-weight:700;">500</td>
      <td>Kapsul</td>
      <td style="font-family: var(--font-mono);">2028-04-15</td>
      <td>Donatur Yayasan ABC</td>
      <td><span class="badge-status hijau">AMAN</span></td>
      <td><span class="badge-status merah">TIDAK SESUAI</span></td>
      <td style="color: var(--status-red); font-size: 11px;">PERINGATAN: ISPA akibat asap karhutla bukan indikasi antibiotik rutin (Rasionalitas Obat). Simpan di Instalasi Farmasi.</td>
    </tr>
    <tr>
      <td><strong>Parasetamol Tablet 500 mg</strong></td>
      <td style="font-family: var(--font-mono); font-weight:700;">300</td>
      <td>Tablet</td>
      <td style="font-family: var(--font-mono);">2026-11-20</td>
      <td>Komunitas Relawan X</td>
      <td><span class="badge-status merah">ED DEKAT (&lt; 2 Bln)</span></td>
      <td><span class="badge-status hijau">SESUAI</span></td>
      <td style="color: var(--status-red); font-weight: 600;">TOLAK DONASI: Menyalahi Pedoman WHO (&lt; 6 bulan sisa simpan).</td>
    </tr>
  `;
}

window.addDonationRow = function() {
  const drugName = prompt("Masukkan nama obat donasi:", "Oralit Sachet 200 ml");
  if (!drugName) return;
  const qty = prompt("Masukkan jumlah:", "200");
  const exp = prompt("Masukkan perkiraan ED (YYYY-MM-DD):", "2027-08-30");

  const tbody = document.getElementById("donation-tbody");
  if (!tbody) return;
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><strong>${drugName}</strong></td>
    <td style="font-family: var(--font-mono); font-weight:700;">${qty || 100}</td>
    <td>Unit</td>
    <td style="font-family: var(--font-mono);">${exp}</td>
    <td>Input Lapangan Petugas</td>
    <td><span class="badge-status hijau">AMAN</span></td>
    <td><span class="badge-status hijau">DITERIMA</span></td>
    <td style="color: var(--color-mint);">Tervalidasi oleh Apoteker Posko</td>
  `;
  tbody.prepend(tr);
  showToast(`Obat donasi '${drugName}' berhasil ditambahkan ke daftar verifikasi.`);
};

// Toast notification helper
function showToast(msg) {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `
    <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2.5" fill="none"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
    <span>${msg}</span>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4500);
}

// Background Wave Animation
function initCyberWavesCanvas() {
  const canvas = document.getElementById("cyber-waves-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  let width = (canvas.width = window.innerWidth);
  let height = (canvas.height = window.innerHeight);

  window.addEventListener("resize", () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  let step = 0;

  function renderWave() {
    ctx.clearRect(0, 0, width, height);
    step += 0.012;

    const isLight = document.body.getAttribute("data-theme") === "light";
    const lineAlpha = isLight ? 0.22 : 0.45;

    const lines = [
      { color: `rgba(53, 95, 243, ${lineAlpha})`, speed: 0.8, amp: 50, freq: 0.002, yOffset: height * 0.45 },
      { color: `rgba(97, 221, 153, ${lineAlpha * 0.8})`, speed: 1.1, amp: 40, freq: 0.0025, yOffset: height * 0.48 },
      { color: `rgba(53, 95, 243, ${lineAlpha * 0.6})`, speed: 0.6, amp: 60, freq: 0.0018, yOffset: height * 0.52 }
    ];

    lines.forEach(line => {
      ctx.beginPath();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = line.color;

      for (let x = 0; x <= width; x += 10) {
        const y = line.yOffset + Math.sin(x * line.freq + step * line.speed) * line.amp * Math.sin(step * 0.5);
        if (x === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    });

    requestAnimationFrame(renderWave);
  }

  renderWave();
}

async function checkBackendHealth() {
  const pill = document.getElementById("backend-status-pill");
  const healthUrl = (typeof window !== "undefined" && window.location.origin && !window.location.origin.startsWith("file:") && !window.location.origin.includes("localhost") && !window.location.origin.includes("127.0.0.1"))
    ? `${window.location.origin}/health`
    : "http://localhost:8000/health";

  try {
    const res = await fetch(healthUrl, { method: "GET" });
    if (res.ok) {
      if (pill) pill.innerHTML = "Backend: FastAPI Live Terhubung";
      loadLiveMapData();
    }
  } catch (err) {
    if (pill) pill.innerHTML = "Backend: Standalone (Data Sintetis)";
  }
}
