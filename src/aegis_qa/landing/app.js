/* Aegis Landing Page — fetch live data with static fallback */

(function () {
  "use strict";

  var API_BASE = window.location.origin;

  // ─── Static fallback data ───
  // Rendered when the Aegis API is not running (portfolio mode).
  var STATIC_PORTFOLIO = {
    name: "Aegis",
    tagline: "The AI Quality Control Plane",
    version: "0.1.0",
    tools: [
      {
        key: "qaagent",
        name: "QA Agent",
        description:
          "AI-powered route discovery, risk analysis, test generation, and orchestration for web applications.",
        features: [
          "Route Discovery",
          "Risk Analysis",
          "Test Generation",
          "Orchestration",
        ],
        repo_url: "https://github.com/jblacketter/qaagent",
        docs_url: "",
      },
      {
        key: "bugalizer",
        name: "Bugalizer",
        description:
          "Intelligent bug triage, code localization, duplicate detection, and fix proposals powered by LLMs.",
        features: [
          "Bug Triage",
          "Code Localization",
          "Duplicate Detection",
          "Fix Proposals",
        ],
        repo_url: "https://github.com/jblacketter/bugalizer",
        docs_url: "",
      },
    ],
    workflows: ["full_pipeline"],
  };

  var STATIC_WORKFLOWS = {
    full_pipeline: {
      name: "Full QA Pipeline",
      steps: [
        { type: "discover", service: "qaagent" },
        { type: "test", service: "qaagent" },
        { type: "submit_bugs", service: "bugalizer" },
      ],
    },
  };

  // ─── Helpers ───

  function fetchJSON(path) {
    return fetch(API_BASE + path).then(function (resp) {
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      return resp.json();
    });
  }

  function statusBadge(status) {
    var cls =
      {
        healthy: "status-healthy",
        unhealthy: "status-unhealthy",
        unreachable: "status-unreachable",
        offline: "status-offline",
      }[status] || "status-unknown";
    return '<span class="status-badge ' + cls + '">' + status + "</span>";
  }

  // ─── Renderers ───

  function renderToolCard(tool, serviceInfo) {
    var status = serviceInfo ? serviceInfo.status : "offline";

    var features = (tool.features || [])
      .map(function (f) {
        return '<span class="feature-tag">' + f + "</span>";
      })
      .join("");

    var links = "";
    if (tool.repo_url) {
      links +=
        '<a href="' +
        tool.repo_url +
        '" class="tool-link" target="_blank" rel="noopener">GitHub</a>';
    }
    if (tool.docs_url) {
      links +=
        '<a href="' +
        tool.docs_url +
        '" class="tool-link" target="_blank" rel="noopener">Docs</a>';
    }

    var linksSection = links
      ? '<div class="tool-card-links">' + links + "</div>"
      : "";

    return (
      '<div class="tool-card">' +
      '<div class="tool-card-header">' +
      '<span class="tool-card-name">' +
      tool.name +
      "</span>" +
      statusBadge(status) +
      "</div>" +
      '<p class="tool-card-desc">' +
      tool.description +
      "</p>" +
      '<div class="tool-card-features">' +
      features +
      "</div>" +
      linksSection +
      "</div>"
    );
  }

  function renderWorkflowCard(key, workflowData) {
    var name = workflowData ? workflowData.name : key;
    var steps = workflowData ? workflowData.steps : [];

    var stepsHtml = steps
      .map(function (s, i) {
        var arrow =
          i < steps.length - 1
            ? ' <span class="workflow-step-arrow">&rarr;</span> '
            : "";
        return (
          '<span class="workflow-step">' + s.type + "</span>" + arrow
        );
      })
      .join("");

    return (
      '<div class="workflow-card">' +
      '<div class="workflow-header">' +
      '<span class="workflow-name">' +
      name +
      "</span>" +
      '<span class="workflow-key">' +
      key +
      "</span>" +
      "</div>" +
      '<div class="workflow-steps">' +
      stepsHtml +
      "</div>" +
      "</div>"
    );
  }

  // ─── Render page ───

  function renderPage(portfolio, services, workflows) {
    var serviceMap = {};
    if (services) {
      services.forEach(function (svc) {
        serviceMap[svc.key] = svc;
      });
    }

    // Update stats
    var toolCount = document.getElementById("tool-count");
    var workflowCount = document.getElementById("workflow-count");
    if (toolCount) toolCount.textContent = portfolio.tools.length;
    if (workflowCount) workflowCount.textContent = portfolio.workflows.length;

    // Render tool cards
    var toolsGrid = document.getElementById("tools-grid");
    if (portfolio.tools && portfolio.tools.length > 0) {
      toolsGrid.innerHTML = portfolio.tools
        .map(function (t) {
          return renderToolCard(t, serviceMap[t.key]);
        })
        .join("");
    } else {
      toolsGrid.innerHTML = "<p>No tools configured.</p>";
    }

    // Render workflows
    var workflowsList = document.getElementById("workflows-list");
    if (portfolio.workflows && portfolio.workflows.length > 0) {
      workflowsList.innerHTML = portfolio.workflows
        .map(function (w) {
          return renderWorkflowCard(w, workflows[w]);
        })
        .join("");
    } else {
      workflowsList.innerHTML = "<p>No workflows configured.</p>";
    }
  }

  // ─── Init ───

  function init() {
    // Try live API first, fall back to static data
    Promise.all([fetchJSON("/api/portfolio"), fetchJSON("/api/services")])
      .then(function (results) {
        renderPage(results[0], results[1], STATIC_WORKFLOWS);
      })
      .catch(function () {
        // API not available — render with static fallback
        renderPage(STATIC_PORTFOLIO, null, STATIC_WORKFLOWS);
      });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
