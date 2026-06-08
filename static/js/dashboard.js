// ============================================
// POLYMARKET BOT - DASHBOARD JAVASCRIPT
// ============================================

// Global state
const state = {
    candles: [],
    trades: [],
    orders: [],
    stats: null,
    signal: null,
    windowInfo: null,
    pendingOrder: null,
    pnlHistory: [],
};

// Chart instances
let candleChart = null;
let pnlChart = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Dashboard initializing...');
    initCharts();
    startDataRefresh();
    updateTimestamp();
    setInterval(updateTimestamp, 1000);
});

// ============================================
// CHART INITIALIZATION
// ============================================
function initCharts() {
    // Initialize candlestick chart using Lightweight Charts
    initCandleChart();

    // Initialize P&L chart using Chart.js
    initPnLChart();
}

function initCandleChart() {
    const chartContainer = document.getElementById('tradingview-chart');
    const chart = LightweightCharts.createChart(chartContainer, {
        layout: {
            textColor: '#6B7280',
            background: { color: '#FFFFFF' },
        },
        timeScale: {
            timeVisible: true,
            secondsVisible: true,
        },
        grid: {
            hStyle: LightweightCharts.GridLineStyle.Dashed,
            vStyle: LightweightCharts.GridLineStyle.Dashed,
        },
    });

    candleChart = chart.addCandlestickSeries({
        upColor: '#10B981',
        downColor: '#EF4444',
        borderUpColor: '#10B981',
        borderDownColor: '#EF4444',
        wickUpColor: '#10B981',
        wickDownColor: '#EF4444',
    });

    chart.timeScale().fitContent();
    window.candleChartInstance = chart;
}

function initPnLChart() {
    const ctx = document.getElementById('pnl-chart').getContext('2d');
    pnlChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Cumulative P&L',
                    data: [],
                    borderColor: '#0052CC',
                    backgroundColor: 'rgba(0, 82, 204, 0.05)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointBackgroundColor: '#0052CC',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false,
                },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: '#E5E7EB' },
                    ticks: { color: '#6B7280' },
                },
                x: {
                    grid: { color: '#E5E7EB' },
                    ticks: { color: '#6B7280' },
                },
            },
        },
    });
}

// ============================================
// DATA REFRESH LOOP
// ============================================
function startDataRefresh() {
    // Refresh every 1 second
    setInterval(async () => {
        await refreshAllData();
    }, 1000);

    // Initial load
    refreshAllData();
}

async function refreshAllData() {
    try {
        await Promise.all([
            fetchCandles(),
            fetchStats(),
            fetchSignalComponents(),
            fetchWindowInfo(),
            fetchPendingOrder(),
            fetchTrades(),
            fetchBTCPrice(),
        ]);

        updateUI();
    } catch (error) {
        console.error('Error refreshing data:', error);
    }
}

// ============================================
// API CALLS
// ============================================
async function fetchCandles() {
    try {
        const response = await fetch('/api/candles');
        state.candles = await response.json();
    } catch (error) {
        console.error('Error fetching candles:', error);
    }
}

async function fetchStats() {
    try {
        const response = await fetch('/api/stats');
        state.stats = await response.json();
    } catch (error) {
        console.error('Error fetching stats:', error);
    }
}

async function fetchSignalComponents() {
    try {
        const response = await fetch('/api/signal-components');
        const components = await response.json();
        state.signal = state.signal || {};
        state.signal.components = components;
    } catch (error) {
        console.error('Error fetching signal components:', error);
    }
}

async function fetchWindowInfo() {
    try {
        const response = await fetch('/api/window-info');
        state.windowInfo = await response.json();
    } catch (error) {
        console.error('Error fetching window info:', error);
    }
}

async function fetchPendingOrder() {
    try {
        const response = await fetch('/api/pending-order');
        state.pendingOrder = await response.json();
    } catch (error) {
        console.error('Error fetching pending order:', error);
    }
}

async function fetchTrades() {
    try {
        const response = await fetch('/api/trades');
        state.trades = await response.json();
    } catch (error) {
        console.error('Error fetching trades:', error);
    }
}

async function fetchBTCPrice() {
    try {
        const response = await fetch('/api/btc/price');
        const data = await response.json();
        state.btcPrice = data.current_price;
        state.btcChange24h = data.change_24h;
    } catch (error) {
        console.error('Error fetching BTC price:', error);
    }
}

// ============================================
// UI UPDATE
// ============================================
function updateUI() {
    updateBTCPrice();
    updateCandleChart();
    updateSignal();
    updateWindow();
    updateMartingale();
    updatePendingOrder();
    updateTradesTable();
    updatePnLChart();
}

