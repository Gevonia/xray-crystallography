/* API client — fetch wrapper for all backend endpoints. */

const API = {
  async _fetch(url, opts = {}) {
    const res = await fetch(url, opts);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  },

  _post(url, body) {
    return this._fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  },

  // Jobs
  createJob(name = '') { return this._post('/api/jobs', { name }); },
  listJobs() { return this._fetch('/api/jobs'); },
  getJob(id) { return this._fetch(`/api/jobs/${id}`); },
  deleteJob(id) { return this._fetch(`/api/jobs/${id}`, { method: 'DELETE' }); },

  // Upload
  async uploadImages(jobId, files) {
    const fd = new FormData();
    for (const f of files) fd.append('files', f);
    const res = await fetch(`/api/jobs/${jobId}/upload`, { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  },

  // Pipeline
  runStep(jobId, step) { return this._post(`/api/jobs/${jobId}/steps/${step}`); },
  runFullPipeline(jobId) { return this._post(`/api/jobs/${jobId}/run`); },

  // Results
  getSpots(jobId) { return this._fetch(`/api/jobs/${jobId}/spots`); },
  getCrystal(jobId) { return this._fetch(`/api/jobs/${jobId}/crystal`); },
  getStatistics(jobId) { return this._fetch(`/api/jobs/${jobId}/statistics`); },

  // System
  getDependencies() { return this._fetch('/api/system/dependencies'); },
  getConfig() { return this._fetch('/api/system/config'); },
};
