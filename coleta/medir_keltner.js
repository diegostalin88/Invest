// Medição (só leitura) da estratégia "Compra: Defesa Institucional Keltner". No app ela dispara com UMA de duas
// condições (preço acima da MME200 OU fechamento abaixo da banda inferior de Keltner) e, com peso 2,5, passa
// sozinha do mínimo de entrada. Compara, com o MESMO motor e a regra escolhida de cada papel, as operações fora
// da amostra com a definição atual, exigindo as duas condições juntas e só com o toque na banda.
// A mudança é feita numa cópia em memória da página e desfeita no fim; não grava nada no site.
//
// Uso: node coleta/medir_keltner.js site [saida.json]   (MERCADO=br para o Brasil)
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const RAIZ = path.resolve(process.argv[2] || 'site');
const SAIDA = process.argv[3] || 'medir_keltner.json';
const TIPOS = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.json': 'application/json' };

function servir() {
    const srv = http.createServer((req, res) => {
        const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/+/, '') || 'index.html';
        const arq = path.join(RAIZ, rel);
        if (!arq.startsWith(RAIZ) || !fs.existsSync(arq) || fs.statSync(arq).isDirectory()) { res.writeHead(404); res.end(''); return; }
        res.writeHead(200, { 'Content-Type': TIPOS[path.extname(arq)] || 'application/octet-stream' });
        fs.createReadStream(arq).pipe(res);
    });
    return new Promise(ok => srv.listen(0, '127.0.0.1', () => ok(srv)));
}

(async () => {
    const srv = await servir();
    const browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    await page.route('https://s3.tradingview.com/**', r => r.fulfill({ status: 200, contentType: 'application/javascript', body: '' }));
    if (process.env.LIBS_LOCAIS) {  // só para rodar localmente sem acesso aos CDNs
        const local = { 'cdn.tailwindcss.com': 'tailwind.js', 'cdn.plot.ly': 'plotly.min.js', 'xlsx.full.min.js': 'xlsx.full.min.js', 'FileSaver.min.js': 'FileSaver.min.js', 'lightweight-charts': 'lightweight-charts.standalone.production.js' };
        await page.route(/^https:\/\/(cdn\.tailwindcss\.com|cdn\.plot\.ly|cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net)\//, rt => {
            const k = Object.keys(local).find(c => rt.request().url().includes(c));
            return k ? rt.fulfill({ status: 200, contentType: 'application/javascript', body: fs.readFileSync(path.join(process.env.LIBS_LOCAIS, local[k])) }) : rt.abort();
        });
        await page.route(/^https:\/\/fonts\.(googleapis|gstatic)\.com\//, rt => rt.fulfill({ status: 200, contentType: 'text/css', body: '' }));
    }
    await page.goto(`http://127.0.0.1:${srv.address().port}/index.html?classico=1&mercado=${process.env.MERCADO || 'us'}`);
    await page.waitForFunction(() => window.investDebug && Object.keys(window.investDebug.allData || {}).length > 0, null, { timeout: 15 * 60 * 1000 });
    await page.waitForTimeout(5000);
    const r = await page.evaluate(async () => {
        const I = window.investDebug, R = I.relatorio || await I.gerarRelatorio(), D = I.allData, P = I.getIndicatorParameters();
        const FRACAO = 0.6, K = I.estrategiasConfluencia.keltner_reversion_buy, original = { buy: [...K.buy], minVotes: K.minVotes };
        const VARIANTES = { atual: original, ambas: { buy: ['Price_Above_EMA_200', 'Keltner_Touch_Lower'], minVotes: 2 }, so_toque: { buy: ['Keltner_Touch_Lower'], minVotes: 1 } };
        const est = lista => { let g = 0, p = 0, v = 0; lista.forEach(x => { if (x.pct > 0) { g += x.pct; v++; } else p -= x.pct; });
            return { n: lista.length, pf: p > 0 ? +(g / p).toFixed(2) : (g > 0 ? 99 : 0), acerto: lista.length ? +(v / lista.length).toFixed(3) : 0,
                mediaCapital: lista.length ? +(lista.reduce((a, x) => a + x.pct, 0) / lista.length * 100).toFixed(3) : 0,
                somaCapital: +(lista.reduce((a, x) => a + x.pct, 0) * 100).toFixed(1), diasMedios: lista.length ? +(lista.reduce((a, x) => a + x.dias, 0) / lista.length).toFixed(1) : 0 }; };
        const g = {}; Object.keys(VARIANTES).forEach(k => g[k] = { todas: [], acima: [], abaixo: [] });
        let papeis = 0;
        try {
            for (const a of R.ativos.filter(x => x.regra && x.confirmada && !String(x.regra).startsWith('recuo'))) {
                const d = D[a.t]; if (!d) continue; const base = I.regraRp(a.regra); if (!base) continue;
                const ind = I.precomputeAllIndicators(d, P), corte = Math.floor(d.close.length * FRACAO); papeis++;
                for (const [k, v] of Object.entries(VARIANTES)) {
                    K.buy = v.buy; K.minVotes = v.minVotes;
                    const res = I.runCoreBacktest(d, base); if (!res) continue;
                    res.tradesDet.filter(x => x.ent >= corte).forEach(x => {
                        const s = x.ent - 1, e = ind.EMA_200[s], t = { pct: x.pct, dias: x.sai - x.ent + 1 };
                        g[k].todas.push(t); if (e) g[k][d.close[s] > e ? 'acima' : 'abaixo'].push(t);
                    });
                }
            }
        } finally { K.buy = original.buy; K.minVotes = original.minVotes; }
        return { mercado: R.mercado, ultimoPregao: R.ultimoPregao, papeis, ...Object.fromEntries(Object.entries(g).map(([k, x]) => [k, { todas: est(x.todas), acima: est(x.acima), abaixo: est(x.abaixo) }])) };
    });
    fs.writeFileSync(SAIDA, JSON.stringify(r, null, 1));
    const nome = { atual: 'atual (acima da MME200 OU toque na banda)', ambas: 'as duas juntas (acima da MME200 E toque)', so_toque: 'só o toque na banda inferior' };
    const L = [`## Estratégia Keltner · ${r.mercado} · dados de ${r.ultimoPregao} · ${r.papeis} papéis (regras de Score)`, '',
        'Operações fora da amostra da regra escolhida de cada papel. Resultado em % do capital (posição pelo risco).', '',
        '| definição | operações | fator de lucro | acerto | média | soma | dias por operação | acima da MME200: op. / FL | abaixo: op. / FL |', '|---|---|---|---|---|---|---|---|---|',
        ...Object.keys(nome).map(k => { const x = r[k]; return `| ${nome[k]} | ${x.todas.n} | ${x.todas.pf} | ${(x.todas.acerto * 100).toFixed(1)}% | ${x.todas.mediaCapital}% | ${x.todas.somaCapital}% | ${x.todas.diasMedios} | ${x.acima.n} / ${x.acima.pf} | ${x.abaixo.n} / ${x.abaixo.pf} |`; })];
    console.log(L.join('\n'));
    if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, L.join('\n') + '\n');
    await browser.close(); srv.close();
})().catch(e => { console.error(e); process.exit(1); });
