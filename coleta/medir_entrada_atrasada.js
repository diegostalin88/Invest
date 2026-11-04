// Mede quanto se perde entrando 1 ou 2 pregões DEPOIS do sistema (quem viu o "Já em operação").
// Usa só os papéis com regra confirmada no Relatório e só as operações do trecho fora da amostra.
// Só leitura: não muda nada no app; escreve no resumo do Actions.
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

// Roda dentro da página: devolve, para cada operação fora da amostra, o retorno no dia certo e atrasado.
async function coletar() {
    const I = window.investDebug, D = I.allData, R = await I.gerarRelatorio(), base = I.getBacktestRiskParams();
    const cost = (base.costPct || 0) / 100, ops = [];
    const atr14 = d => { const n = d.close.length, a = new Array(n).fill(null); let s = 0;
        for (let i = 1; i < n; i++) { const tr = Math.max(d.high[i] - d.low[i], Math.abs(d.high[i] - d.close[i - 1]), Math.abs(d.low[i] - d.close[i - 1]));
            if (i <= 14) { s += tr; if (i === 14) a[i] = s / 14; } else a[i] = (a[i - 1] * 13 + tr) / 14; } return a; };
    for (const a of R.ativos) {
        if (!a.regra || !a.confirmada) continue;
        const d = D[a.t]; if (!d) continue;
        const rp = I.regraRp(a.regra), res = I.runCoreBacktest(d, rp); if (!res) continue;
        const n = d.close.length, corte = Math.floor(n * 0.6), atr = atr14(d);
        for (const x of res.tradesDet) {
            if (x.ent < corte) continue;
            const ent0 = d.open[x.ent] * (1 + cost), saida = ent0 * (1 + x.ret);
            const op = { t: a.t, regra: a.regra, ret0: x.ret, atr: atr[x.ent - 1], tarde: {} };
            for (const k of [1, 2]) {
                // À noite do pregão ent+k-1 a pessoa vê a operação ainda aberta e compra na abertura seguinte
                if (x.sai <= x.ent + k - 1 || x.ent + k >= n) continue;
                const fechNoite = d.close[x.ent + k - 1], entK = d.open[x.ent + k] * (1 + cost);
                op.tarde[k] = { ret: saida / entK - 1, desvioAtr: atr[x.ent - 1] ? (fechNoite - ent0) / atr[x.ent - 1] : null, desvioPct: fechNoite / ent0 - 1 };
            }
            ops.push(op);
        }
    }
    return ops;
}

const est = rs => { let g = 0, p = 0, v = 0; rs.forEach(r => { if (r > 0) { g += r; v++; } else p -= r; });
    return { n: rs.length, media: rs.length ? rs.reduce((s, r) => s + r, 0) / rs.length : NaN, pf: p > 0 ? g / p : (g > 0 ? 99 : 0), acerto: rs.length ? v / rs.length : NaN }; };
const pc = v => Number.isFinite(v) ? (v * 100).toFixed(2) + '%' : '—', f2 = v => Number.isFinite(v) ? v.toFixed(2) : '—';

(async () => {
    await new Promise(ok => srv.listen(0, '127.0.0.1', ok));
    const base = `http://127.0.0.1:${srv.address().port}/`;
    const b = await chromium.launch();
    const L = ['## Entrar atrasado: quanto se perde?', '',
        'Operações fora da amostra das regras confirmadas no Relatório. "No dia certo" = o que o teste mediu (abertura depois do sinal).',
        '"Atrasado k" = quem viu "Já em operação" na noite e comprou na abertura seguinte, saindo junto com o sistema.',
        'Só conta operações ainda abertas na noite da decisão. Desvio = (fechamento da noite − entrada do sistema) em ATR.', ''];
    for (const merc of ['us', 'br']) {
        if (!fs.existsSync(path.join(RAIZ, merc === 'us' ? 'data' : 'data/br', 'manifest.json'))) continue;
        const pg = await b.newPage();
        await pg.route('https://s3.tradingview.com/**', r => r.fulfill({ status: 200, contentType: 'application/javascript', body: '' }));
        if (process.env.LIBS_LOCAIS) {
            const local = { 'cdn.tailwindcss.com': 'tailwind.js', 'cdn.plot.ly': 'plotly.min.js', 'xlsx.full.min.js': 'xlsx.full.min.js', 'FileSaver.min.js': 'FileSaver.min.js', 'lightweight-charts': 'lightweight-charts.standalone.production.js' };
            await pg.route(/^https:\/\/(cdn\.tailwindcss\.com|cdn\.plot\.ly|cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net)\//, r => { const k = Object.keys(local).find(c => r.request().url().includes(c)); return k ? r.fulfill({ status: 200, contentType: 'application/javascript', body: fs.readFileSync(path.join(process.env.LIBS_LOCAIS, local[k])) }) : r.abort(); });
            await pg.route(/^https:\/\/fonts\.(googleapis|gstatic)\.com\//, r => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));
        }
        await pg.goto(`${base}index.html?mercado=${merc}`);
        await pg.waitForFunction(() => window.investDebug && Object.keys(window.investDebug.allData || {}).length > 0 && document.querySelector('#screener-results-container table'), null, { timeout: 15 * 60 * 1000 });
        const ops = await pg.evaluate(coletar);
        await pg.close();
        L.push(`### ${merc.toUpperCase()}: ${ops.length} operações fora da amostra`, '');
        const todas = est(ops.map(o => o.ret0));
        L.push(`No dia certo (todas): média ${pc(todas.media)}, fator de lucro ${f2(todas.pf)}, acerto ${pc(todas.acerto)}`, '');
        L.push('| Atraso | Desvio na noite | Operações | Média no dia certo | Média atrasado | FL no dia certo | FL atrasado | Acerto atrasado |', '| --- | --- | --- | --- | --- | --- | --- | --- |');
        const faixas = [['qualquer', () => true], ['≤ 0 ATR (abaixo da entrada)', v => v <= 0], ['0 a 0,5 ATR', v => v > 0 && v <= 0.5], ['0,5 a 1 ATR', v => v > 0.5 && v <= 1], ['> 1 ATR', v => v > 1], ['≤ 0,5 ATR (junto)', v => v <= 0.5]];
        for (const k of [1, 2]) for (const [nome, ok] of faixas) {
            const sel = ops.filter(o => o.tarde[k] && o.tarde[k].desvioAtr !== null && ok(o.tarde[k].desvioAtr));
            const e0 = est(sel.map(o => o.ret0)), e1 = est(sel.map(o => o.tarde[k].ret));
            L.push(`| ${k} pregão(ões) | ${nome} | ${sel.length} | ${pc(e0.media)} | ${pc(e1.media)} | ${f2(e0.pf)} | ${f2(e1.pf)} | ${pc(e1.acerto)} |`);
        }
        L.push('');
    }
    await b.close(); srv.close();
    const txt = L.join('\n'); console.log(txt);
    if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, txt + '\n');
})().catch(e => { console.error(e); process.exit(1); });
