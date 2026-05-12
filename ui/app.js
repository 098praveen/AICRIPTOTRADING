const wsUrl = `ws://${window.location.host}/ws/data`;
let ws;
const tickers = {};

const connectionStatus = document.getElementById('connection-status');
const dot = document.querySelector('.dot');
const tickerContainer = document.getElementById('ticker-container');
const tradesBody = document.getElementById('trades-body');

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

function updatePortfolio(data) {
    document.getElementById('port-total').textContent = `$${data.total_value.toFixed(2)}`;
    document.getElementById('port-cash').textContent = `$${data.balance.toFixed(2)}`;
    const pnlEl = document.getElementById('port-pnl');
    pnlEl.textContent = `$${data.unrealized_pnl.toFixed(2)}`;
    pnlEl.className = `stat-value ${data.unrealized_pnl >= 0 ? 'price-up' : 'price-down'}`;

    const positionsBody = document.getElementById('positions-body');
    positionsBody.innerHTML = '';
    
    for (const [symbol, pos] of Object.entries(data.positions)) {
        if (pos.qty > 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${symbol}</td>
                <td>${pos.qty.toFixed(6)}</td>
                <td>$${pos.avg_price.toFixed(2)}</td>
                <td>$${(pos.current_price || 0).toFixed(2)}</td>
            `;
            positionsBody.appendChild(tr);
        }
    }
}

function updateTicker(data) {
    const symbol = data.symbol;
    const price = parseFloat(data.last);
    if (isNaN(price)) return;
    
    let card = document.getElementById(`ticker-${symbol}`);
    let isUp = true;

    if (!card) {
        card = document.createElement('div');
        card.id = `ticker-${symbol}`;
        card.className = 'ticker-card';
        card.innerHTML = `
            <div class="ticker-symbol">${symbol}</div>
            <div class="ticker-price" id="price-${symbol}">$${price.toFixed(2)}</div>
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
        
        priceEl.textContent = `$${price.toFixed(2)}`;
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

    let priceStr = msg.data.price ? `$${msg.data.price.toFixed(2)}` : '-';
    let qtyStr = msg.data.qty ? msg.data.qty.toFixed(4) : '-';
    
    let pnlStr = '-';
    if (msg.data.realized_pnl !== undefined) {
        const pnl = msg.data.realized_pnl;
        const color = pnl >= 0 ? 'var(--positive)' : 'var(--negative)';
        pnlStr = `<strong style="color:${color}">$${pnl.toFixed(2)}</strong>`;
    }
    
    tr.innerHTML = `
        <td>${time}</td>
        <td><span class="badge">${msg.event}</span></td>
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

connect();

const style = document.createElement('style');
style.innerHTML = `
@keyframes fade-in {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
}
`;
document.head.appendChild(style);