function updateBTCPrice() {
    if (!state.btcPrice) return;

    const priceEl = document.getElementById('btcPrice');
    const changeEl = document.getElementById('btcChange');

    if (priceEl) {
        priceEl.textContent = `$${state.btcPrice.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
    }

    if (changeEl && state.btcChange24h) {
        const change = state.btcChange24h.change_pct || 0;
        changeEl.textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
        changeEl.style.color = change >= 0 ? '#10B981' : '#EF4444';
    }
}

function updateCandleChart() {
    if (!candleChart || !state.candles || state.candles.length === 0) return;

    const data = state.candles.map(candle => ({
        time: Math.floor(candle.timestamp / 1000),
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
    }));

    candleChart.setData(data);
    window.candleChartInstance.timeScale().fitContent();
}

function updateSignal() {
    if (!state.stats) return;

    const score = state.stats.signal_score || 0;
    const direction = state.stats.signal_direction || '--';

    // Update direction
    const dirEl = document.getElementById('signal-direction');
    dirEl.textContent = direction;
    dirEl.style.color = direction === 'UP' ? '#10B981' : '#EF4444';

    // Update score
    document.getElementById('signal-score').textContent = score.toFixed(1);

    // Update components
    if (state.signal && state.signal.components) {
        updateComponent('ta', state.signal.components.ta);
        updateComponent('fr', state.signal.components.funding_rate);
        updateComponent('fg', state.signal.components.fear_greed);
        updateComponent('ob', state.signal.components.orderbook);
    }
}

function updateComponent(id, value) {
    const fillEl = document.getElementById(`comp-${id}`);
    const textEl = document.getElementById(`comp-${id}-text`);

    if (fillEl && textEl && value !== undefined) {
        const percentage = Math.min(100, Math.max(0, value));
        fillEl.style.width = `${percentage}%`;
        textEl.textContent = `${percentage.toFixed(0)}%`;
    }
}

function updateWindow() {
    if (!state.windowInfo) return;

    const countdown = state.windowInfo.countdown;
    const percentage = state.windowInfo.percentage;
    const inEntry = state.windowInfo.in_entry_window;

    // Update countdown timer
    const minutes = Math.floor(countdown / 60);
    const seconds = countdown % 60;
    document.getElementById('countdown-time').textContent =
        `${minutes}:${seconds.toString().padStart(2, '0')}`;

    // Update progress bar
    document.getElementById('window-progress').style.width = `${percentage}%`;

    // Update entry stage highlight
    const entryStage = document.getElementById('entry-stage');
    if (inEntry) {
        entryStage.classList.add('entry');
    } else {
        entryStage.classList.remove('entry');
    }
}

function updateMartingale() {
    if (!state.stats) return;

    const stats = state.stats;

    document.getElementById('current-level').textContent = stats.current_level || 1;
    document.getElementById('current-stake').textContent = `$${stats.current_stake?.toFixed(2) || '0.00'}`;
    document.getElementById('wins').textContent = stats.total_wins || 0;
    document.getElementById('losses').textContent = stats.total_losses || 0;
    document.getElementById('win-rate').textContent = `${(stats.win_rate || 0).toFixed(1)}%`;
    document.getElementById('total-trades').textContent = stats.total_trades || 0;

    const pnl = stats.net_pnl || 0;
    const pnlEl = document.getElementById('net-pnl');
    pnlEl.textContent = `$${pnl.toFixed(2)}`;
    pnlEl.classList.toggle('negative', pnl < 0);
}

function updatePendingOrder() {
    const orderCard = document.getElementById('order-card');

    if (!state.pendingOrder) {
        orderCard.style.display = 'none';
        return;
    }

    orderCard.style.display = 'block';

    const order = state.pendingOrder;
    const dirEl = document.querySelector('.order-direction');

    dirEl.textContent = order.direction === 'UP' ? '📈 UP' : '📉 DOWN';
    dirEl.classList.remove('up', 'down');
    dirEl.classList.add(order.direction.toLowerCase());

    document.getElementById('order-stake').textContent = `$${order.stake?.toFixed(2) || '--'}`;
    document.getElementById('order-level').textContent = order.level || '--';
    document.getElementById('order-id').textContent = order.order_id?.substring(0, 12) + '...' || '--';
}

function updateTradesTable() {
    const tbody = document.getElementById('trades-tbody');

    if (!state.trades || state.trades.length === 0) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="6">No trades yet...</td></tr>';
        return;
    }

    tbody.innerHTML = state.trades
        .slice()
        .reverse()
        .slice(0, 20)
        .map((trade, idx) => {
            const isWin = trade.type === 'WIN';
            const result = isWin
                ? `+$${(trade.pnl || 0).toFixed(2)}`
                : `-$${(trade.loss || 0).toFixed(2)}`;

            return `
            <tr>
                <td>${new Date().toLocaleTimeString()}</td>
                <td>${trade.level}</td>
                <td><span class="${isWin ? 'win' : 'loss'}">${trade.type}</span></td>
                <td>$${(trade.stake || 0).toFixed(2)}</td>
                <td>${isWin ? '✅' : '❌'}</td>
                <td><span class="${isWin ? 'win' : 'loss'}">${result}</span></td>
            </tr>
        `;
        })
        .join('');
}

function updatePnLChart() {
    if (!pnlChart || !state.trades || state.trades.length === 0) return;

    let cumulative = 0;
    const labels = [];
    const data = [];

    state.trades.forEach((trade, idx) => {
        if (trade.type === 'WIN') {
            cumulative += trade.pnl || 0;
        } else {
            cumulative -= trade.loss || 0;
        }

        labels.push(`Trade ${idx + 1}`);
        data.push(cumulative.toFixed(2));
    });

    // Keep only last 30 trades
    const sliceStart = Math.max(0, labels.length - 30);
    pnlChart.data.labels = labels.slice(sliceStart);
    pnlChart.data.datasets[0].data = data.slice(sliceStart);
    pnlChart.update('none');
}

// ============================================
// UTILITIES
// ============================================
function updateTimestamp() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
    });
    document.getElementById('timestamp').textContent = timeString;
}

// Start the dashboard
console.log('✅ Dashboard ready!');
