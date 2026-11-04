// Auditoria adversarial do Invest (só leitura; não publica nada e não muda o app).
// Roda o MOTOR DO APP (copiado de app/index.html em tempo de execução por motor_node.js) e tenta DERRUBAR a vantagem:
//   base (reproduz confirmados / só treino / todos) · entradas aleatórias com a mesma saída · Score degenerado (só MME200/Keltner)
//   custos ×2 e ×3 · deslizamento na abertura · atraso de 1 pregão · vizinhos (ATR 2/3, score 1,5/2,5, divisão 50/50 e 70/30)
//   carteira com capital limitado contra comprar e segurar · regime, setor e operações gigantes · teste de vazamento do futuro
//
// Uso (dados reais, depois de montar a pasta "site" como nos outros workflows de medição):
//   node coleta/medir_adversarial.js --site site --mercado us [--indice indice.json] [--saida adv_us.json]
// Uso (dados sintéticos SEM vantagem nenhuma, para ver o que o motor "encontra" no puro acaso):
//   node coleta/medir_adversarial.js --sintetico alta|lateral|queda [--semente 1] [--saida adv_sint.json]
const fs = require('fs');
const path = require('path');

const arg = (k, padrao = null) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : padrao; };
const MERCADO = arg('mercado', 'us');
const APP = path.join(__dirname, '..', 'app', 'index.html');
const M = require('./motor_node')(APP, MERCADO);
const SEMENTES_ALEAT = +arg('sementes', 20);
const rapido = process.argv.includes('--rapido');
// --inicio-teste AAAA-MM-DD: o teste de cada papel começa no 1º pregão a partir dessa data (treino = tudo antes).
// Serve para o critério 2 do docs/congelamento.md. As divisões 50/50 e 70/30 continuam por fração, de propósito.
const INICIO_TESTE = arg('inicio-teste');
if (INICIO_TESTE) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(INICIO_TESTE)) throw new Error('--inicio-teste precisa ser AAAA-MM-DD');
    let f = M.avaliarPapelRelatorio.toString(); const de = 'const corte = Math.floor(n * FRACAO_ESCOLHA);';
    if (!f.includes(de)) throw new Error('corte do avaliarPapelRelatorio não encontrado no app');
    f = f.replace(de, 'const corte = CORTE_DATA ? corteNaData(d.dates, CORTE_DATA) : Math.floor(n * FRACAO_ESCOLHA);');
    require('vm').runInContext('var CORTE_DATA = null; function corteNaData(datas, dia) { const k = datas.findIndex(x => x >= dia); return k < 0 ? datas.length : k; }\n' + f, M);
}
const corteDe = (d, fracao) => INICIO_TESTE && fracao === 0.6 ? M.corteNaData(d.dates, INICIO_TESTE) : Math.floor(d.close.length * fracao);

// ---------- utilidades ----------
function mulberry(seed) { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function normal(r) { let u = 0, v = 0; while (u === 0) u = r(); while (v === 0) v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
const fl = l => { let g = 0, p = 0; l.forEach(x => { if (x > 0) g += x; else p -= x; }); return p > 0 ? g / p : (g > 0 ? 99 : 0); };
const media = l => l.length ? l.reduce((a, b) => a + b, 0) / l.length : null;
const r2 = (v, k = 2) => v === null || v === undefined || !isFinite(v) ? null : +v.toFixed(k);
const quantil = (v, p) => { const s = [...v].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.max(0, Math.floor(p * s.length)))]; };
function resumo(lista) {   // lista de operações {pct, ret}
    const pct = lista.map(x => x.pct), ret = lista.map(x => x.ret);
    return { n: lista.length, fl: r2(fl(pct)), acerto: r2(lista.length ? pct.filter(x => x > 0).length / lista.length : null, 3),
        mediaRet: r2(media(ret) === null ? null : media(ret) * 100, 3), somaR: r2(pct.reduce((a, b) => a + b, 0) * 100, 1) };
}
// Intervalo de confiança do fator de lucro por reamostragem (bootstrap) das operações
function icFl(lista, vezes = 1000, seed = 7) {
    if (lista.length < 10) return null; const r = mulberry(seed), pct = lista.map(x => x.pct), v = [];
    for (let k = 0; k < vezes; k++) { let g = 0, p = 0; for (let j = 0; j < pct.length; j++) { const x = pct[Math.floor(r() * pct.length)]; if (x > 0) g += x; else p -= x; } v.push(p > 0 ? g / p : 99); }
    return [r2(quantil(v, 0.05)), r2(quantil(v, 0.95))];
}

