const byId = (id) => document.getElementById(id);
const pageNames = {
  triage: "New case",
  agents: "Agent map",
  graph: "Knowledge graph",
  parts: "Parts map",
  directives: "Airworthiness directives",
  rul: "RUL prediction",
  audit: "Audit log",
  evaluation: "Evaluation",
};
const agentStages = [
  { label: "Whisper", key: "whisper", state: "optional" },
  { label: "Triage", key: "triage", state: "keyword" },
  { label: "Retrieval", key: "retrieval", state: "stub" },
  { label: "Compliance", key: "compliance", state: "stub" },
  { label: "Predictive maint.", key: "pdm", state: "stub" },
  { label: "Draft", key: "draft", state: "stub" },
  { label: "Verifier", key: "verifier", state: "stub" },
  { label: "Approval", key: "gate", state: "held" },
];
const ataNames = {
  "27": "Flight controls",
  "28": "Fuel",
  "29": "Hydraulic power",
  "31": "Instruments",
  "32": "Landing gear",
  "34": "Navigation",
  "55": "Stabilizers",
  "71": "Power plant",
};
let activeCase = null;
let activeView = "triage";
let activeResultTab = "evidence";
let speechMode = false;
let caseOffset = 0;
const casePageSize = 50;
let caseSearchTimer = null;

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function setError(message = "") {
  const error = byId("form-error");
  error.textContent = message;
  error.hidden = !message;
}

