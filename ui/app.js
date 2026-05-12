const apiOrigin = window.location.protocol.startsWith('http')
    ? window.location.origin
    : 'http://127.0.0.1:8000';
const wsProtocol = apiOrigin.startsWith('https') ? 'wss' : 'ws';
const wsHost = new URL(apiOrigin).host;
const wsUrl = `${wsProtocol}://${wsHost}/ws/data`;
let ws;
const tickers = {};
let isCapitalInputDirty = false;
let resetButtonTimer;

const connectionStatus = document.getElementById('connection-status');
const dot = document.querySelector('.dot');
const tickerContainer = document.getElementById('ticker-container');
const tradesBody = document.getElementById('trades-body');
const resetBalance = document.getElementById('reset-balance');
const resetPortfolio = document.getElementById('reset-portfolio');
const portfolioSentiment = document.getElementById('portfolio-sentiment');
const moneyFormatter = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
});

function connect() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        connectionStatus.textContent = 'Connected Live';
        dot.classList.add('connected');
    };

    ws.onclose = () => {
        connectionStatus.textContent = 'Disconnected. Reconnecting...';
        dot.classList.remove('connected');
        setTimeout(connect, 3000);
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'market_data') {
            updateTicker(msg.data);
        } else if (msg.type === 'trade_event') {
            if (msg.event === 'PORTFOLIO_UPDATE') {
                updatePortfolio(msg.data);
            } else {
                addTradeEvent(msg);
            }
        }
    };
}

async function loadPortfolio() {
    try {
        const response = await fetch(`${apiOrigin}/api/portfolio`);
        if (!response.ok) throw new Error('Portfolio request failed');
        updatePortfolio(await response.json());
    } catch (error) {
        console.error('Could not load portfolio:', error);
    }
}

async function resetVirtualMoney() {
    const balance = Number(resetBalance.value);
    if (!Number.isFinite(balance) || balance <= 0) {
        alert('Enter a virtual money amount greater than $0.');
        resetBalance.focus();
        return;
    }

    resetPortfolio.disabled = true;
    resetPortfolio.textContent = 'Funding...';

    try {
        const response = await fetch(`${apiOrigin}/api/portfolio/reset`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ balance })
        });
        if (!response.ok) throw new Error('Portfolio reset failed');
        isCapitalInputDirty = false;
        updatePortfolio(await response.json());
        tradesBody.innerHTML = '';
        resetPortfolio.textContent = 'Capital Updated';
        clearTimeout(resetButtonTimer);
        resetButtonTimer = setTimeout(() => {
            resetPortfolio.textContent = 'Update Capital';
        }, 1200);
    } catch (error) {
        console.error('Could not reset portfolio:', error);
        alert('Could not reset virtual money. Please try again.');
        resetPortfolio.textContent = 'Update Capital';
    } finally {
        resetPortfolio.disabled = false;
    }
}

