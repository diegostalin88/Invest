// Medição (só leitura) da proposta "stop inicial a pelo menos N ATR": para cada papel confirmado do Relatório,
// roda a regra escolhida com o MESMO motor do app variando só o stop inicial e compara as operações fora da
// amostra. O tamanho da posição continua saindo do risco (stop mais longe = menos ações), então o resultado
// por operação (pct, em % do capital) já é comparável entre as variantes. Não grava nada no site.
//
// Uso: node coleta/medir_stop_atr.js site [saida.json]   (MERCADO=br para o Brasil)
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const RAIZ = path.resolve(process.argv[2] || 'site');
const SAIDA = process.argv[3] || 'medir_stop_atr.json';
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
    await page.goto(`http://127.0.0.1:${srv.address().port}/index.html?mercado=${process.env.MERCADO || 'us'}`);
    await page.waitForFunction(() => window.investDebug && Object.keys(window.investDebug.allData || {}).length > 0, null, { timeout: 15 * 60 * 1000 });
    await page.waitForTimeout(5000);
    const r = await page.evaluate(async () => {
        const I = window.investDebug, R = I.relatorio || await I.gerarRelatorio(), D = I.allData, P = I.getIndicatorParameters();
        const FRACAO = 0.6;
        // stopMinAtr 0 = regra atual (o mais protetor entre 2,5 ATR e 8%); 2,5 = só ATR (a trava de 8% nunca vence)
        const VARIANTES = [0, 1, 1.5, 2, 2.5];
        const FAIXAS = [[0, 3.2, 'ATR até 3,2% (a trava de 8% nunca aperta)'], [3.2, 5.3, 'ATR de 3,2% a 5,3%'], [5.3, 8, 'ATR de 5,3% a 8%'], [8, 1e9, 'ATR acima de 8%']];
        const est = lista => { let g = 0, p = 0, v = 0, ruido = 0; lista.forEach(x => { if (x.pct > 0) { g += x.pct; v++; } else p -= x.pct; if (x.ruido) ruido++; });
            return { n: lista.length, pf: p > 0 ? +(g / p).toFixed(2) : (g > 0 ? 99 : 0), acerto: lista.length ? +(v / lista.length).toFixed(3) : 0,
                mediaCapital: lista.length ? +(lista.reduce((a, x) => a + x.pct, 0) / lista.length * 100).toFixed(3) : 0,
                somaCapital: +(lista.reduce((a, x) => a + x.pct, 0) * 100).toFixed(1), stopRuido: lista.length ? +(ruido / lista.length).toFixed(3) : 0 }; };
        const tudo = {}, porFaixa = {}, porRegra = {};
        VARIANTES.forEach(k => { tudo[k] = []; porFaixa[k] = FAIXAS.map(() => []); porRegra[k] = {}; });
        let papeis = 0;
        for (const a of R.ativos.filter(x => x.regra && x.confirmada)) {
            const d = D[a.t]; if (!d) continue;
            const base = I.regraRp(a.regra); if (!base) continue;
            const ind = I.precomputeAllIndicators(d, P), corte = Math.floor(d.close.length * FRACAO);
            papeis++;
            for (const k of VARIANTES) {
                const res = I.runCoreBacktest(d, { ...base, stopMinAtr: k }); if (!res) continue;
                res.tradesDet.filter(x => x.ent >= corte).forEach(x => {
                    const atr = ind.ATR[x.ent - 1], atrPct = atr ? atr / d.open[x.ent] * 100 : null;
                    // "ruído": perdeu e saiu em até 3 pregões (o stop foi pego logo de cara)
                    const t = { pct: x.pct, ruido: x.ret < 0 && x.sai - x.ent <= 2 };
                    tudo[k].push(t);
                    (porRegra[k][a.regra] = porRegra[k][a.regra] || []).push(t);
                    if (atrPct !== null) porFaixa[k][FAIXAS.findIndex(f => atrPct >= f[0] && atrPct < f[1])].push(t);
                });
            }
        }
        const out = { mercado: R.mercado, ultimoPregao: R.ultimoPregao, papeis, variantes: VARIANTES, faixas: FAIXAS.map(f => f[2]), geral: {}, porFaixa: {}, porRegra: {} };
        VARIANTES.forEach(k => { out.geral[k] = est(tudo[k]); out.porFaixa[k] = porFaixa[k].map(est); out.porRegra[k] = Object.fromEntries(Object.entries(porRegra[k]).map(([id, l]) => [id, est(l)])); });
        return out;
    });
    fs.writeFileSync(SAIDA, JSON.stringify(r, null, 1));
    const nome = k => k === 0 ? 'atual (2,5 ATR ou 8%, o mais perto)' : k === 2.5 ? 'só ATR (2,5 ATR, sem a trava de 8%)' : `mínimo de ${String(k).replace('.', ',')} ATR`;
    const L = [`## Stop mínimo em ATR · ${r.mercado} · dados de ${r.ultimoPregao} · ${r.papeis} papéis`, '',
        'Operações fora da amostra da regra escolhida de cada papel. Resultado em % do capital (posição pelo risco).', '',
        '| stop inicial | operações | fator de lucro | acerto | média por operação | soma | stop pego em até 3 pregões |', '|---|---|---|---|---|---|---|',
        ...r.variantes.map(k => { const g = r.geral[k]; return `| ${nome(k)} | ${g.n} | ${g.pf} | ${(g.acerto * 100).toFixed(1)}% | ${g.mediaCapital}% | ${g.somaCapital}% | ${(g.stopRuido * 100).toFixed(1)}% |`; }), '',
        ...r.faixas.flatMap((f, i) => [`**${f}**`, '', '| stop inicial | operações | fator de lucro | acerto | soma |', '|---|---|---|---|---|',
            ...r.variantes.map(k => { const g = r.porFaixa[k][i]; return `| ${nome(k)} | ${g.n} | ${g.pf} | ${(g.acerto * 100).toFixed(1)}% | ${g.somaCapital}% |`; }), ''])];
    console.log(L.join('\n'));
    if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, L.join('\n') + '\n');
    await browser.close(); srv.close();
})().catch(e => { console.error(e); process.exit(1); });
