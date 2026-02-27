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

  function relativeTime(isoString) {
    if (!isoString) return "";
    var now = new Date();
    var then = new Date(isoString);
    var diffMs = now - then;
    var diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return diffSec + "s ago";
    var diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return diffMin + "m ago";
    var diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return diffHr + "h ago";
    var diffDay = Math.floor(diffHr / 24);
    return diffDay + "d ago";
  }

  function formatDuration(ms) {
    if (ms == null) return "";
    if (ms < 1000) return Math.round(ms) + "ms";
    return (ms / 1000).toFixed(1) + "s";
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

  function renderRunRow(run) {
    var statusCls = run.success ? "run-status-pass" : "run-status-fail";
    var statusText = run.success ? "pass" : "fail";

    return (
      '<div class="run-row">' +
      '<span class="run-status ' + statusCls + '">' + statusText + "</span>" +
      '<span class="run-name">' + run.workflow_name + "</span>" +
      '<span class="run-meta">' +
      '<span class="run-steps">' + (run.step_count || 0) + " steps</span>" +
      "<span>" + formatDuration(run.duration_ms) + "</span>" +
      "<span>" + relativeTime(run.started_at) + "</span>" +
      "</span>" +
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

  function renderRuns(runs) {
    var runsList = document.getElementById("runs-list");
    if (!runsList) return;
    if (runs && runs.length > 0) {
      runsList.innerHTML = runs.map(renderRunRow).join("");
    } else {
      runsList.innerHTML =
        '<p class="runs-empty">No execution history available.</p>';
    }
  }

  var EVENT_ICONS = {
    "workflow.started": "▶",
    "step.completed": "✓",
    "workflow.completed": "✔",
    "failure.detected": "✗",
  };

  function renderEventRow(evt) {
    var icon = EVENT_ICONS[evt.event_type] || "•";
    var isFailure = evt.event_type === "failure.detected" ||
      (evt.data && evt.data.success === false);
    var iconCls = isFailure ? "event-icon-fail" : "event-icon-ok";

    return (
      '<div class="event-row">' +
      '<span class="event-icon ' + iconCls + '">' + icon + "</span>" +
      '<span class="event-type">' + evt.event_type + "</span>" +
      '<span class="event-workflow">' + evt.workflow_name + "</span>" +
      '<span class="event-time">' + relativeTime(evt.timestamp) + "</span>" +
      "</div>"
    );
  }

  function renderEvents(events) {
    var eventsList = document.getElementById("events-list");
    if (!eventsList) return;
    if (events && events.length > 0) {
      eventsList.innerHTML = events.map(renderEventRow).join("");
    } else {
      eventsList.innerHTML =
        '<p class="events-empty">No recent events.</p>';
    }
  }

  function buildWorkflowMap(workflowList) {
    var map = {};
    workflowList.forEach(function (wf) {
      map[wf.key] = wf;
    });
    return map;
  }

  // ─── Init ───

  function init() {
    // Try live API first, fall back to static data
    Promise.all([
      fetchJSON("/api/portfolio"),
      fetchJSON("/api/services"),
      fetchJSON("/api/workflows"),
    ])
      .then(function (results) {
        var workflows = buildWorkflowMap(results[2]);
        renderPage(results[0], results[1], workflows);
      })
      .catch(function () {
        // API not available — render with static fallback
        renderPage(STATIC_PORTFOLIO, null, STATIC_WORKFLOWS);
      });

    // Fetch recent runs (separate call — graceful failure)
    fetchJSON("/api/history")
      .then(function (runs) {
        renderRuns(runs);
      })
      .catch(function () {
        // No history available — leave default "no history" message
      });

    // Fetch recent events (separate call — graceful failure)
    fetchJSON("/api/events?limit=5")
      .then(function (events) {
        renderEvents(events);
      })
      .catch(function () {
        // No events available — leave default message
      });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
