// Carrega o MOTOR do app (as funções de app/index.html, copiadas byte a byte em tempo de execução) dentro do Node,
// sem navegador e sem CDN. Nada da lógica quantitativa é reescrito aqui: se o app mudar, este módulo pega a versão nova.
// Uso: const M = require('./motor_node')('app/index.html'); M.runCoreBacktest(dados, rp) ...
const fs = require('fs');
const vm = require('vm');

const FUNCOES = ['getIndicatorParameters', 'calculateSMA', 'calculateEMA', 'calculateBB', 'calculateATR', 'calculateKeltnerChannels',
    'calculateVWAP', 'calculateADL', 'calculateOBV', 'findPivotPoints', 'detectDivergences', 'precomputeAllIndicators', 'analyzeAllSignals',
    'computeStrategyScore', 'computeHistoricalRegime', 'v14_calculateIFR', 'runCoreBacktest', 'perfilDoAtivo', 'regrasRelatorio',
    'estatTrades', 'ganhoEsperado', 'avaliarPapelRelatorio', 'suporteResistencia', 'universoRelatorio'];
const CONSTANTES = ['PIVOT_WINDOW', 'confluenceStrategies', 'strategyWeights'];

// Acha o fim de um bloco { ... } a partir de `ini` (posição do "{"), pulando strings, templates e comentários.
function fimDoBloco(src, ini) {
    let i = ini, prof = 0;
    const pularString = q => { i++; while (i < src.length && src[i] !== q) { if (src[i] === '\\') i++; i++; } };
    const pularTemplate = () => {
        i++;
        while (i < src.length && src[i] !== '`') {
            if (src[i] === '\\') { i += 2; continue; }
            if (src[i] === '$' && src[i + 1] === '{') { const f = fimDoBloco(src, i + 1); i = f + 1; continue; }
            i++;
        }
    };
    for (; i < src.length; i++) {
        const c = src[i];
        if (c === '"' || c === "'") pularString(c);
        else if (c === '`') pularTemplate();
        else if (c === '/' && src[i + 1] === '/') { while (i < src.length && src[i] !== '\n') i++; }
        else if (c === '/' && src[i + 1] === '*') { i = src.indexOf('*/', i + 2) + 1; }
        else if (c === '{') prof++;
        else if (c === '}') { prof--; if (prof === 0) return i; }
    }
    throw new Error('bloco sem fim');
}

function extrair(src) {
    const partes = [];
    for (const nome of FUNCOES) {
        const m = new RegExp(`\\n\\s*(async\\s+)?function ${nome}\\s*\\(`).exec(src);
        if (!m) throw new Error(`função ${nome} não encontrada no app`);
        const ini = m.index + 1, abre = src.indexOf('{', src.indexOf(')', ini));
        // a lista de parâmetros pode ter "=" com objetos; acha o "{" do corpo depois do ")" que fecha a assinatura
        let p = src.indexOf('(', ini), prof = 0, j = p;
        for (; j < src.length; j++) { if (src[j] === '(') prof++; else if (src[j] === ')') { prof--; if (prof === 0) break; } }
        const corpo = src.indexOf('{', j);
        partes.push(src.slice(ini, fimDoBloco(src, corpo) + 1));
        void abre;
    }
    for (const nome of CONSTANTES) {
        const m = new RegExp(`\\n\\s*const ${nome}\\s*=\\s*`).exec(src);
        if (!m) throw new Error(`constante ${nome} não encontrada no app`);
        const ini = m.index + 1, valor = m.index + m[0].length;
        const fim = src[valor] === '{' ? fimDoBloco(src, valor) + 1 : src.indexOf(';', valor);
        partes.push(src.slice(ini, fim).replace(/^\s*const /, 'var ') + ';');
    }
    // As constantes do Relatório também vêm do app (para não divergir)
    const rel = /const FRACAO_ESCOLHA = [^;]+;/.exec(src); if (!rel) throw new Error('constantes do Relatório não encontradas');
    partes.push(rel[0].replace(/^const /, 'var '));
    return partes.join('\n\n');
}