// ---------- dados ----------
function carregarSite(pasta) {
    const base = path.join(pasta, 'data', MERCADO === 'br' ? 'br' : '');
    const man = JSON.parse(fs.readFileSync(path.join(base, 'manifest.json'), 'utf8'));
    const dados = {};
    for (const nome of man.arquivosPrecos) {
        const o = JSON.parse(fs.readFileSync(path.join(base, nome), 'utf8'));
        if (o.formato === 'colunar-v1') { for (const [t, a] of Object.entries(o.ativos)) { const n = a.close.length; dados[t] = { dates: a.dates || o.datas.slice(a.i0, a.i0 + n), open: a.open, high: a.high, low: a.low, close: a.close, volume: a.volume }; } }
        else Object.assign(dados, o);
    }
    let fund = {}; try { fund = JSON.parse(fs.readFileSync(path.join(base, man.arquivoFundamentos || 'fundamentos.json'), 'utf8')); } catch (e) {}
    let calib = null; try { calib = JSON.parse(fs.readFileSync(path.join(base, 'calibracao.json'), 'utf8')); } catch (e) {}
    return { dados, fund: fund.ativos || fund, calib, ultimo: man.ultimoPregao };
}
// Universo sintético: fator de mercado + ruído próprio, SEM nenhuma previsibilidade (passeio aleatório).
function sintetico(cenario, semente, nAtivos = 400, nDias = 750) {
    const r = mulberry(semente), dias = []; const d = new Date(Date.UTC(2026, 9, 30));
    while (dias.length < nDias) { if (d.getUTCDay() % 6) dias.unshift(d.toISOString().slice(0, 10)); d.setUTCDate(d.getUTCDate() - 1); }
    const anual = { alta: 0.20, lateral: 0.0, queda: -0.20 }[cenario]; if (anual === undefined) throw new Error('cenário: alta | lateral | queda');
    const sm = 0.010, mu = Math.log(1 + anual) / 252, rm = dias.map(() => mu + sm * normal(r));
    const dados = {}, fund = {}, setores = ['Technology', 'Healthcare', 'Financial Services', 'Industrials', 'Consumer Cyclical', 'Energy'];
    for (let k = 0; k < nAtivos; k++) {
        const beta = 0.5 + r() * 1.1, si = 0.012 + r() * 0.016, p0 = 20 + r() * 280, volBase = (60e6 + r() * 240e6) / p0;
        const o = [], h = [], l = [], c = [], v = []; let prev = p0;
        for (let i = 0; i < nDias; i++) {
            const tot = beta * rm[i] + si * normal(r) - 0.5 * si * si, noite = 0.3 * tot + 0.3 * si * normal(r), dia = tot - noite;
            const op = prev * Math.exp(noite), cl = op * Math.exp(dia), ruido = Math.abs(normal(r)) * 0.5 * si, ruido2 = Math.abs(normal(r)) * 0.5 * si;
            o.push(op); c.push(cl); h.push(Math.max(op, cl) * Math.exp(ruido)); l.push(Math.min(op, cl) * Math.exp(-ruido2));
            v.push(volBase * Math.exp(0.3 * normal(r)) * (1 + Math.abs(dia) / si * 0.3)); prev = cl;
        }
        const t = 'S' + String(k).padStart(3, '0'); dados[t] = { dates: dias.slice(), open: o, high: h, low: l, close: c, volume: v };
        fund[t] = { sector: setores[k % setores.length] };
    }
    // "índice": média do fator de mercado (o que comprar e segurar renderia)
    let px = 100; const indice = { dates: dias.slice(), close: rm.map(x => (px *= Math.exp(x))) };
    return { dados, fund, calib: null, ultimo: dias[dias.length - 1], indice: { INDICE: indice } };
}

