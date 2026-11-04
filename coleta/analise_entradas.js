// Análise (só leitura) das entradas do Relatório: para cada papel com veredito de entrada, mostra a
// tendência do próprio papel (preço × MME200/MME50), volatilidade, distância do stop em ATR, IFR,
// estratégias que dispararam e próximo balanço. Mede também, na carteira inteira e com o MESMO motor
// do app, como foram as operações da regra escolhida quando o sinal saiu ACIMA × ABAIXO da MME200
// do papel (pergunta levantada no caso AAOI). Não grava nada no site.
//
// Uso: node coleta/analise_entradas.js site [saida.json]
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const RAIZ = path.resolve(process.argv[2] || 'site');
const SAIDA = process.argv[3] || 'analise_entradas.json';
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
    await page.waitForTimeout(5000);   // dá tempo de o relatório publicado carregar
    const r = await page.evaluate(async () => {
        const I = window.investDebug, R = I.relatorio || await I.gerarRelatorio(), D = I.allData, P = I.getIndicatorParameters(), F = I.fundamentos || {};
        const FRACAO = 0.6;
        const ifr = (c, i, p = 14) => { let g = 0, l = 0; for (let k = i - p + 1; k <= i; k++) { const dlt = c[k] - c[k - 1]; if (dlt > 0) g += dlt; else l -= dlt; } return l === 0 ? 100 : 100 - 100 / (1 + g / l); };
        const est = lista => { let g = 0, p = 0, v = 0; lista.forEach(x => { if (x.pct > 0) { g += x.pct; v++; } else p -= x.pct; });
            return { n: lista.length, pf: p > 0 ? +(g / p).toFixed(2) : (g > 0 ? 99 : 0), acerto: lista.length ? +(v / lista.length).toFixed(2) : 0, medRet: lista.length ? +(lista.reduce((a, x) => a + x.ret, 0) / lista.length * 100).toFixed(2) : 0 }; };
        // 1) Medição na carteira inteira: operações fora da amostra da regra escolhida, por posição do sinal × MME200
        const glob = { acima: [], abaixo: [] }, porRegra = {};
        const porPapel = {};
        R.ativos.filter(a => a.regra && a.confirmada).forEach(a => {
            const d = D[a.t]; if (!d) return;
            const res = I.runCoreBacktest(d, I.regraRp(a.regra)); if (!res) return;
            const ind = I.precomputeAllIndicators(d, P), corte = Math.floor(d.close.length * FRACAO);
            const sep = { acima: [], abaixo: [] };
            res.tradesDet.filter(x => x.ent >= corte).forEach(x => {
                const s = x.ent - 1, e = ind.EMA_200[s]; if (!e) return;
                const lado = d.close[s] > e ? 'acima' : 'abaixo';
                sep[lado].push(x); glob[lado].push(x);
                (porRegra[a.regra] = porRegra[a.regra] || { acima: [], abaixo: [] })[lado].push(x);
            });
            porPapel[a.t] = { acima: est(sep.acima), abaixo: est(sep.abaixo) };
        });
        // 2) Papéis com veredito de entrada (entrar ou atrasado)
        const entradas = R.ativos.map(a => ({ a, v: I.vereditoEntrada(a) })).filter(x => ['entrar', 'atrasado'].includes(x.v.estado)).map(({ a, v }) => {
            const d = D[a.t], n = d.close.length, i = n - 1, ind = I.precomputeAllIndicators(d, P);
            const e200 = ind.EMA_200[i], e50 = (() => { const k = 2 / 51; let m = d.close[0]; for (let j = 1; j < n; j++) m = d.close[j] * k + m * (1 - k); return m; })();
            const atr = ind.ATR ? ind.ATR[i] : null;
            let sinais = null; try { const ie = a.desde ? d.dates.indexOf(a.desde) : -1; const s = I.analyzeAllSignals(d, ind, ie > 0 ? ie - 1 : i); sinais = I.computeStrategyScore(s, I.getCurrentWeights()); } catch (e) { sinais = { erro: String(e) }; }
            const max252 = Math.max(...d.high.slice(-252)), ret = k => n > k ? +((d.close[i] / d.close[i - k] - 1) * 100).toFixed(1) : null;
            const f = F[a.t] || {};
            return { t: a.t, nome: f.longName || f.shortName || '', setor: f.sector || null, industria: f.industry || null, balanco: f.nextEarningsDate || null,
                regra: a.regra, conf: v.conf, pfTeste: a.teste.pf, nTeste: a.teste.n, acerto: a.teste.acerto, mediaGanho: a.teste.mediaGanho, mediaPerda: a.teste.mediaPerda,
                preco: d.close[i], entrada: a.entrada, stop: a.stop, alvo: a.alvo, resistencia: a.resistencia, suporte: a.suporte,
                mme200: e200, vsMme200: e200 ? +((d.close[i] / e200 - 1) * 100).toFixed(1) : null, mme50: e50, vsMme50: +((d.close[i] / e50 - 1) * 100).toFixed(1),
                atrPct: atr ? +(atr / d.close[i] * 100).toFixed(2) : null, stopEmAtr: atr ? +((d.close[i] - a.stop) / atr).toFixed(2) : null,
                ifr14: +ifr(d.close, i).toFixed(1), ret20: ret(20), ret60: ret(60), ret252: ret(252), doTopo52s: +((d.close[i] / max252 - 1) * 100).toFixed(1),
                estrategias: sinais && sinais.activated, score: sinais && sinais.totalScore, rr: v.rr, historicoPapel: porPapel[a.t] || null, pe: f.pe ?? null, receita: f.revenueGrowth ?? null, margem: f.netMargin ?? null };
        });
        const regras = {}; Object.entries(porRegra).forEach(([k, x]) => regras[k] = { acima: est(x.acima), abaixo: est(x.abaixo) });
        return { ultimoPregao: R.ultimoPregao, geradoEm: R.geradoEm, global: { acima: est(glob.acima), abaixo: est(glob.abaixo) }, regras, entradas };
    });
    fs.writeFileSync(SAIDA, JSON.stringify(r, null, 1));
    const L = ['## Análise das entradas do Relatório', '', `Dados de ${r.ultimoPregao}. Operações fora da amostra da regra escolhida de cada papel, separadas pela posição do sinal em relação à MME200 do papel:`, '',
        '| | operações | fator de lucro | acerto | média por operação |', '|---|---|---|---|---|',
        `| Sinal acima da MME200 | ${r.global.acima.n} | ${r.global.acima.pf} | ${r.global.acima.acerto} | ${r.global.acima.medRet}% |`,
        `| Sinal abaixo da MME200 | ${r.global.abaixo.n} | ${r.global.abaixo.pf} | ${r.global.abaixo.acerto} | ${r.global.abaixo.medRet}% |`, '',
        ...Object.entries(r.regras).map(([k, x]) => `- ${k}: acima ${x.acima.n} op. FL ${x.acima.pf} · abaixo ${x.abaixo.n} op. FL ${x.abaixo.pf}`), '',
        '| papel | setor | preço × MME200 | × MME50 | ATR % | stop em ATR | IFR14 | 20d | topo 52s | balanço | FL teste (n) | estratégias |', '|---|---|---|---|---|---|---|---|---|---|---|---|',
        ...r.entradas.map(e => `| ${e.t} | ${e.industria || e.setor || ''} | ${e.vsMme200}% | ${e.vsMme50}% | ${e.atrPct} | ${e.stopEmAtr} | ${e.ifr14} | ${e.ret20}% | ${e.doTopo52s}% | ${e.balanco || '—'} | ${e.pfTeste} (${e.nTeste}) | ${(e.estrategias || []).join(', ')} |`)];
    console.log(L.join('\n'));
    if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, L.join('\n') + '\n');
    await browser.close(); srv.close();
})().catch(e => { console.error(e); process.exit(1); });
