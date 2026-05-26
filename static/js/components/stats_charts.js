/* Statistics charts rendered on Canvas — resolution bins, I/sigma, completeness. */

class StatsCharts {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.data = null;
  }

  setData(integrationResult) {
    this.data = integrationResult;
    this.render();
  }

  render() {
    var ctx = this.ctx;
    var w = this.canvas.width || 600;
    var h = this.canvas.height || 300;
    this.canvas.width = w;
    this.canvas.height = h;
    ctx.clearRect(0, 0, w, h);

    if (!this.data || !this.data.resolution_bins || !this.data.resolution_bins.length) {
      ctx.fillStyle = '#6b7280';
      ctx.font = '12px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No integration data yet', w / 2, h / 2);
      return;
    }

    var bins = this.data.resolution_bins;
    var margin = { top: 20, right: 30, bottom: 40, left: 50 };
    var plotW = w - margin.left - margin.right;
    var plotH = h - margin.top - margin.bottom;

    // Background
    ctx.fillStyle = '#f8f9fb';
    ctx.fillRect(margin.left, margin.top, plotW, plotH);

    // Axes
    ctx.strokeStyle = '#c4cad4';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(margin.left, margin.top);
    ctx.lineTo(margin.left, margin.top + plotH);
    ctx.lineTo(margin.left + plotW, margin.top + plotH);
    ctx.stroke();

    // I/sigma bars
    var maxISigma = 0;
    for (var i = 0; i < bins.length; i++) {
      if (bins[i].i_sigma > maxISigma) maxISigma = bins[i].i_sigma;
    }
    maxISigma = Math.max(maxISigma, 1);

    var barWidth = (plotW / bins.length) * 0.6;
    var gap = (plotW / bins.length) * 0.4;

    for (var i = 0; i < bins.length; i++) {
      var bin = bins[i];
      var barH = (bin.i_sigma / maxISigma) * plotH;
      var x = margin.left + i * (plotW / bins.length) + gap / 2;
      var y = margin.top + plotH - barH;

      // I/sigma bar
      var grad = ctx.createLinearGradient(x, y, x, margin.top + plotH);
      grad.addColorStop(0, '#7c3aed');
      grad.addColorStop(1, '#a78bfa');
      ctx.fillStyle = grad;
      ctx.fillRect(x, y, barWidth, barH);

      // Bin label
      ctx.fillStyle = '#6b7280';
      ctx.font = '8px JetBrains Mono, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(bin.resolution.toFixed(1), x + barWidth / 2, margin.top + plotH + 15);

      // Completeness dot
      var dotY = margin.top + plotH * (1 - bin.completeness);
      ctx.fillStyle = '#10b981';
      ctx.beginPath();
      ctx.arc(x + barWidth / 2, dotY, 3, 0, Math.PI * 2);
      ctx.fill();
    }

    // Y-axis labels
    ctx.fillStyle = '#6b7280';
    ctx.font = '9px JetBrains Mono, monospace';
    ctx.textAlign = 'right';
    for (var i = 0; i <= 4; i++) {
      var val = (maxISigma * i / 4).toFixed(1);
      var y = margin.top + plotH - (plotH * i / 4);
      ctx.fillText(val, margin.left - 6, y + 3);
    }

    // Labels
    ctx.fillStyle = '#1a1d23';
    ctx.font = '9px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Resolution (A)', margin.left + plotW / 2, margin.top + plotH + 30);

    // Legend
    ctx.fillStyle = '#7c3aed';
    ctx.fillRect(margin.left, margin.top - 12, 8, 8);
    ctx.fillStyle = '#1a1d23';
    ctx.font = '9px Inter, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('I/sigma', margin.left + 12, margin.top - 4);

    ctx.fillStyle = '#10b981';
    ctx.beginPath();
    ctx.arc(margin.left + 60, margin.top - 8, 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#1a1d23';
    ctx.fillText('Completeness', margin.left + 68, margin.top - 4);

    // Summary stats
    ctx.fillStyle = '#1a1d23';
    ctx.font = '11px JetBrains Mono, monospace';
    ctx.textAlign = 'right';
    ctx.fillText(
      'I/sigma: ' + (this.data.overall_i_over_sigma || '—').toString() +
      '  |  Completeness: ' + ((this.data.completeness * 100) || '—').toString() + '%',
      margin.left + plotW, margin.top - 12
    );
  }
}