module.exports = function carregar(caminhoApp, mercado = 'us') {
    const src = fs.readFileSync(caminhoApp, 'utf8');
    const codigo = extrair(src);
    const ctx = { console, Math, Infinity, isFinite, Object, Array, JSON, Set,
        allData: {}, regimeByDateMap: {}, historicalRegimeData: [], poolRelatorio: null,
        // única dependência de tela usada pelo motor: perfilDoAtivo/regrasRelatorio não leem DOM; calibração padrão do app
        paramsCalibrados: () => ({ alvo: 3, dias: 10 }),
        MERCADO: { adtvPadrao: +((new RegExp(`${mercado}: \\{[^}]*adtvPadrao: (\\d+)`).exec(src) || [])[1] || 0) } };
    vm.createContext(ctx);
    vm.runInContext(codigo, ctx, { filename: 'motor_extraido_do_app.js' });
    // Variante PARA OS ATAQUES (o app não usa): o mesmo runCoreBacktest, com três ganchos desligados por padrão:
    //  __aleatoria: troca o sinal do Score por um sorteio com probabilidade __prob (mesmo stop, tamanho, custo e filtro de regime);
    //  __atraso: executa a entrada N pregões depois do previsto (na abertura);
    //  __desliz: deslizamento extra na abertura da entrada e na saída por stop com gap, em frações do ATR do sinal.
    // Cada troca é conferida: se o texto do app mudar, falha em vez de medir outra coisa.
    let v = ctx.runCoreBacktest.toString();
    const trocar = (de, para) => { if (!v.includes(de)) throw new Error('gancho não encontrado: ' + de.slice(0, 60)); v = v.replace(de, para); };
    trocar('function runCoreBacktest(', 'function runCoreBacktestVar(');
    trocar('let pendingEntry = false,', 'let __espera = 0; let pendingEntry = false,');
    trocar('if (pendingEntry && position === \'out\') {', 'if (pendingEntry && position === \'out\' && (__espera-- <= 0)) {');
    trocar('entryPrice = dataSubset.open[i] * (1 + costFraction);', 'entryPrice = (dataSubset.open[i] + (riskParams.__desliz || 0) * pendingATR) * (1 + costFraction);');
    trocar('if (totalScore >= riskParams.minScore && totalScore > 0 && indicators.ATR[i]) {',
        'if ((riskParams.__aleatoria ? riskParams.__rng() < riskParams.__prob : (totalScore >= riskParams.minScore && totalScore > 0)) && indicators.ATR[i]) { __espera = riskParams.__atraso || 0;');
    trocar('if (ema200 && dataSubset.close[i] > ema200 && ifr2[i] !== null && ifr2[i] < 10 && indicators.ATR[i]) { pendingEntry = true;',
        'if ((riskParams.__aleatoria ? (riskParams.__rng() < riskParams.__prob) : (ema200 && dataSubset.close[i] > ema200 && ifr2[i] !== null && ifr2[i] < 10)) && indicators.ATR[i]) { __espera = riskParams.__atraso || 0; pendingEntry = true;');
    trocar('if (dataSubset.low[i] <= stopPrice) { exitPrice = Math.min(stopPrice, dataSubset.open[i]);',
        'if (dataSubset.low[i] <= stopPrice) { exitPrice = Math.min(stopPrice, dataSubset.open[i]) - (dataSubset.open[i] < stopPrice ? (riskParams.__desliz || 0) * pendingATR : 0);');
    vm.runInContext(v, ctx, { filename: 'motor_variante_ataques.js' });
    // Parâmetros padrão do app (os valores dos campos do formulário em index.html)
    const campo = id => { const m = new RegExp(`id="${id}"[^>]*value="([^"]*)"`).exec(src); return m ? m[1] : null; };
    const pesos = {}; for (const k of Object.keys(ctx.strategyWeights)) pesos[k] = ctx.strategyWeights[k].weight;
    ctx.RP_PADRAO = {
        capital: +campo('param-capital') || 10000, riskTrade: +campo('param-risk-trade') || 1, atrMult: +campo('param-atr-multiple') || 2.5,
        stopLossPct: +campo('param-stop-loss') || 8, minScore: +campo('param-min-score') || 0, costPct: +campo('param-costs') || 0,
        targetProfitFactor: +campo('param-rr') || 0, regimeFilter: /id="param-regime-filter"[^>]*checked/.test(src),
        alvoAtr: 0, saidaDias: 0, precoMin: 0, volMax: 0, modoEntrada: 'score', weights: pesos
    };
    ctx.CODIGO_EXTRAIDO = codigo;
    return ctx;
};
module.exports.fimDoBloco = fimDoBloco;
