/* X-ray Crystallography Pipeline — SPA Controller */

const STATE = {
  activeJobId: null,
  jobs: [],
  pollTimer: null,
};

const PIPELINE_STEPS = [
  'import', 'find-spots', 'index', 'integrate',
  'scale', 'merge', 'molecular-replacement', 'refine', 'validate',
];

const STEP_LABELS = {
  'import': 'Import',
  'find-spots': 'Find Spots',
  'index': 'Index',
  'integrate': 'Integrate',
  'scale': 'Scale',
  'merge': 'Merge',
  'molecular-replacement': 'Mol. Repl.',
  'refine': 'Refine',
  'validate': 'Validate',
};

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
  setupUploadZone();
  refreshJobList();
  refreshEngines();
});

// --- Toast ---
function showToast(msg, type = 'success') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById('toastContainer').appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

// --- Upload ---
function setupUploadZone() {
  const zone = document.getElementById('uploadZone');
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    uploadFiles(e.dataTransfer.files);
  });
}

async function uploadFiles(files) {
  if (!files.length) return;
  if (!STATE.activeJobId) {
    showToast('Create a job first', 'error');
    return;
  }
  try {
    const result = await API.uploadImages(STATE.activeJobId, files);
    showToast(`Uploaded ${result.count} image(s)`);
    refreshJobDetail(STATE.activeJobId);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// --- Job CRUD ---
async function createJob() {
  try {
    const data = await API.createJob('Crystal ' + new Date().toLocaleDateString());
    STATE.activeJobId = data.job_id;
    await refreshJobList();
    selectJob(data.job_id);
    showToast('Job created');
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function refreshJobList() {
  try {
    STATE.jobs = await API.listJobs();
    renderJobList();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

function renderJobList() {
  const container = document.getElementById('jobList');
  if (!STATE.jobs.length) {
    container.innerHTML = '<div style="font-size:10px;color:var(--text-dim);padding:8px">No jobs yet</div>';
    return;
  }
  container.innerHTML = STATE.jobs.map(j => {
    const active = j.job_id === STATE.activeJobId ? ' active' : '';
    const shortId = j.job_id.slice(0, 8);
    const pipeline = j.pipeline || [];
    const completed = pipeline.filter(s => s.status === 'completed').length;
    const failed = pipeline.filter(s => s.status === 'failed').length;
    const overallStatus = failed > 0 ? 'failed' : (completed === pipeline.length && pipeline.length > 0 ? 'completed' : (completed > 0 ? 'running' : 'created'));
    const date = j.created_at ? new Date(j.created_at).toLocaleDateString() : '';
    return `<div class="job-item${active}" onclick="selectJob('${j.job_id}')">
      <div>
        <div class="job-name">${shortId}…</div>
        <div class="job-date">${date}</div>
      </div>
      <span class="job-status ${overallStatus}">${overallStatus}</span>
      <span style="cursor:pointer;color:var(--text-dim);font-size:10px" onclick="event.stopPropagation();deleteJobPrompt('${j.job_id}')">&times;</span>
    </div>`;
  }).join('');
}

function selectJob(jobId) {
  STATE.activeJobId = jobId;
  renderJobList();
  refreshJobDetail(jobId);
  startPolling(jobId);
}

async function refreshJobDetail(jobId) {
  try {
    const job = await API.getJob(jobId);
    renderPipelineBar(job.pipeline || []);
    updateButtons(job.pipeline || []);
    renderMainContent(job);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function deleteJobPrompt(jobId) {
  if (!confirm('Delete this job and all data?')) return;
  try {
    await API.deleteJob(jobId);
    if (STATE.activeJobId === jobId) {
      STATE.activeJobId = null;
      stopPolling();
      document.getElementById('mainArea').innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">&#x2697;</div>
          <div class="empty-state-text">No job selected</div>
          <div class="empty-state-hint">Create a new job to start.</div>
        </div>`;
    }
    await refreshJobList();
    showToast('Job deleted');
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// --- Pipeline bar ---
function renderPipelineBar(pipeline) {
  const bar = document.getElementById('mainArea');
  const html = pipeline.map((s, i) => {
    const arrow = i < pipeline.length - 1 ? '<span class="pipeline-arrow">&#x2192;</span>' : '';
    return `<span class="pipeline-step ${s.status}">
      <span class="step-icon">${iconForStatus(s.status)}</span>${STEP_LABELS[s.step] || s.step}
    </span>${arrow}`;
  }).join('');

  const pipelineHtml = `<div class="card">
    <div class="section-title">Pipeline Progress</div>
    <div class="pipeline-bar">${html || '<span style="color:var(--text-dim);font-size:10px">No steps run</span>'}</div>
  </div>`;
  bar.innerHTML = pipelineHtml;
}

function iconForStatus(s) {
  if (s === 'completed') return '✓';
  if (s === 'running') return '●';
  if (s === 'failed') return '✗';
  return '○';
}

function updateButtons(pipeline) {
  const btnAll = document.getElementById('btnRunAll');
  const btnStep = document.getElementById('btnRunStep');
  const btnCancel = document.getElementById('btnCancel');

  const anyRunning = pipeline.some(s => s.status === 'running' || s.status === 'queued');
  const allDone = pipeline.every(s => s.status === 'completed' || s.status === 'skipped');

  btnAll.disabled = anyRunning || allDone;
  btnStep.disabled = anyRunning || allDone;
  btnCancel.disabled = !anyRunning;
}

// --- Main content ---
function renderMainContent(job) {
  const area = document.getElementById('mainArea');
  const images = job.images || [];
  const hasImages = images.length > 0;

  let extra = '';
  if (hasImages) {
    extra += `<div class="card">
      <div class="section-title">Uploaded Images (${images.length})</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:4px">
        ${images.slice(0, 5).map(i => `<span style="font-family:var(--font-mono);font-size:9px;background:var(--bg-input);padding:3px 8px;border-radius:4px">${i.filename}</span>`).join('')}
        ${images.length > 5 ? `<span style="font-size:9px;color:var(--text-dim)">+${images.length - 5} more</span>` : ''}
      </div>
      <img src="/api/jobs/${job.job_id}/preview" style="max-width:100%;max-height:300px;margin-top:8px;border-radius:4px" onerror="this.style.display='none'">
    </div>`;
  }

  area.innerHTML += extra;
}

// --- Execution ---
async function runFullPipeline() {
  if (!STATE.activeJobId) return;
  try {
    setStatus('processing');
    await API.runFullPipeline(STATE.activeJobId);
    showToast('Pipeline started');
    startPolling(STATE.activeJobId);
  } catch (e) {
    showToast(e.message, 'error');
    setStatus('ready');
  }
}

async function runCurrentStep() {
  if (!STATE.activeJobId) return;
  try {
    const job = await API.getJob(STATE.activeJobId);
    const pipeline = job.pipeline || [];
    const next = pipeline.find(s => s.status === 'pending');
    if (!next) { showToast('All steps completed'); return; }
    await API.runStep(STATE.activeJobId, next.step);
    setStatus('processing');
    startPolling(STATE.activeJobId);
  } catch (e) {
    showToast(e.message, 'error');
    setStatus('ready');
  }
}

async function cancelJob() {
  if (!STATE.activeJobId) return;
  stopPolling();
  setStatus('ready');
  showToast('Cancelled');
  refreshJobDetail(STATE.activeJobId);
}

// --- Polling ---
function startPolling(jobId) {
  stopPolling();
  STATE.pollTimer = setInterval(async () => {
    try {
      const job = await API.getJob(jobId);
      const pipeline = job.pipeline || [];
      renderPipelineBar(pipeline);
      updateButtons(pipeline);
      const anyRunning = pipeline.some(s => s.status === 'running' || s.status === 'queued');
      const allDone = pipeline.every(s => s.status === 'completed' || s.status === 'failed' || s.status === 'skipped');
      if (!anyRunning) {
        setStatus('ready');
        if (allDone) stopPolling();
      }
      await refreshJobList();
    } catch (e) { /* ignore poll errors */ }
  }, 2000);
}

function stopPolling() {
  if (STATE.pollTimer) { clearInterval(STATE.pollTimer); STATE.pollTimer = null; }
  setStatus('ready');
}

// --- System ---
async function refreshEngines() {
  try {
    const status = await API.getDependencies();
    const deps = status.dependencies || {};
    const container = document.getElementById('engineList');
    container.innerHTML = Object.entries(deps).map(([name, ok]) =>
      `<span class="engine-tag ${ok ? 'available' : 'missing'}">${name}: ${ok ? 'ok' : 'missing'}</span>`
    ).join('');
    const allOk = Object.values(deps).every(Boolean);
    const dot = document.getElementById('sysDot');
    dot.className = 'status-dot ' + (allOk ? 'ready' : '');
    document.getElementById('sysLabel').textContent = allOk ? 'All engines ready' : 'Some engines missing';
  } catch (e) { /* ignore */ }
}

function setStatus(state) {
  const dot = document.getElementById('sysDot');
  dot.className = 'status-dot ' + (state === 'processing' ? 'processing' : 'ready');
  document.getElementById('sysLabel').textContent = state === 'processing' ? 'Processing...' : 'Ready';
}
