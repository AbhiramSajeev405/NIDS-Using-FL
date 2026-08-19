/* ═══════════════════════════════════════════════════════════════════
   FL-NIDS Real-Time Dashboard — WebSocket Client + Chart.js
   11-Panel Interactive Dashboard
   ═══════════════════════════════════════════════════════════════════ */

(function () {
    'use strict';

    /* ─── Chart.js global config ──────────────────────────────── */
    Chart.defaults.color = '#8892a8';
    Chart.defaults.borderColor = 'rgba(255,255,255,0.04)';
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.font.size = 11;
    Chart.defaults.plugins.legend.labels.boxWidth = 10;
    Chart.defaults.plugins.legend.labels.padding = 12;
    Chart.defaults.animation = { duration: 400 };

    /* ─── State ───────────────────────────────────────────────── */
    let convergenceChart, commChart, anomalyChart, divergenceChart, timelineChart;
    let reconnectTimer = null;
    let ws = null;
    let reconnectDelay = 1000;
    let lastState = null;
    let incidentFilter = 'all';

    // Sparkline history (last 20 values)
    const sparkData = {
        accuracy: [], detection: [], f1: [],
        precision: [], fpr: [], fairness: []
    };
    const SPARK_MAX = 20;

    /* ─── Init ────────────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', () => {
        initCharts();
        connectWebSocket();
        initClock();
        initFilters();
        initControls();
    });

    /* ═══════════════════════════════════════════════════════════
       WEBSOCKET
       ═══════════════════════════════════════════════════════════ */
    function connectWebSocket() {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${proto}//${location.host}/ws/live`);

        ws.onopen = function () {
            setWsStatus('connected');
            reconnectDelay = 1000;
        };

        ws.onmessage = function (event) {
            try {
                const state = JSON.parse(event.data);
                lastState = state;
                render(state);
            } catch (e) {
                console.error('Parse error:', e);
            }
        };

        ws.onclose = function () {
            setWsStatus('disconnected');
            scheduleReconnect();
        };

        ws.onerror = function () {
            ws.close();
        };
    }

    function scheduleReconnect() {
        if (reconnectTimer) return;
        setWsStatus('connecting');
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connectWebSocket();
            reconnectDelay = Math.min(reconnectDelay * 1.5, 10000);
        }, reconnectDelay);
    }

    function setWsStatus(status) {
        const el = document.getElementById('ws-indicator');
        el.className = 'ws-indicator ' + status;
        const labels = { connected: '⬤ Connected', disconnected: '⬤ Disconnected', connecting: '⬤ Reconnecting…' };
        el.textContent = labels[status] || status;
    }

    /* ═══════════════════════════════════════════════════════════
       RENDER — Main entry point for incoming state
       ═══════════════════════════════════════════════════════════ */
    function render(state) {
        renderStatusBar(state);
        renderKPIs(state);
        renderConvergenceChart(state);
        renderHierarchy(state);
        renderHeatmap(state);
        renderCommChart(state);
        renderAnomalyChart(state);
        renderDivergenceChart(state);
        renderIncidents(state);
        renderTimeline(state);
    }

    /* ─── Status Bar ──────────────────────────────────────────── */
    function renderStatusBar(state) {
        const s = state.training_status || {};
        const tag = document.getElementById('status-tag');
        const status = (s.status || 'idle').toLowerCase();
        tag.textContent = status.toUpperCase();
        tag.className = 'tag ' + status;

        setText('current-round', s.current_round || 0);
        setText('total-rounds', s.total_rounds || 0);
        setText('model-type', (s.model_type || '—').toUpperCase());
        setText('strategy', (s.strategy || '—').toUpperCase());
        setText('scenario-name', s.scenario || '—');

        // Elapsed time
        if (s.start_time) {
            const elapsed = Math.floor((Date.now() / 1000) - s.start_time);
            const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
            const ss = String(elapsed % 60).padStart(2, '0');
            setText('elapsed-time', `${mm}:${ss}`);
        }

        // Defense indicators
        const defenses = state.defenses || {};
        toggleBadge('def-dp', defenses.differential_privacy);
        toggleBadge('def-gc', defenses.gradient_clipping);
        toggleBadge('def-ce', defenses.contribution_eval);
        toggleBadge('def-pd', defenses.poison_detection);
    }

    function toggleBadge(id, active) {
        const el = document.getElementById(id);
        if (el) el.className = 'defense-badge ' + (active ? 'on' : 'off');
    }

    /* ─── KPI Cards ───────────────────────────────────────────── */
    function renderKPIs(state) {
        const g = state.global_metrics || {};

        updateKPI('accuracy', g.accuracy, '%', 2, 'cyan');
        updateKPI('detection', g.detection_rate, '%', 2, 'green');
        updateKPI('f1', g.f1_score, '', 3, 'purple');
        updateKPI('precision', g.precision, '', 3, 'teal');
        updateKPI('fpr', g.fpr, '%', 2, 'red');

        const fair = (state.fairness || {}).jains_index;
        updateKPI('fairness', fair, '', 3, 'amber');
    }

    function updateKPI(name, value, suffix, decimals, color) {
        const v = value != null ? value : 0;
        const display = suffix === '%' ? (v * 100).toFixed(decimals) : v.toFixed(decimals);

        const el = document.getElementById('kpi-' + name);
        if (el) {
            if (suffix === '%') {
                el.innerHTML = display + '<span class="kpi-unit">%</span>';
            } else {
                el.textContent = display;
            }
        }

        const barPct = Math.min(100, v * 100);
        setBar('kpi-' + name + '-bar', barPct);

        // Sparkline
        if (sparkData[name] !== undefined) {
            sparkData[name].push(v);
            if (sparkData[name].length > SPARK_MAX) sparkData[name].shift();
            renderSparkline('spark-' + name, sparkData[name], color);
        }
    }

    function renderSparkline(containerId, data, color) {
        const container = document.getElementById(containerId);
        if (!container || data.length === 0) return;

        const max = Math.max(...data, 0.01);
        const html = data.map(v => {
            const h = Math.max(2, (v / max) * 22);
            const colorMap = {
                cyan: 'rgba(0,229,255,0.3)', green: 'rgba(118,255,3,0.3)',
                purple: 'rgba(179,136,255,0.3)', teal: 'rgba(100,255,218,0.3)',
                red: 'rgba(255,82,82,0.3)', amber: 'rgba(255,215,64,0.3)',
            };
            return `<div class="spark-bar" style="height:${h}px;background:${colorMap[color] || colorMap.cyan}"></div>`;
        }).join('');
        container.innerHTML = html;
    }

    /* ─── Convergence Chart ───────────────────────────────────── */
    function renderConvergenceChart(state) {
        const h = state.convergence_history || [];
        if (!convergenceChart || h.length === 0) return;

        convergenceChart.data.labels = h.map(r => 'R' + r.round);
        convergenceChart.data.datasets[0].data = h.map(r => r.accuracy != null ? r.accuracy * 100 : null);
        const accData = h.map(r => r.accuracy != null ? r.accuracy * 100 : null).filter(v => v !== null);
  const lossData = h.map(r => r.loss != null ? r.loss : null).filter(v => v !== null);
  convergenceChart.data.datasets[0].data = accData;
  convergenceChart.data.datasets[1].data = lossData;

  // Dynamic scaling
  if (accData.length > 0) {
    const accMin = Math.floor(Math.min(...accData) * 0.95);
    const accMax = Math.ceil(Math.max(...accData) * 1.05);
    const accRange = accMax - accMin;
    convergenceChart.options.scales.y.min = Math.max(0, accMin - accRange * 0.1);
    convergenceChart.options.scales.y.max = Math.min(100, accMax + accRange * 0.1);
  }
  if (lossData.length > 0) {
    const lossMin = Math.max(0, Math.floor(Math.min(...lossData) * 0.9));
    const lossMax = Math.ceil(Math.max(...lossData) * 1.1);
    const lossRange = lossMax - lossMin;
    convergenceChart.options.scales.y1.min = lossMin;
    convergenceChart.options.scales.y1.max = lossMax + lossRange * 0.1;
  }
        convergenceChart.update('none');
    }

    /* ─── Hierarchy Map ───────────────────────────────────────── */
    function renderHierarchy(state) {
        // Global node
        const gAcc = (state.global_metrics || {}).accuracy;
        setText('node-global-acc', gAcc != null ? (gAcc * 100).toFixed(1) + '%' : '—');

        const globalNode = document.getElementById('node-global');
        const ts = (state.training_status || {}).status || 'idle';
        globalNode.className = 'tree-node node-global' + (ts === 'training' ? ' active pulse' : '');

        // Countries
        const countries = state.countries || {};
        const countriesRow = document.getElementById('countries-row');
        if (Object.keys(countries).length > 0) {
            countriesRow.innerHTML = Object.entries(countries).map(([cid, c]) => {
                // Support both flat (c.accuracy) and nested (c.metrics.accuracy) formats
                const rawAcc = (c.metrics && c.metrics.accuracy != null) ? c.metrics.accuracy : (c.accuracy != null ? c.accuracy : null);
                const acc = rawAcc != null ? (rawAcc * 100).toFixed(1) + '%' : '—';
                const statusClass = c.status === 'aggregating' ? ' active' : '';
                return `<div class="tree-node${statusClass}" title="${cid}">
                    <span class="node-icon">🏳️</span>
                    <span class="node-label">${cid.replace('country_', 'Country ')}</span>
                    <span class="node-metric">${acc}</span>
                </div>`;
            }).join('');
        }

        // Clients
        const clients = state.clients || {};
        const poison = state.poison_detection || {};
        const drift = state.drift || {};
        const clientsRow = document.getElementById('clients-row');
        if (Object.keys(clients).length > 0) {
            clientsRow.innerHTML = Object.entries(clients).map(([cid, c]) => {
                // Support both flat (c.accuracy) and nested (c.metrics.accuracy) formats
                const rawAcc = (c.metrics && c.metrics.accuracy != null) ? c.metrics.accuracy : (c.accuracy != null ? c.accuracy : null);
                const acc = rawAcc != null ? (rawAcc * 100).toFixed(1) + '%' : '—';
                let statusClass = '';
                let badges = '';

                if (c.status === 'training') statusClass = ' active';
                if (poison[cid] && poison[cid].poisoned) {
                    statusClass = ' warning-node';
                    badges += '<span class="node-badge badge-poison">⚠ POISON</span>';
                }
                if (drift.drift_detected) {
                    badges += '<span class="node-badge badge-drift">↭ DRIFT</span>';
                }

                return `<div class="tree-node${statusClass}" title="${cid}">
                    <span class="node-icon">💻</span>
                    <span class="node-label">${cid.replace('Client_0', 'C')}</span>
                    <span class="node-metric">${acc}</span>
                    ${badges}
                </div>`;
            }).join('');
        }
    }

    /* ─── Client Heatmap ──────────────────────────────────────── */
    function renderHeatmap(state) {
        const clients = state.clients || {};
        const grid = document.getElementById('heatmap-grid');
        const entries = Object.entries(clients);
        if (entries.length === 0) return;

        grid.innerHTML = entries.map(([cid, c]) => {
            // Support both flat and nested metric formats
            let dr = 0;
            if (c.metrics) {
                dr = c.metrics.detection_rate != null ? c.metrics.detection_rate : (c.metrics.accuracy || 0);
            } else {
                dr = c.detection_rate != null ? c.detection_rate : (c.accuracy || 0);
            }
            const pct = dr * 100;
            const color = heatColor(dr);
            return `<div class="heat-cell" style="background:${color}" title="${cid}">
                <span class="heat-label">${cid.replace('Client_0', 'C')}</span>
                <span class="heat-value">${pct.toFixed(1)}%</span>
            </div>`;
        }).join('');
    }

    function heatColor(value) {
        // 0 = deep red, 0.5 = amber, 1.0 = green
        const v = Math.max(0, Math.min(1, value));
        if (v < 0.5) {
            const t = v * 2;
            return `rgba(${Math.round(255 - t * 155)}, ${Math.round(t * 140 + 50)}, ${Math.round(50)}, 0.2)`;
        }
        const t = (v - 0.5) * 2;
        return `rgba(${Math.round(100 - t * 80)}, ${Math.round(190 + t * 65)}, ${Math.round(50 - t * 15)}, 0.2)`;
    }

    /* ─── Communication Chart ─────────────────────────────────── */
    function renderCommChart(state) {
        const h = state.communication_history || [];
        if (!commChart || h.length === 0) return;

        commChart.data.labels = h.map(r => 'R' + r.round);
        commChart.data.datasets[0].data = h.map(r => r.upload_mb || 0);
        commChart.data.datasets[1].data = h.map(r => r.download_mb || 0);
        commChart.update('none');

        const totalUp = h.reduce((s, r) => s + (r.upload_mb || 0), 0);
        const totalDown = h.reduce((s, r) => s + (r.download_mb || 0), 0);
        setText('comm-upload', totalUp.toFixed(2));
        setText('comm-download', totalDown.toFixed(2));
    }

    /* ─── Anomaly Timeline Chart ──────────────────────────────── */
    function renderAnomalyChart(state) {
        const anomaly = state.anomaly || {};
        const history = anomaly.history || [];
        if (!anomalyChart || history.length === 0) return;

        anomalyChart.data.labels = history.map(r => 'R' + r.round);
        anomalyChart.data.datasets[0].data = history.map(r => r.mean_score || 0);
        anomalyChart.data.datasets[1].data = history.map(r => r.max_score || 0);
        anomalyChart.data.datasets[2].data = history.map(r => 0.8); // threshold line
        anomalyChart.update('none');

        setText('anomaly-avg', (anomaly.current_mean || 0).toFixed(3));
        setText('anomaly-high', anomaly.above_threshold || 0);
    }

    /* ─── Weight Divergence Radar ─────────────────────────────── */
    function renderDivergenceChart(state) {
        const div = state.weight_divergence || {};
        const clients = Object.keys(div);
        if (!divergenceChart || clients.length === 0) return;

        divergenceChart.data.labels = clients.map(c => c.replace('Client_0', 'C'));
        divergenceChart.data.datasets[0].data = clients.map(c => {
            const v = div[c];
            return typeof v === 'object' ? (v.cosine_distance || 0) : (v || 0);
        });
        divergenceChart.update('none');
    }

    /* ─── Incident Feed ───────────────────────────────────────── */
    function renderIncidents(state) {
        const incidents = state.incidents || [];
        const feed = document.getElementById('incident-feed');
        setText('incident-count', incidents.length + ' events');

        if (incidents.length === 0) {
            feed.innerHTML = '<div class="incident-empty">Waiting for incidents…</div>';
            return;
        }

        // Filter
        const filtered = incidentFilter === 'all'
            ? incidents
            : incidents.filter(i => (i.type || 'attack') === incidentFilter);

        feed.innerHTML = filtered.slice(-50).reverse().map(inc => {
            const type = inc.type || 'attack';
            const severity = inc.severity || (type === 'poison' ? 'high' : type === 'drift' ? 'medium' : 'low');
            const time = inc.timestamp ? new Date(inc.timestamp).toLocaleTimeString() : '—';
            const statusBadge = inc.status
                ? `<span class="incident-badge mitigated">${inc.status}</span>`
                : '';

            return `<div class="incident-item type-${type} severity-${severity}">
                <span class="incident-time">${time}</span>
                <span class="incident-badge ${type}">${type.toUpperCase()}</span>
                <span class="incident-text">${inc.client_id || '—'}: ${inc.description || inc.attack_type || 'Event detected'}</span>
                ${statusBadge}
            </div>`;
        }).join('');
    }

    /* ─── Training Timeline (Gantt) ───────────────────────────── */
    function renderTimeline(state) {
        const events = state.timeline || [];
        if (!timelineChart || events.length === 0) return;

        // Build horizontal bar chart data
        const categories = [...new Set(events.map(e => e.name))].slice(-15);
        const colorMap = {
            training: '#00e5ff', aggregation: '#76ff03',
            evaluation: '#ff6e40', communication: '#ab47bc',
            defense: '#ffd740', other: '#78909c'
        };

        timelineChart.data.labels = categories;
        timelineChart.data.datasets = [{
            data: categories.map(cat => {
                const evt = events.find(e => e.name === cat);
                return evt ? evt.duration_ms || 0 : 0;
            }),
            backgroundColor: categories.map(cat => {
                const evt = events.find(e => e.name === cat);
                return colorMap[(evt || {}).category || 'other'] || '#78909c';
            }),
            borderRadius: 4,
            borderSkipped: false,
        }];
        timelineChart.update('none');
    }

    /* ═══════════════════════════════════════════════════════════
       CHART INITIALIZATION
       ═══════════════════════════════════════════════════════════ */
    function initCharts() {
        // Convergence
        const ctxConv = document.getElementById('convergence-chart');
        if (ctxConv) {
            convergenceChart = new Chart(ctxConv, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'Accuracy (%)',
                            data: [],
                            borderColor: '#00e5ff',
                            backgroundColor: 'rgba(0,229,255,0.08)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.35,
                            pointRadius: 3,
                            pointBackgroundColor: '#00e5ff',
                            yAxisID: 'y',
                        },
                        {
                            label: 'Loss',
                            data: [],
                            borderColor: '#ff5252',
                            backgroundColor: 'rgba(255,82,82,0.05)',
                            borderWidth: 2,
                            fill: false,
                            tension: 0.35,
                            pointRadius: 3,
                            pointBackgroundColor: '#ff5252',
                            yAxisID: 'y1',
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        y: { position: 'left', min: 0, max: 100, title: { display: true, text: 'Accuracy %' }, grid: { color: 'rgba(255,255,255,0.03)' } },
                        y1: { position: 'right', min: 0, title: { display: true, text: 'Loss' }, grid: { drawOnChartArea: false } },
                        x: { grid: { color: 'rgba(255,255,255,0.03)' } }
                    },
                    plugins: { legend: { position: 'top' } }
                }
            });
        }

        // Communication
        const ctxComm = document.getElementById('comm-chart');
        if (ctxComm) {
            commChart = new Chart(ctxComm, {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [
                        { label: 'Upload (MB)', data: [], backgroundColor: 'rgba(0,229,255,0.4)', borderRadius: 4 },
                        { label: 'Download (MB)', data: [], backgroundColor: 'rgba(118,255,3,0.4)', borderRadius: 4 }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.03)' } },
                        x: { grid: { display: false } }
                    },
                    plugins: { legend: { position: 'top' } }
                }
            });
        }

        // Anomaly Timeline
        const ctxAnomaly = document.getElementById('anomaly-chart');
        if (ctxAnomaly) {
            anomalyChart = new Chart(ctxAnomaly, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'Mean Score',
                            data: [],
                            borderColor: '#ff6e40',
                            backgroundColor: 'rgba(255,110,64,0.08)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.3,
                            pointRadius: 3,
                            pointBackgroundColor: '#ff6e40',
                        },
                        {
                            label: 'Max Score',
                            data: [],
                            borderColor: '#ff5252',
                            borderWidth: 1.5,
                            borderDash: [4, 3],
                            fill: false,
                            tension: 0.3,
                            pointRadius: 2,
                        },
                        {
                            label: 'Threshold',
                            data: [],
                            borderColor: 'rgba(255,215,64,0.4)',
                            borderWidth: 1,
                            borderDash: [8, 4],
                            fill: false,
                            pointRadius: 0,
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { min: 0, max: 1, grid: { color: 'rgba(255,255,255,0.03)' } },
                        x: { grid: { display: false } }
                    },
                    plugins: { legend: { position: 'top' } }
                }
            });
        }

        // Weight Divergence Radar
        const ctxDiv = document.getElementById('divergence-chart');
        if (ctxDiv) {
            divergenceChart = new Chart(ctxDiv, {
                type: 'radar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Divergence',
                        data: [],
                        borderColor: '#b388ff',
                        backgroundColor: 'rgba(179,136,255,0.12)',
                        borderWidth: 2,
                        pointBackgroundColor: '#b388ff',
                        pointRadius: 4,
                        pointHoverRadius: 6,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        r: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255,255,255,0.06)' },
                            angleLines: { color: 'rgba(255,255,255,0.06)' },
                            pointLabels: { font: { size: 11 }, color: '#8892a8' },
                            ticks: { display: false }
                        }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }

        // Training Timeline (horizontal bar)
        const ctxTimeline = document.getElementById('timeline-chart');
        if (ctxTimeline) {
            timelineChart = new Chart(ctxTimeline, {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: [],
                        borderRadius: 4,
                        borderSkipped: false,
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            title: { display: true, text: 'Duration (ms)' },
                            grid: { color: 'rgba(255,255,255,0.03)' }
                        },
                        y: {
                            grid: { display: false },
                            ticks: { font: { size: 10 } }
                        }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }
    }

    /* ═══════════════════════════════════════════════════════════
       CLOCK & FILTERS & CONTROLS
       ═══════════════════════════════════════════════════════════ */
    function initClock() {
        function tick() {
            const now = new Date();
            setText('live-clock',
                now.getHours().toString().padStart(2, '0') + ':' +
                now.getMinutes().toString().padStart(2, '0') + ':' +
                now.getSeconds().toString().padStart(2, '0')
            );
        }
        tick();
        setInterval(tick, 1000);
    }

    function initFilters() {
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                incidentFilter = btn.dataset.filter;
                if (lastState) renderIncidents(lastState);
            });
        });
    }

    async function initControls() {
        // Fetch current config on load to populate dropdowns
        try {
            const resp = await fetch('/api/config');
            if (resp.ok) {
                const conf = await resp.json();
                if (conf.model) document.getElementById('ctrl-model').value = conf.model;
                if (conf.strategy) document.getElementById('ctrl-strategy').value = conf.strategy;
                if (conf.scenario) document.getElementById('ctrl-scenario').value = conf.scenario;
                if (conf.rounds) document.getElementById('ctrl-rounds').value = conf.rounds;
            }
        } catch (e) {
            console.error('Failed to init config:', e);
        }

        const btnSave = document.getElementById('btn-save-config');
        if (btnSave) {
            btnSave.addEventListener('click', async () => {
                const payload = {
                    model: document.getElementById('ctrl-model').value,
                    strategy: document.getElementById('ctrl-strategy').value,
                    scenario: document.getElementById('ctrl-scenario').value,
                    rounds: parseInt(document.getElementById('ctrl-rounds').value) || 80,
                };

                const originalText = btnSave.textContent;
                btnSave.textContent = 'Saving...';
                btnSave.disabled = true;

                try {
                    const resp = await fetch('/api/config/save', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload),
                    });
                    if (resp.ok) {
                        btnSave.textContent = '✅ Saved!';
                        setTimeout(() => {
                            btnSave.textContent = originalText;
                            btnSave.disabled = false;
                        }, 2000);
                    } else {
                        throw new Error('Server returned error');
                    }
                } catch (e) {
                    console.error('Save failed:', e);
                    btnSave.textContent = '❌ Failed';
                    setTimeout(() => {
                        btnSave.textContent = originalText;
                        btnSave.disabled = false;
                    }, 2000);
                }
            });
        }

        // Shutdown button
        const btnShutdown = document.getElementById('btn-shutdown');
        if (btnShutdown) {
            btnShutdown.addEventListener('click', async () => {
                if (confirm('Are you sure you want to shutdown the entire FL-NIDS system?')) {
                    const originalText = btnShutdown.textContent;
                    btnShutdown.textContent = 'Shutting down...';
                    btnShutdown.disabled = true;

                    try {
                        const resp = await fetch('/api/shutdown', {
                            method: 'POST',
                        });
                        if (resp.ok) {
                            btnShutdown.textContent = '✅ Shutdown triggered!';
                            alert('Shutdown triggered. Check server logs for confirmation.');
                        } else {
                            throw new Error('Server returned error');
                        }
                    } catch (e) {
                        console.error('Shutdown failed:', e);
                        btnShutdown.textContent = '❌ Failed';
                        alert('Shutdown failed. Check console for details.');
                    } finally {
                        setTimeout(() => {
                            btnShutdown.textContent = originalText;
                            btnShutdown.disabled = false;
                        }, 3000);
                    }
                }
            });
        }

        // Reload button
        const btnReload = document.getElementById('btn-reload');
        if (btnReload) {
            btnReload.addEventListener('click', async () => {
                const originalText = btnReload.textContent;
                btnReload.textContent = 'Reloading...';
                btnReload.disabled = true;

                try {
                    const resp = await fetch('/api/reload', {
                        method: 'POST',
                    });
                    if (resp.ok) {
                        btnReload.textContent = '✅ Reload triggered!';
                        alert('Configuration reload triggered. Check server logs for confirmation.');
                    } else {
                        throw new Error('Server returned error');
                    }
                } catch (e) {
                    console.error('Reload failed:', e);
                    btnReload.textContent = '❌ Failed';
                    alert('Reload failed. Check console for details.');
                } finally {
                    setTimeout(() => {
                        btnReload.textContent = originalText;
                        btnReload.disabled = false;
                    }, 2000);
                }
            });
        }
    }

    /* ═══════════════════════════════════════════════════════════
       UTILITIES
       ═══════════════════════════════════════════════════════════ */
    function setText(id, text) {
        const el = document.getElementById(id);
        if (el && el.textContent !== String(text)) {
            el.textContent = text;
        }
    }

    function setBar(id, pct) {
        const el = document.getElementById(id);
        if (el) el.style.width = Math.min(100, Math.max(0, pct)) + '%';
    }

})();