function setView(name) {
  if (!pageNames[name]) name = "triage";
  activeView = name;
  document.querySelectorAll("[data-view-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.viewPanel !== name;
  });
  document.querySelectorAll(".nav-link").forEach((link) => {
    const selected = link.dataset.view === name;
    link.classList.toggle("active", selected);
    if (selected) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  byId("page-title").textContent = pageNames[name];
  if (name === "audit") loadAudit();
  if (name === "parts") renderParts();
  if (name === "graph") loadCaseGraph();
  if (name === "evaluation") loadEvaluation();
}

function traceMessage(result, key) {
  return (result.trace || []).find((entry) => entry.agent === key)?.msg || "Not run";
}

function renderAgents(result = null, usedSpeech = false) {
  const strip = byId("agent-strip");
  strip.replaceChildren(node("span", "agent-label", "Agents"));
  for (const stage of agentStages) {
    const chip = node("span", `agent-chip ${stage.state}`);
    const dot = node("i");
    chip.append(dot, node("span", "", stage.label));
    if (stage.key === "whisper" && usedSpeech) {
      chip.className = "agent-chip done";
      chip.title = "Voice note transcribed locally with Whisper";
    } else if (stage.key === "triage" && result) {
      chip.className = "agent-chip done";
      chip.title = traceMessage(result, stage.key);
    } else if (stage.key === "gate" && result?.outcome === "awaiting_approval") {
      chip.className = "agent-chip active";
      chip.title = traceMessage(result, stage.key);
    } else if (["retrieval", "compliance", "pdm", "draft", "verifier"].includes(stage.key) && result) {
      chip.className = "agent-chip stub";
      chip.title = traceMessage(result, stage.key);
    } else {
      chip.title = stage.state === "stub" ? "Connected in the graph, implementation pending" : stage.state;
    }
    strip.append(chip);
  }
}

function formatAta(ata) {
  if (!ata?.length) return "No ATA match";
  return ata.map(([code, name, score]) => `${code} · ${name} (${Math.round(score * 100)}%)`).join(" · ");
}

function renderSummary(result) {
  const summary = byId("result-summary");
  summary.replaceChildren();
  const topAta = result.ata?.[0];
  const symptoms = (result.entities || []).filter(([kind]) => kind === "SYMPTOM").map(([, value]) => value);
  const components = (result.entities || []).filter(([kind]) => kind === "COMPONENT").map(([, value]) => value);
  const phases = (result.entities || []).filter(([kind]) => kind === "PHASE").map(([, value]) => value);
  const rows = [
    ["Language", (result.language || "unknown").toUpperCase()],
    ["ATA ranking", topAta ? `${topAta[0]} · ${topAta[1]}` : "No match"],
    ["Symptoms", symptoms.join(", ") || "No keyword match"],
    ["Components", components.join(", ") || "No keyword match"],
    ["Flight phase", phases.join(", ") || "Not identified"],
    ["Evidence", `${result.evidence?.length || 0} validated sources`],
  ];
  for (const [label, value] of rows) {
    const cell = node("div", "summary-cell");
    cell.append(node("small", "", label), node("strong", "", value));
    summary.append(cell);
  }
}

function renderCase(result, usedSpeech = false) {
  activeCase = result;
  if (result.case_id) activeCase.case_id = result.case_id;
  byId("empty-state").hidden = true;
  byId("case-result").hidden = false;
  byId("result-ata").textContent = result.ata?.[0]
    ? `ATA ${result.ata[0][0]} · ${result.ata[0][1]}`
    : "Triage complete · no ATA match";
  byId("result-subtitle").textContent = result.case_id || "Current analysis";
  byId("case-description").textContent = result.text || "No description was saved for this case.";
  byId("case-created-at").textContent = result.created_at ? `Created ${new Date(result.created_at).toLocaleString()}` : "Creation time unavailable";
  renderAircraftContext(result.aircraft_context);
  byId("revise-case").disabled = !result.text;
  byId("export-case").disabled = false;
  const status = result.decision || result.outcome || "unknown";
  const statusPill = byId("result-status");
  statusPill.className = `status-pill status-${status.replaceAll("_", "-")}`;
  statusPill.textContent = status.replaceAll("_", " ").toUpperCase();
  byId("result-notice").textContent = status === "abstained"
    ? "ABSTAINED · No evidence-backed recommendation was produced. Retrieval and claim verification are not implemented."
    : status === "awaiting_approval"
      ? "REVIEW REQUIRED · Review supporting evidence and cited claims before recording a decision."
      : ["approve", "reject"].includes(status)
        ? `DECISION LOGGED · Reviewer decision: ${status.toUpperCase()}.`
      : "Analysis status is unavailable.";
  renderSummary(result);
  renderAgents(result, usedSpeech);
  byId("decision-actions").hidden = status !== "awaiting_approval" || Boolean(result.decision);
  activeResultTab = "evidence";
  document.querySelectorAll(".result-tab").forEach((tab) => {
    const selected = tab.dataset.resultTab === activeResultTab;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
  });
  renderResultTab(activeResultTab);
  if (result.case_id) {
    byId("language-label").textContent = (result.language || "EN").toUpperCase();
  }
}

function renderAircraftContext(context) {
  const target = byId("aircraft-context-result");
  const fields = context?.fields || {};
  const labels = { aircraft_model: "Aircraft model", aircraft_serial: "Aircraft serial / MSN", component: "Component", part_number: "Part number", component_serial: "Component serial" };
  const entries = Object.entries(labels).filter(([key]) => fields[key]);
  target.replaceChildren();
  target.hidden = false;
  target.append(node("strong", "", entries.length ? "User supplied · not verified" : "No aircraft or component details provided"));
  if (entries.length) {
    const list = node("dl", "context-result-list");
    entries.forEach(([key, label]) => list.append(node("dt", "", label), node("dd", "", fields[key])));
    target.append(list);
  }
}

function exportActiveCase() {
  if (!activeCase) return;
  const payload = {
    format: "aerosafe-case-export/v1",
    exported_at: new Date().toISOString(),
    case_id: activeCase.case_id || null,
    case: activeCase,
    limitations: [
      "ATA and entity tags are keyword-baseline signals, not verified findings.",
      "Evidence retrieval, directive applicability, and claim verification are not implemented.",
      "This export is not an approved maintenance record or maintenance instruction.",
    ],
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = node("a");
  link.href = url;
  link.download = `${activeCase.case_id || "aerosafe-case"}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function reviseActiveCase() {
  if (!activeCase?.text) return;
  byId("case-text").value = activeCase.text;
  const fields = activeCase.aircraft_context?.fields || {};
  byId("aircraft-model").value = fields.aircraft_model || "";
  byId("aircraft-serial").value = fields.aircraft_serial || "";
  byId("component-name").value = fields.component || "";
  byId("part-number").value = fields.part_number || "";
  byId("component-serial").value = fields.component_serial || "";
  byId("case-text").focus();
  byId("revise-note").textContent = "Review or edit this text, then Analyze to create a separate case. The selected case will remain unchanged.";
  byId("revise-note").hidden = false;
  byId("case-form").scrollIntoView({ behavior: "smooth", block: "center" });
}

function renderResultTab(tabName) {
  activeResultTab = tabName;
  document.querySelectorAll(".result-tab").forEach((tab) => {
    const selected = tab.dataset.resultTab === tabName;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
  });
  const content = byId("result-tab-content");
  content.replaceChildren();
  const result = activeCase;
  if (!result) {
    content.append(node("div", "data-empty", "Analyze a case to view its details."));
    return;
  }

  if (tabName === "evidence") {
    const evidence = result.evidence || [];
    if (!evidence.length) {
      content.append(node("div", "data-empty", "No evidence retrieved. The retrieval backend is not implemented; this case cannot support a recommendation."));
      return;
    }
    evidence.forEach((item) => {
      const row = node("div", "evidence-row");
      row.append(node("strong", "evidence-id", item.id || "Source"), node("span", "evidence-source", item.source || "Unknown source"), node("span", "evidence-text", item.text || "No source text"));
      content.append(row);
    });
    return;
  }

  if (tabName === "signals") {
    const signals = result.signals || [];
    if (!signals.length) {
      content.append(node("div", "data-empty", "No ATA keyword signals matched this description. This is not a finding that the aircraft has no defect."));
      return;
    }
    content.append(node("p", "signal-method-note", "Relative match share is a normalized count of matched baseline phrases. It is not probability, confidence, severity, or a diagnosis."));
    signals.forEach((signal) => {
      const card = node("article", "signal-card");
      const head = node("div", "signal-card-head");
      head.append(node("strong", "", `#${signal.rank} · ATA ${signal.ata} · ${signal.name}`), node("span", "signal-score", `${Math.round(signal.relative_match_share * 100)}% match share`));
      const meter = node("div", "signal-meter");
      const fill = node("span");
      fill.style.width = `${Math.min(100, Math.max(0, signal.relative_match_share * 100))}%`;
      meter.append(fill);
      const terms = node("div", "signal-terms");
      (signal.matched_terms || []).forEach(({ term, count }) => terms.append(node("span", "signal-term", `${term} · ${count}`)));
      card.append(head, meter, terms);
      content.append(card);
    });
    return;
  }

  if (tabName === "directives") {
    const directives = result.ad_results || [];
    if (!directives.length) {
      content.append(node("div", "data-empty", "No directives were evaluated. This does not mean that no applicable directives exist."));
      return;
    }
    directives.forEach((item) => {
      const row = node("div", "evidence-row");
      row.append(node("strong", "evidence-id", item.id || "AD"), node("span", "evidence-source", (item.status || "unknown").toUpperCase()), node("span", "evidence-text", item.text || "Directive result"));
      content.append(row);
    });
    return;
  }

  if (tabName === "rul") {
    content.append(node("div", "data-empty", result.rul ? JSON.stringify(result.rul) : "No remaining-useful-life estimate. No sensor file or RUL model is connected."));
    return;
  }

  if (tabName === "graph") {
    content.append(node("div", "data-empty", "Loading the case-local keyword graph…"));
    const caseId = result.case_id;
    if (!caseId) {
      content.replaceChildren(node("div", "data-empty", "Save a case before viewing its graph."));
      return;
    }
    request(`/cases/${encodeURIComponent(caseId)}/graph`).then((graph) => {
      if (activeResultTab !== "graph" || activeCase?.case_id !== caseId) return;
      content.replaceChildren();
      content.append(node("p", "signal-method-note", `Case-local graph · ${graph.nodes.length} nodes · ${graph.edges.length} links · source: ${graph.source}`));
      const list = node("div", "graph-preview-list");
      graph.nodes.forEach((item) => {
        const chip = node("div", `graph-preview-node ${item.kind}`);
        chip.append(node("strong", "", item.label), node("small", "", item.detail));
        list.append(chip);
      });
      content.append(list);
      const link = node("a", "graph-preview-link", "Open interactive graph view →");
      link.href = "#graph";
      content.append(link);
    }).catch((error) => {
      if (activeResultTab === "graph" && activeCase?.case_id === caseId) content.replaceChildren(node("div", "data-empty", `Graph unavailable: ${error.message}`));
    });
    return;
  }

  if (tabName === "trace") {
    const trace = result.trace || [];
    if (!trace.length) {
      content.append(node("div", "data-empty", "No agent trace recorded."));
      return;
    }
    const list = node("div", "trace-list");
    trace.forEach((entry, index) => {
      const row = node("div", "trace-item");
      row.append(node("span", "trace-time", String(index + 1).padStart(2, "0")), node("strong", "trace-agent", entry.agent || "agent"), node("span", "trace-message", entry.msg || ""));
      list.append(row);
    });
    content.append(list);
  }
}