// ---------- pipeline do Relatório, com o motor do app ----------
const cacheInd = new WeakMap(); const precomputeOriginal = M.precomputeAllIndicators;
M.precomputeAllIndicators = (d, p) => { if (!cacheInd.has(d)) cacheInd.set(d, precomputeOriginal(d, p)); return cacheInd.get(d); };
const runOriginal = M.runCoreBacktest;

// Roda o Relatório (6 regras por papel, escolha no treino, confirmação no teste) e devolve as operações FORA DA AMOSTRA
// da regra escolhida, separadas em confirmados / aprovados só no treino / todos.
function pipeline({ rp = {}, ganchos = null, fracao = 0.6, universo, calib }) {
    M.FRACAO_ESCOLHA = fracao; if (INICIO_TESTE) M.CORTE_DATA = fracao === 0.6 ? INICIO_TESTE : null;
    M.runCoreBacktest = ganchos ? (d, x) => M.runCoreBacktestVar(d, { ...x, ...ganchos }) : runOriginal;
    const base = { ...M.RP_PADRAO, ...rp }, regras = M.regrasRelatorio(base, calib || { alvo: 3, dias: 10 });
    const grupos = { confirmados: [], treinoOk: [], todos: [] }, papeis = { confirmados: 0, treinoOk: 0, todos: 0 }, detalhe = [];
    M.poolRelatorio = null;
    for (const t of universo) {
        const d = M.allData[t]; const a = M.avaliarPapelRelatorio(t, regras); if (!a.regra) continue;
        const regra = regras.find(x => x.id === a.regra), corte = corteDe(d, fracao);
        const res = M.runCoreBacktest(d, regra.rp); if (!res) continue;
        const te = res.tradesDet.filter(x => x.ent >= corte).map(x => ({ ...x, t, regra: a.regra, prio: a.treino.pf, entD: d.dates[x.ent], saiD: d.dates[Math.min(x.sai, d.dates.length - 1)] }));
        const em = [['todos', true], ['treinoOk', a.treino.pf >= 1], ['confirmados', a.confirmada]];
        for (const [g, ok] of em) if (ok) { grupos[g].push(...te); papeis[g]++; }
        detalhe.push({ t, regra: a.regra, confirmada: a.confirmada, pfTreino: a.treino.pf, te });
    }
    M.runCoreBacktest = runOriginal; M.FRACAO_ESCOLHA = 0.6;
    const out = {}; for (const g of Object.keys(grupos)) out[g] = { papeis: papeis[g], ...resumo(grupos[g]), ic90: icFl(grupos[g]) };
    return { ...out, _ops: grupos, _detalhe: detalhe };
}
const enxuto = r => { const o = {}; for (const g of ['confirmados', 'treinoOk', 'todos']) o[g] = r[g]; return o; };

