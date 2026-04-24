const scenarioSelect = document.querySelector("#scenario");
const providerSelect = document.querySelector("#provider");
const runButton = document.querySelector("#run-button");
const statusBand = document.querySelector("#status-band");
const timeline = document.querySelector("#timeline");
const causalLinks = document.querySelector("#causal-links");
const proofList = document.querySelector("#proof-list");
const outputJson = document.querySelector("#output-json");
const pattern = document.querySelector("#pattern");

const agents = ["01-intake", "02-policy", "03-risk", "04-refund", "05-comms"];

async function loadInitialState() {
  const [scenarios, config] = await Promise.all([
    fetchJson("/api/scenarios"),
    fetchJson("/api/config"),
  ]);

  scenarioSelect.innerHTML = scenarios
    .map((scenario) => `<option value="${escapeHtml(scenario.id)}">${escapeHtml(scenario.name)}</option>`)
    .join("");
  providerSelect.value = config.default_provider;
  pattern.textContent = config.orchestration_pattern;
  renderEmptyTimeline();
}

async function runWorkflow() {
  runButton.disabled = true;
  setStatus("running", "Running", "Agents are reading state, handing off contracts, and verifying outcomes.");
  renderEmptyTimeline("running");
  causalLinks.innerHTML = "";
  proofList.innerHTML = "";

  try {
    const report = await fetchJson("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scenario: scenarioSelect.value,
        provider: providerSelect.value,
      }),
    });
    renderReport(report);
  } catch (error) {
    setStatus("failed", "Request failed", error.message);
  } finally {
    runButton.disabled = false;
  }
}

function renderReport(report) {
  const failure = report.failure ? `${report.failure.type}: ${report.failure.message}` : "All gates passed.";
  setStatus(report.status, report.status.toUpperCase(), `${report.run_id} - ${failure}`);
  timeline.innerHTML = report.receipts.map(renderReceipt).join("");
  causalLinks.innerHTML = renderEdges(report.causality_graph?.edges || []);
  proofList.innerHTML = renderProof(report);
  outputJson.textContent = JSON.stringify(
    {
      run_id: report.run_id,
      status: report.status,
      provider: report.provider,
      orchestration_pattern: report.orchestration_pattern,
      failure: report.failure,
      links: report.links,
    },
    null,
    2,
  );
}

function renderReceipt(receipt) {
  const artifactTags = (receipt.proof_artifacts || [])
    .map((artifact) => {
      const state = artifact.verified ? "good" : "bad";
      return `<span class="tag ${state}">artifact: ${escapeHtml(artifact.name)}</span>`;
    })
    .join("");
  const outcomeTags = (receipt.outcomes || [])
    .map((outcome) => {
      const state = outcome.passed ? "good" : "bad";
      return `<span class="tag ${state}">outcome: ${escapeHtml(outcome.name)}</span>`;
    })
    .join("");
  const issueTags = (receipt.issues || [])
    .map((issue) => `<span class="tag bad">${escapeHtml(issue.code)}: ${escapeHtml(issue.message)}</span>`)
    .join("");
  return `
    <article class="agent-step ${escapeHtml(receipt.status)}">
      <div class="step-head">
        <strong>${escapeHtml(receipt.step_id)}<br>${escapeHtml(receipt.agent)}</strong>
        <span class="pill ${escapeHtml(receipt.status)}">${escapeHtml(receipt.status.toUpperCase())}</span>
      </div>
      <p>${escapeHtml(receipt.action)}</p>
      <div class="metrics">
        <div class="metric">state reads<strong>${receipt.state_reads.length}</strong></div>
        <div class="metric">handoffs<strong>${receipt.handoffs.length}</strong></div>
        <div class="metric">artifacts<strong>${receipt.proof_artifacts.length}</strong></div>
        <div class="metric">outcomes<strong>${receipt.outcomes.length}</strong></div>
      </div>
      <div class="tags">${artifactTags}${outcomeTags}${issueTags}</div>
    </article>
  `;
}

function renderEdges(edges) {
  if (!edges.length) {
    return '<div class="causal-item">No causal links recorded.</div>';
  }
  return edges
    .map((edge) => {
      const detail = edge.handoff_id || edge.artifact_id || edge.kind;
      return `
        <div class="causal-item">
          <strong>${escapeHtml(edge.kind)}</strong><br>
          ${escapeHtml(edge.from)} to ${escapeHtml(edge.to)}<br>
          <small>${escapeHtml(detail)}</small>
        </div>
      `;
    })
    .join("");
}

function renderProof(report) {
  const artifacts = report.receipts.flatMap((receipt) =>
    receipt.proof_artifacts.map((artifact) => ({
      ...artifact,
      step_id: receipt.step_id,
    })),
  );
  const outcomes = report.receipts.flatMap((receipt) =>
    receipt.outcomes.map((outcome) => ({
      ...outcome,
      step_id: receipt.step_id,
    })),
  );
  const rows = [
    ...artifacts.map((artifact) => ({
      state: artifact.verified ? "good" : "bad",
      text: `${artifact.step_id}: artifact ${artifact.name} verified=${artifact.verified}`,
    })),
    ...outcomes.map((outcome) => ({
      state: outcome.passed ? "good" : "bad",
      text: `${outcome.step_id}: outcome ${outcome.name} passed=${outcome.passed}`,
    })),
  ];
  if (!rows.length) {
    return '<div class="proof-item">No proof artifacts or outcomes recorded.</div>';
  }
  return rows
    .map((row) => `<div class="proof-item ${row.state}">${escapeHtml(row.text)}</div>`)
    .join("");
}

function renderEmptyTimeline(state = "idle") {
  timeline.innerHTML = agents
    .map(
      (agent) => `
        <article class="agent-step">
          <div class="step-head">
            <strong>${escapeHtml(agent)}</strong>
            <span class="pill">${state}</span>
          </div>
          <p>Waiting for receipt.</p>
        </article>
      `,
    )
    .join("");
}

function setStatus(state, label, text) {
  statusBand.className = `status-band ${state}`;
  statusBand.innerHTML = `<strong>${escapeHtml(label)}</strong><span>${escapeHtml(text)}</span>`;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

runButton.addEventListener("click", runWorkflow);
loadInitialState().catch((error) => {
  setStatus("failed", "Startup failed", error.message);
});
