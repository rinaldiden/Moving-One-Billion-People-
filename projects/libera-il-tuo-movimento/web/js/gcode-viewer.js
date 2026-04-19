/**
 * G-code 3D Viewer — rendering con Canvas 2D (proiezione isometrica).
 * Nessuna dipendenza esterna (no Three.js).
 * Per file piccoli (<50k righe) e' piu' che sufficiente.
 */

const canvas = document.getElementById('gcode-canvas');
const ctx = canvas.getContext('2d');

let paths = [];
let bounds = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity, minZ: Infinity, maxZ: -Infinity };
let rotation = { x: -30, z: 45 };
let zoom = 1;
let isDragging = false;
let lastMouse = { x: 0, y: 0 };

/**
 * Parsa il G-code e estrae i movimenti G0/G1.
 */
function parseGcode(gcode) {
    const lines = gcode.split('\n');
    const result = [];
    let pos = { x: 0, y: 0, z: 0 };
    let isExtrude = false;

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('G0') && !trimmed.startsWith('G1')) continue;

        const newPos = { ...pos };
        isExtrude = trimmed.startsWith('G1');

        const xMatch = trimmed.match(/X([-\d.]+)/);
        const yMatch = trimmed.match(/Y([-\d.]+)/);
        const zMatch = trimmed.match(/Z([-\d.]+)/);
        const eMatch = trimmed.match(/E([-\d.]+)/);

        if (xMatch) newPos.x = parseFloat(xMatch[1]);
        if (yMatch) newPos.y = parseFloat(yMatch[1]);
        if (zMatch) newPos.z = parseFloat(zMatch[1]);

        // Solo G1 con estrusione
        if (isExtrude && eMatch && parseFloat(eMatch[1]) > 0) {
            result.push({
                from: { ...pos },
                to: { ...newPos },
                z: newPos.z,
            });
        }

        // Update bounds
        bounds.minX = Math.min(bounds.minX, newPos.x);
        bounds.maxX = Math.max(bounds.maxX, newPos.x);
        bounds.minY = Math.min(bounds.minY, newPos.y);
        bounds.maxY = Math.max(bounds.maxY, newPos.y);
        bounds.minZ = Math.min(bounds.minZ, newPos.z);
        bounds.maxZ = Math.max(bounds.maxZ, newPos.z);

        pos = newPos;
    }
    return result;
}

/**
 * Proiezione isometrica 3D -> 2D.
 */
function project(x, y, z) {
    const radX = (rotation.x * Math.PI) / 180;
    const radZ = (rotation.z * Math.PI) / 180;

    // Ruota Z
    const rx = x * Math.cos(radZ) - y * Math.sin(radZ);
    const ry = x * Math.sin(radZ) + y * Math.cos(radZ);
    const rz = z;

    // Ruota X
    const fy = ry * Math.cos(radX) - rz * Math.sin(radX);
    const fz = ry * Math.sin(radX) + rz * Math.cos(radX);

    return { x: rx, y: fy };
}

/**
 * Rendering del G-code sul canvas.
 */
function render() {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvas.clientWidth * dpr;
    canvas.height = canvas.clientHeight * dpr;
    ctx.scale(dpr, dpr);

    const w = canvas.clientWidth;
    const h = canvas.clientHeight;

    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, w, h);

    if (paths.length === 0) {
        ctx.fillStyle = '#333';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('G-code viewer — in attesa di dati', w / 2, h / 2);
        return;
    }

    // Center and scale
    const cx = (bounds.minX + bounds.maxX) / 2;
    const cy = (bounds.minY + bounds.maxY) / 2;
    const cz = (bounds.minZ + bounds.maxZ) / 2;
    const range = Math.max(
        bounds.maxX - bounds.minX,
        bounds.maxY - bounds.minY,
        bounds.maxZ - bounds.minZ,
        1
    );
    const scale = (Math.min(w, h) * 0.7 * zoom) / range;

    const zRange = bounds.maxZ - bounds.minZ || 1;

    ctx.lineWidth = 0.5;

    for (const seg of paths) {
        const p1 = project(seg.from.x - cx, seg.from.y - cy, seg.from.z - cz);
        const p2 = project(seg.to.x - cx, seg.to.y - cy, seg.to.z - cz);

        // Color by Z height
        const t = (seg.z - bounds.minZ) / zRange;
        const r = Math.round(30 + t * 60);
        const g = Math.round(100 + t * 155);
        const b = Math.round(255 - t * 100);
        ctx.strokeStyle = `rgb(${r},${g},${b})`;

        ctx.beginPath();
        ctx.moveTo(w / 2 + p1.x * scale, h / 2 - p1.y * scale);
        ctx.lineTo(w / 2 + p2.x * scale, h / 2 - p2.y * scale);
        ctx.stroke();
    }

    // Info
    ctx.fillStyle = '#555';
    ctx.font = '11px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`${paths.length} segmenti | drag per ruotare | scroll per zoom`, 10, h - 10);
}

// --- Interazione mouse ---

canvas.addEventListener('mousedown', (e) => {
    isDragging = true;
    lastMouse = { x: e.clientX, y: e.clientY };
});

canvas.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const dx = e.clientX - lastMouse.x;
    const dy = e.clientY - lastMouse.y;
    rotation.z += dx * 0.5;
    rotation.x += dy * 0.5;
    rotation.x = Math.max(-90, Math.min(90, rotation.x));
    lastMouse = { x: e.clientX, y: e.clientY };
    render();
});

canvas.addEventListener('mouseup', () => { isDragging = false; });
canvas.addEventListener('mouseleave', () => { isDragging = false; });

canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    zoom *= e.deltaY > 0 ? 0.9 : 1.1;
    zoom = Math.max(0.1, Math.min(10, zoom));
    render();
}, { passive: false });

// --- API pubblica ---

window.renderGcode = function(gcode) {
    bounds = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity, minZ: Infinity, maxZ: -Infinity };
    rotation = { x: -30, z: 45 };
    zoom = 1;
    paths = parseGcode(gcode);
    render();
};

// Render iniziale (vuoto)
render();

// Resize
window.addEventListener('resize', () => { if (paths.length > 0) render(); });