// ---------- carteira realista (capital limitado, sem alavancagem) ----------
function carteira(ops, { capital = 100000, risco = 0.01, maxPos = 0, custo = 0.001, rng = null } = {}, inicio, fim) {
    // rng: em vez de priorizar pelo fator de lucro do treino, sorteia a ordem dos sinais do mesmo dia (mede a sorte da fila)
    const pr = new Map(ops.map(o => [o, rng ? rng() : o.prio]));
    const porEnt = {}, ordem = [...ops].sort((a, b) => a.entD < b.entD ? -1 : a.entD > b.entD ? 1 : pr.get(b) - pr.get(a));
    ordem.forEach(o => (porEnt[o.entD] = porEnt[o.entD] || []).push(o));
    const datas = new Set(); for (const t of new Set(ops.map(o => o.t))) M.allData[t].dates.forEach(x => { if (x >= inicio && x <= fim) datas.add(x); });
    const dias = [...datas].sort(); const idx = {}; for (const t of new Set(ops.map(o => o.t))) { idx[t] = {}; M.allData[t].dates.forEach((x, i) => idx[t][x] = i); }
    let caixa = capital, abertas = [], serie = [], maxAbertas = 0, expo = [], recusadas = 0, aceitas = 0;
    let ultimoPatr = capital;
    for (const dia of dias) {
        // saídas do dia (resultado já com custo nas duas pernas, como no motor)
        abertas = abertas.filter(p => { if (p.o.saiD === dia) { caixa += p.valorEnt * (1 + p.o.ret); return false; } return true; });
        // entradas do dia: tamanho pelo risco até o stop (1% do patrimônio de ontem), limitado ao caixa
        for (const o of porEnt[dia] || []) {
            const d = M.allData[o.t], fracStop = o.pct !== 0 ? risco * o.ret / o.pct : null;
            if (!(fracStop > 0)) { recusadas++; continue; }
            if (maxPos && abertas.length >= maxPos) { recusadas++; continue; }
            const quer = ultimoPatr * risco / fracStop, valor = Math.min(quer, caixa);
            if (valor < quer * 0.25) { recusadas++; continue; }
            caixa -= valor; aceitas++; abertas.push({ o, valorEnt: valor, pxEnt: d.open[o.ent] * (1 + custo) });
        }
        // marcação a mercado no fechamento
        let investido = 0; for (const p of abertas) { const d = M.allData[p.o.t], i = idx[p.o.t][dia]; const c = i !== undefined ? d.close[i] : null; investido += c ? p.valorEnt * c / p.pxEnt : p.valorEnt; }
        ultimoPatr = caixa + investido; serie.push(ultimoPatr); expo.push(investido / ultimoPatr); maxAbertas = Math.max(maxAbertas, abertas.length);
    }
    return { ...metricas(serie, dias), exposicaoMedia: r2(media(expo) * 100, 1), maxAbertas, aceitas, recusadas };
}
function metricas(serie, dias) {
    if (serie.length < 2) return { retorno: null };
    const rets = []; for (let i = 1; i < serie.length; i++) rets.push(serie[i] / serie[i - 1] - 1);
    let pico = serie[0], dd = 0; serie.forEach(x => { pico = Math.max(pico, x); dd = Math.max(dd, 1 - x / pico); });
    const anos = (new Date(dias[dias.length - 1]) - new Date(dias[0])) / (365.25 * 864e5);
    const total = serie[serie.length - 1] / serie[0] - 1, m = media(rets), sd = Math.sqrt(media(rets.map(x => (x - m) ** 2)));
    const cagr = Math.pow(1 + total, 1 / anos) - 1;
    return { de: dias[0], ate: dias[dias.length - 1], retorno: r2(total * 100, 1), anual: r2(cagr * 100, 1), quedaMax: r2(dd * 100, 1),
        sharpe: r2(sd > 0 ? m / sd * Math.sqrt(252) : null), anualPorQueda: r2(dd > 0 ? cagr / dd : null) };
}
function comprarSegurar(serie, inicio, fim) {
    const dias = [], v = []; serie.dates.forEach((x, i) => { if (x >= inicio && x <= fim) { dias.push(x); v.push(serie.close[i]); } });
    return metricas(v, dias);
}
function igualPeso(universo, inicio, fim) {   // carteira de pesos iguais de todo o universo (rebalanceada todo dia)
    const porDia = {};
    for (const t of universo) { const d = M.allData[t]; for (let i = 1; i < d.close.length; i++) { const x = d.dates[i]; if (x > inicio && x <= fim) (porDia[x] = porDia[x] || []).push(d.close[i] / d.close[i - 1] - 1); } }
    const dias = Object.keys(porDia).sort(); let v = 1; const s = [1]; dias.forEach(x => s.push(v *= 1 + media(porDia[x])));
    return metricas(s, [inicio, ...dias]);
}

