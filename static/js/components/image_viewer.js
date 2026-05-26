/* Diffraction image viewer with spot overlay support. */

class DiffractionImageViewer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.imageData = null;
    this.spots = [];
    this.zoom = 1;
    this.offsetX = 0;
    this.offsetY = 0;
    this.dragging = false;
    this.dragStartX = 0;
    this.dragStartY = 0;
    this._bindEvents();
  }

  _bindEvents() {
    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.15 : 0.85;
      this.zoom = Math.max(0.1, Math.min(10, this.zoom * factor));
      this.render();
    });
    this.canvas.addEventListener('mousedown', (e) => {
      this.dragging = true;
      this.dragStartX = e.offsetX - this.offsetX;
      this.dragStartY = e.offsetY - this.offsetY;
    });
    this.canvas.addEventListener('mousemove', (e) => {
      if (!this.dragging) return;
      this.offsetX = e.offsetX - this.dragStartX;
      this.offsetY = e.offsetY - this.dragStartY;
      this.render();
    });
    this.canvas.addEventListener('mouseup', () => { this.dragging = false; });
    this.canvas.addEventListener('mouseleave', () => { this.dragging = false; });
  }

  async loadImage(url) {
    try {
      const resp = await fetch(url);
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const blob = await resp.blob();
      const img = new Image();
      img.src = URL.createObjectURL(blob);
      await new Promise((resolve, reject) => {
        img.onload = resolve;
        img.onerror = reject;
      });
      this.imageData = img;
      this.canvas.width = this.canvas.clientWidth || 600;
      this.canvas.height = this.canvas.clientHeight || 500;
      this.zoom = 1;
      this.offsetX = 0;
      this.offsetY = 0;
      this.render();
    } catch (e) {
      console.warn('Failed to load diffraction image:', e.message);
    }
  }

  setSpots(spots) {
    this.spots = spots || [];
    this.render();
  }

  render() {
    var ctx = this.ctx;
    var w = this.canvas.width;
    var h = this.canvas.height;
    ctx.clearRect(0, 0, w, h);

    if (!this.imageData) {
      ctx.fillStyle = '#6b7280';
      ctx.font = '12px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No image loaded', w / 2, h / 2);
      return;
    }

    ctx.save();
    ctx.translate(this.offsetX, this.offsetY);
    ctx.scale(this.zoom, this.zoom);
    ctx.drawImage(this.imageData, 0, 0, this.imageData.width, this.imageData.height);

    if (this.spots.length > 0) {
      for (var i = 0; i < this.spots.length; i++) {
        var spot = this.spots[i];
        var x = spot[1];
        var y = spot[0];
        ctx.fillStyle = 'rgba(250, 204, 21, 0.7)';
        ctx.strokeStyle = 'rgba(180, 83, 9, 0.9)';
        ctx.lineWidth = 1 / this.zoom;
        ctx.beginPath();
        ctx.arc(x, y, 3 / this.zoom, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }
    }

    var cx = this.imageData.width / 2;
    var cy = this.imageData.height / 2;
    var maxR = Math.min(cx, cy);
    ctx.strokeStyle = 'rgba(124, 58, 237, 0.4)';
    ctx.lineWidth = 0.5 / this.zoom;
    for (var i = 1; i <= 4; i++) {
      ctx.beginPath();
      ctx.arc(cx, cy, maxR * i / 4, 0, Math.PI * 2);
      ctx.stroke();
    }

    ctx.restore();
  }

  reset() {
    this.zoom = 1;
    this.offsetX = 0;
    this.offsetY = 0;
    this.render();
  }
}