function updatePortfolio(data) {
    document.getElementById('port-capital').textContent = moneyFormatter.format(data.initial_balance || data.total_value || 0);
    document.getElementById('port-total').textContent = moneyFormatter.format(data.total_value);
    document.getElementById('port-cash').textContent = moneyFormatter.format(data.balance);
    document.getElementById('port-next-order').textContent = moneyFormatter.format(data.estimated_next_trade || 0);
    if (!isCapitalInputDirty && document.activeElement !== resetBalance) {
        resetBalance.value = Number(data.initial_balance || data.total_value || resetBalance.value).toFixed(2);
    }

    const pnlEl = document.getElementById('port-pnl');
    pnlEl.textContent = moneyFormatter.format(data.unrealized_pnl);
    pnlEl.className = `stat-value ${data.unrealized_pnl >= 0 ? 'price-up' : 'price-down'}`;
    updateMarketSentiment(data.market_sentiment);

    const positionsBody = document.getElementById('positions-body');
    positionsBody.innerHTML = '';
    
    for (const [symbol, pos] of Object.entries(data.positions)) {
        if (pos.qty > 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${symbol}</td>
                <td>${pos.qty.toFixed(6)}</td>
                <td>${moneyFormatter.format(pos.avg_price)}</td>
                <td>${moneyFormatter.format(pos.current_price || 0)}</td>
            `;
            positionsBody.appendChild(tr);
        }
    }
}

function updateMarketSentiment(sentimentMap) {
    if (!portfolioSentiment || !sentimentMap || Object.keys(sentimentMap).length === 0) {
        if (portfolioSentiment) {
            portfolioSentiment.innerHTML = '<div class="sentiment-empty">Waiting for BTC and ETH market sentiment...</div>';
        }
        return;
    }

    portfolioSentiment.innerHTML = '';
    for (const sentiment of Object.values(sentimentMap)) {
        const card = document.createElement('div');
        const tone = sentiment.tone || 'neutral';
        card.className = `sentiment-card sentiment-${tone}`;
        card.dataset.price = sentiment.price || 0;
        card.dataset.trend = sentiment.trend_pct || 0;
        card.dataset.momentum = sentiment.momentum_pct || 0;
        card.dataset.volatility = sentiment.volatility_pct || 0;
        card.innerHTML = `
            <div class="sentiment-topline">
                <span class="sentiment-symbol">${sentiment.symbol}</span>
                <span class="sentiment-label">${sentiment.label}</span>
            </div>
            <div class="sentiment-price">${moneyFormatter.format(sentiment.price || 0)}</div>
            <div class="sentiment-metrics">
                <span>Trend ${formatPercent(sentiment.trend_pct)}</span>
                <span>Momentum ${formatPercent(sentiment.momentum_pct)}</span>
                <span>Vol ${formatPercent(sentiment.volatility_pct)}</span>
            </div>
        `;
        portfolioSentiment.appendChild(card);
    }
}

function updateSingleSentiment(sentiment) {
    if (!sentiment) return;
    const current = {};
    if (portfolioSentiment) {
        for (const card of portfolioSentiment.querySelectorAll('.sentiment-card')) {
            const symbol = card.querySelector('.sentiment-symbol')?.textContent;
            if (symbol && symbol !== sentiment.symbol) {
                current[symbol] = {
                    symbol,
                    label: card.querySelector('.sentiment-label')?.textContent || 'Neutral',
                    tone: [...card.classList].find((name) => name.startsWith('sentiment-') && name !== 'sentiment-card')?.replace('sentiment-', '') || 'neutral',
                    price: Number(card.dataset.price || 0),
                    trend_pct: Number(card.dataset.trend || 0),
                    momentum_pct: Number(card.dataset.momentum || 0),
                    volatility_pct: Number(card.dataset.volatility || 0)
                };
            }
        }
    }
    current[sentiment.symbol] = sentiment;
    updateMarketSentiment(current);
}

function formatPercent(value) {
    const numeric = Number(value || 0);
    const sign = numeric > 0 ? '+' : '';
    return `${sign}${numeric.toFixed(3)}%`;
}

function updateTicker(data) {
    const symbol = data.symbol;
    const price = parseFloat(data.last);
    if (isNaN(price)) return;
    updateSingleSentiment(data.sentiment);
    
    let card = document.getElementById(`ticker-${symbol}`);
    let isUp = true;

    if (!card) {
        card = document.createElement('div');
        card.id = `ticker-${symbol}`;
        card.className = 'ticker-card';
        card.innerHTML = `
            <div class="ticker-symbol">${symbol}</div>
            <div class="ticker-price" id="price-${symbol}">${moneyFormatter.format(price)}</div>
            <div class="ticker-details">
                <span>Bid: <span id="bid-${symbol}">${data.bid || '-'}</span></span>
                <span>Ask: <span id="ask-${symbol}">${data.ask || '-'}</span></span>
            </div>
        `;
        tickerContainer.appendChild(card);
        tickers[symbol] = price;
    } else {
        const prevPrice = tickers[symbol];
        const priceEl = document.getElementById(`price-${symbol}`);
        
        if (price !== prevPrice) {
            isUp = price > prevPrice;
            priceEl.className = `ticker-price ${isUp ? 'price-up' : 'price-down'}`;
        }
        
        priceEl.textContent = moneyFormatter.format(price);
        document.getElementById(`bid-${symbol}`).textContent = data.bid || '-';
        document.getElementById(`ask-${symbol}`).textContent = data.ask || '-';
        
        tickers[symbol] = price;
    }
}

function addTradeEvent(msg) {
    const tr = document.createElement('tr');
    const time = new Date().toLocaleTimeString();
    
    tr.style.animation = "fade-in 0.5s ease-out";
    
    let actionStr = msg.data.action ? `<strong>${msg.data.action}</strong>` : '-';
    if (msg.event === 'SIGNAL_GENERATED') actionStr = `<span style="color:var(--text-secondary)">Signal: ${actionStr}</span>`;

    const strategyStr = msg.data.strategy
        ? `<span class="badge strategy-badge" title="${msg.data.strategy_reason || ''}">${msg.data.strategy}</span>`
        : '-';
    let priceStr = msg.data.price ? moneyFormatter.format(msg.data.price) : '-';
    let qtyStr = msg.data.qty ? msg.data.qty.toFixed(4) : '-';
    if (msg.data.notional !== undefined) {
        qtyStr = `${qtyStr}<span class="notional">${moneyFormatter.format(msg.data.notional)}</span>`;
    }
    
    let pnlStr = '-';
    if (msg.data.realized_pnl !== undefined) {
        const pnl = msg.data.realized_pnl;
        const color = pnl >= 0 ? 'var(--positive)' : 'var(--negative)';
        pnlStr = `<strong style="color:${color}">${moneyFormatter.format(pnl)}</strong>`;
    }
    
    tr.innerHTML = `
        <td>${time}</td>
        <td><span class="badge">${msg.event}</span></td>
        <td>${strategyStr}</td>
        <td>${msg.data.symbol || '-'}</td>
        <td>${actionStr}</td>
        <td>${priceStr}</td>
        <td>${qtyStr}</td>
        <td>${pnlStr}</td>
    `;
    
    tradesBody.insertBefore(tr, tradesBody.firstChild);
    
    if (tradesBody.children.length > 50) {
        tradesBody.removeChild(tradesBody.lastChild);
    }
}

resetPortfolio.addEventListener('click', resetVirtualMoney);
resetBalance.addEventListener('input', () => {
    isCapitalInputDirty = true;
});
resetBalance.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
        resetVirtualMoney();
    }
});

connect();
loadPortfolio();

const style = document.createElement('style');
style.innerHTML = `
@keyframes fade-in {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
}
`;
document.head.appendChild(style);
