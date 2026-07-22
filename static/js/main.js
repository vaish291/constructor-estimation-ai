let currentAITotal = 0.0;
let currentArea = 0.0;
let currentPerimeter = 0.0;
let currentMetrics = {};
let currentBoq = {};
let currentOptimization = {};
let chartInstance = null;

const fmt = (n) => (Number(n) || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 });

document.getElementById('planForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const btn = document.getElementById('analyzeBtn');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = 'Analyzing plan with AI...';

    try {
        const formData = new FormData();
        formData.append('plan_file', document.getElementById('planFile').files[0]);
        formData.append('location_id', document.getElementById('locationSelect').value);
        formData.append('schedule_type', document.getElementById('scheduleSelect').value);
        formData.append('gst_pct', document.getElementById('gstPct').value || 18);
        formData.append('wastage_pct', document.getElementById('wastagePct').value || 'auto');
        formData.append('profit_pct', document.getElementById('profitPct').value || 15);
        formData.append('budget_tier', document.getElementById('budgetTier').value);
        formData.append('scale_factor', document.getElementById('scaleFactor').value || 50);

        const res = await fetch('/api/analyze-plan', { method: 'POST', body: formData });
        const data = await res.json();

        if (data.error) {
            alert(data.error);
            return;
        }

        currentMetrics = data.metrics;
        currentBoq = data.boq;
        currentOptimization = data.optimization;
        currentArea = data.metrics.built_up_area_sqm;
        currentPerimeter = data.metrics.perimeter_m;
        currentAITotal = data.boq.total_ai_cost;

        renderMetrics(data.metrics, data.boq);
        renderBoqTable(data.boq);
        renderOptimization(data.optimization);
        renderRecommendation(data.recommendation);

        if (data.metrics.ocr_metadata) {
            document.getElementById('ocrBox').classList.remove('d-none');
            document.getElementById('ocrText').innerText = data.metrics.ocr_metadata || '(no text detected)';
        }
    } catch (err) {
        alert('Something went wrong while analyzing the plan: ' + err);
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
});

function renderMetrics(metrics, boq) {
    document.getElementById('areaVal').innerHTML = `${fmt(metrics.built_up_area_sqm)} <small>sq.m</small>`;
    document.getElementById('perimVal').innerHTML = `${fmt(metrics.perimeter_m)} <small>m</small>`;
    document.getElementById('roomVal').innerText = metrics.room_count;
    document.getElementById('wallVal').innerText = metrics.wall_count;
    document.getElementById('doorVal').innerText = metrics.door_count;
    document.getElementById('windowVal').innerText = metrics.window_count;
    document.getElementById('slabVal').innerHTML = `${fmt(boq.slab_area_sqm)} <small>sq.m</small>`;
    document.getElementById('paintTileVal').innerText = `${fmt(boq.paint_area_sqm)} / ${fmt(boq.tile_area_sqm)} sq.m`;
}

function renderBoqTable(boq) {
    const tbody = document.getElementById('boqTable');
    tbody.innerHTML = '';

    boq.material_boq.forEach(item => {
        tbody.innerHTML += `
            <tr>
                <td class="fw-medium">${item.item}</td>
                <td class="mono">${fmt(item.quantity)} ${item.unit}</td>
                <td class="mono">₹${fmt(item.rate)}</td>
                <td><span class="badge badge-source">${item.rate_source || ''}</span></td>
                <td class="mono fw-semibold">₹${fmt(item.total_cost)}</td>
            </tr>`;
    });

    boq.labour_boq.forEach(item => {
        tbody.innerHTML += `
            <tr class="row-labour">
                <td class="fw-medium">${item.category} (Labour)</td>
                <td class="mono">${fmt(item.days)} Days</td>
                <td class="mono">₹${fmt(item.rate)}</td>
                <td>-</td>
                <td class="mono fw-semibold">₹${fmt(item.total_cost)}</td>
            </tr>`;
    });

    const tfoot = document.getElementById('boqFoot');
    tfoot.innerHTML = `
        <tr><td colspan="4">Material Cost</td><td class="mono">₹${fmt(boq.material_cost)}</td></tr>
        <tr><td colspan="4">Labour Cost</td><td class="mono">₹${fmt(boq.labour_cost)}</td></tr>
        <tr><td colspan="4">Material Wastage Allowance</td><td class="mono">₹${fmt(boq.wastage_amount)}</td></tr>
        <tr><td colspan="4">GST @ ${boq.gst_pct}%</td><td class="mono">₹${fmt(boq.gst_amount)}</td></tr>
        <tr><td colspan="4">Contractor Profit @ ${boq.profit_pct}%</td><td class="mono">₹${fmt(boq.profit_amount)}</td></tr>
        <tr class="border-top border-2"><td colspan="4" class="fs-6">AI Total Cost Estimate</td><td class="mono fs-6 text-primary">₹${fmt(boq.total_ai_cost)}</td></tr>
    `;
}