async function loadCases(restoreLatest = false, append = false) {
  const list = byId("case-list");
  try {
    const params = new URLSearchParams({ limit: String(casePageSize), offset: String(append ? caseOffset : 0) });
    const query = byId("case-search").value.trim();
    const outcome = byId("case-status-filter").value;
    if (query) params.set("q", query);
    if (outcome) params.set("outcome", outcome);
    const cases = await request(`/cases?${params}`);
    if (!append) {
      caseOffset = 0;
      list.replaceChildren();
    }
    caseOffset += cases.length;
    byId("case-count").textContent = String(caseOffset);
    if (!caseOffset && !append) {
      const hasFilters = query || outcome;
      list.append(node("div", "case-list-empty", hasFilters ? "No cases match these filters." : "No cases yet"));
      byId("case-load-more").hidden = true;
      return;
    }
    cases.forEach((item) => {
      const ata = item.ata?.[0];
      const row = node("button", `case-row ${item.outcome || ""}${activeCase?.case_id === item.case_id ? " selected" : ""}`);
      row.type = "button";
      row.dataset.caseId = item.case_id;
      row.title = item.text || item.case_id;
      const title = node("span", "case-row-title", item.case_id);
      const timestamp = item.created_at ? new Date(item.created_at).toLocaleString() : "";
      const context = item.aircraft_context?.fields || {};
      const contextLabel = [context.aircraft_model, context.component].filter(Boolean).join(" · ");
      title.append(node("small", "", [ata ? `ATA ${ata[0]}` : "ATA —", contextLabel, timestamp].filter(Boolean).join(" · ")));
      const label = (item.outcome || "unknown").replaceAll("_", " ").toUpperCase();
      row.append(title, node("span", "case-row-status", label));
      list.append(row);
    });
    byId("case-load-more").hidden = cases.length < casePageSize;
    if (restoreLatest && !activeCase && cases.length) {
      await loadCase(cases[0].case_id);
    }
  } catch (error) {
    list.replaceChildren(node("div", "case-list-empty", `Could not load cases: ${error.message}`));
  }
}

