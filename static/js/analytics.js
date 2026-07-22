const fmtCur = (n) => '₹' + (Number(n) || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });

async function loadAnalytics() {
    const res = await fetch('/api/analytics-data');
    const data = await res.json();

    document.getElementById('statProjects').innerText = data.summary.total_projects;
    document.getElementById('statTotalValue').innerText = fmtCur(data.summary.total_ai_value);
    document.getElementById('statCostPerSqm').innerText = fmtCur(data.summary.avg_cost_per_sqm);
    document.getElementById('statVariance').innerText = `${data.summary.avg_variance}%`;

    new Chart(document.getElementById('costByProjectChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [
                { label: 'AI Estimate', data: data.ai_costs, backgroundColor: '#2563eb' },
                { label: 'Manual Estimate', data: data.manual_costs, backgroundColor: '#f59e0b' }
            ]
        },
        options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
    });

    const b = data.latest_breakdown;
    new Chart(document.getElementById('breakdownChart').getContext('2d'), {
        type: 'doughnut',
        data: {
            labels: ['Material', 'Labour', 'Wastage', 'GST', 'Contractor Profit'],
            datasets: [{
                data: [b.material, b.labour, b.wastage, b.gst, b.profit],
                backgroundColor: ['#2563eb', '#f59e0b', '#94a3b8', '#dc2626', '#16a34a']
            }]
        },
        options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
    });

    new Chart(document.getElementById('varianceChart').getContext('2d'), {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Variance %',
                data: data.variances,
                borderColor: '#dc2626',
                backgroundColor: 'rgba(220,38,38,.15)',
                tension: 0.3,
                fill: true
            }]
        },
        options: { responsive: true, plugins: { legend: { display: false } } }
    });

    new Chart(document.getElementById('areaChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [{ label: 'Built-up Area (sq.m)', data: data.areas, backgroundColor: '#1e293b' }]
        },
        options: { responsive: true, indexAxis: 'y', plugins: { legend: { display: false } } }
    });
}

loadAnalytics();
