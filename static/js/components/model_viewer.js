/* 3D model viewer using Mol* (https://molstar.org) via iframe. */

function launchMolStarViewer(pdbUrl, containerId) {
  var container = document.getElementById(containerId);
  if (!container) return;

  var viewerUrl = 'https://molstar.org/viewer/?pdb-url=' +
    encodeURIComponent(pdbUrl) +
    '&pdb-provider=url';

  var iframe = document.createElement('iframe');
  iframe.src = viewerUrl;
  iframe.style.width = '100%';
  iframe.style.height = '500px';
  iframe.style.border = 'none';
  iframe.style.borderRadius = 'var(--radius, 8px)';
  iframe.allow = 'fullscreen';

  container.innerHTML = '';
  container.appendChild(iframe);
}

function launchMolStarWithDensity(pdbUrl, mtzUrl, containerId) {
  // Mol* doesn't directly support MTZ URLs via query params,
  // so we launch the standard viewer with the PDB and show a note.
  launchMolStarViewer(pdbUrl, containerId);

  var note = document.createElement('div');
  note.style.cssText = 'font-size:10px;color:var(--text-dim);margin-top:4px;text-align:center';
  note.textContent = 'Electron density maps require local Mol* with MTZ support.';
  document.getElementById(containerId).appendChild(note);
}