byId("case-search").addEventListener("input", () => {
  window.clearTimeout(caseSearchTimer);
  caseSearchTimer = window.setTimeout(() => loadCases(), 250);
});
byId("case-status-filter").addEventListener("change", () => loadCases());
byId("case-load-more").addEventListener("click", () => loadCases(false, true));

async function loadCase(caseId) {
  try {
    const result = await request(`/cases/${encodeURIComponent(caseId)}`);
    result.case_id = caseId;
    renderCase(result);
    await loadCases();
    if (activeView === "graph") await loadCaseGraph(caseId);
  } catch (error) {
    setError(error.message);
  }
}

function renderWorkflow() {
  const map = byId("workflow-map");
  map.replaceChildren();
  const nodes = [
    ["01", "Whisper", "Optional · local speech model", "optional"],
    ["02", "Triage", "Keyword ATA baseline", "done"],
    ["03", "Retrieval", "Hybrid search · not implemented", "stub"],
    ["04", "Compliance", "Directive rules · not implemented", "stub"],
    ["05", "Predictive maintenance", "RUL model · not implemented", "stub"],
    ["06", "Draft", "Local recommendation model · not implemented", "stub"],
    ["07", "Verifier", "Claim support check · not implemented", "stub"],
    ["08", "Human approval", "Held while evidence is unavailable", "stub"],
  ];
  nodes.forEach(([index, title, detail, state]) => {
    const item = node("article", `workflow-node ${state}`);
    item.append(node("span", "node-index", index), node("strong", "", title), node("small", "", detail));
    map.append(item);
  });
}

function svgElement(tag, attrs = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
  return element;
}

function showGraphNode(item, graph) {
  byId("graph-selected").textContent = item.label;
  byId("graph-detail").textContent = item.detail;
  byId("graph-source").textContent = `Source: ${graph.source.replaceAll("_", " ")}`;
  document.querySelectorAll(".graph-node").forEach((nodeItem) => {
    nodeItem.classList.toggle("selected", nodeItem.dataset.nodeId === item.id);
    nodeItem.setAttribute("aria-pressed", String(nodeItem.dataset.nodeId === item.id));
  });
}

function renderCaseGraph(graph) {
  const stage = byId("graph-network");
  const empty = byId("graph-empty");
  empty.hidden = true;
  stage.replaceChildren();
  const ataNodes = graph.nodes.filter((item) => item.kind === "ata");
  const tagNodes = graph.nodes.filter((item) => item.kind !== "case" && item.kind !== "ata");
  const shownTags = tagNodes.slice(0, 8);
  const visibleNodes = [...graph.nodes.filter((item) => item.kind === "case" || item.kind === "ata"), ...shownTags];
  const height = Math.max(430, (Math.max(ataNodes.length, shownTags.length, 1) + 1) * 84);
  const positions = new Map();
  positions.set("case", { x: 145, y: height / 2 });
  ataNodes.forEach((item, index) => positions.set(item.id, { x: 450, y: ((index + 1) * height) / (ataNodes.length + 1) }));
  shownTags.forEach((item, index) => positions.set(item.id, { x: 770, y: ((index + 1) * height) / (shownTags.length + 1) }));

  const svg = svgElement("svg", {
    viewBox: `0 0 930 ${height}`,
    role: "img",
    "aria-label": `Case relationship graph with ${visibleNodes.length} nodes`,
    preserveAspectRatio: "xMidYMin meet",
  });
  const lines = svgElement("g", { class: "graph-edges" });
  for (const edge of graph.edges) {
    const source = positions.get(edge.source);
    const target = positions.get(edge.target);
    if (!source || !target) continue;
    lines.append(svgElement("line", { x1: source.x + 66, y1: source.y, x2: target.x - 74, y2: target.y }));
  }
  svg.append(lines);

  visibleNodes.forEach((item) => {
    const position = positions.get(item.id);
    const group = svgElement("g", {
      class: `graph-node graph-node-${item.kind}`,
      transform: `translate(${position.x}, ${position.y})`,
      tabindex: "0",
      role: "button",
      "aria-label": `${item.kind}: ${item.label}`,
      "aria-pressed": "false",
    });
    group.dataset.nodeId = item.id;
    group.append(svgElement("rect", { x: -70, y: -27, width: 140, height: 54, rx: 14 }));
    const label = svgElement("text", { "text-anchor": "middle", y: 4 });
    label.textContent = item.label.length > 21 ? `${item.label.slice(0, 19)}…` : item.label;
    group.append(label);
    group.addEventListener("click", () => showGraphNode(item, graph));
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        showGraphNode(item, graph);
      }
    });
    svg.append(group);
  });
  stage.append(svg);
  byId("graph-count").textContent = `${graph.nodes.length} nodes · ${graph.edges.length} links`;
  byId("graph-limitations").textContent = graph.limitations + (tagNodes.length > shownTags.length ? ` Showing ${shownTags.length} of ${tagNodes.length} keyword tags.` : "");
  showGraphNode(graph.nodes[0], graph);
}

