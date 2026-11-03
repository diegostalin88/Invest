// Mede o efeito da correção do stop: roda o Backtest padrão em todos os papéis com a versão
// atual (antigo.html, igual à main) e a corrigida (index.html). Só leitura; escreve no resumo do Actions.
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const RAIZ = path.resolve(process.argv[2] || 'site');
const srv = http.createServer((req, res) => {
    const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/+/, '') || 'index.html';
    const arq = path.join(RAIZ, rel);
    if (!arq.startsWith(RAIZ) || !fs.existsSync(arq) || fs.statSync(arq).isDirectory()) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': arq.endsWith('.html') ? 'text/html; charset=utf-8' : 'application/json' });
    fs.createReadStream(arq).pipe(res);
});
const med = a => { const s = a.filter(Number.isFinite).sort((x, y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : NaN; };
(async () => {
    await new Promise(ok => srv.listen(0, '127.0.0.1', ok));
    const base = `http://127.0.0.1:${srv.address().port}/`;
    const b = await chromium.launch(); const linhas = ['## Backtest padrão: versão atual × corrigida (stop com gap e stop móvel sem look-ahead)', ''];
    for (const merc of ['us', 'br']) {
        if (!fs.existsSync(path.join(RAIZ, merc === 'us' ? 'data' : 'data/br', 'manifest.json'))) continue;
        const res = {};
        for (const pg_ of ['antigo.html', 'index.html']) {
            const pg = await b.newPage();
            await pg.route('https://s3.tradingview.com/**', r => r.fulfill({ status: 200, contentType: 'application/javascript', body: '' }));
            if (process.env.LIBS_LOCAIS) {  // só para rodar localmente sem CDN
                const local = { 'cdn.tailwindcss.com': 'tailwind.js', 'cdn.plot.ly': 'plotly.min.js', 'xlsx.full.min.js': 'xlsx.full.min.js', 'FileSaver.min.js': 'FileSaver.min.js', 'lightweight-charts': 'lightweight-charts.standalone.production.js' };
                await pg.route(/^https:\/\/(cdn\.tailwindcss\.com|cdn\.plot\.ly|cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net)\//, r => { const k = Object.keys(local).find(c => r.request().url().includes(c)); return k ? r.fulfill({ status: 200, contentType: 'application/javascript', body: fs.readFileSync(path.join(process.env.LIBS_LOCAIS, local[k])) }) : r.abort(); });
                await pg.route(/^https:\/\/fonts\.(googleapis|gstatic)\.com\//, r => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));
            }
            await pg.goto(`${base}${pg_}?mercado=${merc}`);
            await pg.waitForFunction(() => window.investDebug && Object.keys(window.investDebug.allData || {}).length > 0 && document.querySelector('#screener-results-container table'), null, { timeout: 15 * 60 * 1000 });
            res[pg_] = await pg.evaluate(() => {
                const I = window.investDebug, D = I.allData, rp = I.getBacktestRiskParams(), out = {};
                for (const t of Object.keys(D)) { if (D[t].close.length < 260) continue; const x = I.runCoreBacktest(D[t], rp); if (x && x.trades >= 5) out[t] = [x.returnPct * 100, x.profitFactor, x.maxDD * 100, x.trades, x.winRate * 100]; }
                return out;
            });
            await pg.close();
        }
        const A = res['antigo.html'], N = res['index.html']; const ts = Object.keys(A).filter(t => N[t]);
        const col = (R, k) => ts.map(t => R[t][k]);
        const pfA = col(A, 1).map(v => Math.min(v, 10)), pfN = col(N, 1).map(v => Math.min(v, 10));
        const lucA = ts.filter(t => A[t][1] > 1).length, lucN = ts.filter(t => N[t][1] > 1).length;
        const f = (v, d = 2) => Number.isFinite(v) ? v.toFixed(d) : '—';
        linhas.push(`### ${merc.toUpperCase()}: ${ts.length} papéis com 5+ trades`, '', '| Medida (mediana) | Atual | Corrigida |', '| --- | --- | --- |',
            `| Retorno total (%) | ${f(med(col(A, 0)), 1)} | ${f(med(col(N, 0)), 1)} |`,
            `| Fator de lucro | ${f(med(pfA))} | ${f(med(pfN))} |`,
            `| Queda máxima (%) | ${f(med(col(A, 2)), 1)} | ${f(med(col(N, 2)), 1)} |`,
            `| Taxa de acerto (%) | ${f(med(col(A, 4)), 1)} | ${f(med(col(N, 4)), 1)} |`,
            `| Trades por papel | ${f(med(col(A, 3)), 0)} | ${f(med(col(N, 3)), 0)} |`,
            `| Papéis com resultado diferente | — | ${ts.filter(t => Math.abs(A[t][0] - N[t][0]) > 1e-9).length} |`,
            `| Retorno médio (%) | ${f(col(A, 0).reduce((a, b) => a + b, 0) / ts.length, 2)} | ${f(col(N, 0).reduce((a, b) => a + b, 0) / ts.length, 2)} |`,
            `| Papéis com fator de lucro > 1 | ${lucA} (${f(100 * lucA / ts.length, 0)}%) | ${lucN} (${f(100 * lucN / ts.length, 0)}%) |`, '');
    }
    await b.close(); srv.close();
    const txt = linhas.join('\n'); console.log(txt);
    if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, txt + '\n');
})().catch(e => { console.error(e); process.exit(1); });
