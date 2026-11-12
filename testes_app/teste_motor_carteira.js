// Testes do motor da carteira (sem rede): node testes_app/teste_motor_carteira.js
const C = require('../app/motor-carteira.js');
const assert = require('assert');
let falhas = 0;
const t = (nome, f) => { try { f(); console.log('ok  ', nome); } catch (e) { falhas++; console.log('FALHOU', nome, '\n   ', e.message); } };
const perto = (a, b, tol = 1e-6, msg = '') => assert(Math.abs(a - b) <= tol, `${msg} esperado ${b}, veio ${a}`);
// mercado sintético: dias corridos de 2024-01-01 a 2024-12-31
function serie(ini, n, f) { const d = [], c = []; for (let i = 0; i < n; i++) { d.push(C.addDias(ini, i)); c.push(f(i)); } return { datas: d, fech: c }; }
function dados({ bova = i => 100, ivvb = i => 200, btc = i => 300000, cdiDia = 0, ipcaMes = 0, desd = [] } = {}) {
    const n = 366, ini = '2024-01-01';
    const cdi = serie(ini, n, i => Math.pow(1 + cdiDia, i + 1));
    const meses = []; const v = []; for (let m = 1; m <= 12; m++) { meses.push(`2024-${String(m).padStart(2, '0')}`); v.push(ipcaMes); }
    return { ativos: { BOVA11: { nome: 'BOVA11', classe: 'acoes_br', ...serie(ini, n, bova), desdobramentos: desd }, IVVB11: { nome: 'IVVB11', classe: 'acoes_eua', ...serie(ini, n, ivvb), desdobramentos: [] }, BTC: { nome: 'BTC', classe: 'cripto', ...serie(ini, n, btc), desdobramentos: [] } },
        cdi: { datas: cdi.datas, acum: cdi.fech }, ipca: { meses, var: v } };
}
t('o caso do +200%: aportes, vendas e recompras com preço parado dão rentabilidade zero', () => {
    const D = dados();
    const L = [{ data: '2024-01-02', tipo: 'aporte', valor: 1000 }, { data: '2024-01-02', tipo: 'compra', ativo: 'BOVA11', qtd: 10, preco: 100 },
        { data: '2024-02-01', tipo: 'aporte', valor: 2000 }, { data: '2024-02-01', tipo: 'compra', ativo: 'BOVA11', qtd: 20, preco: 100 },
        { data: '2024-03-01', tipo: 'venda', ativo: 'BOVA11', qtd: 30, preco: 100 }, { data: '2024-03-05', tipo: 'compra', ativo: 'BOVA11', qtd: 30, preco: 100 },
        { data: '2024-04-01', tipo: 'aporte', valor: 3000 }, { data: '2024-04-01', tipo: 'compra', ativo: 'BOVA11', qtd: 30, preco: 100 }];
    const R = C.calcular(D, L, { hoje: '2024-12-31' });
    perto(R.patrimonio, 6000, 1e-6, 'patrimônio'); perto(R.aportado, 6000, 1e-6, 'aportado'); perto(R.metricas.total.nominal, 0, 1e-9, 'rentabilidade');
});
t('valorização de 10% com aporte no meio: cota mede só a valorização', () => {
    const D = dados({ bova: i => i < 100 ? 100 : 110 });   // sobe 10% no dia 100 (2024-04-10)
    const L = [{ data: '2024-01-02', tipo: 'aporte', valor: 1000 }, { data: '2024-01-02', tipo: 'compra', ativo: 'BOVA11', qtd: 10, preco: 100 },
        { data: '2024-06-01', tipo: 'aporte', valor: 11000 }, { data: '2024-06-01', tipo: 'compra', ativo: 'BOVA11', qtd: 100, preco: 110 }];
    const R = C.calcular(D, L, { hoje: '2024-12-31' });
    perto(R.patrimonio, 12100, 1e-6); perto(R.metricas.total.nominal, 0.10, 1e-9);
    // ganho em reais: 100 (só o primeiro lote valorizou)
    perto(R.patrimonio - R.aportado, 100, 1e-6);
});
t('compra sem aporte lançado vira aporte automático', () => {
    const D = dados({ bova: i => 100 + i * 0 });
    const R = C.calcular(D, [{ data: '2024-01-02', tipo: 'compra', ativo: 'BOVA11', qtd: 10, preco: 100 }], { hoje: '2024-12-31' });
    perto(R.aportado, 1000); assert(R.avisos.some(a => a.includes('aporte')));
});
t('retirada não muda a cota', () => {
    const D = dados({ bova: i => i < 50 ? 100 : 120 });
    const L = [{ data: '2024-01-02', tipo: 'compra', ativo: 'BOVA11', qtd: 10, preco: 100 }, { data: '2024-03-01', tipo: 'venda', ativo: 'BOVA11', qtd: 5, preco: 120 }, { data: '2024-03-01', tipo: 'retirada', valor: 600 }];
    const R = C.calcular(D, L, { hoje: '2024-12-31' });
    perto(R.patrimonio, 600); perto(R.metricas.total.nominal, 0.2, 1e-9); perto(R.vendas[0].lucro, 100);
});
t('rentabilidade real desconta o IPCA', () => {
    const D = dados({ bova: i => 100 * Math.pow(1.01, Math.floor(i / 30)), ipcaMes: 0.5 });
    const R = C.calcular(D, [{ data: '2024-01-01', tipo: 'compra', ativo: 'BOVA11', qtd: 10, preco: 100 }], { hoje: '2024-12-31' });
    const T = R.metricas.total; perto((1 + T.nominal) / (1 + T.ipca) - 1, T.real, 1e-12); assert(T.real < T.nominal && T.ipca > 0.04 && T.ipca < 0.07, `ipca ${T.ipca}`);
});
t('renda fixa a 100% do CDI rende o CDI', () => {
    const D = dados({ cdiDia: 0.0004 });
    const R = C.calcular(D, [{ data: '2024-01-01', tipo: 'aporte', valor: 1000 }, { data: '2024-01-01', tipo: 'rf_aplicar', ativo: 'Tesouro Selic', valor: 1000, pctCDI: 100 }], { hoje: '2024-12-31' });
    perto(R.metricas.total.nominal, R.metricas.total.cdi, 1e-9);
});
t('desdobramento 1:10 não muda o patrimônio', () => {
    // preço já corrigido pelo Yahoo: 10 o ano todo; antes do desdobramento, o preço de tela era 100
    const D = dados({ bova: i => 10, desd: [['2024-06-01', 10]] });
    const R = C.calcular(D, [{ data: '2024-01-02', tipo: 'compra', ativo: 'BOVA11', qtd: 10, preco: 100 }], { hoje: '2024-12-31' });
    perto(R.patrimonio, 1000); perto(R.posicoes[0].qtd, 100); perto(R.metricas.total.nominal, 0, 1e-9);
});
t('IR: ETF paga 15% mesmo abaixo de 20 mil; ação abaixo de 20 mil é isenta; cripto até 35 mil isenta', () => {
    const v = [{ data: '2024-05-10', tipo: 'etf', bruto: 5000, lucro: 1000 }, { data: '2024-05-11', tipo: 'acao', bruto: 10000, lucro: 2000 }, { data: '2024-05-12', tipo: 'cripto', bruto: 30000, lucro: 5000 }];
    const [m] = C.impostoMensal(v); perto(m.impBolsa, 150); perto(m.isentoAcoes, 2000); perto(m.impCripto, 0);
    const [m2] = C.impostoMensal([{ data: '2024-05-12', tipo: 'cripto', bruto: 40000, lucro: 5000 }]); perto(m2.impCripto, 750);
});
t('IR: prejuízo do mês anterior abate o lucro', () => {
    const r = C.impostoMensal([{ data: '2024-05-10', tipo: 'etf', bruto: 5000, lucro: -400 }, { data: '2024-06-10', tipo: 'etf', bruto: 5000, lucro: 1000 }]);
    perto(r[1].baseComum, 600); perto(r[1].impBolsa, 90);
});
t('rebalanceamento: aporte vai para o que está abaixo da meta', () => {
    const D = dados();
    const R = C.calcular(D, [{ data: '2024-01-02', tipo: 'compra', ativo: 'BOVA11', qtd: 100, preco: 100 }], { hoje: '2024-12-31' });
    const B = C.rebalancear(R, { acoes_br: 50, acoes_eua: 50 }, 10000);
    assert(B.precisa); perto(B.divisao.acoes_eua, 10000); perto(B.divisao.acoes_br, 0);
});
t('referência 1/3 com preços parados e CDI zero rende zero', () => {
    perto(C.referencia(dados(), '2024-01-02', '2024-12-31'), 0, 1e-12);
    const D = dados({ cdiDia: 0.0004 }); const r = C.referencia(D, '2024-01-02', '2024-12-31'); const cdi = D.cdi.acum[365] / D.cdi.acum[1] - 1;
    assert(r > 0 && r < cdi, `ref ${r} cdi ${cdi}`);
});
t('posição em 31/12 pelo custo', () => {
    const it = C.posicaoEm(dados(), [{ data: '2024-01-02', tipo: 'compra', ativo: 'BOVA11', qtd: 10, preco: 100, custos: 5 }, { data: '2024-03-02', tipo: 'venda', ativo: 'BOVA11', qtd: 5, preco: 120 }], '2024-12-31');
    perto(it[0].qtd, 5); perto(it[0].custo, 502.5);
});