async function loadCaseGraph(caseId = activeCase?.case_id) {
  const selector = byId("graph-case-select");
  const empty = byId("graph-empty");
  byId("graph-count").textContent = "Loading case graph…";
  try {
    const cases = await request("/cases");
    selector.replaceChildren(node("option", "", "Choose a case"));
    selector.options[0].value = "";
    cases.forEach((item) => {
      const option = node("option", "", `${item.case_id} · ${item.ata?.[0]?.[0] ? `ATA ${item.ata[0][0]}` : "No ATA match"}`);
      option.value = item.case_id;
      selector.append(option);
    });
    const selectedId = caseId || cases[0]?.case_id;
    if (!selectedId) {
      byId("graph-network").replaceChildren();
      empty.hidden = false;
      empty.replaceChildren(node("strong", "", "No cases to graph yet"), node("p", "", "Create a case from Triage to see its local ATA ranking and extracted keyword tags here."));
      byId("graph-count").textContent = "No case selected";
      byId("graph-selected").textContent = "Choose a node";
      byId("graph-detail").textContent = "The graph is built from the selected case’s triage output.";
      byId("graph-source").textContent = "No case selected";
      return;
    }
    selector.value = selectedId;
    const graph = await request(`/cases/${encodeURIComponent(selectedId)}/graph`);
    renderCaseGraph(graph);
  } catch (error) {
    byId("graph-network").replaceChildren();
    empty.hidden = false;
    empty.replaceChildren(node("strong", "", "Graph unavailable"), node("p", "", error.message));
    byId("graph-count").textContent = "Could not load graph";
  }
}

function renderRulChart(result) {
  const host = byId("rul-chart");
  host.replaceChildren();
  const width = 760;
  const height = 280;
  const pad = { top: 28, right: 26, bottom: 42, left: 56 };
  const values = result.series.map((point) => point.health_index);
  const minY = Math.min(result.threshold, ...values);
  const maxY = Math.max(1, ...values);
  const xStart = result.series[0].cycle;
  const observedEnd = result.last_cycle;
  const observedSpan = Math.max(1, observedEnd - xStart);
  const plottedForecast = Math.min(result.estimate_cycles, observedSpan * 2);
  const xEnd = observedEnd + Math.max(plottedForecast, observedSpan * 0.2);
  const x = (cycle) => pad.left + ((cycle - xStart) / Math.max(1, xEnd - xStart)) * (width - pad.left - pad.right);
  const y = (health) => pad.top + ((maxY - health) / Math.max(0.01, maxY - minY)) * (height - pad.top - pad.bottom);
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Observed health index and illustrative projected trend" });
  const thresholdY = y(result.threshold);
  svg.append(svgElement("line", { x1: pad.left, y1: thresholdY, x2: width - pad.right, y2: thresholdY, class: "rul-threshold-line" }));
  const observedPath = result.series.map((point, index) => `${index ? "L" : "M"}${x(point.cycle)},${y(point.health_index)}`).join(" ");
  svg.append(svgElement("path", { d: observedPath, class: "rul-observed-line" }));
  const lastPoint = result.series[result.series.length - 1];
  const projectionCycle = observedEnd + plottedForecast;
  const projectionHealth = Math.max(result.threshold, lastPoint.health_index + result.slope_per_cycle * plottedForecast);
  svg.append(svgElement("path", { d: `M${x(lastPoint.cycle)},${y(lastPoint.health_index)} L${x(projectionCycle)},${y(projectionHealth)}`, class: "rul-projected-line" }));
  result.series.forEach((point) => svg.append(svgElement("circle", { cx: x(point.cycle), cy: y(point.health_index), r: 4, class: "rul-point" })));
  const axis = svgElement("text", { x: pad.left, y: height - 10, class: "rul-axis-label" });
  axis.textContent = `Observed cycles ${xStart}–${observedEnd} · threshold ${result.threshold.toFixed(2)}`;
  svg.append(axis);
  host.append(svg);
  host.append(node("div", "chart-legend", "Observed series   ·   Dashed line: linear projection   ·   Threshold shown in red"));
}

