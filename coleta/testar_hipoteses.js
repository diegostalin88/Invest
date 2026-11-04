// Teste das hipóteses novas registradas em docs/hipotese-momento-tendencia.md (só leitura; não muda o app).
//   A) momento de 12 meses sem o último mês, carteira dos 40 (EUA) / 10 (Brasil) melhores, rebalanceada todo mês;
//   B) tendência no índice: fica no índice quando o fechamento do mês está acima da média de 10 meses, senão caixa.
// Uso: node coleta/testar_hipoteses.js --site site --indices indices_longos.json [--cdi cdi.json] [--saida hipoteses.json]
const fs = require('fs');
const path = require('path');

const arg = (k, padrao = null) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : padrao; };
const r2 = (v, k = 2) => v === null || v === undefined || !isFinite(v) ? null : +v.toFixed(k);
const media = l => l.length ? l.reduce((a, b) => a + b, 0) / l.length : null;
const quantil = (v, p) => { const s = [...v].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.max(0, Math.floor(p * s.length)))]; };
function mulberry(seed) { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

// ---------- métricas de uma série de retornos mensais ----------
function metricas(rets, rf = null) {
    if (!rets.length) return null;
    let v = 1, pico = 1, dd = 0; rets.forEach(r => { v *= 1 + r; pico = Math.max(pico, v); dd = Math.max(dd, 1 - v / pico); });
    const ex = rets.map((r, i) => r - (rf ? rf[i] || 0 : 0)), m = media(ex), sd = Math.sqrt(media(ex.map(x => (x - m) ** 2)));
    return { meses: rets.length, retorno: r2((v - 1) * 100, 1), anual: r2((Math.pow(v, 12 / rets.length) - 1) * 100, 1), quedaMax: r2(dd * 100, 1), sharpe: r2(sd > 0 ? m / sd * Math.sqrt(12) : null) };
}

// ---------- dados de ações (formato publicado pelo app) ----------
function carregar(pasta) {
    const man = JSON.parse(fs.readFileSync(path.join(pasta, 'manifest.json'), 'utf8'));
    const brutos = {};
    for (const nome of man.arquivosPrecos) {
        const o = JSON.parse(fs.readFileSync(path.join(pasta, nome), 'utf8'));
        if (o.formato === 'colunar-v1') { for (const [t, a] of Object.entries(o.ativos)) brutos[t] = { dates: a.dates || o.datas.slice(a.i0, a.i0 + a.close.length), close: a.close, volume: a.volume }; }
        else for (const [t, a] of Object.entries(o)) brutos[t] = { dates: a.dates, close: a.close, volume: a.volume };
    }
    const cal = [...new Set(Object.values(brutos).flatMap(d => d.dates))].sort(), pos = new Map(cal.map((d, i) => [d, i]));
    const ativos = {};
    for (const [t, d] of Object.entries(brutos)) {
        const c = new Float64Array(cal.length).fill(NaN), dv = new Float64Array(cal.length).fill(NaN);
        d.dates.forEach((x, i) => { const g = pos.get(x); c[g] = d.close[i]; dv[g] = d.close[i] * (d.volume ? d.volume[i] || 0 : 0); });
        ativos[t] = { c, dv };
    }
    return { cal, ativos };
}
const fimDeMes = cal => cal.map((d, i) => i).filter(i => i === cal.length - 1 || cal[i].slice(0, 7) !== cal[i + 1].slice(0, 7));
function ultimoValido(arr, ate, desde) { for (let j = ate; j >= desde; j--) if (arr[j] > 0) return arr[j]; return null; }

// ---------- Hipótese A ----------
function hipoteseA(D, { N, topLiq, precoMin, look = 252, skip = 21, custo = 0.001, sorteios = 200, semente = 7 }) {
    const { cal, ativos } = D, fins = fimDeMes(cal).filter(g => g >= look);
    const tickers = Object.keys(ativos);
    const elegiveis = g => {
        const l = [];
        for (const t of tickers) {
            const { c, dv } = ativos[t];
            if (!(c[g] >= precoMin) || !(c[g - look] > 0) || !(c[g - skip] > 0)) continue;
            let s = 0, n = 0; for (let j = g - 19; j <= g; j++) if (dv[j] > 0) { s += dv[j]; n++; }
            if (n < 15) continue;
            l.push({ t, liq: s / n, nota: c[g - skip] / c[g - look] - 1 });
        }
        return l.sort((a, b) => b.liq - a.liq).slice(0, topLiq);
    };
    const periodos = [];   // [{g, g2, eleg}]
    for (let k = 0; k < fins.length - 1; k++) { const e = elegiveis(fins[k]); if (e.length >= 2 * N) periodos.push({ g: fins[k], g2: fins[k + 1], eleg: e }); }
    if (!periodos.length) return null;
    const ret = (t, g, g2) => { const a = ativos[t].c[g], b = ultimoValido(ativos[t].c, g2, g); return a > 0 && b > 0 ? b / a - 1 : 0; };
    // carteira em pesos iguais escolhida por `escolher(periodo)`; custo sobre o giro (pesos à deriva × pesos novos)
    const rodar = (escolher, c = custo) => {
        let antes = new Map(); const rets = [];
        for (const p of periodos) {
            const lista = escolher(p), w = 1 / lista.length; let giro = 0;
            const novos = new Map(lista.map(t => [t, w]));
            new Set([...antes.keys(), ...novos.keys()]).forEach(t => giro += Math.abs((novos.get(t) || 0) - (antes.get(t) || 0)));
            let bruto = 0; const deriva = new Map();
            lista.forEach(t => { const r = ret(t, p.g, p.g2); bruto += w * r; deriva.set(t, w * (1 + r)); });
            const tot = [...deriva.values()].reduce((a, b) => a + b, 0); deriva.forEach((v, t) => deriva.set(t, v / tot));
            rets.push(bruto - giro * c); antes = deriva;
        }
        return rets;
    };
    const topo = (n, lk = look) => p => {
        if (lk === look) return [...p.eleg].sort((a, b) => b.nota - a.nota).slice(0, n).map(x => x.t);
        return p.eleg.map(x => ({ t: x.t, nota: ativos[x.t].c[p.g - skip] > 0 && ativos[x.t].c[p.g - lk] > 0 ? ativos[x.t].c[p.g - skip] / ativos[x.t].c[p.g - lk] - 1 : -Infinity }))
            .sort((a, b) => b.nota - a.nota).slice(0, n).map(x => x.t);
    };
    const principal = rodar(topo(N));
    const todos = rodar(p => p.eleg.map(x => x.t));
    const rng = mulberry(semente), acaso = [];
    for (let s = 0; s < sorteios; s++) acaso.push(metricas(rodar(p => { const l = p.eleg.map(x => x.t); for (let i = l.length - 1; i > 0; i--) { const j = Math.floor(rng() * (i + 1)); [l[i], l[j]] = [l[j], l[i]]; } return l.slice(0, N); })));
    const dist = k => ({ p5: r2(quantil(acaso.map(x => x[k]), 0.05), 1), mediana: r2(quantil(acaso.map(x => x[k]), 0.5), 1), p95: r2(quantil(acaso.map(x => x[k]), 0.95), 1) });
    return {
        de: cal[periodos[0].g], ate: cal[periodos[periodos.length - 1].g2], meses: periodos.length, elegiveisMedio: r2(media(periodos.map(p => p.eleg.length)), 0),
        datas: periodos.map(p => [cal[p.g], cal[p.g2]]),
        principal: metricas(principal), principalRets: principal, pesosIguaisTodos: metricas(todos),
        acaso: { sorteios, retorno: dist('retorno'), quedaMax: dist('quedaMax') },
        robustez: {
            momento6: metricas(rodar(topo(N, 126 + skip))), momento3: metricas(rodar(topo(N, 63 + skip))),
            metadePapeis: metricas(rodar(topo(Math.max(2, Math.round(N / 2))))), dobroPapeis: metricas(rodar(topo(N * 2))), custo2x: metricas(rodar(topo(N), custo * 2))
        }
    };
}

// ---------- índice nas mesmas datas ----------
function serieMensalNasDatas(serie, pares) {
    const v = d => { let r = null; for (let i = 0; i < serie.dates.length && serie.dates[i] <= d; i++) r = serie.close[i]; return r; };
    // busca binária
    const fech = d => { let lo = 0, hi = serie.dates.length - 1, r = -1; while (lo <= hi) { const m = (lo + hi) >> 1; if (serie.dates[m] <= d) { r = m; lo = m + 1; } else hi = m - 1; } return r >= 0 ? serie.close[r] : null; };
    void v; return pares.map(([a, b]) => { const x = fech(a), y = fech(b); return x > 0 && y > 0 ? y / x - 1 : 0; });
}

// ---------- Hipótese B ----------
function hipoteseB(serie, rfMensal, { inicio, meses = 10, custo = 0.001 }) {
    const idx = serie.dates.map((d, i) => i).filter(i => serie.dates[i] >= inicio && (i === serie.dates.length - 1 || serie.dates[i].slice(0, 7) !== serie.dates[i + 1].slice(0, 7)));
    const fm = idx.map(i => ({ d: serie.dates[i], c: serie.close[i] }));
    const rTrend = [], rBH = [], rf = [], datas = []; let dentro = null, trocas = 0, mesesDentro = 0;
    for (let k = meses - 1; k < fm.length - 1; k++) {
        const mm = media(fm.slice(k - meses + 1, k + 1).map(x => x.c)), sinal = fm[k].c > mm;
        const rIdx = fm[k + 1].c / fm[k].c - 1, rCaixa = rfMensal(fm[k].d.slice(0, 7), fm[k + 1].d.slice(0, 7));
        let r = sinal ? rIdx : rCaixa; if (dentro !== null && dentro !== sinal) { r -= custo; trocas++; } if (dentro === null && sinal) r -= custo;
        dentro = sinal; if (sinal) mesesDentro++;
        rTrend.push(r); rBH.push(rIdx); rf.push(rCaixa); datas.push(fm[k + 1].d);
    }
    const corte = Math.floor(rTrend.length / 2);
    const bloco = (a, b) => ({ de: datas[a], ate: datas[b - 1], tendencia: metricas(rTrend.slice(a, b), rf.slice(a, b)), comprarSegurar: metricas(rBH.slice(a, b), rf.slice(a, b)) });
    return { inteiro: bloco(0, rTrend.length), primeiraMetade: bloco(0, corte), segundaMetade: bloco(corte, rTrend.length), trocas, mesesNoIndice: mesesDentro, meses: rTrend.length };
}
// juro mensal: ^IRX (taxa anual em %, valor do fim do mês anterior) ou CDI (taxa diária em %, composta no mês)
function juroIRX(irx) {
    if (!irx) return () => 0; const porMes = {}; irx.dates.forEach((d, i) => porMes[d.slice(0, 7)] = irx.close[i]);
    return (mesAnterior) => { const y = porMes[mesAnterior]; return y > 0 ? Math.pow(1 + y / 100, 1 / 12) - 1 : 0; };
}
function juroCDI(cdi) {
    if (!cdi || !cdi.length) return () => 0; const porMes = {};
    cdi.forEach(({ data, valor }) => { const [dd, mm, aa] = data.split('/'); const k = `${aa}-${mm}`; porMes[k] = (porMes[k] || 1) * (1 + (+valor) / 100); void dd; });
    return (mesAnterior, mes) => porMes[mes] ? porMes[mes] - 1 : 0;
}

// ---------- execução ----------
const SITE = arg('site', 'site');
const IND = arg('indices') && fs.existsSync(arg('indices')) ? JSON.parse(fs.readFileSync(arg('indices'), 'utf8')) : {};
const CDI = arg('cdi') && fs.existsSync(arg('cdi')) ? JSON.parse(fs.readFileSync(arg('cdi'), 'utf8')) : null;
const R = { registro: 'docs/hipotese-momento-tendencia.md', geradoEm: new Date().toISOString() };
const L = ['## Hipóteses novas (registradas antes de rodar)', ''];
const linhaM = (nome, m) => m ? `| ${nome} | ${m.retorno}% | ${m.anual}% | ${m.quedaMax}% | ${m.sharpe} |` : `| ${nome} | — | — | — | — |`;

for (const [merc, pasta, cfg, nomeInd] of [['us', path.join(SITE, 'data'), { N: 40, topLiq: 400, precoMin: 5 }, 'SPY'], ['br', path.join(SITE, 'data', 'br'), { N: 10, topLiq: 60, precoMin: 2 }, 'BOVA11.SA']]) {
    if (!fs.existsSync(path.join(pasta, 'manifest.json'))) continue;
    // HIP_N / HIP_TOPLIQ: só para teste local com amostra pequena (o registro fixa 40/400 e 10/60)
    if (process.env.HIP_N) Object.assign(cfg, { N: +process.env.HIP_N, topLiq: +(process.env.HIP_TOPLIQ || cfg.topLiq) });
    const A = hipoteseA(carregar(pasta), cfg);
    if (!A) { L.push(`### A · ${merc.toUpperCase()}: dados insuficientes (menos de ${2 * cfg.N} elegíveis com 12 meses de histórico)`, ''); continue; }
    const ind = IND[nomeInd] ? metricas(serieMensalNasDatas(IND[nomeInd], A.datas)) : null;
    const ind2 = merc === 'br' && IND['^BVSP'] ? metricas(serieMensalNasDatas(IND['^BVSP'], A.datas)) : null;
    const c1 = A.principal.retorno > A.acaso.retorno.p95, c2 = ind ? A.principal.retorno > ind.retorno && A.principal.quedaMax <= 1.5 * ind.quedaMax : null, c3 = ind ? A.robustez.custo2x.retorno > ind.retorno : null;
    const { principalRets, datas, ...semRets } = A; void principalRets; void datas;
    R['A_' + merc] = { ...semRets, indice: { nome: nomeInd, ...ind }, ibovespa: ind2, criterios: { acimaDoAcasoP95: c1, venceIndiceComQuedaAte1_5x: c2, custo2xAindaVence: c3 }, aprovada: c1 && c2 === true && c3 === true };
    L.push(`### A · momento 12 meses · ${merc.toUpperCase()} · ${A.de} a ${A.ate} (${A.meses} meses, ~${A.elegiveisMedio} elegíveis por mês, ${cfg.N} na carteira)`, '',
        '| carteira | retorno | anual | queda máx. | Sharpe |', '|---|---|---|---|---|',
        linhaM(`momento (top ${cfg.N})`, A.principal), linhaM(`índice ${nomeInd}`, ind), ...(ind2 ? [linhaM('Ibovespa (^BVSP)', ind2)] : []), linhaM('pesos iguais, todos os elegíveis', A.pesosIguaisTodos),
        `| acaso (${A.acaso.sorteios} sorteios de ${cfg.N} papéis) | p5 ${A.acaso.retorno.p5}% · mediana ${A.acaso.retorno.mediana}% · p95 ${A.acaso.retorno.p95}% | — | mediana ${A.acaso.quedaMax.mediana}% | — |`,
        ...Object.entries(A.robustez).map(([k, m]) => linhaM(`robustez: ${k}`, m)), '',
        `Critérios: acima do p95 do acaso **${c1 ? 'sim' : 'não'}** · vence o índice com queda até 1,5× **${c2 === null ? 'sem índice' : c2 ? 'sim' : 'não'}** · custo ×2 ainda vence **${c3 === null ? 'sem índice' : c3 ? 'sim' : 'não'}** → **${R['A_' + merc].aprovada ? 'APROVADA' : 'REPROVADA'}**`, '');
}

for (const [merc, nomeSerie, inicio, juro, nomeJuro] of [['us', 'SPY', '1993-01-01', juroIRX(IND['^IRX']), IND['^IRX'] ? 'T-bill 13 semanas (^IRX)' : '0% (juro indisponível)'], ['br', '^BVSP', '2000-01-01', juroCDI(CDI), CDI && CDI.length ? 'CDI (Banco Central, série 12)' : '0% (CDI indisponível)']]) {
    const s = IND[nomeSerie]; if (!s) { L.push(`### B · tendência · ${merc.toUpperCase()}: série ${nomeSerie} indisponível`, ''); continue; }
    const B = hipoteseB(s, juro, { inicio });
    const ok = b => b.tendencia.sharpe >= b.comprarSegurar.sharpe && b.tendencia.quedaMax <= b.comprarSegurar.quedaMax * 2 / 3;
    const aprov = ok(B.inteiro) && ok(B.segundaMetade);
    R['B_' + merc] = { serie: nomeSerie, caixa: nomeJuro, ...B, criterios: { inteiro: ok(B.inteiro), segundaMetade: ok(B.segundaMetade) }, aprovada: aprov };
    L.push(`### B · tendência no índice (média de 10 meses) · ${merc.toUpperCase()} · ${nomeSerie} · caixa: ${nomeJuro}`, '',
        `${B.meses} meses, ${B.mesesNoIndice} no índice, ${B.trocas} trocas.`, '',
        '| período | estratégia | retorno | anual | queda máx. | Sharpe (sobre o juro) |', '|---|---|---|---|---|---|',
        ...['inteiro', 'primeiraMetade', 'segundaMetade'].flatMap(k => { const b = B[k]; return [`| ${k} (${b.de} a ${b.ate}) | tendência | ${b.tendencia.retorno}% | ${b.tendencia.anual}% | ${b.tendencia.quedaMax}% | ${b.tendencia.sharpe} |`, `| | comprar e segurar | ${b.comprarSegurar.retorno}% | ${b.comprarSegurar.anual}% | ${b.comprarSegurar.quedaMax}% | ${b.comprarSegurar.sharpe} |`]; }), '',
        `Critérios (Sharpe ≥ e queda ≤ 2/3): inteiro **${ok(B.inteiro) ? 'sim' : 'não'}** · segunda metade **${ok(B.segundaMetade) ? 'sim' : 'não'}** → **${aprov ? 'APROVADA' : 'REPROVADA'}**`, '');
}
fs.writeFileSync(arg('saida', 'hipoteses.json'), JSON.stringify(R, null, 1));
console.log(L.join('\n'));
if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, L.join('\n') + '\n');
