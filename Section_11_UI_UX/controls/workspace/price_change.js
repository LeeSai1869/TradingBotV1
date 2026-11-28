import {selectSymbol, symbolName} from '../symbol/index.js';

const percent = new Intl.NumberFormat(undefined, {
    style: 'percent', maximumFractionDigits: 2, minimumFractionDigits: 2, signDisplay: 'exceptZero',
});
const orders = {
    highest: (a, b) => b - a,
    lowest: (a, b) => a - b,
};

function element(parent, tag, text = '') {
    const node = document.createElement(tag);
    node.textContent = text;
    parent.append(node);
    return node;
}

function select(parent, label, choices) {
    const wrapper = element(parent, 'label', label);
    const input = element(wrapper, 'select');
    input.setAttribute('aria-label', label);
    for (const [value, text] of choices) element(input, 'option', text).value = value;
    return input;
}

export function mountPriceChange(parent) {
    const panel = element(parent, 'details');
    panel.className = 'workspace-card price-change';
    element(panel, 'summary', 'Price Change');
    const controls = element(panel, 'div');
    controls.className = 'price-change-controls';
    const period = select(controls, 'Period', ['1h', '4h', '24h', '7d'].map(value => [value, value]));
    period.value = '24h';
    const sort = select(controls, 'Sort', [
        ['direction', 'By % Change'], ['magnitude', 'Biggest move'],
    ]);
    const refresh = element(controls, 'button', 'Refresh');
    refresh.type = 'button';
    const table = element(panel, 'table');
    table.setAttribute('aria-label', 'Coin price changes');
    const head = element(element(table, 'thead'), 'tr');
    element(head, 'th', 'Coin').scope = 'col';
    const changeHeader = element(head, 'th', '% Change');
    changeHeader.scope = 'col';
    const arrows = element(changeHeader, 'span');
    arrows.className = 'price-change-arrows';
    const buttons = [
        ['lowest', '↑', 'Lowest to highest'],
        ['highest', '↓', 'Highest to lowest'],
    ].map(([order, icon, label]) => {
        const button = element(arrows, 'button', icon);
        button.type = 'button';
        button.title = label;
        button.setAttribute('aria-label', label);
        button.onclick = () => {
            direction = order;
            render();
        };
        return [order, button];
    });
    const body = element(table, 'tbody');
    const status = element(panel, 'p');
    status.setAttribute('role', 'status');
    let rows = [], request, direction = 'highest';

    function render() {
        const magnitude = sort.value === 'magnitude';
        changeHeader.setAttribute('aria-sort',
            magnitude ? 'other' : direction === 'lowest' ? 'ascending' : 'descending');
        for (const [value, button] of buttons) button.setAttribute('aria-pressed', String(direction === value));
        body.replaceChildren();
        const ranked = [...rows].sort((a, b) => {
            if (a.change_pct === null) return b.change_pct === null ? 0 : 1;
            if (b.change_pct === null) return -1;
            const first = magnitude ? Math.abs(a.change_pct) : a.change_pct;
            const second = magnitude ? Math.abs(b.change_pct) : b.change_pct;
            return orders[direction](first, second);
        });
        for (const row of ranked) {
            const line = element(body, 'tr');
            const coin = element(line, 'td');
            const name = symbolName(row.symbol);
            const link = element(coin, 'button', name ? `${name} · ${row.symbol}` : row.symbol);
            link.type = 'button';
            link.onclick = () => {
                if (!selectSymbol(row.symbol)) status.textContent = `${row.symbol} is no longer available in the chart.`;
            };
            const amount = element(line, 'td', row.change_pct === null ? '—' : percent.format(row.change_pct / 100));
            amount.dataset.direction = row.change_pct > 0 ? 'up' : row.change_pct < 0 ? 'down' : '';
            if (row.reference_at != null) amount.title = 'Compared with ' + new Date(row.reference_at).toLocaleString();
            if (row.stale) {
                element(coin, 'small', 'Stale · ' + new Date(row.as_of).toLocaleString()).className = 'price-change-stale';
            }
        }
    }

    async function load() {
        request?.abort();
        const current = new AbortController();
        request = current;
        status.textContent = 'Loading stored prices…';
        rows = [];
        render();
        const timeout = setTimeout(() => current.abort(), 8000);
        try {
            const response = await fetch('/api/price_change?' + new URLSearchParams({period: period.value}),
                {cache: 'no-store', signal: current.signal});
            const packet = await response.json();
            if (!response.ok) throw new Error(packet.error || 'Could not load price changes.');
            if (request !== current) return;
            rows = packet.rows;
            render();
            status.textContent = rows.length ? 'Changes end at each coin’s latest stored close.' : 'No active coins.';
        } catch (error) {
            if (request === current) status.textContent = current.signal.aborted ? 'Price change request timed out.' : error.message;
        } finally {
            clearTimeout(timeout);
            if (request === current) request = null;
        }
    }

    panel.addEventListener('toggle', () => {
        if (panel.open) void load();
        else { request?.abort(); request = null; }
    });
    period.onchange = refresh.onclick = load;
    sort.onchange = render;
    render();
}
