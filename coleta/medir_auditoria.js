// Medição (só leitura) dos 3 testes propostos pela auditoria de 04/11/2026, com o MESMO motor do app:
//  1) só aceitar o sinal se o papel foi bom NO MESMO REGIME (acima/abaixo da MME200) no período de TREINO
//     (os 60% iniciais; usar o período de teste para filtrar seria olhar o futuro);
//  2) stop móvel mais curto: distância nunca maior que a do stop inicial, ou 1,5 ATR em vez de 2,5; e stop no
//     preço de entrada (zero a zero) depois de andar 1 ou 1,5 ATR a favor;
//  3) carteira com limite de papéis abertos por setor (grupo SIC da SEC), medindo a queda máxima;
//  4) trava de espaço até a resistência (≥ 1 × o risco até o stop) do veredito do Relatório, que o motor não usa.
// Roda nos papéis confirmados, nos que só passaram no TREINO (fator de lucro ≥ 1, sem olhar o teste) e em todos
// os que têm regra. Os confirmados passaram no teste, o que infla os números; "treinoOk" é a estimativa sem esse viés.
//
// Uso: node coleta/medir_auditoria.js site setores.json [saida.json]
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const RAIZ = path.resolve(process.argv[2] || 'site');
const SETORES = process.argv[3] && fs.existsSync(process.argv[3]) ? JSON.parse(fs.readFileSync(process.argv[3], 'utf8')) : {};
const SAIDA = process.argv[4] || 'medir_auditoria.json';
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
    const r = await page.evaluate(async (SET) => {
        const I = window.investDebug, R = I.relatorio || await I.gerarRelatorio(), D = I.allData, P = I.getIndicatorParameters(), F = I.fundamentos || {};
        const FRACAO = 0.6;
        const est = lista => { let g = 0, p = 0, v = 0; lista.forEach(x => { if (x.pct > 0) { g += x.pct; v++; } else p -= x.pct; });
            return { n: lista.length, pf: p > 0 ? +(g / p).toFixed(2) : (g > 0 ? 99 : 0), acerto: lista.length ? +(v / lista.length).toFixed(3) : 0,
                somaCapital: +(lista.reduce((a, x) => a + x.pct, 0) * 100).toFixed(1) }; };
        const pfDe = l => { let g = 0, p = 0; l.forEach(x => { if (x.pct > 0) g += x.pct; else p -= x.pct; }); return p > 0 ? g / p : (g > 0 ? 99 : 0); };
        const saida = {};
        const pivosAltos = (d, w) => { const r = []; for (let i = w; i < d.high.length - w; i++) { let m = -Infinity; for (let j = i - w; j <= i + w; j++) m = Math.max(m, d.high[j]); if (d.high[i] === m) r.push({ index: i, price: d.high[i] }); } return r; };
        for (const universo of ['confirmadas', 'treinoOk', 'todas']) {
            const papeis = R.ativos.filter(a => a.regra && (universo === 'todas' || (universo === 'confirmadas' ? a.confirmada : a.treino && a.treino.pf >= 1)));
            const t4 = { todas: [], semResistencia: [], espacoOk: [], espacoCurto: [], comTrava: [] };
            const t1 = { todas: [], estrito: [], brando: [] }, t2 = { atual: { todas: [], volateis: [] }, inicial: { todas: [], volateis: [] }, atr15: { todas: [], volateis: [] }, empate1: { todas: [], volateis: [] }, empate15: { todas: [], volateis: [] } };
            const ops = [];  // para a carteira (teste 3)
            for (const a of papeis) {
                const d = D[a.t]; if (!d) continue; const base = I.regraRp(a.regra); if (!base) continue;
                const ind = I.precomputeAllIndicators(d, P), corte = Math.floor(d.close.length * FRACAO);
                const lado = x => { const s = x.ent - 1, e = ind.EMA_200[s]; return e ? (d.close[s] > e ? 'acima' : 'abaixo') : null; };
                const res = I.runCoreBacktest(d, base); if (!res) continue;
                // Teste 1
                const treino = { acima: [], abaixo: [] };
                res.tradesDet.filter(x => x.ent < corte).forEach(x => { const l = lado(x); if (l) treino[l].push(x); });
                const teste = res.tradesDet.filter(x => x.ent >= corte);
                teste.forEach(x => {
                    const l = lado(x); t1.todas.push(x); if (!l) return;
                    const tr = treino[l], bom = tr.length >= 3 && pfDe(tr) >= 1.5;
                    if (bom) t1.estrito.push(x);
                    if (bom || tr.length < 3) t1.brando.push(x);
                });
                // Teste 4: no dia do sinal (ent − 1), resistência = topo (pivô já confirmado, último ano) mais próximo acima do fechamento
                const pivos = pivosAltos(d, 5);
                teste.forEach(x => {
                    const s = x.ent - 1, c = d.close[s], atr = ind.ATR[s]; if (!atr) return;
                    const stop = Math.max(c - atr * base.atrMult, c * (1 - base.stopLossPct / 100)), risco = c - stop;
                    const res4 = pivos.filter(p => p.index >= s - 252 && p.index + 5 <= s && p.price > c).reduce((m, p) => Math.min(m, p.price), Infinity);
                    t4.todas.push(x);
                    if (!isFinite(res4)) { t4.semResistencia.push(x); t4.comTrava.push(x); }
                    else if (res4 - c >= risco) { t4.espacoOk.push(x); t4.comTrava.push(x); }
                    else t4.espacoCurto.push(x);
                });
                // Teste 3: operações de teste com datas, setor e prioridade (fator de lucro do TREINO)
                const setor = (SET[a.t] && SET[a.t].grupo) || (F[a.t] && F[a.t].sector) || ('?' + a.t);
                teste.forEach(x => ops.push({ t: a.t, setor, ent: d.dates[x.ent], sai: d.dates[Math.min(x.sai, d.dates.length - 1)], pct: x.pct, prio: (a.treino && a.treino.pf) || 0 }));
                // Teste 2
                for (const [k, extra] of [['atual', {}], ['inicial', { trailInicial: true }], ['atr15', { trailAtr: 1.5 }], ['empate1', { breakevenAtr: 1 }], ['empate15', { breakevenAtr: 1.5 }]]) {
                    const rr = k === 'atual' ? res : I.runCoreBacktest(d, { ...base, ...extra }); if (!rr) continue;
                    rr.tradesDet.filter(x => x.ent >= corte).forEach(x => {
                        t2[k].todas.push(x);
                        const atr = ind.ATR[x.ent - 1]; if (atr && atr / d.open[x.ent] * 100 > 3.2) t2[k].volateis.push(x);
                    });
                }
            }
            // Teste 3: carteira em ordem de data; no mesmo dia, maior fator de lucro de treino primeiro
            const carteira = (capSetor, capTotal) => {
                const ordem = [...ops].sort((x, y) => x.ent < y.ent ? -1 : x.ent > y.ent ? 1 : y.prio - x.prio);
                const abertas = [], aceitas = [];
                let maxMesmoSetor = 0;
                for (const o of ordem) {
                    for (let i = abertas.length - 1; i >= 0; i--) if (abertas[i].sai <= o.ent) abertas.splice(i, 1);
                    const noSetor = abertas.filter(x => x.setor === o.setor).length;
                    if (capSetor && noSetor >= capSetor) continue;
                    if (capTotal && abertas.length >= capTotal) continue;
                    abertas.push(o); aceitas.push(o); maxMesmoSetor = Math.max(maxMesmoSetor, noSetor + 1);
                }
                // Patrimônio realizado (soma dos resultados na data de saída), queda máxima e pior dia
                const porDia = {}; aceitas.forEach(o => porDia[o.sai] = (porDia[o.sai] || 0) + o.pct);
                const dias = Object.keys(porDia).sort(); let acc = 0, pico = 0, dd = 0, piorDia = 0;
                dias.forEach(dt => { acc += porDia[dt]; pico = Math.max(pico, acc); dd = Math.max(dd, pico - acc); piorDia = Math.min(piorDia, porDia[dt]); });
                const e = est(aceitas); return { ...e, quedaMaxima: +(dd * 100).toFixed(1), piorDia: +(piorDia * 100).toFixed(2), maxMesmoSetor, somaPorQueda: dd > 0 ? +(e.somaCapital / (dd * 100)).toFixed(2) : null };
            };
            const comSetor = new Set(ops.filter(o => !String(o.setor).startsWith('?')).map(o => o.t)).size;
            saida[universo] = {
                papeis: papeis.length, comSetor,
                teste1: Object.fromEntries(Object.entries(t1).map(([k, l]) => [k, est(l)])),
                teste2: Object.fromEntries(Object.entries(t2).map(([k, x]) => [k, { todas: est(x.todas), volateis: est(x.volateis) }])),
                teste4: Object.fromEntries(Object.entries(t4).map(([k, l]) => [k, est(l)])),
                teste3: { semLimite: carteira(0, 0), tres: carteira(3, 0), dois: carteira(2, 0), doisSeis: carteira(2, 6), seis: carteira(0, 6) }
            };
        }
        return { mercado: R.mercado, ultimoPregao: R.ultimoPregao, ...saida };
    }, SETORES);
    fs.writeFileSync(SAIDA, JSON.stringify(r, null, 1));
    const L = [`## Testes da auditoria · ${r.mercado} · dados de ${r.ultimoPregao}`, ''];
    for (const u of ['confirmadas', 'treinoOk', 'todas']) {
        const x = r[u]; L.push(`### Papéis: ${u} (${x.papeis}; ${x.comSetor} com setor da SEC)`, '');
        L.push('| teste 1: regime | operações | fator de lucro | acerto | soma |', '|---|---|---|---|---|',
            ...Object.entries(x.teste1).map(([k, v]) => `| ${k} | ${v.n} | ${v.pf} | ${(v.acerto * 100).toFixed(1)}% | ${v.somaCapital}% |`), '');
        L.push('| teste 2: stop móvel | operações | fator de lucro | soma | voláteis (ATR>3,2%): op. / FL / soma |', '|---|---|---|---|---|',
            ...Object.entries(x.teste2).map(([k, v]) => `| ${k} | ${v.todas.n} | ${v.todas.pf} | ${v.todas.somaCapital}% | ${v.volateis.n} / ${v.volateis.pf} / ${v.volateis.somaCapital}% |`), '');
        L.push('| teste 3: carteira | operações | fator de lucro | soma | queda máxima | soma ÷ queda | pior dia | máx. no mesmo setor |', '|---|---|---|---|---|---|---|---|',
            ...Object.entries(x.teste3).map(([k, v]) => `| ${k} | ${v.n} | ${v.pf} | ${v.somaCapital}% | ${v.quedaMaxima}% | ${v.somaPorQueda} | ${v.piorDia}% | ${v.maxMesmoSetor} |`), '');
        L.push('| teste 4: resistência | operações | fator de lucro | acerto | soma |', '|---|---|---|---|---|',
            ...Object.entries(x.teste4).map(([k, v]) => `| ${k} | ${v.n} | ${v.pf} | ${(v.acerto * 100).toFixed(1)}% | ${v.somaCapital}% |`), '');
    }
    console.log(L.join('\n'));
    if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, L.join('\n') + '\n');
    await browser.close(); srv.close();
})().catch(e => { console.error(e); process.exit(1); });
