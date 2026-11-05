// Medição (só leitura) da proposta "não entrar perto do balanço": para cada papel confirmado do Relatório,
// separa as operações fora da amostra da regra escolhida entre as que começaram com balanço nos próximos
// 5 pregões (contando o dia do sinal) e as demais, e entre as que atravessaram um balanço e as que não.
// As datas vêm de coleta/datas_balanco.py (8-K item 2.02 da SEC). Não grava nada no site.
//
// Uso: node coleta/medir_balanco.js site balancos.json [saida.json]
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const RAIZ = path.resolve(process.argv[2] || 'site');
const BALANCOS = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const SAIDA = process.argv[4] || 'medir_balanco.json';
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
    const r = await page.evaluate(async (B) => {
        const I = window.investDebug, R = I.relatorio || await I.gerarRelatorio(), D = I.allData;
        const FRACAO = 0.6, JANELA = 5;
        const est = lista => { let g = 0, p = 0, v = 0; lista.forEach(x => { if (x.pct > 0) { g += x.pct; v++; } else p -= x.pct; });
            return { n: lista.length, pf: p > 0 ? +(g / p).toFixed(2) : (g > 0 ? 99 : 0), acerto: lista.length ? +(v / lista.length).toFixed(3) : 0,
                mediaCapital: lista.length ? +(lista.reduce((a, x) => a + x.pct, 0) / lista.length * 100).toFixed(3) : 0,
                somaCapital: +(lista.reduce((a, x) => a + x.pct, 0) * 100).toFixed(1), piorCapital: lista.length ? +(Math.min(...lista.map(x => x.pct)) * 100).toFixed(2) : 0 }; };
        const g = { todas: [], perto: [], longe: [], atravessou: [], naoAtravessou: [] };
        let papeis = 0, semDatas = 0;
        for (const a of R.ativos.filter(x => x.regra && x.confirmada)) {
            const d = D[a.t]; if (!d) continue;
            const datas = B[a.t]; if (!datas || !datas.length) { semDatas++; continue; }
            const base = I.regraRp(a.regra); if (!base) continue;
            const res = I.runCoreBacktest(d, base); if (!res) continue;
            papeis++;
            const corte = Math.floor(d.close.length * FRACAO), n = d.dates.length;
            const temEntre = (ini, fim) => datas.some(x => x >= ini && x <= fim);
            res.tradesDet.filter(x => x.ent >= corte).forEach(x => {
                const t = { pct: x.pct };
                g.todas.push(t);
                (temEntre(d.dates[x.ent - 1], d.dates[Math.min(x.ent + JANELA - 2, n - 1)]) ? g.perto : g.longe).push(t);
                (temEntre(d.dates[x.ent - 1], d.dates[Math.min(x.sai, n - 1)]) ? g.atravessou : g.naoAtravessou).push(t);
            });
        }
        return { mercado: R.mercado, ultimoPregao: R.ultimoPregao, papeis, semDatas, janela: JANELA, ...Object.fromEntries(Object.entries(g).map(([k, l]) => [k, est(l)])) };
    }, BALANCOS);
    fs.writeFileSync(SAIDA, JSON.stringify(r, null, 1));
    const linha = (rot, x) => `| ${rot} | ${x.n} | ${x.pf} | ${(x.acerto * 100).toFixed(1)}% | ${x.mediaCapital}% | ${x.somaCapital}% | ${x.piorCapital}% |`;
    const L = [`## Balanço perto da entrada · ${r.mercado} · dados de ${r.ultimoPregao} · ${r.papeis} papéis com datas (${r.semDatas} sem)`, '',
        'Operações fora da amostra da regra escolhida de cada papel. Resultado em % do capital (posição pelo risco).', '',
        '| grupo | operações | fator de lucro | acerto | média por operação | soma | pior operação |', '|---|---|---|---|---|---|---|',
        linha('todas', r.todas), linha(`balanço do sinal até ${r.janela} pregões`, r.perto), linha('sem balanço perto (= com a trava)', r.longe),
        linha('atravessou um balanço', r.atravessou), linha('não atravessou', r.naoAtravessou)];
    console.log(L.join('\n'));
    if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, L.join('\n') + '\n');
    await browser.close(); srv.close();
})().catch(e => { console.error(e); process.exit(1); });
