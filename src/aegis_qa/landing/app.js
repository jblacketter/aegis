/* Aegis Landing Page — fetch live data and render UI */

(function () {
  "use strict";

  const API_BASE = window.location.origin;

  async function fetchJSON(path) {
    const resp = await fetch(API_BASE + path);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  }

  function statusBadge(status) {
    const cls = {
      healthy: "status-healthy",
      unhealthy: "status-unhealthy",
      unreachable: "status-unreachable",
    }[status] || "status-unknown";
    return `<span class="status-badge ${cls}">${status}</span>`;
  }

  function renderToolCard(tool, serviceInfo) {
    const status = serviceInfo ? serviceInfo.status : "unknown";
    const features = (tool.features || [])
      .map((f) => `<span class="feature-tag">${f}</span>`)
      .join("");

    return `
      <div class="tool-card">
        <div class="tool-card-header">
          <span class="tool-card-name">${tool.name}</span>
          ${statusBadge(status)}
        </div>
        <p class="tool-card-desc">${tool.description}</p>
        <div class="tool-card-features">${features}</div>
      </div>
    `;
  }

  function renderWorkflow(key) {
    return `
      <div class="workflow-card">
        <div class="workflow-key">${key}</div>
      </div>
    `;
  }

  async function init() {
    try {
      const [portfolio, services] = await Promise.all([
        fetchJSON("/api/portfolio"),
        fetchJSON("/api/services"),
      ]);

      // Build service lookup by key
      const serviceMap = {};
      for (const svc of services) {
        serviceMap[svc.key] = svc;
      }

      // Render tool cards
      const toolsGrid = document.getElementById("tools-grid");
      if (portfolio.tools && portfolio.tools.length > 0) {
        toolsGrid.innerHTML = portfolio.tools
          .map((t) => renderToolCard(t, serviceMap[t.key]))
          .join("");
      } else {
        toolsGrid.innerHTML = "<p>No tools configured.</p>";
      }

      // Render workflows
      const workflowsList = document.getElementById("workflows-list");
      if (portfolio.workflows && portfolio.workflows.length > 0) {
        workflowsList.innerHTML = portfolio.workflows
          .map((w) => renderWorkflow(w))
          .join("");
      } else {
        workflowsList.innerHTML = "<p>No workflows configured.</p>";
      }
    } catch (err) {
      console.error("Failed to load Aegis data:", err);
      const toolsGrid = document.getElementById("tools-grid");
      toolsGrid.innerHTML =
        '<p class="loading-placeholder">Could not connect to Aegis API.</p>';
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
