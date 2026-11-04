// Estudo de cenário "queda forte + reversão (Otimista)", conforme docs/cenario-queda-reversao.md (só leitura; não muda o app).
// Réplica independente, escrita a partir do registro: usa os indicadores e o v14_analisarSinais copiados do app em tempo de execução.
// Uso: node coleta/estudar_cenario.js --site site --mercado br|us [--indice indice_br.json] [--sorteios 500] [--saida cenario_br.json]
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const arg = (k, padrao = null) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : padrao; };
const MERCADO = arg('mercado', 'br'), SORTEIOS = +arg('sorteios', 500), CUSTO = 0.001, SEM_REPETIR = 20, JANELA = 60;
const APP = path.join(__dirname, '..', 'app', 'index.html');
const motor = require('./motor_node');
const M = motor(APP, MERCADO);

// funções v14_* e a tabela estrategiasV14, copiadas do app
const src = fs.readFileSync(APP, 'utf8'), partes = [];
for (const m of src.matchAll(/\n(\s*)function (v14_\w+)\s*\(/g)) { const ini = m.index + 1; let j = src.indexOf('(', ini), p = 0; for (; j < src.length; j++) { if (src[j] === '(') p++; else if (src[j] === ')') { p--; if (p === 0) break; } } partes.push(src.slice(ini, motor.fimDoBloco(src, src.indexOf('{', j)) + 1)); }
{ const m = /\n\s*const estrategiasV14\s*=\s*/.exec(src); const v = m.index + m[0].length; partes.push('var estrategiasV14 = ' + src.slice(v, motor.fimDoBloco(src, v) + 1) + ';'); }
vm.runInContext(partes.join('\n\n'), M, { filename: 'v14_extraido_do_app.js' });
const OTIMISTA = M.estrategiasV14.optimistic_buy;

const media = l => l.length ? l.reduce((a, b) => a + b, 0) / l.length : null;
const r2 = (v, k = 2) => v === null || v === undefined || !isFinite(v) ? null : +v.toFixed(k);
const pct = v => r2(v * 100);
const quantil = (v, p) => { const s = [...v].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.max(0, Math.floor(p * s.length)))]; };
function mulberry(seed) { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

// ---------- dados ----------
const base = path.join(arg('site', 'site'), 'data', MERCADO === 'br' ? 'br' : '');
const man = JSON.parse(fs.readFileSync(path.join(base, 'manifest.json'), 'utf8')); const dados = {};
for (const nome of man.arquivosPrecos) {
    const o = JSON.parse(fs.readFileSync(path.join(base, nome), 'utf8'));
    if (o.formato === 'colunar-v1') { for (const [t, a] of Object.entries(o.ativos)) dados[t] = { dates: a.dates || o.datas.slice(a.i0, a.i0 + a.close.length), open: a.open, high: a.high, low: a.low, close: a.close, volume: a.volume }; }
    else Object.assign(dados, o);
}
let indice = null; try { const ind = JSON.parse(fs.readFileSync(arg('indice') || path.join(base, man.arquivoIndice || 'indice.json'), 'utf8')); const s = ind.series || ind; indice = s[MERCADO === 'br' ? 'BOVA11.SA' : 'SPY'] || s.BOVA11 || Object.values(s)[0]; } catch (e) { }
const fechIndice = d => { if (!indice) return null; let lo = 0, hi = indice.dates.length - 1, r = -1; while (lo <= hi) { const m = (lo + hi) >> 1; if (indice.dates[m] <= d) { r = m; lo = m + 1; } else hi = m - 1; } return r >= 0 ? indice.close[r] : null; };
M.allData = dados; const universo = M.universoRelatorio();

// ---------- saída do app: stop inicial = o mais próximo entre 2,5 ATR e 8%; móvel = fechamento − 2,5 ATR (só sobe); gap sai na abertura ----------
function saidaApp(d, atr, i) {
    const e = i + 1; if (e >= d.close.length || !(atr[i] > 0)) return null;
    const ent = d.open[e] * (1 + CUSTO); let stop = Math.max(ent - 2.5 * atr[i], ent * 0.92);
    for (let k = e; k < d.close.length; k++) {
        if (d.low[k] <= stop) { const px = Math.min(stop, d.open[k]) * (1 - CUSTO); return { ret: px / ent - 1, ent: d.dates[e], sai: d.dates[k], aberta: false }; }
        if (atr[k] > 0) stop = Math.max(stop, d.close[k] - 2.5 * atr[k]);
    }
    const n = d.close.length - 1; return { ret: d.close[n] * (1 - CUSTO) / ent - 1, ent: d.dates[e], sai: d.dates[n], aberta: true };
}
const horizonte = (d, i, h) => { const e = i + 1, s = e + h - 1; if (s >= d.close.length) return null; return d.close[s] * (1 - CUSTO) / (d.open[e] * (1 + CUSTO)) - 1; };

// ---------- percorre os papéis ----------
const params = M.getIndicatorParameters();
const porQueda = { 0.30: { eventos: [], quedaDias: [] }, 0.25: { eventos: [], quedaDias: [] }, 0.40: { eventos: [], quedaDias: [] } };
const qualquer = [];
for (const t of universo) {
    const d = dados[t], n = d.close.length; if (n < 260) continue;
    const ind = M.v14_precomputarIndicadores(d, params), atr = M.calculateATR(d, 14);
    const ultimo = { 0.30: -1e9, 0.25: -1e9, 0.40: -1e9 };
    for (let i = 200; i < n - 1; i++) {
        let max = -Infinity; for (let j = Math.max(0, i - JANELA + 1); j <= i; j++) max = Math.max(max, d.high[j]);
        const queda = 1 - d.close[i] / max;
        let sai = null; const s = () => sai || (sai = saidaApp(d, atr, i));
        { const x = s(); if (x) qualquer.push(x.ret); }
        let sinal = null;
        for (const q of [0.25, 0.30, 0.40]) {
            if (queda < q) continue;
            const x = s(); if (!x) continue;
            porQueda[q].quedaDias.push({ t, i, ...x });
            if (sinal === null) { const sig = M.v14_analisarSinais(d, ind, i); const c = Object.keys(sig.buy || {}); sinal = OTIMISTA.buy.filter(k => c.includes(k)).length >= OTIMISTA.minVotes; }
            if (sinal && i - ultimo[q] >= SEM_REPETIR) {
                ultimo[q] = i; const a = fechIndice(d.dates[i]), b = fechIndice(x.sai);
                porQueda[q].eventos.push({ t, data: d.dates[i], ...x, h20: horizonte(d, i, 20), h40: horizonte(d, i, 40), h60: horizonte(d, i, 60), indice: a > 0 && b > 0 ? b / a - 1 : null });
            }
        }
    }
}

// ---------- resumo e critérios ----------
function resumo(ev) {
    const r = ev.map(x => x.ret), g = r.filter(v => v > 0), p = r.filter(v => v <= 0);
    return { eventos: ev.length, papeis: new Set(ev.map(x => x.t)).size, meses: new Set(ev.map(x => x.data.slice(0, 7))).size, de: ev.map(x => x.data).sort()[0], ate: ev.map(x => x.data).sort().pop(),
        media: pct(media(r)), mediana: pct(quantil(r, 0.5)), acerto: r2(g.length / (r.length || 1) * 100, 0), ganhoMedio: pct(media(g)), perdaMedia: pct(media(p)), melhor: pct(Math.max(...r)), pior: pct(Math.min(...r)),
        h20: pct(media(ev.map(x => x.h20).filter(v => v !== null))), h40: pct(media(ev.map(x => x.h40).filter(v => v !== null))), h60: pct(media(ev.map(x => x.h60).filter(v => v !== null))),
        indiceMesmasDatas: pct(media(ev.map(x => x.indice).filter(v => v !== null))) };
}
const ev = porQueda[0.30].eventos, R = { mercado: MERCADO, ultimoPregao: man.ultimoPregao, universo: universo.length, registro: 'docs/cenario-queda-reversao.md' };
R.cenario = resumo(ev);
const pool = porQueda[0.30].quedaDias.map(x => x.ret), rng = mulberry(2026), acaso = [];
for (let s = 0; s < SORTEIOS; s++) { let soma = 0; for (let k = 0; k < ev.length; k++) soma += pool[Math.floor(rng() * pool.length)]; acaso.push(soma / ev.length); }
R.acasoMesmaQueda = { diasNoPool: pool.length, p5: pct(quantil(acaso, 0.05)), p50: pct(quantil(acaso, 0.5)), p95: pct(quantil(acaso, 0.95)) };
R.qualquerDia = pct(media(qualquer));
R.variantes = { queda25: resumo(porQueda[0.25].eventos), queda40: resumo(porQueda[0.40].eventos) };
const c1 = R.cenario.media > R.acasoMesmaQueda.p95, c2 = R.cenario.media > 0 && (R.cenario.indiceMesmasDatas === null || R.cenario.media > R.cenario.indiceMesmasDatas), c3 = R.variantes.queda25.media >= 0 && R.variantes.queda40.media >= 0;
R.criterios = { acimaP95Acaso: c1, expectativaPositivaEAcimaDoIndice: c2, variantesNaoNegativas: c3 }; R.favoravel = c1 && c2 && c3;
R.porMes = Object.entries(ev.reduce((a, x) => (a[x.data.slice(0, 7)] = (a[x.data.slice(0, 7)] || 0) + 1, a), {})).sort((a, b) => b[1] - a[1]).slice(0, 5);
R.listaEventos = ev.map(x => ({ t: x.t, data: x.data, ret: pct(x.ret), sai: x.sai }));
fs.writeFileSync(arg('saida', `cenario_${MERCADO}.json`), JSON.stringify(R, null, 1));
const c = R.cenario, L = [`### Cenário queda ≥ 30% + Otimista · ${MERCADO.toUpperCase()} · ${R.universo} papéis · ${c.de} a ${c.ate}`, '',
    `Eventos ${c.eventos} (${c.papeis} papéis, ${c.meses} meses) · média ${c.media}% · mediana ${c.mediana}% · acerto ${c.acerto}% · ganho médio ${c.ganhoMedio}% / perda média ${c.perdaMedia}% · melhor ${c.melhor}% · pior ${c.pior}%`,
    `Horizontes fixos 20/40/60: ${c.h20}% / ${c.h40}% / ${c.h60}%`,
    `Acaso na mesma queda (${SORTEIOS} sorteios, ${pool.length} dias): p5 ${R.acasoMesmaQueda.p5}% · p50 ${R.acasoMesmaQueda.p50}% · p95 ${R.acasoMesmaQueda.p95}%`,
    `Índice nas mesmas datas ${c.indiceMesmasDatas}% · qualquer dia ${R.qualquerDia}% · variantes 25%/40%: ${R.variantes.queda25.media}% (${R.variantes.queda25.eventos}) / ${R.variantes.queda40.media}% (${R.variantes.queda40.eventos})`,
    `Meses com mais eventos: ${R.porMes.map(([m, k]) => `${m} (${k})`).join(', ')}`,
    `Critérios: acaso p95 **${c1 ? 'sim' : 'não'}** · expectativa e índice **${c2 ? 'sim' : 'não'}** · variantes **${c3 ? 'sim' : 'não'}** → **${R.favoravel ? 'FAVORÁVEL' : 'NÃO FAVORÁVEL'}**`, ''];
console.log(L.join('\n'));
if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, L.join('\n') + '\n');
