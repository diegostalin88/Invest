// Motor da carteira (07/11/2026). Sem tela: recebe os dados de mercado (carteira.json) e os lançamentos do
// usuário e devolve patrimônio, cotas, rentabilidade nominal e real, posições, rebalanceamento e imposto.
//
// Rentabilidade pelo MÉTODO DE COTAS (o dos fundos de investimento): a carteira começa valendo 1 por cota.
// Todo dinheiro que entra (aporte) compra cotas pelo valor do dia; todo dinheiro que sai (retirada) vende cotas.
// Só a valorização dos ativos muda o valor da cota. Assim, aportes, vendas e recompras não inflam o resultado.
// Venda dentro da carteira não é saída: o dinheiro fica no caixa (faz parte do patrimônio) até uma retirada.
(function (raiz) {
    'use strict';
    const M = {};
    const EPS = 0.005;
    M.TIPOS = {
        aporte: 'Aporte', retirada: 'Retirada', compra: 'Compra', venda: 'Venda', provento: 'Provento',
        taxa: 'Taxa/custódia', rf_aplicar: 'Aplicação em renda fixa', rf_resgatar: 'Resgate de renda fixa',
        rf_saldo: 'Saldo informado da renda fixa', preco: 'Preço atual (manual)', posicao_inicial: 'Posição inicial',
        bonificacao: 'Ações recebidas (bonificação, desdobramento, fusão)',
    };
    M.TIPO_IR = { acao: 'Ação', etf: 'ETF', bdr: 'BDR', fii: 'FII', cripto: 'Cripto', rf: 'Renda fixa' };
    // Contas: BR (reais, B3) e EUA (dólar, corretora lá fora). Na conta EUA, preços e valores são lançados em
    // dólar e convertidos para reais pela PTAX do dia do lançamento; o saldo em dólar é valorizado pela PTAX de cada dia.
    M.CONTAS = { BR: 'Brasil (R$)', EUA: 'EUA (US$)' };
    const ETFS = new Set(['BOVA11', 'BOVV11', 'BRAX11', 'IVVB11', 'SMAL11', 'PIBB11', 'ECOO11', 'XBOV11', 'NASD11', 'SPXI11', 'WRLD11', 'ACWI11',
        'DIVO11', 'HASH11', 'QBTC11', 'BITH11', 'ETHE11', 'GOLD11', 'B5P211', 'IMAB11', 'FIXA11', 'LFTS11', 'DEBB11', 'NTNS11']);
    const CRIPTO = new Set(['BTC', 'ETH', 'SOL', 'USDT', 'XRP', 'ADA', 'BNB', 'LTC']);
    // BDR (código com final 32, 33, 34, 35 ou 39): 15% sobre o lucro, sem a isenção de R$ 20 mil das ações.
    M.ehBDR = (cod) => /^[A-Z0-9]{4}3[2-59]$/.test(cod);
    M.tipoIRPadrao = (cod) => CRIPTO.has(cod) ? 'cripto' : ETFS.has(cod) ? 'etf' : /11$/.test(cod) ? 'fii' : M.ehBDR(cod) ? 'bdr' : 'acao';

    // ---------- datas ----------
    const dia = (s) => String(s).slice(0, 10);
    const addDias = (s, n) => { const d = new Date(s + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
    const diasEntre = (a, b) => Math.round((Date.parse(b + 'T00:00:00Z') - Date.parse(a + 'T00:00:00Z')) / 864e5);
    const diasNoMes = (ano, mes) => new Date(Date.UTC(ano, mes, 0)).getUTCDate();
    M.ultimoDiaUtil = (ano, mes) => { const d = new Date(Date.UTC(ano, mes, 0)); while (d.getUTCDay() === 0 || d.getUTCDay() === 6) d.setUTCDate(d.getUTCDate() - 1); return d.toISOString().slice(0, 10); };
    M.addDias = addDias; M.diasEntre = diasEntre;

    // ---------- séries de mercado ----------
    // Preço "de tela" na data: o Yahoo corrige desdobramentos para trás; desfazemos isso para que a quantidade
    // que o usuário tinha antes do desdobramento seja valorizada pelo preço daquela época.
    function prepararAtivos(dados) {
        const out = {};
        for (const [cod, a] of Object.entries((dados && dados.ativos) || {})) {
            const desd = (a.desdobramentos || []).slice().sort((x, y) => x[0] < y[0] ? -1 : 1);
            const fech = a.fech.map((c, i) => { let f = 1; for (const [d, r] of desd) if (a.datas[i] < d) f *= r; return c * f; });
            const fechUSD = a.fechUSD ? a.fechUSD.map((c, i) => { let f = 1; for (const [d, r] of desd) if (a.datas[i] < d) f *= r; return c * f; }) : null;
            out[cod] = { nome: a.nome, classe: a.classe, datas: a.datas, fech, desd, moeda: a.moeda || 'BRL', fechUSD, alavancado: a.alavancado || null, tipo: a.tipo || '', setor: a.setor || null, apoio: !!a.apoio, fund: a.fund || null };
        }
        return out;
    }
    // procura o último índice com datas[i] <= d (busca binária)
    function ateData(datas, d) { let lo = 0, hi = datas.length - 1, r = -1; while (lo <= hi) { const m = (lo + hi) >> 1; if (datas[m] <= d) { r = m; lo = m + 1; } else hi = m - 1; } return r; }
    M.ateData = ateData;
    // preço de tela (sem a correção de desdobramentos posteriores) no último pregão até a data, ou null
    M.precoTela = function (dados, cod, d) {
        const a = dados && dados.ativos && dados.ativos[cod]; if (!a || !a.datas.length || a.datas[0] > d) return null;
        const i = ateData(a.datas, d); let f = 1; for (const [dd, r] of (a.desdobramentos || [])) if (a.datas[i] < dd) f *= r;
        return a.fech[i] * f;
    };
    function cdiAcum(dados, d) { const c = dados && dados.cdi; if (!c || !c.datas.length) return 1; const i = ateData(c.datas, d); return i < 0 ? 1 : c.acum[i]; }
    M.cdiAcum = cdiAcum;
    // PTAX (reais por dólar) na data: a do dia ou a última anterior (fim de semana e feriado).
    function criarPTAX(dados) {
        const s = dados && dados.ptaxSerie, ult = dados && dados.ptax && dados.ptax.valor;
        return (d) => { if (s && s.datas && s.datas.length) { const i = ateData(s.datas, d); return i >= 0 ? s.valor[i] : s.valor[0]; } return ult || null; };
    }
    M.criarPTAX = criarPTAX;

    // Índice do IPCA por dia: a variação do mês é distribuída pelos dias do mês (juros compostos). Meses ainda
    // não divulgados repetem a última variação conhecida e ficam marcados como estimativa.
    function criarIPCA(dados) {
        const ip = (dados && dados.ipca) || { meses: [], var: [] };
        const mapa = new Map(ip.meses.map((m, i) => [m, ip.var[i]]));
        const ultimoMes = ip.meses[ip.meses.length - 1] || null, ultimaVar = ip.var[ip.var.length - 1] || 0;
        const cache = new Map();
        const primeiro = ip.meses[0] || '2015-01';
        function fimDoMes(m) {   // índice no último dia do mês m (base 1 no início do primeiro mês da série)
            if (cache.has(m)) return cache.get(m);
            let v = 1, [a, mm] = primeiro.split('-').map(Number);
            const [af, mf] = m.split('-').map(Number);
            if (af * 12 + mf < a * 12 + mm) { cache.set(m, 1); return 1; }
            while (a * 12 + mm <= af * 12 + mf) { const k = `${a}-${String(mm).padStart(2, '0')}`; v *= 1 + (mapa.has(k) ? mapa.get(k) : ultimaVar) / 100; mm++; if (mm > 12) { mm = 1; a++; } }
            cache.set(m, v); return v;
        }
        function indice(d) {
            const [a, m, dd] = d.split('-').map(Number);
            const mesAnt = m === 1 ? `${a - 1}-12` : `${a}-${String(m - 1).padStart(2, '0')}`;
            const k = `${a}-${String(m).padStart(2, '0')}`;
            const base = fimDoMes(mesAnt), v = mapa.has(k) ? mapa.get(k) : ultimaVar;
            return base * Math.pow(1 + v / 100, dd / diasNoMes(a, m));
        }
        return { indice, ultimoMes, estimado: (d) => !!ultimoMes && d.slice(0, 7) > ultimoMes };
    }
    M.criarIPCA = criarIPCA;

    // ---------- normalização dos lançamentos ----------
    function normalizar(lancs) {
        return (lancs || []).map((l, k) => ({ ...l, data: dia(l.data), ordem: k, ativo: l.ativo ? String(l.ativo).trim().toUpperCase() : '',
            conta: l.conta === 'EUA' && !String(l.tipo).startsWith('rf_') ? 'EUA' : 'BR', irRetido: +l.irRetido || 0,
            qtd: +l.qtd || 0, preco: +l.preco || 0, valor: +l.valor || 0, custos: +l.custos || 0, pctCDI: l.pctCDI === undefined || l.pctCDI === '' ? 100 : +l.pctCDI }))
            .filter(l => /^\d{4}-\d{2}-\d{2}$/.test(l.data) && M.TIPOS[l.tipo])
            .sort((a, b) => a.data < b.data ? -1 : a.data > b.data ? 1 : a.ordem - b.ordem);
    }
    M.normalizar = normalizar;

    // ---------- cálculo principal ----------
    // opcoes: { aporteAutomatico: true, tiposIR: {COD: 'etf'}, classes: {COD: 'acoes_eua'}, hoje: 'AAAA-MM-DD' }
    M.calcular = function (dados, lancamentos, opcoes = {}) {
        const L = normalizar(lancamentos);
        const auto = opcoes.aporteAutomatico !== false;
        const tiposIR = opcoes.tiposIR || {};
        const tipoIR = (cod) => tiposIR[cod] || M.tipoIRPadrao(cod);
        const ativos = prepararAtivos(dados);
        const ipca = criarIPCA(dados);
        const ptaxDe = criarPTAX(dados);
        const classesUsuario = opcoes.classes || {};
        if (!L.length) return { vazio: true, ativos };
        const ultimaData = [L[L.length - 1].data, ...Object.values(ativos).map(a => a.datas[a.datas.length - 1]),
            dados && dados.cdi && dados.cdi.datas.length ? dados.cdi.datas[dados.cdi.datas.length - 1] : L[0].data].sort().pop();
        const fim = opcoes.hoje && opcoes.hoje > ultimaData ? ultimaData : (opcoes.hoje || ultimaData);
        const ini = L[0].data;

        const pos = {};           // cod → {qtd, custo, custoUSD, conta} (custo total pelo preço médio; em reais)
        const precoManual = {};   // cod → [ [data, preço] ] (na moeda da conta do papel)
        const rf = {};            // nome → {saldo, pct, aplicado}
        const vendas = [];        // para o imposto
        const proventos = [];
        const avisos = [];
        let caixa = 0, caixaUSD = 0, cotas = 0, cota = 1, aportado = 0, implicitos = 0, implicitosUSD = 0, semCompra = 0, semCompraUSD = 0, fluxoEUA = 0, semCompraAtivos = new Set(), semCompraQtd = {}, aportesCorrigidos = 0, aportadoEUA = 0;
        const serie = { datas: [], patrimonio: [], aportado: [], cota: [], caixa: [], ipca: [], cdi: [], eua: [] };
        let j = 0, semPtax = false;
        const px = (d) => { const v = ptaxDe(d); if (v) return v; semPtax = true; return 1; };
        const contaDe = (cod) => (pos[cod] && pos[cod].conta) || 'BR';
        // preço em reais na data (papel da conta EUA sem cotação: preço manual em dólar × PTAX do dia)
        const precoDe = (cod, d) => {
            const a = ativos[cod];
            if (a) { const i = ateData(a.datas, d); if (i >= 0) return a.fech[i]; }
            const fx = contaDe(cod) === 'EUA' ? px(d) : 1;
            const pm = precoManual[cod]; if (pm && pm.length) { let p = null; for (const [dd, v] of pm) if (dd <= d) p = v; if (p !== null) return p * fx; return pm[0][1] * fx; }
            const ps = pos[cod]; if (!ps || !(ps.qtd > 0)) return 0;
            return ps.conta === 'EUA' && ps.custoUSD ? ps.custoUSD / ps.qtd * fx : ps.custo / ps.qtd;
        };
        const precoUSDDe = (cod, d) => {
            const a = ativos[cod];
            if (a && a.fechUSD) { const i = ateData(a.datas, d); if (i >= 0) return a.fechUSD[i]; }
            return precoDe(cod, d) / px(d);
        };
        const avisosConta = new Set(), semMercado = new Set();
        // fechamento de mercado na data (na moeda do papel), ou null se não há cotação até ela
        const precoMercado = (cod, d, usd = false) => { const a = ativos[cod]; if (!a || a.datas[0] > d) return null; const i = ateData(a.datas, d); return (usd && a.fechUSD ? a.fechUSD : a.fech)[i]; };
        const ipcaFim = ipca.indice(fim);
        for (let d = ini, ant = null; d <= fim; ant = d, d = addDias(d, 1)) {
            // desdobramentos e grupamentos
            for (const [cod, a] of Object.entries(ativos)) for (const [dd, r] of a.desd) if (dd === d && pos[cod] && pos[cod].qtd > 0) pos[cod].qtd *= r;
            // renda fixa rende o CDI do dia × percentual contratado
            if (ant) { const f = cdiAcum(dados, d) / cdiAcum(dados, ant) - 1; for (const c of Object.values(rf)) c.saldo *= 1 + f * c.pct / 100; }
            let fluxo = 0;
            for (; j < L.length && L[j].data === d; j++) {
                const l = L[j];
                const cod = l.ativo;
                if (l.conta === 'EUA') { fluxoEUA = 0; fluxo += lancEUA(l, d) + fluxoEUA; continue; }
                if (cod && pos[cod] && pos[cod].conta === 'EUA' && ['compra', 'venda', 'provento', 'preco'].includes(l.tipo) && !avisosConta.has(cod)) { avisosConta.add(cod); avisos.push(`${cod} tem lançamentos nas duas contas (Brasil e EUA). Lance todos na mesma conta.`); }
                if (cod && ativos[cod] && ativos[cod].moeda === 'USD' && ['compra', 'venda'].includes(l.tipo) && !avisosConta.has(cod)) { avisosConta.add(cod); avisos.push(`${cod} é cotado em dólar: lance as operações dele na conta EUA, com preços em US$.`); }
                if (l.tipo === 'aporte') { caixa += l.valor; fluxo += l.valor; }
                else if (l.tipo === 'retirada') { caixa -= l.valor; fluxo -= l.valor; }
                else if (l.tipo === 'compra') {
                    const p = pos[cod] || (pos[cod] = { qtd: 0, custo: 0, conta: 'BR' });
                    const v = l.qtd * l.preco + l.custos; p.qtd += l.qtd; p.custo += v; caixa -= v;
                    (precoManual[cod] || (precoManual[cod] = [])).push([d, l.preco]);
                } else if (l.tipo === 'venda') {
                    const p = pos[cod] || (pos[cod] = { qtd: 0, custo: 0, conta: 'BR' });
                    if (l.qtd > p.qtd + 1e-9) avisos.push(`${fmtD(d)}: venda de ${l.qtd} ${cod}, mas a carteira só tinha ${+p.qtd.toFixed(8)}. Falta lançar uma compra antes.`);
                    const q = Math.min(l.qtd, p.qtd), pm = p.qtd > 0 ? p.custo / p.qtd : 0;
                    const bruto = l.qtd * l.preco, liquido = bruto - l.custos;
                    vendas.push({ data: d, ativo: cod, conta: 'BR', tipo: tipoIR(cod), qtd: l.qtd, preco: l.preco, bruto, custos: l.custos, pm, lucro: liquido - q * pm });
                    p.custo -= q * pm; p.qtd -= q; if (p.qtd < 1e-9) { p.qtd = 0; p.custo = 0; }
                    caixa += liquido;
                    // venda maior que a posição: a parte sem compra lançada veio de fora da carteira; conta como aporte
                    // (pelo valor da venda), senão o dinheiro dela apareceria como lucro e inflaria a rentabilidade
                    if (l.qtd > q + 1e-9) { const x = liquido * (l.qtd - q) / l.qtd; fluxo += x; semCompra += x; semCompraAtivos.add(cod); const f = semCompraQtd[cod] || (semCompraQtd[cod] = { qtd: 0, primeira: d, conta: 'BR' }); f.qtd += l.qtd - q; }
                    (precoManual[cod] || (precoManual[cod] = [])).push([d, l.preco]);
                }
                else if (l.tipo === 'posicao_inicial') {
                    // papel que você já tinha: o preço médio vale para o imposto; para a rentabilidade, entra como aporte
                    // pelo preço de mercado do dia (sem cotação, pelo preço médio), para não criar lucro que não houve
                    const p = pos[cod] || (pos[cod] = { qtd: 0, custo: 0, conta: 'BR' });
                    p.qtd += l.qtd; p.custo += l.qtd * l.preco;
                    const pm = precoMercado(cod, d); fluxo += l.qtd * (pm !== null ? pm : l.preco); if (pm === null) semMercado.add(cod);
                    if (pm === null) (precoManual[cod] || (precoManual[cod] = [])).push([d, l.preco]);
                }
                else if (l.tipo === 'bonificacao') {
                    // ações que chegaram sem pagar (bonificação, desdobramento não visto nas cotações, troca em fusão):
                    // somam à quantidade com o custo informado pela empresa (ou zero); não mexem no caixa nem nas cotas
                    const p = pos[cod] || (pos[cod] = { qtd: 0, custo: 0, conta: 'BR' });
                    p.qtd += l.qtd; p.custo += l.qtd * l.preco;
                }
                else if (l.tipo === 'provento') { caixa += l.valor; proventos.push({ data: d, ativo: cod, conta: 'BR', valor: l.valor, especie: l.especie || 'dividendo' }); }
                else if (l.tipo === 'taxa') caixa -= l.valor;
                else if (l.tipo === 'rf_aplicar') { const c = rf[cod || 'Renda fixa'] || (rf[cod || 'Renda fixa'] = { saldo: 0, pct: l.pctCDI, aplicado: 0 }); c.saldo += l.valor; c.aplicado += l.valor; c.pct = l.pctCDI; caixa -= l.valor; }
                else if (l.tipo === 'rf_resgatar') { const c = rf[cod || 'Renda fixa']; if (!c) { avisos.push(`${fmtD(d)}: resgate de "${cod || 'Renda fixa'}" sem aplicação antes.`); continue; } const v = Math.min(l.valor, c.saldo); const prop = c.saldo > 0 ? v / c.saldo : 0; c.aplicado *= 1 - prop; c.saldo -= v; caixa += l.valor; }
                else if (l.tipo === 'rf_saldo') { const c = rf[cod || 'Renda fixa'] || (rf[cod || 'Renda fixa'] = { saldo: 0, pct: 100, aplicado: 0 }); c.saldo = l.valor; }
                else if (l.tipo === 'preco') (precoManual[cod] || (precoManual[cod] = [])).push([d, l.preco]);
            }
            // compra sem aporte lançado: o dinheiro veio de fora, então conta como aporte do dia
            if (caixa < -EPS && auto) { fluxo += -caixa; implicitos += -caixa; caixa = 0; }
            if (caixaUSD < -EPS && auto) { const v = -caixaUSD * px(d); fluxo += v; implicitosUSD += -caixaUSD; aportadoEUA += v; caixaUSD = 0; }
            let P = caixa + caixaUSD * px(d), PE = caixaUSD * px(d);
            for (const [cod, p] of Object.entries(pos)) if (p.qtd > 0 && p.conta === 'EUA') PE += p.qtd * precoDe(cod, d);
            for (const [cod, p] of Object.entries(pos)) if (p.qtd > 0) P += p.qtd * precoDe(cod, d);
            for (const c of Object.values(rf)) P += c.saldo;
            aportado += fluxo;
            const ix = ipca.indice(d);
            aportesCorrigidos += fluxo * ipcaFim / ix;
            if (cotas <= 1e-12) { if (P > EPS) cotas = P / cota; }
            else {
                const base = P - fluxo;
                if (base > EPS) { cota = base / cotas; cotas += fluxo / cota; }
                else { cotas = P > EPS ? P / cota : 0; }
            }
            if (P <= EPS) cotas = 0;
            serie.datas.push(d); serie.patrimonio.push(P); serie.aportado.push(aportado); serie.cota.push(cota);
            serie.caixa.push(caixa); serie.ipca.push(ix); serie.cdi.push(cdiAcum(dados, d)); serie.eua.push(PE);
        }
        // lançamento da conta EUA: valores em dólar; devolve o fluxo do dia em reais (aporte/retirada × PTAX)
        function lancEUA(l, d) {
            const cod = l.ativo, fx = px(d);
            if (cod && pos[cod] && pos[cod].conta !== 'EUA' && pos[cod].qtd > 0 && !avisosConta.has(cod)) { avisosConta.add(cod); avisos.push(`${cod} tem lançamentos nas duas contas (Brasil e EUA). Lance todos na mesma conta.`); }
            if (l.tipo === 'aporte') { caixaUSD += l.valor; aportadoEUA += l.valor * fx; return l.valor * fx; }
            if (l.tipo === 'retirada') { caixaUSD -= l.valor; aportadoEUA -= l.valor * fx; return -l.valor * fx; }
            if (l.tipo === 'compra') {
                const p = pos[cod] || (pos[cod] = { qtd: 0, custo: 0, custoUSD: 0, conta: 'EUA' });
                p.conta = 'EUA'; p.custoUSD = p.custoUSD || 0;
                const v = l.qtd * l.preco + l.custos; p.qtd += l.qtd; p.custoUSD += v; p.custo += v * fx; caixaUSD -= v;
                (precoManual[cod] || (precoManual[cod] = [])).push([d, l.preco]);
            } else if (l.tipo === 'venda') {
                const p = pos[cod] || (pos[cod] = { qtd: 0, custo: 0, custoUSD: 0, conta: 'EUA' });
                if (l.qtd > p.qtd + 1e-9) avisos.push(`${fmtD(d)}: venda de ${l.qtd} ${cod}, mas a carteira só tinha ${+p.qtd.toFixed(8)}. Falta lançar uma compra antes.`);
                const q = Math.min(l.qtd, p.qtd), pm = p.qtd > 0 ? p.custo / p.qtd : 0, pmUSD = p.qtd > 0 ? (p.custoUSD || 0) / p.qtd : 0;
                const brutoUSD = l.qtd * l.preco, liquidoUSD = brutoUSD - l.custos;
                // ganho em reais: venda pela PTAX do dia da venda − custo pela PTAX de cada compra (Lei 14.754/2023)
                vendas.push({ data: d, ativo: cod, conta: 'EUA', tipo: 'exterior', qtd: l.qtd, preco: l.preco, precoUSD: l.preco, ptax: fx, bruto: brutoUSD * fx, brutoUSD, custos: l.custos * fx,
                    pm, pmUSD, lucro: liquidoUSD * fx - q * pm, lucroUSD: liquidoUSD - q * pmUSD });
                p.custo -= q * pm; p.custoUSD -= q * pmUSD; p.qtd -= q; if (p.qtd < 1e-9) { p.qtd = 0; p.custo = 0; p.custoUSD = 0; }
                caixaUSD += liquidoUSD;
                if (l.qtd > q + 1e-9) { const x = liquidoUSD * (l.qtd - q) / l.qtd; semCompraUSD += x; semCompraAtivos.add(cod); const f = semCompraQtd[cod] || (semCompraQtd[cod] = { qtd: 0, primeira: d, conta: 'EUA' }); f.qtd += l.qtd - q; aportadoEUA += x * fx; fluxoEUA += x * fx; }
                (precoManual[cod] || (precoManual[cod] = [])).push([d, l.preco]);
            } else if (l.tipo === 'posicao_inicial') {
                const p = pos[cod] || (pos[cod] = { qtd: 0, custo: 0, custoUSD: 0, conta: 'EUA' });
                p.conta = 'EUA'; p.custoUSD = (p.custoUSD || 0) + l.qtd * l.preco; p.custo += l.qtd * l.preco * fx; p.qtd += l.qtd;
                const pmU = precoMercado(cod, d, true); if (pmU === null) { semMercado.add(cod); (precoManual[cod] || (precoManual[cod] = [])).push([d, l.preco]); }
                const v = l.qtd * (pmU !== null ? pmU : l.preco) * fx; aportadoEUA += v; return v;
            } else if (l.tipo === 'bonificacao') {
                const p = pos[cod] || (pos[cod] = { qtd: 0, custo: 0, custoUSD: 0, conta: 'EUA' });
                p.conta = 'EUA'; p.custoUSD = (p.custoUSD || 0) + l.qtd * l.preco; p.custo += l.qtd * l.preco * fx; p.qtd += l.qtd;
            } else if (l.tipo === 'provento') { caixaUSD += l.valor; proventos.push({ data: d, ativo: cod, conta: 'EUA', valor: l.valor * fx, valorUSD: l.valor, irRetidoUSD: l.irRetido, irRetido: l.irRetido * fx, ptax: fx, especie: l.especie || 'dividendo' }); }
            else if (l.tipo === 'taxa') caixaUSD -= l.valor;
            else if (l.tipo === 'preco') (precoManual[cod] || (precoManual[cod] = [])).push([d, l.preco]);
            return 0;
        }
        // posições de hoje
        const n = serie.datas.length - 1, P = serie.patrimonio[n];
        const posicoes = [];
        for (const [cod, p] of Object.entries(pos)) if (p.qtd > 1e-9) {
            const preco = precoDe(cod, fim), valor = p.qtd * preco;
            const temDados = !!ativos[cod];
            const ultimaDataPreco = temDados ? ativos[cod].datas[ateData(ativos[cod].datas, fim)] : ((precoManual[cod] || []).filter(x => x[0] <= fim).pop() || [null])[0];
            const eua = p.conta === 'EUA', fxFim = eua ? px(fim) : 1;
            const extra = eua ? { conta: 'EUA', moeda: 'USD', precoUSD: precoUSDDe(cod, fim), pmUSD: (p.custoUSD || 0) / p.qtd, custoUSD: p.custoUSD || 0, valorUSD: valor / fxFim,
                resultadoUSD: valor / fxFim - (p.custoUSD || 0), alavancado: temDados ? ativos[cod].alavancado : null } : { conta: 'BR', moeda: 'BRL' };
            posicoes.push({ ativo: cod, nome: temDados ? ativos[cod].nome : cod, classe: classeDe(cod, ativos, tipoIR, classesUsuario, p.conta), tipoIR: eua ? 'exterior' : tipoIR(cod), qtd: p.qtd, pm: p.custo / p.qtd, custo: p.custo, preco, valor,
                resultado: valor - p.custo, resultadoPct: p.custo > 0 ? valor / p.custo - 1 : null, peso: P > 0 ? valor / P : 0, temDados, dataPreco: ultimaDataPreco, ...extra });
        }
        for (const [nome, c] of Object.entries(rf)) if (c.saldo > EPS) posicoes.push({ ativo: nome, nome, classe: 'rf', tipoIR: 'rf', qtd: null, pm: null, custo: c.aplicado, preco: null, valor: c.saldo, resultado: c.saldo - c.aplicado, resultadoPct: c.aplicado > 0 ? c.saldo / c.aplicado - 1 : null, peso: P > 0 ? c.saldo / P : 0, pctCDI: c.pct, temDados: true });
        if (caixa > EPS) posicoes.push({ ativo: 'Caixa', nome: 'Caixa na corretora', classe: 'caixa', conta: 'BR', moeda: 'BRL', tipoIR: null, valor: caixa, peso: P > 0 ? caixa / P : 0, custo: caixa, resultado: 0 });
        if (caixaUSD > EPS) { const v = caixaUSD * px(fim); posicoes.push({ ativo: 'Caixa EUA', nome: 'Caixa em dólar (conta EUA)', classe: 'caixa', conta: 'EUA', moeda: 'USD', tipoIR: null, valor: v, valorUSD: caixaUSD, peso: P > 0 ? v / P : 0, custo: v, resultado: 0 }); }
        posicoes.sort((a, b) => b.valor - a.valor);
        if (implicitos > EPS) avisos.push(`Compras de ${fmtR(implicitos)} não tinham aporte lançado antes; contei esse valor como aporte nas datas das compras.`);
        if (implicitosUSD > EPS) avisos.push(`Na conta EUA, compras de US$ ${implicitosUSD.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} não tinham aporte (remessa) lançado antes; contei como aporte, convertido pela PTAX do dia.`);
        if (semCompra > EPS || semCompraUSD > EPS) avisos.unshift(`Vendas sem compra lançada antes (${[...semCompraAtivos].join(', ')}): ${semCompra > EPS ? fmtR(semCompra) : ''}${semCompra > EPS && semCompraUSD > EPS ? ' e ' : ''}${semCompraUSD > EPS ? 'US$ ' + semCompraUSD.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : ''}. Para não inflar a rentabilidade, contei esse dinheiro como aporte. Para corrigir, lance em Lançar → Posição inicial a quantidade que você já tinha e o preço médio da declaração de IR, com data antes da primeira venda.`);
        if (semMercado.size) avisos.push(`Posição inicial sem cotação de mercado na data (${[...semMercado].join(', ')}): usei o preço médio informado. Peça no chat para incluir o papel na coleta de preços.`);
        if (semPtax) avisos.push('Sem a cotação do dólar (PTAX) nos dados de mercado: os valores da conta EUA não puderam ser convertidos para reais.');
        const temEUA = L.some(l => l.conta === 'EUA');
        const contas = temEUA ? { BR: { valor: P - serie.eua[n] }, EUA: { valor: serie.eua[n], valorUSD: serie.eua[n] / px(fim), caixaUSD, aportado: aportadoEUA }, ptax: px(fim), ptaxData: (dados && dados.ptaxSerie && dados.ptaxSerie.datas.length) ? dados.ptaxSerie.datas[ateData(dados.ptaxSerie.datas, fim)] : (dados && dados.ptax && dados.ptax.data) } : null;
        return { vazio: false, ini, fim, serie, posicoes, vendas, proventos, avisos, semCompra: { valor: semCompra, valorUSD: semCompraUSD, ativos: [...semCompraAtivos], faltam: semCompraQtd }, patrimonio: P, aportado, aportesCorrigidos, caixa, caixaUSD, contas, cotas, cota,
            ipcaEstimado: ipca.estimado(fim), ipcaUltimoMes: ipca.ultimoMes, ativos, dados, ipca, metricas: metricas(serie, dados, ativos, ipca) };
    };
    function classeDe(cod, ativos, tipoIR, classesUsuario = {}, conta = 'BR') {
        if (classesUsuario[cod]) return classesUsuario[cod];
        if (ativos[cod] && ativos[cod].classe) return ativos[cod].classe;
        if (conta === 'EUA') return 'exterior';
        const t = tipoIR(cod); return t === 'cripto' ? 'cripto' : 'outros';
    }
    const fmtD = (d) => d.split('-').reverse().join('/');
    const fmtR = (v) => 'R$ ' + v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    // ---------- rentabilidade em janelas ----------
    function idxAte(serie, d) { return ateData(serie.datas, d); }
    function janela(serie, desde) {
        // devolve índice do dia-base (fechamento anterior ao início da janela)
        const i = idxAte(serie, addDias(desde, -1));
        return i;
    }
    function metricas(serie, dados, ativos, ipca) {
        const n = serie.datas.length - 1; if (n < 0) return null;
        const fim = serie.datas[n];
        // primeiro dia com patrimônio
        let i0 = serie.patrimonio.findIndex(p => p > EPS); if (i0 < 0) i0 = 0;
        const r = (a, b) => serie.cota[b] / serie.cota[a] - 1;
        const inf = (a, b) => serie.ipca[b] / serie.ipca[a] - 1;
        const real = (a, b) => (1 + r(a, b)) / (1 + inf(a, b)) - 1;
        const cdi = (a, b) => serie.cdi[b] / serie.cdi[a] - 1;
        // o primeiro dia (aporte inicial) é a base: a cota vale 1 no fechamento dele
        const per = (a) => a === null || a < i0 ? null : { de: serie.datas[a], nominal: r(a, n), real: real(a, n), ipca: inf(a, n), cdi: cdi(a, n), dias: n - a,
            bova: retAtivo(ativos.BOVA11, serie.datas[a], fim), ivvb: retAtivo(ativos.IVVB11, serie.datas[a], fim), btc: retAtivo(ativos.BTC, serie.datas[a], fim),
            ref: referencia(dados, ativos, serie.datas[a], fim, 0), refBtc: referencia(dados, ativos, serie.datas[a], fim, 0.05) };
        const anoIni = `${fim.slice(0, 4)}-01-01`;
        const iAno = janela(serie, anoIni), i12 = idxAte(serie, addDias(fim, -365)), iMes = janela(serie, fim.slice(0, 8) + '01');
        const total = per(i0);
        const anos = diasEntre(serie.datas[i0], fim) / 365.25;
        if (total) { total.anos = anos; total.aa = anos >= 1 ? Math.pow(1 + total.nominal, 1 / anos) - 1 : null; total.aaReal = anos >= 1 ? Math.pow(1 + total.real, 1 / anos) - 1 : null; }
        // maior queda da cota
        let pico = 0, dd = 0; for (let k = i0; k <= n; k++) { pico = Math.max(pico, serie.cota[k]); dd = Math.max(dd, 1 - serie.cota[k] / pico); }
        // por ano civil
        const porAno = [];
        let anoAtual = null, base = i0;
        for (let k = i0; k <= n; k++) {
            const a = serie.datas[k].slice(0, 4);
            if (anoAtual === null) anoAtual = a;
            if (a !== anoAtual) { porAno.push(linhaAno(anoAtual, base, k - 1)); base = k - 1; anoAtual = a; }
        }
        if (anoAtual) porAno.push(linhaAno(anoAtual, base, n));
        function linhaAno(a, b, e) { return { ano: a, nominal: r(b, e), real: real(b, e), ipca: inf(b, e), cdi: cdi(b, e), parcial: e === n && !serie.datas[e].endsWith('12-31'), ref: referencia(dados, ativos, serie.datas[b], serie.datas[e], 0) }; }
        return { total, ano: per(Math.max(iAno, i0)), m12: i12 >= i0 ? per(i12) : null, mes: per(Math.max(iMes, i0)), quedaMax: dd, porAno };
    }
    function retAtivo(a, de, ate, usd = false) {
        if (!a) return null; const i = ateData(a.datas, de), k = ateData(a.datas, ate);
        if (i < 0 || k < 0 || a.datas[0] > de) return null;
        const f = usd && a.fechUSD ? a.fechUSD : a.fech; return f[k] / f[i] - 1;
    }
    M.retAtivo = retAtivo;
    // Período escolhido pelo usuário: "base" é o fechamento de partida (ex.: 7 dias antes de hoje para "semana")
    // e "ate" o fechamento final. Se a carteira começou depois da base, começa no primeiro dia com patrimônio.
    M.periodo = function (R, base, ate) {
        if (!R || R.vazio) return null;
        const s = R.serie, n = s.datas.length - 1;
        let i0 = s.patrimonio.findIndex(p => p > EPS); if (i0 < 0) return null;
        const b = ateData(s.datas, ate || R.fim); let a = ateData(s.datas, base), ajustado = false;
        if (a < i0) { a = i0; ajustado = true; }
        if (b <= a) return null;
        const da = s.datas[a], db = s.datas[b], ativos = R.ativos, dados = R.dados;
        const nominal = s.cota[b] / s.cota[a] - 1, ipcaP = s.ipca[b] / s.ipca[a] - 1;
        let pico = 0, dd = 0; for (let k = a; k <= b; k++) { pico = Math.max(pico, s.cota[k]); dd = Math.max(dd, 1 - s.cota[k] / pico); }
        const aportes = s.aportado[b] - s.aportado[a];
        return { de: da, ate: db, ajustado, dias: diasEntre(da, db), nominal, real: (1 + nominal) / (1 + ipcaP) - 1, ipca: ipcaP, cdi: s.cdi[b] / s.cdi[a] - 1,
            bova: retAtivo(ativos.BOVA11, da, db), ivvb: retAtivo(ativos.IVVB11, da, db), btc: retAtivo(ativos.BTC, da, db),
            ref: referencia(dados, ativos, da, db, 0), refBtc: referencia(dados, ativos, da, db, 0.05), quedaMax: dd,
            patrimonioIni: s.patrimonio[a], patrimonioFim: s.patrimonio[b], aportes, ganho: s.patrimonio[b] - s.patrimonio[a] - aportes };
    };
    // Papel × setor no mesmo período, pelo preço de mercado (não depende dos seus lançamentos). EUA: contra o ETF
    // setorial, em dólar. B3: contra a média da cesta de empresas do setor (peso igual, comprada no início).
    M.setorPeriodo = function (ativos, cod, de, ate) {
        const a = ativos[cod]; if (!a || !a.setor) return null;
        const usd = a.moeda === 'USD', r = retAtivo(a, de, ate, usd);
        let rs = null, usados = [];
        if (a.setor.ref) { rs = retAtivo(ativos[a.setor.ref], de, ate, usd); if (rs !== null) usados = [a.setor.ref]; }
        else {
            const rr = a.setor.pares.map(p => [p, retAtivo(ativos[p], de, ate, usd)]).filter(x => x[1] !== null);
            if (rr.length) { rs = rr.reduce((t, x) => t + x[1], 0) / rr.length; usados = rr.map(x => x[0]); }
        }
        return { ativo: cod, nome: a.setor.nome, ref: a.setor.ref || null, pares: usados, retorno: r, setor: rs, diferenca: r !== null && rs !== null ? r - rs : null, usd };
    };
    // Carteira de referência dos estudos: 1/3 BOVA11, 1/3 IVVB11, 1/3 CDI (× (1 − btc)) + btc em Bitcoin,
    // rebalanceada no fim de cada trimestre. Serve de régua: é o que a estratégia passiva teria feito.
    function referencia(dados, ativos, de, ate, btc) {
        const B = ativos.BOVA11, I = ativos.IVVB11, C = ativos.BTC;
        if (!B || !I || (btc > 0 && !C) || !(dados && dados.cdi && dados.cdi.datas.length)) return null;
        if (B.datas[0] > de || I.datas[0] > de || (btc > 0 && C.datas[0] > de)) return null;
        const px = (a, d) => a.fech[ateData(a.datas, d)];
        const pesos = btc > 0 ? [(1 - btc) / 3, (1 - btc) / 3, (1 - btc) / 3, btc] : [1 / 3, 1 / 3, 1 / 3, 0];
        const preco = (d) => [px(B, d), px(I, d), cdiAcum(dados, d), btc > 0 ? px(C, d) : 1];
        let p0 = preco(de), q = pesos.map((w, k) => w / p0[k]), v = 1, d = de;
        while (d < ate) {
            const [a, m] = d.split('-').map(Number);
            const mt = Math.ceil(m / 3) * 3; let prox = M.ultimoDiaUtil(a, mt); if (prox <= d) { const a2 = mt === 12 ? a + 1 : a, m2 = mt === 12 ? 3 : mt + 3; prox = M.ultimoDiaUtil(a2, m2); }
            const alvo = prox < ate ? prox : ate;
            const p = preco(alvo); v = q.reduce((s, x, k) => s + x * p[k], 0);
            q = pesos.map((w, k) => w * v / p[k]); d = alvo;
        }
        return v - 1;
    }
    M.referencia = (dados, de, ate, btc = 0) => referencia(dados, prepararAtivos(dados), de, ate, btc);

    // ---------- ficha Bazin e Graham (só informação; não é regra de compra) ----------
    // Bazin: preço teto = dividendo médio por ação dos últimos 5 anos completos ÷ 6%.
    // Graham: valor = √(22,5 × LPA × VPA), com os filtros do investidor defensivo (P/L ≤ 15, P/VP ≤ 1,5 ou
    // P/L × P/VP ≤ 22,5, lucro em todos os anos, dividendos todos os anos).
    M.ficha = function (ativos, cod, ano) {
        const a = ativos[cod], f = a && (a.fund || null); if (!f) return null;
        const usd = a.moeda === 'USD', serie = usd && a.fechUSD ? a.fechUSD : a.fech, preco = serie[serie.length - 1];
        const dataPreco = a.datas[a.datas.length - 1];
        ano = ano || +dataPreco.slice(0, 4);
        const anos = [1, 2, 3, 4, 5].map(k => String(ano - k)), dv = f.dividendosAno || {};
        const divs = anos.map(y => +dv[y] || 0), media = divs.reduce((x, y) => x + y, 0) / 5;
        const teto = media / 0.06, ultimo = divs[0];
        const lucros = (f.lucros || []).map(x => x[1]), lucroSempre = lucros.length ? lucros.every(v => v > 0) : null;
        const pagouTodos = divs.every(v => v > 0);
        const dividaOk = f.dividaPL === null || f.dividaPL === undefined ? null : f.dividaPL <= 100;
        const pl = f.lpa > 0 ? preco / f.lpa : null, pvp = f.vpa > 0 ? preco / f.vpa : null;
        const graham = f.lpa > 0 && f.vpa > 0 ? Math.sqrt(22.5 * f.lpa * f.vpa) : null;
        const bazin = { teto, media, dyUltimoAno: preco > 0 ? ultimo / preco : null, margem: preco > 0 && teto > 0 ? teto / preco - 1 : null, anos, divs,
            filtros: [['Pagou dividendos nos 5 anos', pagouTodos], ['Dividendo do último ano ≥ 6% do preço', preco > 0 ? ultimo / preco >= 0.06 : null],
                ['Dívida até 1× o patrimônio', dividaOk], ['Lucro em todos os anos', lucroSempre]] };
        bazin.passa = bazin.filtros.every(x => x[1] !== false) && preco <= teto;
        const g = { valor: graham, margem: graham && preco > 0 ? graham / preco - 1 : null, pl, pvp, lpa: f.lpa, vpa: f.vpa,
            motivo: graham ? null : !(f.lpa > 0) ? 'lucro por ação negativo ou zero: a fórmula não se aplica' : 'patrimônio por ação negativo ou zero: a fórmula não se aplica',
            filtros: [['P/L até 15', pl === null ? false : pl <= 15], ['P/VP até 1,5 (ou P/L × P/VP até 22,5)', pvp === null ? false : (pvp <= 1.5 || (pl !== null && pl * pvp <= 22.5))],
                ['Lucro em todos os anos', lucroSempre], ['Dividendos todos os anos', pagouTodos]] };
        g.passa = g.filtros.every(x => x[1] !== false) && graham !== null && preco <= graham;
        return { ativo: cod, usd, preco, dataPreco, dataFund: f.data || null, financeira: !!f.financeira, dividaPL: f.dividaPL ?? null, anosLucro: (f.lucros || []).map(x => x[0]), bazin, graham: g };
    };

    // ---------- rebalanceamento ----------
    // Metas por classe (% do total). Faixa de tolerância "5/25": a classe está fora quando se afasta 5 pontos da
    // meta, ou 25% da própria meta (o que for menor; útil para metas pequenas como 5% de BTC). O aporte é dividido
    // primeiro para o que está abaixo da meta, sem vender nada (sem imposto e sem custo).
    M.CLASSES = [['acoes_br', 'Ações Brasil (BOVA11)'], ['acoes_eua', 'Ações EUA (IVVB11)'], ['rf', 'Renda fixa (CDI)'], ['cripto', 'Bitcoin'], ['exterior', 'Conta EUA (papéis em dólar)'], ['outros', 'Outros']];
    M.METAS_PADRAO = { acoes_br: 31.67, acoes_eua: 31.67, rf: 31.66, cripto: 5, exterior: 0, outros: 0 };
    M.rebalancear = function (R, metas, aporte = 0) {
        if (!R || R.vazio) return null;
        const valor = {}; M.CLASSES.forEach(([k]) => valor[k] = 0);
        for (const p of R.posicoes) { const k = p.classe === 'caixa' ? (p.conta === 'EUA' ? 'exterior' : 'rf') : (valor[p.classe] !== undefined ? p.classe : 'outros'); valor[k] += p.valor; }
        const total = Object.values(valor).reduce((a, b) => a + b, 0); if (!(total > 0)) return null;
        const somaMetas = M.CLASSES.reduce((s, [k]) => s + (+metas[k] || 0), 0) || 100;
        const classes = M.CLASSES.map(([k, nome]) => {
            const meta = (+metas[k] || 0) / somaMetas, peso = valor[k] / total, dif = peso - meta;
            const faixa = Math.min(0.05, 0.25 * meta);
            return { k, nome, valor: valor[k], peso, meta, dif, faixa, fora: (meta > 0 || valor[k] > 0) && Math.abs(dif) > Math.max(faixa, 0.005), paraMeta: meta * total - valor[k] };
        }).filter(c => c.meta > 0 || c.valor > 0);
        const novoTotal = total + aporte, falta = {}; let somaFalta = 0;
        classes.forEach(c => { falta[c.k] = Math.max(0, novoTotal * c.meta - c.valor); somaFalta += falta[c.k]; });
        const divisao = {};
        classes.forEach(c => { divisao[c.k] = aporte <= 0 ? 0 : somaFalta >= aporte ? aporte * falta[c.k] / somaFalta : falta[c.k] + (aporte - somaFalta) * c.meta; });
        const precisa = classes.some(c => c.fora);
        // próxima revisão: fim do trimestre
        const [a, m] = R.fim.split('-').map(Number); const mt = Math.ceil(m / 3) * 3;
        return { total, classes, aporte, divisao, precisa, proximaRevisao: M.ultimoDiaUtil(a, mt) };
    };

    // ---------- imposto de renda ----------
    // Regras para pessoa física em 2026 (operações comuns, sem day trade):
    //  - Ações: isentas se o total vendido em ações no mês for até R$ 20 mil; acima, 15% sobre o lucro.
    //  - ETF de ações e BDR: 15% sobre o lucro, sem isenção. Prejuízo de ações, ETFs e BDRs se compensa no mesmo grupo.
    //  - FII: 20%, sem isenção, prejuízo em grupo separado.
    //  - Cripto: isento se o total vendido no mês (todas as criptos) for até R$ 35 mil; acima, 15% sobre o ganho
    //    (até R$ 5 milhões de ganho). Prejuízo de cripto não se compensa. DARF 4600, com o programa GCAP.
    //  DARF 6015 para bolsa; vencimento no último dia útil do mês seguinte; abaixo de R$ 10 acumula.
    M.ISENCAO_ACOES = 20000; M.ISENCAO_CRIPTO = 35000;
    M.impostoMensal = function (vendas) {
        const meses = {};
        for (const v of vendas) if (v.conta !== 'EUA') (meses[v.data.slice(0, 7)] || (meses[v.data.slice(0, 7)] = [])).push(v);
        let prejComum = 0, prejFII = 0, acumuladoDarf = 0;
        const out = [];
        for (const mes of Object.keys(meses).sort()) {
            const vs = meses[mes];
            const soma = (t, f) => vs.filter(v => v.tipo === t).reduce((s, v) => s + f(v), 0);
            const vendAcoes = soma('acao', v => v.bruto), lucAcoes = soma('acao', v => v.lucro), lucETF = soma('etf', v => v.lucro) + soma('bdr', v => v.lucro), lucBDR = soma('bdr', v => v.lucro), lucFII = soma('fii', v => v.lucro);
            const vendCripto = soma('cripto', v => v.bruto), lucCripto = vs.filter(v => v.tipo === 'cripto' && v.lucro > 0).reduce((s, v) => s + v.lucro, 0);
            const acoesIsentas = vendAcoes <= M.ISENCAO_ACOES;
            const prejIni = prejComum, prejFIIIni = prejFII;
            let baseComum = (acoesIsentas ? Math.min(0, lucAcoes) : lucAcoes) + lucETF;
            const isentoAcoes = acoesIsentas && lucAcoes > 0 ? lucAcoes : 0;
            let usado = 0;
            if (baseComum > 0) { usado = Math.min(baseComum, prejComum); baseComum -= usado; prejComum -= usado; }
            else { prejComum += -baseComum; baseComum = 0; }
            let baseFII = lucFII; if (baseFII > 0) { const u = Math.min(baseFII, prejFII); baseFII -= u; prejFII -= u; } else { prejFII += -baseFII; baseFII = 0; }
            const impBolsa = baseComum * 0.15 + baseFII * 0.20;
            let darf = impBolsa + acumuladoDarf, pagar = darf >= 10 ? darf : 0; acumuladoDarf = darf >= 10 ? 0 : darf;
            const criptoIsenta = vendCripto <= M.ISENCAO_CRIPTO;
            const impCripto = criptoIsenta ? 0 : lucCripto * 0.15;
            const [a, m] = mes.split('-').map(Number);
            const venc = m === 12 ? M.ultimoDiaUtil(a + 1, 1) : M.ultimoDiaUtil(a, m + 1);
            out.push({ mes, vendas: vs, vendAcoes, lucAcoes, lucETF, lucBDR, lucFII, acoesIsentas, isentoAcoes, prejUsado: usado, prejAnterior: prejIni, prejFIIAnterior: prejFIIIni,
                prejComum, prejFII, baseComum, baseFII, impBolsa, darfBolsa: pagar, acumulaProximo: acumuladoDarf, vendCripto, lucCripto, criptoIsenta, impCripto, vencimento: venc });
        }
        return out;
    };
    // Conta EUA (Lei 14.754/2023, aplicações financeiras no exterior de pessoa física, desde 2024): apuração ANUAL,
    // 15% sobre ganhos de venda + dividendos e juros, convertidos para reais pela PTAX de cada data. Sem isenção mensal.
    // Prejuízo de venda compensa ganhos e rendimentos do mesmo ano e dos anos seguintes. O imposto retido lá fora
    // (dividendos) pode ser deduzido, até o imposto brasileiro sobre aquele rendimento. Pago com a declaração (DAA).
    M.impostoExterior = function (vendas, proventos) {
        const anos = {};
        const ano = (a) => anos[a] || (anos[a] = { ano: a, vendas: [], proventos: [] });
        vendas.filter(v => v.conta === 'EUA').forEach(v => ano(v.data.slice(0, 4)).vendas.push(v));
        (proventos || []).filter(p => p.conta === 'EUA').forEach(p => ano(p.data.slice(0, 4)).proventos.push(p));
        let prej = 0; const out = [];
        for (const a of Object.keys(anos).sort()) {
            const x = anos[a];
            const ganhos = x.vendas.reduce((s, v) => s + v.lucro, 0), rend = x.proventos.reduce((s, p) => s + p.valor + p.irRetido, 0);
            const retido = x.proventos.reduce((s, p) => s + p.irRetido, 0), vendido = x.vendas.reduce((s, v) => s + v.bruto, 0);
            const prejAnterior = prej;
            let base = ganhos + rend; let usado = 0;
            if (base > 0) { usado = Math.min(base, prej); base -= usado; prej -= usado; } else { prej += -base; base = 0; }
            const imposto = base * 0.15, credito = Math.min(retido, rend * 0.15, imposto);
            out.push({ ano: a, vendas: x.vendas, proventos: x.proventos, vendido, ganhos, rendimentos: rend, retido, prejAnterior, prejUsado: usado, prejFinal: prej,
                base, imposto, credito, pagar: Math.max(0, imposto - credito), vencimento: M.ultimoDiaUtil(+a + 1, 5) });
        }
        return out;
    };
    // Bens e direitos em 31/12: posição pelo CUSTO (quantidade × preço médio), como a Receita pede.
    M.posicaoEm = function (dados, lancamentos, data, opcoes = {}) {
        const L = normalizar(lancamentos).filter(l => l.data <= data);
        const ativos = prepararAtivos(dados);
        const ptaxDe = criarPTAX(dados);
        const pos = {}, rf = {}; const tiposIR = opcoes.tiposIR || {}; const tipoIR = (c) => tiposIR[c] || M.tipoIRPadrao(c);
        const desd = []; for (const [cod, a] of Object.entries(ativos)) for (const [d, r] of a.desd) desd.push([d, cod, r]);
        let k = 0;
        const eventos = [...L.map(l => ({ d: l.data, l })), ...desd.filter(x => x[0] <= data).map(([d, cod, r]) => ({ d, desd: [cod, r] }))].sort((a, b) => a.d < b.d ? -1 : a.d > b.d ? 1 : (a.desd ? -1 : 1));
        for (const e of eventos) {
            if (e.desd) { const p = pos[e.desd[0]]; if (p) p.qtd *= e.desd[1]; continue; }
            const l = e.l; const p = l.ativo && (pos[l.ativo] || (pos[l.ativo] = { qtd: 0, custo: 0, custoUSD: 0, conta: l.conta }));
            const fx = l.conta === 'EUA' ? (ptaxDe(l.data) || 1) : 1;
            if (l.tipo === 'compra' || l.tipo === 'posicao_inicial' || l.tipo === 'bonificacao') { const v = l.qtd * l.preco + (l.tipo === 'compra' ? l.custos : 0); p.qtd += l.qtd; p.custo += v * fx; if (l.conta === 'EUA') { p.conta = 'EUA'; p.custoUSD += v; } }
            else if (l.tipo === 'venda') { const q = Math.min(l.qtd, p.qtd), pm = p.qtd > 0 ? p.custo / p.qtd : 0, pmU = p.qtd > 0 ? p.custoUSD / p.qtd : 0; p.qtd -= q; p.custo -= q * pm; p.custoUSD -= q * pmU; if (p.qtd < 1e-9) { p.qtd = 0; p.custo = 0; p.custoUSD = 0; } }
            else if (l.tipo === 'rf_aplicar') { const n = l.ativo || 'Renda fixa'; rf[n] = (rf[n] || 0) + l.valor; }
            else if (l.tipo === 'rf_resgatar') { const n = l.ativo || 'Renda fixa'; rf[n] = Math.max(0, (rf[n] || 0) - l.valor); }
            k++;
        }
        const itens = Object.entries(pos).filter(([, p]) => p.qtd > 1e-9).map(([cod, p]) => p.conta === 'EUA'
            ? { ativo: cod, conta: 'EUA', tipo: tiposIR[cod] === 'acao' || (!tiposIR[cod] && ativos[cod] && ativos[cod].tipo === "EQUITY") ? 'acao_ext' : 'etf_ext', qtd: p.qtd, pm: p.custo / p.qtd, custo: p.custo, custoUSD: p.custoUSD, pmUSD: p.custoUSD / p.qtd }
            : { ativo: cod, conta: 'BR', tipo: tipoIR(cod), qtd: p.qtd, pm: p.custo / p.qtd, custo: p.custo });
        Object.entries(rf).filter(([, v]) => v > EPS).forEach(([n, v]) => itens.push({ ativo: n, tipo: 'rf', qtd: null, pm: null, custo: v, aproximado: true }));
        return itens;
    };
    M.CODIGOS_IR = {
        acao: 'Bens e Direitos: grupo 03 (Participações societárias), código 01 (Ações)',
        etf: 'Bens e Direitos: grupo 07 (Fundos), código de fundo de índice / ETF',
        fii: 'Bens e Direitos: grupo 07 (Fundos), código 03 (Fundos Imobiliários)',
        cripto: 'Bens e Direitos: grupo 08 (Criptoativos), código 01 (Bitcoin) ou 02 (outras criptos)',
        rf: 'Bens e Direitos: grupo 04 (Aplicações e investimentos), código 02 (títulos públicos e privados, como Tesouro e CDB)',
        acao_ext: 'Bens e Direitos: grupo 03 (Participações societárias), código 01 (Ações), localização Estados Unidos; informe que é aplicação financeira no exterior',
        etf_ext: 'Bens e Direitos: grupo 07 (Fundos), código de ETF/fundo no exterior, localização Estados Unidos; informe que é aplicação financeira no exterior',
        bdr: 'Bens e Direitos: grupo 04 (Aplicações e investimentos), código 04 (ativos negociados em bolsa no Brasil, como BDRs); confira com o informe da corretora',
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = M; else raiz.Carteira = M;
})(typeof window !== 'undefined' ? window : globalThis);
