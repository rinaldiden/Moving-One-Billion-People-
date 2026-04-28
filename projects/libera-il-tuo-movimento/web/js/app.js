/**
 * LIBERA IL TUO MOVIMENTO — App
 * WebSocket pipeline, UI, coordinamento.
 */

const promptInput = document.getElementById('prompt-input');
const runBtn = document.getElementById('run-btn');
const statusBar = document.getElementById('status-bar');
const logContent = document.getElementById('log-content');
const downloadBtn = document.getElementById('download-gcode');
const gcodeStats = document.getElementById('gcode-stats');

let ws = null;
let currentGcode = null;

// --- Pipeline ---

runBtn.addEventListener('click', () => {
    const prompt = promptInput.value.trim();
    if (!prompt) return;
    startPipeline(prompt);
});

function startPipeline(prompt) {
    runBtn.disabled = true;
    runBtn.textContent = 'Gli agenti stanno ragionando...';
    statusBar.classList.remove('hidden', 'error');
    statusBar.textContent = 'Connessione alla pipeline...';
    logContent.innerHTML = '';
    downloadBtn.disabled = true;
    currentGcode = null;
    resetPipelineNodes();

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/api/pipeline/ws`);

    ws.onopen = () => {
        statusBar.textContent = 'Pipeline avviata. Gli agenti stanno lavorando.';
        ws.send(JSON.stringify({ prompt }));
    };

    ws.onmessage = (event) => {
        handleMessage(JSON.parse(event.data));
    };

    ws.onerror = () => {
        statusBar.textContent = 'Errore di connessione al server';
        statusBar.classList.add('error');
        resetBtn();
    };

    ws.onclose = () => { resetBtn(); };
}

function resetBtn() {
    runBtn.disabled = false;
    runBtn.textContent = 'Lancia la pipeline';
}

function handleMessage(msg) {
    switch (msg.type) {
        case 'agent_start':
            statusBar.textContent = `[${msg.step}/${msg.total}] ${msg.label}...`;
            setNodeState(msg.agent, 'active');
            addLog(msg.label, 'working');
            break;

        case 'agent_done':
            setNodeState(msg.agent, 'done');
            addLog(msg.label + ' — fatto', 'done', msg.output_preview);
            break;

        case 'agent_error':
            setNodeState(msg.agent, 'error');
            statusBar.textContent = `Errore: ${msg.error}`;
            statusBar.classList.add('error');
            addLog('Errore: ' + msg.error, 'error');
            break;

        case 'pipeline_done':
            statusBar.textContent = 'Pipeline completata. Il giunto e\' pronto.';
            statusBar.style.borderLeftColor = 'var(--accent2)';
            statusBar.style.color = 'var(--accent2)';
            loadGcode();
            break;

        case 'pipeline_error':
            statusBar.textContent = `Pipeline interrotta allo step ${msg.step}. Riprova.`;
            statusBar.classList.add('error');
            statusBar.style.borderLeftColor = 'var(--danger)';
            resetBtn();
            break;

        case 'error':
            statusBar.textContent = msg.message;
            statusBar.classList.add('error');
            break;
    }
}

// --- Pipeline nodes ---

function resetPipelineNodes() {
    document.querySelectorAll('.pipe-node').forEach(n => {
        n.classList.remove('active', 'done', 'error');
    });
}

function setNodeState(agent, state) {
    const node = document.querySelector(`.pipe-node[data-agent="${agent}"]`);
    if (!node) return;
    node.classList.remove('active', 'done', 'error');
    node.classList.add(state);
}

// --- Log ---

function addLog(text, type, preview) {
    const entry = document.createElement('div');
    entry.className = 'log-entry';

    const colors = {
        working: 'var(--accent)',
        done: 'var(--accent2)',
        error: 'var(--danger)'
    };

    let html = `<span class="log-agent" style="color:${colors[type]}">${text}</span>`;
    if (preview) {
        html += `<br><span class="log-text">${escapeHtml(preview)}</span>`;
    }
    entry.innerHTML = html;
    logContent.appendChild(entry);
    logContent.scrollTop = logContent.scrollHeight;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// --- G-code ---

async function loadGcode() {
    try {
        const res = await fetch('/api/output/gcode');
        const data = await res.json();
        currentGcode = data.gcode;
        downloadBtn.disabled = false;

        const lines = currentGcode.split('\n');
        const moves = lines.filter(l => l.startsWith('G1')).length;
        gcodeStats.textContent = `${lines.length} righe, ${moves} movimenti`;

        if (window.renderGcode) {
            window.renderGcode(currentGcode);
        }
    } catch (e) {
        console.error('Errore caricamento G-code:', e);
    }
}

downloadBtn.addEventListener('click', () => {
    if (!currentGcode) return;
    const blob = new Blob([currentGcode], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'joint_output.gcode';
    a.click();
    URL.revokeObjectURL(url);
});

// --- Training stats ---

async function loadTrainingStats() {
    try {
        const res = await fetch('/api/training/stats');
        const data = await res.json();
        document.getElementById('stat-pairs').textContent = data.pairs;
        document.getElementById('stat-stl').textContent = data.stl_files;
        document.getElementById('stat-gcode').textContent = data.gcode_files;
    } catch (e) {
        // Server non attivo
    }
}

loadTrainingStats();