async function loadEvaluation() {
  byId("evaluation-macro-f1").textContent = "Loading…";
  try {
    const result = await request("/evaluation");
    byId("evaluation-macro-f1").textContent = result.macro_f1 === null ? "—" : result.macro_f1.toFixed(3);
    byId("evaluation-accuracy").textContent = result.accuracy === null ? "—" : result.accuracy.toFixed(3);
    byId("evaluation-top3").textContent = result.top3_accuracy === null ? "—" : result.top3_accuracy.toFixed(3);
    byId("evaluation-samples").textContent = String(result.sample_count);
    byId("evaluation-sample-count").textContent = `${result.sample_count} synthetic examples`;
    byId("evaluation-warning").textContent = result.warning;
    const rows = byId("evaluation-rows");
    rows.replaceChildren();
    result.per_class.forEach((item) => {
      const row = node("tr");
      [item.ata, String(item.support), item.precision.toFixed(3), item.recall.toFixed(3), item.f1.toFixed(3)].forEach((value) => row.append(node("td", "", value)));
      rows.append(row);
    });
    const matrixHead = byId("confusion-head");
    const matrixRows = byId("confusion-rows");
    matrixHead.replaceChildren();
    matrixRows.replaceChildren();
    const matrix = result.confusion_matrix || { labels: [], rows: [] };
    const header = node("tr");
    const corner = node("th", "", "Expected ↓ / Predicted →");
    corner.scope = "col";
    header.append(corner);
    matrix.labels.forEach((label) => {
      const cell = node("th", "", label === "__no_match__" ? "No match" : label);
      cell.scope = "col";
      header.append(cell);
    });
    matrixHead.append(header);
    matrix.labels.forEach((label, rowIndex) => {
      const row = node("tr");
      const labelCell = node("th", "", label === "__no_match__" ? "No match" : label);
      labelCell.scope = "row";
      row.append(labelCell);
      matrix.rows[rowIndex].forEach((count, columnIndex) => {
        const cell = node("td", count && rowIndex === columnIndex ? "confusion-correct" : count ? "confusion-error" : "", String(count));
        cell.title = `${count} expected ${label}, predicted ${matrix.labels[columnIndex]}`;
        row.append(cell);
      });
      matrixRows.append(row);
    });
  } catch (error) {
    byId("evaluation-macro-f1").textContent = "Error";
    byId("evaluation-sample-count").textContent = error.message;
    byId("evaluation-warning").textContent = "Could not load evaluation results.";
    byId("evaluation-top3").textContent = "—";
  }
}

function renderParts() {
  const svg = `<svg viewBox="0 0 720 310" role="img" aria-label="Illustrative aircraft ATA systems map">
    <g fill="#e8e4da" stroke="#aaa491" stroke-width="2">
      <path d="M92 145 Q110 126 150 129 L267 136 L490 70 Q518 63 535 69 Q542 73 529 82 L383 143 L573 136 Q610 138 626 149 Q610 160 573 162 L383 156 L529 220 Q542 229 535 233 Q518 239 490 232 L267 166 L150 173 Q110 176 92 155Z"/>
      <path d="M311 137 L285 100 Q280 91 290 92 L333 132 M311 164 L285 202 Q280 211 290 210 L333 169" fill="#f3f0e8"/>
      <path d="M144 138 L116 113 Q109 107 114 104 L151 132 M144 164 L116 189 Q109 195 114 198 L151 170" fill="#f3f0e8"/>
      <path d="M480 96 L455 75 Q449 70 455 67 L487 89 M480 207 L455 228 Q449 233 455 236 L487 214" fill="#f3f0e8"/>
    </g>
    <g class="ata-hotspot" data-ata="71" role="button" tabindex="0" aria-label="ATA 71 Power plant"><circle cx="334" cy="111" r="15"/><text x="334" y="115" text-anchor="middle">71</text></g>
    <g class="ata-hotspot" data-ata="27" role="button" tabindex="0" aria-label="ATA 27 Flight controls"><circle cx="389" cy="92" r="15"/><text x="389" y="96" text-anchor="middle">27</text></g>
    <g class="ata-hotspot" data-ata="28" role="button" tabindex="0" aria-label="ATA 28 Fuel"><circle cx="477" cy="176" r="15"/><text x="477" y="180" text-anchor="middle">28</text></g>
    <g class="ata-hotspot" data-ata="29" role="button" tabindex="0" aria-label="ATA 29 Hydraulic power"><circle cx="342" cy="153" r="15"/><text x="342" y="157" text-anchor="middle">29</text></g>
    <g class="ata-hotspot" data-ata="31" role="button" tabindex="0" aria-label="ATA 31 Instruments"><circle cx="252" cy="151" r="15"/><text x="252" y="155" text-anchor="middle">31</text></g>
    <g class="ata-hotspot" data-ata="34" role="button" tabindex="0" aria-label="ATA 34 Navigation"><circle cx="205" cy="151" r="15"/><text x="205" y="155" text-anchor="middle">34</text></g>
    <g class="ata-hotspot" data-ata="32" role="button" tabindex="0" aria-label="ATA 32 Landing gear"><circle cx="390" cy="184" r="17"/><text x="390" y="188" text-anchor="middle">32</text></g>
    <g class="ata-hotspot" data-ata="55" role="button" tabindex="0" aria-label="ATA 55 Stabilizers"><circle cx="147" cy="151" r="15"/><text x="147" y="155" text-anchor="middle">55</text></g>
    <text x="360" y="285" text-anchor="middle" fill="#858174" font-size="11">ATA system positions shown for illustration only</text>
  </svg>`;
  byId("aircraft-map").innerHTML = svg;
  const list = byId("ata-list");
  list.replaceChildren();
  const available = activeCase?.ata?.length ? activeCase.ata : Object.entries(ataNames).map(([code, name]) => [code, name, 0]);
  available.forEach(([code, name]) => {
    const item = node("button", "ata-item", `${code} · ${name}`);
    item.type = "button";
    item.dataset.ata = code;
    item.append(node("span", "", activeCase?.ata?.some(([found]) => found === code) ? "Ranked" : "Overview"));
    list.append(item);
  });
  const first = activeCase?.ata?.[0];
  selectAta(first?.[0] || "32");
  const phases = (activeCase?.entities || []).filter(([kind]) => kind === "PHASE").map(([, value]) => value);
  byId("phase-note").textContent = phases.length ? `Keyword matches: ${phases.join(", ")}. This is not a flight-data record.` : "No phase keyword match for this case.";
}

