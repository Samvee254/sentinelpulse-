// Change this if your API URL is ever different.
const API_BASE = "https://sentinelpulse-api-v8sz.onrender.com";

// ---- First-visit intro ----
const introOverlay = document.getElementById("intro-overlay");
const introDismiss = document.getElementById("intro-dismiss");

if (localStorage.getItem("sp_intro_seen")) {
  introOverlay.classList.add("hidden");
}

introDismiss.addEventListener("click", () => {
  introOverlay.classList.add("hidden");
  localStorage.setItem("sp_intro_seen", "1");
});

// ---- Tab switching ----
const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = document.querySelectorAll(".tab-panel");

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabButtons.forEach((b) => b.classList.remove("active"));
    tabPanels.forEach((p) => p.classList.remove("active"));

    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");

    if (btn.dataset.tab === "alerts-tab") {
      loadAlerts();
    }
  });
});

// ---- Check a link ----
const checkForm = document.getElementById("check-form");
const checkResult = document.getElementById("check-result");

checkForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = document.getElementById("check-input").value.trim();
  if (!url) return;

  checkResult.innerHTML = '<div class="spinner"></div>';
  const submitBtn = checkForm.querySelector("button");
  submitBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/urls/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    const data = await res.json();
    renderCheckResult(data);
  } catch (err) {
    checkResult.innerHTML = `<p class="error-state">Couldn't check this link right now. ${err.message}</p>`;
  } finally {
    submitBtn.disabled = false;
  }
});

function riskTier(score) {
  if (score >= 70) return { tier: "high", label: "High risk" };
  if (score >= 30) return { tier: "medium", label: "Use caution" };
  return { tier: "low", label: "Looks low risk" };
}

function renderCheckResult(data) {
  const { tier, label } = riskTier(data.risk_score);
  const reasons = (data.reasons || [])
    .map((r) => `<li>${escapeHtml(r)}</li>`)
    .join("");

  checkResult.innerHTML = `
    <div class="result-card risk-${tier}">
      <p class="result-status">${escapeHtml(data.domain)}</p>
      <p class="result-score">${Math.round(data.risk_score)}/100</p>
      <p class="result-status">${label} -- ${escapeHtml(data.status)}</p>
      ${reasons ? `<ul class="reason-list">${reasons}</ul>` : ""}
    </div>
  `;
}

// ---- Alerts feed ----
const alertsList = document.getElementById("alerts-list");

async function loadAlerts() {
  alertsList.innerHTML = '<div class="spinner"></div>';
  try {
    const res = await fetch(`${API_BASE}/alerts/`);
    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    const alerts = await res.json();

    if (!alerts.length) {
      alertsList.innerHTML = '<p class="empty-state">No alerts yet. Check back soon.</p>';
      return;
    }

    alertsList.innerHTML = alerts.map(renderAlertCard).join("");
  } catch (err) {
    alertsList.innerHTML = `<p class="error-state">Couldn't load alerts. ${err.message}</p>`;
  }
}

function renderAlertCard(alert) {
  const sev = (alert.severity || "low").toLowerCase();
  const when = new Date(alert.published_at).toLocaleString();
  return `
    <div class="alert-card sev-${sev}">
      <p class="alert-title">${escapeHtml(alert.title)}</p>
      <p class="alert-message">${escapeHtml(alert.message)}</p>
      <p class="alert-meta">${sev}${alert.region ? " - " + escapeHtml(alert.region) : ""} - ${when}</p>
    </div>
  `;
}

// ---- Report a scam ----
const reportForm = document.getElementById("report-form");
const reportResult = document.getElementById("report-result");

reportForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    url: document.getElementById("report-url").value.trim() || null,
    phone_number: document.getElementById("report-phone").value.trim() || null,
    description: document.getElementById("report-description").value.trim(),
  };

  reportResult.innerHTML = '<div class="spinner"></div>';
  const submitBtn = reportForm.querySelector("button");
  submitBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/reports/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error(`Server returned ${res.status}`);

    reportResult.innerHTML = '<p class="result-card">Thank you. Your report has been submitted.</p>';
    reportForm.reset();
  } catch (err) {
    reportResult.innerHTML = `<p class="error-state">Couldn't submit your report. ${err.message}</p>`;
  } finally {
    submitBtn.disabled = false;
  }
});

// ---- Helpers ----
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