// ---------- teste de vazamento: o sinal do dia i muda se apagarmos o futuro? ----------
function testeVazamento(universo, amostras = 300, seed = 11) {
    const r = mulberry(seed); const P = M.getIndicatorParameters(); let difSinal = 0, difAtr = 0, difEma = 0, n = 0; const exemplos = [];
    for (let k = 0; k < amostras; k++) {
        const t = universo[Math.floor(r() * universo.length)], d = M.allData[t]; if (d.close.length < 260) continue;
        const i = 210 + Math.floor(r() * (d.close.length - 220)); const corte = {}; for (const c of ['dates', 'open', 'high', 'low', 'close', 'volume']) corte[c] = d[c].slice(0, i + 1);
        const indA = precomputeOriginal(d, P), indB = precomputeOriginal(corte, P);
        const sA = Object.keys(M.analyzeAllSignals(d, indA, i).buy).sort().join(), sB = Object.keys(M.analyzeAllSignals(corte, indB, i).buy).sort().join();
        n++; if (sA !== sB) { difSinal++; if (exemplos.length < 5) exemplos.push({ t, data: d.dates[i], comFuturo: sA, semFuturo: sB }); }
        if (Math.abs((indA.ATR[i] || 0) - (indB.ATR[i] || 0)) > 1e-9) difAtr++;
        if (Math.abs((indA.EMA_200[i] || 0) - (indB.EMA_200[i] || 0)) > 1e-9) difEma++;
    }
    return { amostras: n, sinaisDiferentes: difSinal, atrDiferente: difAtr, mme200Diferente: difEma, exemplos };
}