function selectAta(code) {
  document.querySelectorAll(".ata-hotspot").forEach((spot) => spot.classList.toggle("active", spot.dataset.ata === code));
  document.querySelectorAll(".ata-item").forEach((item) => item.classList.toggle("active", item.dataset.ata === code));
  byId("part-selected").textContent = ataNames[code] ? `ATA ${code} · ${ataNames[code]}` : `ATA ${code}`;
  const ranked = activeCase?.ata?.find(([found]) => found === code);
  byId("part-detail").textContent = ranked
    ? `Keyword baseline rank: ${Math.round(ranked[2] * 100)}%. Aircraft parts, configuration and open cases are not connected.`
    : "No keyword match in the current case. Aircraft parts, configuration and open cases are not connected.";
}

async function loadAudit() {
  const banner = byId("audit-banner");
  const rows = byId("audit-rows");
  banner.textContent = "Checking chain…";
  banner.classList.remove("corrupt");
  try {
    const data = await request("/audit/records");
    banner.classList.toggle("corrupt", !data.intact);
    banner.textContent = data.intact
      ? `Chain intact · ${data.records.length} ${data.records.length === 1 ? "record" : "records"} verified`
      : `Integrity issue at record ${data.first_bad_index}`;
    rows.replaceChildren();
    if (!data.records.length) {
      const row = node("tr");
      const cell = node("td", "table-empty", "No records recorded yet.");
      cell.colSpan = 5;
      row.append(cell);
      rows.append(row);
      return;
    }
    data.records.slice().reverse().forEach((record) => {
      const row = node("tr");
      const date = record.ts ? new Date(record.ts).toLocaleString() : "—";
      [String(record.index), date, record.actor || "—", record.action || "—"].forEach((value) => row.append(node("td", "", value)));
      const hashCell = node("td");
      const hash = node("code", "", record.hash || "");
      hash.title = record.hash || "";
      hashCell.append(hash, node("small", "audit-prev", `prev ${String(record.prev_hash || "").slice(0, 10)}…`));
      row.append(hashCell);
      rows.append(row);
    });
  } catch (error) {
    banner.classList.add("corrupt");
    banner.textContent = `Audit check failed: ${error.message}`;
  }
}

async function checkHealth() {
  try {
    await request("/health");
    byId("service-label").textContent = "Local mode";
    byId("service-dot").title = "API is online";
  } catch {
    byId("service-label").textContent = "Service unavailable";
    byId("service-dot").style.background = "#bd5444";
  }
}

byId("case-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setError();
  byId("revise-note").hidden = true;
  const button = byId("analyze-button");
  const audio = byId("audio-file").files[0];
  let text = byId("case-text").value.trim();
  let usedSpeech = false;
  if (!audio && !text) {
    setError("Enter a defect description or choose a voice note.");
    byId("case-text").focus();
    return;
  }
  button.disabled = true;
  button.textContent = audio ? "Transcribing…" : "Analyzing…";
  try {
    if (audio) {
      const form = new FormData();
      form.append("file", audio);
      const transcript = await request("/transcribe", { method: "POST", body: form });
      text = [text, transcript.text].filter(Boolean).join("\n");
      usedSpeech = true;
      byId("language-label").textContent = (transcript.language || "EN/FR").toUpperCase();
      if (!text.trim()) throw new Error("No speech was recognized. Add a typed description or try another recording.");
    }
    button.textContent = "Analyzing…";
    const result = await request("/cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, aircraft_context: {
        aircraft_model: byId("aircraft-model").value,
        aircraft_serial: byId("aircraft-serial").value,
        component: byId("component-name").value,
        part_number: byId("part-number").value,
        component_serial: byId("component-serial").value,
      } }),
    });
    renderCase(result, usedSpeech);
    await loadCases();
    if (activeView !== "triage") window.location.hash = "triage";
    byId("analysis-panel").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) {
    setError(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Analyze";
  }
});