function renderOptimization(optimization) {
    const box = document.getElementById('optimizationBox');
    if (!optimization || !optimization.suggestions || optimization.suggestions.length === 0) {
        box.innerHTML = `<p class="text-muted small mb-0">No lower-cost alternatives identified for the current material list.</p>`;
        return;
    }

    let html = `<div class="table-responsive"><table class="table table-sm mb-2">
        <thead><tr><th>Item</th><th>Alternative</th><th class="text-end">Saving (₹)</th></tr></thead><tbody>`;
    optimization.suggestions.forEach(s => {
        html += `<tr>
            <td>${s.original_item}</td>
            <td>${s.suggested_alternative}<div class="text-muted" style="font-size:.72rem;">${s.note}</div></td>
            <td class="text-end mono text-success fw-semibold">₹${fmt(s.estimated_saving)}</td>
        </tr>`;
    });
    html += `</tbody></table></div>
        <div class="fw-bold text-success">Total Potential Saving: ₹${fmt(optimization.total_estimated_saving)}</div>`;
    box.innerHTML = html;
}

function renderRecommendation(recommendation) {
    const box = document.getElementById('recommendationBox');
    if (!recommendation || !recommendation.recommendations) {
        box.innerHTML = `<p class="text-muted small mb-0">Recommendation data unavailable.</p>`;
        return;
    }
    let html = `<div class="mb-2"><span class="badge badge-source">${recommendation.budget_tier} Tier</span></div><ul class="list-group list-group-flush">`;
    Object.entries(recommendation.recommendations).forEach(([item, grade]) => {
        html += `<li class="list-group-item px-0 d-flex justify-content-between">
            <span class="fw-medium">${item}</span><span class="text-muted">${grade}</span>
        </li>`;
    });
    html += `</ul>`;
    box.innerHTML = html;
}

async function compareEstimates() {
    const manualCost = parseFloat(document.getElementById('manualCost').value) || 0;
    const projectName = document.getElementById('projectName').value;

    if (manualCost <= 0) {
        alert("Please enter a valid manual cost.");
        return;
    }
    if (!currentBoq || !currentBoq.total_ai_cost) {
        alert("Please analyze a floor plan first to generate the AI estimate.");
        return;
    }

    const response = await fetch('/api/save-comparison', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            project_name: projectName,
            area: currentArea,
            perimeter: currentPerimeter,
            ai_cost: currentAITotal,
            manual_cost: manualCost,
            metrics: currentMetrics,
            boq: currentBoq,
            optimization: currentOptimization,
            rate_source: document.getElementById('scheduleSelect').value,
            location_id: parseInt(document.getElementById('locationSelect').value)
        })
    });

    const resData = await response.json();

    const varBox = document.getElementById('varianceBox');
    varBox.classList.remove('d-none', 'bg-danger-subtle', 'text-danger', 'bg-success-subtle', 'text-success');

    if (resData.variance > 0) {
        varBox.classList.add('bg-danger-subtle', 'text-danger');
        varBox.innerText = `AI estimate is higher by ${resData.variance}%`;
    } else {
        varBox.classList.add('bg-success-subtle', 'text-success');
        varBox.innerText = `AI estimate is lower by ${Math.abs(resData.variance)}%`;
    }

    const pdfContainer = document.getElementById('exportBtnContainer');
    pdfContainer.classList.remove('d-none');
    document.getElementById('downloadPdfBtn').href = `/api/export-pdf/${resData.project_id}`;
    document.getElementById('downloadExcelBtn').href = `/api/export-excel/${resData.project_id}`;

    renderChart(currentAITotal, manualCost);
}

function renderChart(ai, manual) {
    const ctx = document.getElementById('comparisonChart').getContext('2d');
    if (chartInstance) chartInstance.destroy();

    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['AI Assisted Estimate', 'Manual Estimate'],
            datasets: [{
                label: 'Cost in ₹',
                data: [ai, manual],
                backgroundColor: ['#2563eb', '#f59e0b']
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } }
        }
    });
}
