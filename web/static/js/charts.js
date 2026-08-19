// Chart.js configuration and management

// Chart instances
let vibeChart = null;
let activityChart = null;

// Chart.js default configuration
Chart.defaults.color = 'rgba(255, 255, 255, 0.8)';
Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';
Chart.defaults.backgroundColor = 'rgba(255, 255, 255, 0.1)';

// Color schemes
const vibeColors = {
    overall: '#6f42c1',
    activity: '#0d6efd',
    positivity: '#198754',
    engagement: '#20c997',
    growth: '#ffc107'
};

const activityColors = {
    messages: '#0d6efd',
    users: '#198754',
    reactions: '#fd7e14',
    members: '#6f42c1'
};

function initializeServerCharts(serverId) {
    // Load vibe history data
    loadVibeChart(serverId);
    
    // Load activity analytics
    loadActivityChart(serverId);
}

function loadVibeChart(serverId, days = 30) {
    fetch(`/api/server/${serverId}/vibe-history?days=${days}`)
        .then(response => response.json())
        .then(data => {
            createVibeChart(data);
        })
        .catch(error => {
            console.error('Error loading vibe chart data:', error);
            showEmptyVibeChart();
        });
}

function loadActivityChart(serverId, days = 30) {
    fetch(`/api/server/${serverId}/analytics?days=${days}`)
        .then(response => response.json())
        .then(data => {
            createActivityChart(data);
        })
        .catch(error => {
            console.error('Error loading activity chart data:', error);
            showEmptyActivityChart();
        });
}

function createVibeChart(data) {
    const ctx = document.getElementById('vibeChart');
    if (!ctx) return;
    
    // Destroy existing chart
    if (vibeChart) {
        vibeChart.destroy();
    }
    
    if (data.length === 0) {
        showEmptyVibeChart();
        return;
    }
    
    const labels = data.map(item => {
        const date = new Date(item.date);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });
    
    vibeChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Overall Vibe',
                    data: data.map(item => item.overall_score),
                    borderColor: vibeColors.overall,
                    backgroundColor: vibeColors.overall + '20',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Activity',
                    data: data.map(item => item.activity_score),
                    borderColor: vibeColors.activity,
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [5, 5]
                },
                {
                    label: 'Positivity',
                    data: data.map(item => item.positivity_score),
                    borderColor: vibeColors.positivity,
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [5, 5]
                },
                {
                    label: 'Engagement',
                    data: data.map(item => item.engagement_score),
                    borderColor: vibeColors.engagement,
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [5, 5]
                },
                {
                    label: 'Growth',
                    data: data.map(item => item.growth_score),
                    borderColor: vibeColors.growth,
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [5, 5]
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: false
                },
                legend: {
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: 'rgba(255, 255, 255, 0.3)',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.8)'
                    }
                },
                y: {
                    min: 0,
                    max: 100,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.8)',
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

function createActivityChart(data) {
    const ctx = document.getElementById('activityChart');
    if (!ctx) return;
    
    // Destroy existing chart
    if (activityChart) {
        activityChart.destroy();
    }
    
    if (data.length === 0) {
        showEmptyActivityChart();
        return;
    }
    
    const labels = data.map(item => {
        const date = new Date(item.date);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });
    
    activityChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Messages',
                    data: data.map(item => item.message_count),
                    backgroundColor: activityColors.messages + '80',
                    borderColor: activityColors.messages,
                    borderWidth: 1,
                    yAxisID: 'y'
                },
                {
                    label: 'Active Users',
                    data: data.map(item => item.active_users),
                    backgroundColor: activityColors.users + '80',
                    borderColor: activityColors.users,
                    borderWidth: 1,
                    yAxisID: 'y1'
                },
                {
                    label: 'Reactions',
                    data: data.map(item => item.reactions_count),
                    backgroundColor: activityColors.reactions + '80',
                    borderColor: activityColors.reactions,
                    borderWidth: 1,
                    yAxisID: 'y'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: false
                },
                legend: {
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: 'rgba(255, 255, 255, 0.3)',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.8)'
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.8)'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    grid: {
                        drawOnChartArea: false
                    },
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.8)'
                    }
                }
            }
        }
    });
}

function showEmptyVibeChart() {
    const ctx = document.getElementById('vibeChart');
    if (!ctx) return;
    
    const parent = ctx.parentElement;
    parent.innerHTML = `
        <div class="d-flex flex-column align-items-center justify-content-center h-100 text-muted">
            <i class="fas fa-chart-line fa-3x mb-3"></i>
            <h6>No Vibe Data Available</h6>
            <p class="text-center mb-0">Refresh the server data to start tracking vibes.</p>
        </div>
    `;
}

function showEmptyActivityChart() {
    const ctx = document.getElementById('activityChart');
    if (!ctx) return;
    
    const parent = ctx.parentElement;
    parent.innerHTML = `
        <div class="d-flex flex-column align-items-center justify-content-center h-100 text-muted">
            <i class="fas fa-chart-bar fa-3x mb-3"></i>
            <h6>No Activity Data Available</h6>
            <p class="text-center mb-0">Refresh the server data to start tracking activity.</p>
        </div>
    `;
}

// Chart refresh functionality
function refreshCharts(serverId) {
    if (vibeChart) {
        vibeChart.destroy();
        vibeChart = null;
    }
    
    if (activityChart) {
        activityChart.destroy();
        activityChart = null;
    }
    
    // Show loading state
    showChartLoading('vibeChart');
    showChartLoading('activityChart');
    
    // Reload charts
    setTimeout(() => {
        initializeServerCharts(serverId);
    }, 500);
}

function showChartLoading(chartId) {
    const ctx = document.getElementById(chartId);
    if (!ctx) return;
    
    const parent = ctx.parentElement;
    parent.innerHTML = `
        <div class="d-flex flex-column align-items-center justify-content-center h-100">
            <div class="spinner-border text-primary mb-3" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <h6 class="text-muted">Loading chart data...</h6>
        </div>
    `;
}

// Export functions for global use
window.ChartsJS = {
    initializeServerCharts,
    refreshCharts,
    loadVibeChart,
    loadActivityChart
};