byId("unclear-button").addEventListener("click", () => {
  byId("case-text").value = "Unclear intermittent fault reported during operation.";
  byId("case-text").focus();
});

byId("audio-file").addEventListener("change", () => {
  byId("file-name").textContent = byId("audio-file").files[0]?.name || "No audio selected";
});

document.querySelectorAll("[data-input-mode]").forEach((tab) => {
  tab.addEventListener("click", () => {
    speechMode = tab.dataset.inputMode === "speak";
    document.querySelectorAll("[data-input-mode]").forEach((item) => {
      const selected = item === tab;
      item.classList.toggle("active", selected);
      item.setAttribute("aria-selected", String(selected));
    });
    byId("audio-row").hidden = !speechMode;
    if (!speechMode) {
      byId("audio-file").value = "";
      byId("file-name").textContent = "No audio selected";
    }
    byId("case-text").placeholder = speechMode
      ? "Optional: add context to the voice note…"
      : "Describe the defect, symptoms and flight phase…";
  });
});

document.querySelectorAll("[data-result-tab]").forEach((tab) => {
  tab.addEventListener("click", () => renderResultTab(tab.dataset.resultTab));
});

byId("decision-actions").addEventListener("click", async (event) => {
  const decision = event.target.dataset.decision;
  if (!decision || !activeCase?.case_id) return;
  try {
    await request(`/cases/${encodeURIComponent(activeCase.case_id)}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    });
    activeCase.decision = decision;
    byId("decision-actions").hidden = true;
    await loadCases();
  } catch (error) {
    setError(error.message);
  }
});

byId("case-list").addEventListener("click", (event) => {
  const row = event.target.closest("[data-case-id]");
  if (row) loadCase(row.dataset.caseId);
});

byId("graph-case-select").addEventListener("change", (event) => {
  if (event.target.value) loadCaseGraph(event.target.value);
});

async function analyzeSensorFile(file) {
  const error = byId("rul-error");
  error.hidden = true;
  if (!file) {
    error.textContent = "Choose a sensor CSV first.";
    error.hidden = false;
    return false;
  }
  const button = byId("rul-button");
  button.disabled = true;
  button.textContent = "Analyzing…";
  try {
    const form = new FormData();
    form.append("file", file);
    const threshold = byId("rul-threshold").value;
    const result = await request(`/rul/analyze?threshold=${encodeURIComponent(threshold)}`, { method: "POST", body: form });
    byId("rul-estimate").replaceChildren(document.createTextNode(String(result.estimate_cycles)), node("small", "", "cycles"));
    byId("rul-result-detail").textContent = `Last health ${result.last_health_index.toFixed(3)} at cycle ${result.last_cycle}. Trend ${result.slope_per_cycle.toFixed(5)} per cycle; threshold ${result.threshold.toFixed(2)}.`;
    byId("rul-method").textContent = "Illustrative linear trend";
    renderRulChart(result);
  } catch (requestError) {
    error.textContent = requestError.message;
    error.hidden = false;
    return false;
  } finally {
    button.disabled = false;
    button.textContent = "Analyze trend";
  }
  return true;
}

byId("rul-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  await analyzeSensorFile(byId("sensor-file").files[0]);
});

byId("use-rul-sample").addEventListener("click", async () => {
  const sampleButton = byId("use-rul-sample");
  sampleButton.disabled = true;
  try {
    const response = await fetch("/static/demo_sensor.csv");
    if (!response.ok) throw new Error("Could not load the sample CSV.");
    const contents = await response.blob();
    const file = new File([contents], "demo_sensor.csv", { type: "text/csv" });
    await analyzeSensorFile(file);
  } catch (error) {
    byId("rul-error").textContent = error.message;
    byId("rul-error").hidden = false;
  } finally {
    sampleButton.disabled = false;
  }
});

byId("verify-audit").addEventListener("click", loadAudit);
byId("revise-case").addEventListener("click", reviseActiveCase);
byId("export-case").addEventListener("click", exportActiveCase);
byId("refresh-evaluation").addEventListener("click", loadEvaluation);
byId("aircraft-map").addEventListener("click", (event) => {
  const spot = event.target.closest("[data-ata]");
  if (spot) selectAta(spot.dataset.ata);
});
byId("aircraft-map").addEventListener("keydown", (event) => {
  const spot = event.target.closest("[data-ata]");
  if (spot && (event.key === "Enter" || event.key === " ")) {
    event.preventDefault();
    selectAta(spot.dataset.ata);
  }
});
byId("ata-list").addEventListener("click", (event) => {
  const item = event.target.closest("[data-ata]");
  if (item) selectAta(item.dataset.ata);
});

window.addEventListener("hashchange", () => setView(window.location.hash.slice(1)));
renderAgents();
renderWorkflow();
checkHealth();
loadCases(true);
setView(window.location.hash.slice(1) || "triage");