// ---------- execução ----------
(async () => {
    const cen = arg('sintetico'); const semente = +arg('semente', 1);
    const fonte = cen ? sintetico(cen, semente) : carregarSite(arg('site', 'site'));
    let indices = fonte.indice || {}; const arqInd = arg('indice'); if (arqInd && fs.existsSync(arqInd)) indices = { ...indices, ...JSON.parse(fs.readFileSync(arqInd, 'utf8')) };
    M.allData = fonte.dados; M.computeHistoricalRegime();
    const universo = M.universoRelatorio(); const calib = fonte.calib && fonte.calib.alvo ? { alvo: fonte.calib.alvo, dias: fonte.calib.dias } : { alvo: 3, dias: 10 };
    const T0 = Date.now(); const log = (...x) => console.error(`[${((Date.now() - T0) / 1000).toFixed(0)}s]`, ...x);
    const R = { fonte: cen ? `sintético "${cen}" (semente ${semente}, sem vantagem embutida)` : `dados publicados (${MERCADO})`, ultimoPregao: fonte.ultimo, universo: universo.length, calibracao: calib, parametros: M.RP_PADRAO };

    log('base'); const base = pipeline({ universo, calib }); R.base = enxuto(base);
    // Janela fora da amostra (o maior histórico define a data de corte de 60%)
    const maior = universo.reduce((m, t) => M.allData[t].dates.length > M.allData[m].dates.length ? t : m, universo[0]);
    const dl = M.allData[maior].dates, inicioTeste = INICIO_TESTE || dl[Math.floor(dl.length * 0.6)], fim = dl[dl.length - 1]; R.janelaTeste = { de: inicioTeste, ate: fim };

    // 1) Entradas aleatórias com o MESMO stop, tamanho, custo, filtro de regime e o MESMO processo de escolha/confirmação.
    //    A probabilidade é ajustada para dar o mesmo número de operações que o sistema (todos, fora da amostra).
    log('aleatório'); const alvoN = base.todos.n; let prob = 0.5;
    for (let it = 0; it < (rapido ? 3 : 6); it++) {
        const rr = pipeline({ universo, calib, ganchos: { __aleatoria: true, __prob: prob, __rng: mulberry(999 + it) } });
        prob = Math.min(1, Math.max(0.01, prob * Math.pow(alvoN / Math.max(1, rr.todos.n), 1.3)));
    }
    const nulos = [];
    for (let s = 0; s < (rapido ? 5 : SEMENTES_ALEAT); s++) nulos.push(enxuto(pipeline({ universo, calib, ganchos: { __aleatoria: true, __prob: prob, __rng: mulberry(1000 + s) } })));
    const sempre = enxuto(pipeline({ universo, calib, ganchos: { __aleatoria: true, __prob: 1, __rng: () => 0 } }));
    const dist = g => { const v = nulos.map(x => x[g].fl).filter(x => x !== null); return { media: r2(media(v)), p5: r2(quantil(v, 0.05)), p95: r2(quantil(v, 0.95)), sistemaAcimaDe: r2(v.filter(x => x < base[g].fl).length / v.length * 100, 0) + '% dos sorteios' }; };
    R.aleatorio = { probPorDia: r2(prob, 3), sorteios: nulos.length, confirmados: dist('confirmados'), treinoOk: dist('treinoOk'), todos: dist('todos'),
        operacoesMedias: r2(media(nulos.map(x => x.todos.n)), 0), comprarSempreQueEstiverFora: sempre };

    // 2) Score degenerado: só a estratégia Keltner (preço > MME200 OU toque na banda) com peso 2,5 — o resto zerado.
    log('score degenerado'); const soK = {}; Object.keys(M.RP_PADRAO.weights).forEach(k => soK[k] = k === 'keltner_reversion_buy' ? 2.5 : 0);
    R.soKeltnerMme200 = enxuto(pipeline({ universo, calib, rp: { weights: soK } }));
    // Com que frequência o Score passa do mínimo num dia qualquer acima da MME200 (o sinal é raro ou quase sempre ligado?)
    { let dias = 0, passa = 0, soK2 = 0; const P = M.getIndicatorParameters();
      for (const t of universo.slice(0, 120)) { const d = M.allData[t], ind = M.precomputeAllIndicators(d, P);
        for (let i = 200; i < d.close.length; i++) { const s = M.analyzeAllSignals(d, ind, i), sc = M.computeStrategyScore(s, M.RP_PADRAO.weights).totalScore; dias++; if (sc >= M.RP_PADRAO.minScore) passa++; if (s.buy.Price_Above_EMA_200 || s.buy.Keltner_Touch_Lower) soK2++; } }
      R.frequenciaSinal = { diasAvaliados: dias, scorePassa: r2(passa / dias * 100, 1) + '%', keltnerSozinhaPassa: r2(soK2 / dias * 100, 1) + '%' }; }

    // 3) Custos e deslizamento
    log('custos'); R.custos = {
        custo2x: enxuto(pipeline({ universo, calib, rp: { costPct: M.RP_PADRAO.costPct * 2 } })),
        custo3x: enxuto(pipeline({ universo, calib, rp: { costPct: M.RP_PADRAO.costPct * 3 } })),
        desliz01atr: enxuto(pipeline({ universo, calib, ganchos: { __desliz: 0.1 } })),
        desliz025atr: enxuto(pipeline({ universo, calib, ganchos: { __desliz: 0.25 } })) };
    // 4) Atraso
    log('atraso'); R.atraso1 = enxuto(pipeline({ universo, calib, ganchos: { __atraso: 1 } }));
    // 5) Vizinhos e divisões
    log('vizinhos'); R.vizinhos = {
        atr2: enxuto(pipeline({ universo, calib, rp: { atrMult: 2 } })), atr3: enxuto(pipeline({ universo, calib, rp: { atrMult: 3 } })),
        score15: enxuto(pipeline({ universo, calib, rp: { minScore: 1.5 } })), score25: enxuto(pipeline({ universo, calib, rp: { minScore: 2.5 } })),
        divisao50: enxuto(pipeline({ universo, calib, fracao: 0.5 })), divisao70: enxuto(pipeline({ universo, calib, fracao: 0.7 })),
        semFiltroRegime: enxuto(pipeline({ universo, calib, rp: { regimeFilter: false } })) };

    // 6) Carteira realista contra comprar e segurar, na mesma janela
    log('carteira'); R.carteira = {};
    for (const g of ['treinoOk', 'todos', 'confirmados']) {
        const ops = base._ops[g]; R.carteira[g] = { semLimite: carteira(ops, {}, inicioTeste, fim), max10: carteira(ops, { maxPos: 10 }, inicioTeste, fim), max5: carteira(ops, { maxPos: 5 }, inicioTeste, fim) };
    }
    R.carteira.aleatorioTodos = carteira(pipeline({ universo, calib, ganchos: { __aleatoria: true, __prob: prob, __rng: mulberry(4242) } })._ops.todos, {}, inicioTeste, fim);
    // Sorte da fila: com capital limitado só uma fração dos sinais entra; sorteia a ordem dos sinais do mesmo dia 30 vezes
    const distCart = ops => { const v = []; for (let s = 0; s < (rapido ? 5 : 30); s++) v.push(carteira(ops, { rng: mulberry(500 + s) }, inicioTeste, fim));
        const q = (k, p) => r2(quantil(v.map(x => x[k]).filter(x => x !== null), p), 1);
        return { sorteios: v.length, retornoMediana: q('retorno', 0.5), retornoP5: q('retorno', 0.05), retornoP95: q('retorno', 0.95), quedaMediana: q('quedaMax', 0.5), aceitasMedia: r2(media(v.map(x => x.aceitas)), 0) }; };
    R.carteiraSorteada = { treinoOk: distCart(base._ops.treinoOk), todos: distCart(base._ops.todos),
        aleatorio: distCart(pipeline({ universo, calib, ganchos: { __aleatoria: true, __prob: prob, __rng: mulberry(4242) } })._ops.todos) };
    R.comprarSegurar = { igualPesoUniverso: igualPeso(universo, inicioTeste, fim) };
    for (const [k, s] of Object.entries(indices)) R.comprarSegurar[k] = comprarSegurar(s, inicioTeste, fim);

    // 7) Dependência de regime, setor e operações gigantes (grupo "todos" e "treinoOk")
    log('regime'); R.dependencia = {};
    const regimeDe = x => M.regimeByDateMap[x];
    for (const g of ['treinoOk', 'todos', 'confirmados']) {
        const ops = base._ops[g]; const porSetor = {}; ops.forEach(o => { const s = (fonte.fund[o.t] && fonte.fund[o.t].sector) || 'sem setor'; (porSetor[s] = porSetor[s] || []).push(o); });
        const ord = [...ops].sort((a, b) => b.pct - a.pct), corta = k => resumo(ord.slice(k));
        const porMes = {}; ops.forEach(o => (porMes[o.entD.slice(0, 7)] = porMes[o.entD.slice(0, 7)] || []).push(o));
        const somaTotal = ops.reduce((a, o) => a + o.pct, 0);
        R.dependencia[g] = {
            setores: Object.fromEntries(Object.entries(porSetor).sort((a, b) => b[1].length - a[1].length).map(([s, l]) => [s, { ...resumo(l), parteDaSoma: r2(l.reduce((a, o) => a + o.pct, 0) / somaTotal * 100, 0) + '%' }])),
            semTecnologia: resumo(ops.filter(o => !/tech/i.test((fonte.fund[o.t] && fonte.fund[o.t].sector) || ''))),
            semAs10Maiores: corta(10), semOs5PorCentoMaiores: corta(Math.ceil(ops.length * 0.05)),
            parteDaSomaNas10Maiores: r2(ord.slice(0, 10).reduce((a, o) => a + o.pct, 0) / somaTotal * 100, 0) + '%',
            amplitudeNaEntrada: { acima70: resumo(ops.filter(o => regimeDe(o.entD) >= 70)), de50a70: resumo(ops.filter(o => regimeDe(o.entD) < 70)) },
            meses: Object.fromEntries(Object.entries(porMes).sort().map(([m, l]) => [m, { n: l.length, fl: resumo(l).fl }])),
            mesesNegativos: Object.values(porMes).filter(l => l.reduce((a, o) => a + o.pct, 0) < 0).length + ' de ' + Object.keys(porMes).length };
    }
    // 8) Vazamento do futuro (independe do período)
    log('vazamento'); R.vazamento = testeVazamento(universo);
    log('fim');
    const saida = arg('saida', `adversarial_${cen || MERCADO}.json`); fs.writeFileSync(saida, JSON.stringify(R, null, 1));
    const linha = (nome, x) => `| ${nome} | ${x.confirmados.fl} (${x.confirmados.n}) | ${x.treinoOk.fl} (${x.treinoOk.n}) | ${x.todos.fl} (${x.todos.n}) |`;
    const L = [`## Auditoria adversarial · ${R.fonte} · até ${R.ultimoPregao}`, '', `Universo ${R.universo} papéis · fora da amostra de ${inicioTeste} a ${fim}`, '',
        '| cenário | confirmados FL (op.) | só treino FL (op.) | todos FL (op.) |', '|---|---|---|---|',
        linha('base (app)', R.base), linha('comprar sempre que estiver fora', R.aleatorio.comprarSempreQueEstiverFora), linha('só Keltner/MME200', R.soKeltnerMme200),
        linha('custo ×2', R.custos.custo2x), linha('custo ×3', R.custos.custo3x), linha('deslize 0,1 ATR', R.custos.desliz01atr), linha('deslize 0,25 ATR', R.custos.desliz025atr),
        linha('atraso 1 pregão', R.atraso1), ...Object.entries(R.vizinhos).map(([k, x]) => linha(k, x)), '',
        `**Entradas aleatórias** (${R.aleatorio.sorteios} sorteios, p=${R.aleatorio.probPorDia}/dia, ~${R.aleatorio.operacoesMedias} operações): ` +
        ['confirmados', 'treinoOk', 'todos'].map(g => `${g} FL médio ${R.aleatorio[g].media} [${R.aleatorio[g].p5}–${R.aleatorio[g].p95}], sistema acima de ${R.aleatorio[g].sistemaAcimaDe}`).join(' · '), '',
        `IC 90% do FL (bootstrap): confirmados ${JSON.stringify(R.base.confirmados.ic90)} · só treino ${JSON.stringify(R.base.treinoOk.ic90)} · todos ${JSON.stringify(R.base.todos.ic90)}`, '',
        `Frequência: o Score passa do mínimo em ${R.frequenciaSinal.scorePassa} dos dias; só a Keltner (preço > MME200 ou toque) em ${R.frequenciaSinal.keltnerSozinhaPassa}.`, '',
        '| carteira (R$ 100 mil, 1% de risco, sem alavancagem) | retorno | anual | queda máx. | Sharpe | exposição média | máx. abertas |', '|---|---|---|---|---|---|---|',
        ...['treinoOk', 'todos', 'confirmados'].flatMap(g => ['semLimite', 'max10', 'max5'].map(k => { const x = R.carteira[g][k]; return `| ${g} · ${k} | ${x.retorno}% | ${x.anual}% | ${x.quedaMax}% | ${x.sharpe} | ${x.exposicaoMedia}% | ${x.maxAbertas} |`; })),
        (x => `| aleatório · semLimite | ${x.retorno}% | ${x.anual}% | ${x.quedaMax}% | ${x.sharpe} | ${x.exposicaoMedia}% | ${x.maxAbertas} |`)(R.carteira.aleatorioTodos),
        ...Object.entries(R.carteiraSorteada).map(([k, x]) => `| ${k} · ordem sorteada ×${x.sorteios} | mediana ${x.retornoMediana}% [${x.retornoP5}% a ${x.retornoP95}%] | — | mediana ${x.quedaMediana}% | — | — | ${x.aceitasMedia} op. aceitas |`),
        ...Object.entries(R.comprarSegurar).map(([k, x]) => `| comprar e segurar · ${k} | ${x.retorno}% | ${x.anual}% | ${x.quedaMax}% | ${x.sharpe} | 100% | — |`), '',
        `Concentração (todos): 10 maiores operações = ${R.dependencia.todos.parteDaSomaNas10Maiores} da soma; sem elas FL ${R.dependencia.todos.semAs10Maiores.fl}; sem os 5% maiores FL ${R.dependencia.todos.semOs5PorCentoMaiores.fl}; sem tecnologia FL ${R.dependencia.todos.semTecnologia.fl}; meses negativos ${R.dependencia.todos.mesesNegativos}.`, '',
        `Vazamento: ${R.vazamento.sinaisDiferentes} de ${R.vazamento.amostras} dias com sinal diferente quando o futuro é apagado (ATR ${R.vazamento.atrDiferente}, MME200 ${R.vazamento.mme200Diferente}).`];
    console.log(L.join('\n'));
    if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, L.join('\n') + '\n\n');
})().catch(e => { console.error(e); process.exit(1); });