// ---------- conta EUA ----------
// VOO cotado em dólar; PTAX 5,00 no 1º semestre e 5,50 a partir de 2024-07-01
function dadosEUA({ voo = i => 100, ptax = d => d < '2024-07-01' ? 5 : 5.5 } = {}) {
    const D = dados(); const s = serie('2024-01-01', 366, voo);
    D.ptaxSerie = { datas: s.datas.slice(), valor: s.datas.map(ptax) };
    D.ativos.VOO = { nome: 'Vanguard S&P 500 ETF', classe: 'exterior', moeda: 'USD', tipo: 'ETF', datas: s.datas, fechUSD: s.fech, fech: s.fech.map((c, i) => c * ptax(s.datas[i])), desdobramentos: [] };
    return D;
}
t('EUA: preço parado em dólar, dólar sobe 10%: carteira em reais sobe 10%', () => {
    const R = C.calcular(dadosEUA(), [{ data: '2024-01-02', tipo: 'aporte', conta: 'EUA', valor: 1000 }, { data: '2024-01-02', tipo: 'compra', conta: 'EUA', ativo: 'VOO', qtd: 10, preco: 100 }], { hoje: '2024-12-31' });
    perto(R.aportado, 5000); perto(R.patrimonio, 5500); perto(R.metricas.total.nominal, 0.10, 1e-9);
    const p = R.posicoes.find(x => x.ativo === 'VOO'); perto(p.valorUSD, 1000); perto(p.pmUSD, 100); perto(p.pm, 500); assert.equal(p.conta, 'EUA');
    perto(R.contas.EUA.valorUSD, 1000); perto(R.contas.BR.valor, 0);
});
t('EUA: aportes e vendas em dólar não inflam a rentabilidade', () => {
    const D = dadosEUA({ ptax: () => 5 });
    const L = [{ data: '2024-01-02', tipo: 'compra', conta: 'EUA', ativo: 'VOO', qtd: 10, preco: 100 }, { data: '2024-03-01', tipo: 'venda', conta: 'EUA', ativo: 'VOO', qtd: 10, preco: 100 },
        { data: '2024-03-02', tipo: 'aporte', conta: 'EUA', valor: 5000 }, { data: '2024-03-03', tipo: 'compra', conta: 'EUA', ativo: 'VOO', qtd: 60, preco: 100 }];
    const R = C.calcular(D, L, { hoje: '2024-12-31' });
    perto(R.patrimonio, 30000); perto(R.aportado, 30000); perto(R.metricas.total.nominal, 0, 1e-9);
});
t('EUA: venda fica fora do DARF mensal e entra no imposto anual de 15% (ganho em reais, PTAX de cada data)', () => {
    const D = dadosEUA({ voo: i => i < 200 ? 100 : 120 });   // 2024-07-19 em diante: US$ 120
    const L = [{ data: '2024-01-02', tipo: 'compra', conta: 'EUA', ativo: 'VOO', qtd: 10, preco: 100 },
        { data: '2024-08-01', tipo: 'venda', conta: 'EUA', ativo: 'VOO', qtd: 10, preco: 120 },
        { data: '2024-09-01', tipo: 'provento', conta: 'EUA', ativo: 'VOO', valor: 70, irRetido: 30 },
        { data: '2024-05-02', tipo: 'compra', ativo: 'BOVA11', qtd: 10, preco: 100 }, { data: '2024-05-10', tipo: 'venda', ativo: 'BOVA11', qtd: 10, preco: 110 }];
    const R = C.calcular(D, L, { hoje: '2024-12-31' });
    const v = R.vendas.find(x => x.conta === 'EUA'); perto(v.lucro, 1200 * 5.5 - 1000 * 5); perto(v.lucroUSD, 200);
    const meses = C.impostoMensal(R.vendas); assert.equal(meses.length, 1); assert.equal(meses[0].mes, '2024-05');
    const a = C.impostoExterior(R.vendas, R.proventos)[0];
    perto(a.rendimentos, 100 * 5.5); perto(a.base, 1600 + 550); perto(a.imposto, 2150 * 0.15); perto(a.credito, 550 * 0.15); perto(a.pagar, 1600 * 0.15); assert.equal(a.vencimento, '2025-05-30');
});
t('EUA: prejuízo de um ano abate o ganho do ano seguinte', () => {
    const r = C.impostoExterior([{ data: '2024-03-01', conta: 'EUA', bruto: 1000, lucro: -300 }, { data: '2025-03-01', conta: 'EUA', bruto: 1000, lucro: 500 }], []);
    perto(r[0].imposto, 0); perto(r[0].prejFinal, 300); perto(r[1].base, 200); perto(r[1].imposto, 30);
});
t('EUA: caixa em dólar conta como Conta EUA no rebalanceamento, e Bens e Direitos sai em reais e dólares', () => {
    const D = dadosEUA();
    const L = [{ data: '2024-01-02', tipo: 'aporte', conta: 'EUA', valor: 2000 }, { data: '2024-01-02', tipo: 'compra', conta: 'EUA', ativo: 'VOO', qtd: 10, preco: 100 }, { data: '2024-01-02', tipo: 'compra', ativo: 'BOVA11', qtd: 100, preco: 100 }];
    const R = C.calcular(D, L, { hoje: '2024-12-31' });
    const B = C.rebalancear(R, { acoes_br: 50, exterior: 50 }, 0); const ex = B.classes.find(c => c.k === 'exterior');
    perto(ex.valor, 2000 * 5.5);
    const it = C.posicaoEm(D, L, '2024-12-31').find(x => x.ativo === 'VOO'); perto(it.custo, 5000); perto(it.custoUSD, 1000); assert.equal(it.tipo, 'etf_ext');
});
t('venda sem compra lançada não infla a rentabilidade (conta como aporte) e avisa', () => {
    const D = dados({ bova: i => i < 100 ? 100 : 110 });
    const L = [{ data: '2024-01-02', tipo: 'compra', ativo: 'BOVA11', qtd: 10, preco: 100 },
        { data: '2024-02-01', tipo: 'venda', ativo: 'P2LT34', qtd: 50, preco: 40 }];   // 2.000 de venda sem compra
    const R = C.calcular(D, L, { hoje: '2024-12-31' });
    perto(R.patrimonio, 1100 + 2000); perto(R.aportado, 3000); perto(R.metricas.total.nominal, 100 / 3000, 1e-9);   // o dinheiro da venda entrou como aporte: só os 100 de valorização contam
    perto(R.semCompra.valor, 2000); assert.deepEqual(R.semCompra.ativos, ['P2LT34']); assert(R.avisos[0].includes('Vendas sem compra'));
    // venda parcial além da posição: só o excedente vira aporte
    const R2 = C.calcular(D, [{ data: '2024-01-02', tipo: 'compra', ativo: 'BOVA11', qtd: 10, preco: 100 }, { data: '2024-06-01', tipo: 'venda', ativo: 'BOVA11', qtd: 15, preco: 110 }], { hoje: '2024-12-31' });
    perto(R2.semCompra.valor, 550); perto(R2.metricas.total.nominal, 0.10, 1e-9);
});
t('BDR: tipo pelo código e 15% sem a isenção de R$ 20 mil', () => {
    assert.equal(C.tipoIRPadrao('P2LT34'), 'bdr'); assert.equal(C.tipoIRPadrao('AAPL34'), 'bdr'); assert.equal(C.tipoIRPadrao('BIVB39'), 'bdr');
    assert.equal(C.tipoIRPadrao('MGLU3'), 'acao'); assert.equal(C.tipoIRPadrao('PETR4'), 'acao'); assert.equal(C.tipoIRPadrao('TAEE11'), 'fii');
    const m = C.impostoMensal([{ data: '2025-01-09', conta: 'BR', tipo: 'bdr', bruto: 5000, lucro: 1000 }])[0];
    perto(m.baseComum, 1000); perto(m.impBolsa, 150); perto(m.darfBolsa, 150); perto(m.lucBDR, 1000);
});
t('período escolhido: rentabilidade, comparativos e queda só dentro do período', () => {
    const D = dados({ bova: i => i < 100 ? 100 : (i < 200 ? 90 : 120), cdiDia: 0.0004 });
    const R = C.calcular(D, [{ data: '2024-01-02', tipo: 'compra', ativo: 'BOVA11', qtd: 10, preco: 100 }, { data: '2024-08-01', tipo: 'aporte', valor: 500 }], { hoje: '2024-12-31' });
    const P = C.periodo(R, '2024-06-01', '2024-12-31');
    assert.equal(P.de, '2024-06-01'); perto(P.bova, 120 / 90 - 1, 1e-9); perto(P.quedaMax, 0, 1e-9); perto(P.aportes, 500);
    perto(P.cdi, Math.pow(1.0004, 213) - 1, 1e-9);
    perto(P.ganho, 300, 1e-6);
    const T = C.periodo(R, '2023-01-01'); assert(T.ajustado); perto(T.nominal, R.metricas.total.nominal, 1e-12); perto(T.quedaMax, 0.10, 1e-9);
    assert.equal(C.periodo(R, '2024-12-31', '2024-12-31'), null);
});
t('setor: B3 contra a média da cesta, EUA contra o ETF em dólar', () => {
    const ini = '2024-01-01', s = (f) => serie(ini, 100, f);
    const A = { MGLU3: { ...s(i => i < 50 ? 10 : 12), setor: { nome: 'Varejo', pares: ['LREN3', 'BHIA3', 'NOVA3'] } },
        LREN3: { ...s(i => i < 50 ? 10 : 11), apoio: true }, BHIA3: { ...s(i => i < 50 ? 10 : 9), apoio: true }, NOVA3: { datas: ['2024-03-01', '2024-03-02'], fech: [1, 1], apoio: true },
        PLTR: { ...s(i => 20), fechUSD: s(i => i < 50 ? 4 : 5).fech, moeda: 'USD', setor: { nome: 'Tecnologia', ref: 'XLK' } },
        XLK: { ...s(i => 20), fechUSD: s(i => i < 50 ? 100 : 110).fech, moeda: 'USD', apoio: true } };
    const at = C.calcular({ ativos: A }, [{ data: ini, tipo: 'aporte', valor: 1 }], { hoje: '2024-04-09' }).ativos;
    const b = C.setorPeriodo(at, 'MGLU3', '2024-01-10', '2024-04-09'); perto(b.retorno, 0.2); perto(b.setor, 0); perto(b.diferenca, 0.2); assert.deepEqual(b.pares, ['LREN3', 'BHIA3']);
    const e = C.setorPeriodo(at, 'PLTR', '2024-01-10', '2024-04-09'); perto(e.retorno, 0.25); perto(e.setor, 0.10); assert(e.usd && e.ref === 'XLK');
    assert.equal(C.setorPeriodo(at, 'LREN3', '2024-01-10', '2024-04-09'), null);
});
t('ficha Bazin e Graham', () => {
    const datas = ['2026-11-05', '2026-11-06'];
    const A = { X: { datas, fech: [9, 10], fund: { lpa: 1, vpa: 8, dividaPL: 40, dividendosAno: { '2021': 0.7, '2022': 0.8, '2023': 0.6, '2024': 0.5, '2025': 0.4 }, lucros: [['2022', 5], ['2023', 6]] } },
        Y: { datas, fech: [5, 5.61], fund: { lpa: 0.11, vpa: 14.4, dividendosAno: { '2025': 0.01 }, lucros: [['2024', -1], ['2025', 1]] } },
        Z: { datas, fech: [1, 1], fund: { lpa: -0.5, vpa: 2 } } };
    const at = C.calcular({ ativos: A }, [{ data: '2026-11-05', tipo: 'aporte', valor: 1 }], { hoje: '2026-11-06' }).ativos;
    const x = C.ficha(at, 'X'); perto(x.bazin.media, 0.6); perto(x.bazin.teto, 10); perto(x.bazin.margem, 0); perto(x.graham.valor, Math.sqrt(180)); perto(x.graham.pl, 10); perto(x.graham.pvp, 1.25);
    assert(x.graham.passa && x.bazin.filtros[0][1] === true && x.bazin.filtros[1][1] === false && !x.bazin.passa);
    const y = C.ficha(at, 'Y'); perto(y.graham.valor, Math.sqrt(22.5 * 0.11 * 14.4)); assert(!y.graham.passa && y.graham.filtros[0][1] === false && y.bazin.teto < 0.1);
    const z = C.ficha(at, 'Z'); assert(z.graham.valor === null && /negativo/.test(z.graham.motivo));
    assert.equal(C.ficha(at, 'NADA'), null);
});
t('posição inicial: preço médio para o imposto, preço de mercado para a rentabilidade', () => {
    const D = dados({ bova: i => i < 100 ? 150 : 165 });   // mercado a 150; sobe 10% no dia 100
    const L = [{ data: '2024-01-02', tipo: 'posicao_inicial', ativo: 'BOVA11', qtd: 10, preco: 100 },   // comprou a 100 lá atrás
        { data: '2024-06-01', tipo: 'venda', ativo: 'BOVA11', qtd: 10, preco: 165 }];
    const R = C.calcular(D, L, { hoje: '2024-12-31' });
    perto(R.aportado, 1500); perto(R.metricas.total.nominal, 0.10, 1e-9);   // sem o lucro falso de 150/100
    perto(R.vendas[0].lucro, 650); perto(R.vendas[0].pm, 100); assert(!R.avisos.some(a => a.includes('sem compra')));
    // sem cotação: entra pelo preço médio e avisa
    const R2 = C.calcular(D, [{ data: '2024-01-02', tipo: 'posicao_inicial', ativo: 'XYZ34', qtd: 5, preco: 40 }], { hoje: '2024-12-31' });
    perto(R2.patrimonio, 200); perto(R2.aportado, 200); assert(R2.avisos.some(a => a.includes('XYZ34')));
    const b = C.posicaoEm(D, L.slice(0, 1), '2024-03-01')[0]; perto(b.custo, 1000); perto(b.qtd, 10);
});
t('posição inicial na conta EUA: custo em dólar pelo preço médio, aporte pelo mercado', () => {
    const D = dadosEUA({ voo: i => 120 });
    const R = C.calcular(D, [{ data: '2024-01-02', tipo: 'posicao_inicial', conta: 'EUA', ativo: 'VOO', qtd: 10, preco: 100 }], { hoje: '2024-06-30' });
    perto(R.aportado, 1200 * 5); perto(R.metricas.total.nominal, 0, 1e-9); const p = R.posicoes.find(x => x.ativo === 'VOO'); perto(p.pmUSD, 100); perto(p.custoUSD, 1000);
});
t('ações recebidas (bonificação): somam quantidade sem mexer no caixa nem nas cotas', () => {
    const D = dados({ bova: i => 100 });
    const L = [{ data: '2024-01-02', tipo: 'compra', ativo: 'BOVA11', qtd: 10, preco: 100 },
        { data: '2024-03-01', tipo: 'bonificacao', ativo: 'BOVA11', qtd: 5, preco: 0 },
        { data: '2024-06-03', tipo: 'venda', ativo: 'BOVA11', qtd: 15, preco: 100 }];
    const R = C.calcular(D, L, { hoje: '2024-12-31' });
    perto(R.aportado, 1000); perto(R.metricas.total.nominal, 0.5, 1e-9);   // 5 ações a mais de graça = +50%
    assert(!R.avisos.some(a => a.includes('só tinha'))); perto(R.vendas[0].pm, 1000 / 15); perto(R.vendas[0].lucro, 500);
    const b = C.posicaoEm(D, L.slice(0, 2), '2024-04-01')[0]; perto(b.qtd, 15); perto(b.custo, 1000);
});
t('preço de tela: desfaz o ajuste de desdobramentos posteriores', () => {
    const D = dados({ bova: i => 100, desd: [['2024-03-01', 4]] });
    perto(C.precoTela(D, 'BOVA11', '2024-02-15'), 400); perto(C.precoTela(D, 'BOVA11', '2024-03-05'), 100);
    assert.strictEqual(C.precoTela(D, 'XXXX3', '2024-03-05'), null); assert.strictEqual(C.precoTela(D, 'BOVA11', '2010-01-01'), null);
});
console.log(falhas ? `\n${falhas} teste(s) falharam` : '\nTodos os testes passaram'); process.exit(falhas ? 1 : 0);
