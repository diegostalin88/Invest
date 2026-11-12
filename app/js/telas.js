// Telas novas do app único (fase 2 da remodelação, 12/11/2026): Início, Mercado, Laboratório e a ficha do ativo.
// Leem data/agente.json (resumo diário de mercado, < 100 KB) e o resultado da carteira (R, calculado pelo
// motor-carteira.js no index.html). Só descrevem: nada aqui é sinal de compra ou venda.
'use strict';
let AG = null;               // agente.json
let MERC = 'br';             // mercado escolhido no topo (br | us)
let ATIVO = null, abaAtivo = 'resumo', voltarPara = 'mercado';
try { MERC = localStorage.getItem('invest-mercado') === 'us' ? 'us' : 'br'; } catch (e) { }

async function carregarAgente() {
    try { const r = await fetch('data/agente.json', { cache: 'no-cache' }); if (!r.ok) throw new Error(r.status); AG = await r.json(); }
    catch (e) { AG = null; }
}
const mercadoAg = (m = MERC) => AG && AG.mercados ? AG.mercados[m] || null : null;
const nomeIndice = (m = MERC) => m === 'us' ? 'S&P 500 (SPY)' : 'Ibovespa (BOVA11)';
const moedaMerc = (m = MERC) => m === 'us' ? US$ : R$;
const pctN = (v, c = 1) => v === null || v === undefined ? '—' : pct(v, c);
const corN = (v) => v === null || v === undefined ? '' : cor(v);
const din = (txt) => `<span class="din">${txt}</span>`;   // valores que o botão de olho esconde

// ---------- topo: selo da data e mercado ----------
function desenharTopo() {
    const m = mercadoAg();
    const sel = document.getElementById('selo-dados');
    if (sel) {
        const d = m && m.saude ? m.saude.ultimoPregao : null;
        const velho = AG && AG.saude && AG.saude.dadosVelhos;
        sel.textContent = d ? `dados de ${dBR(d)}` : 'sem dados de mercado';
        sel.className = 'chip' + (velho || !d ? ' amarelo' : '');
    }
    document.querySelectorAll('[data-merc]').forEach(b => b.classList.toggle('ativa', b.dataset.merc === MERC));
}

// ---------- INÍCIO: como estão o mercado e o meu dinheiro? ----------
function semaforo(T) {
    if (!T) return ['', 'sem dados'];
    if (T.ambiente === 'tendência de alta') return ['verde', 'Tendência de alta'];
    if (T.ambiente === 'queda') return ['vermelho', 'Mercado em queda'];
    return ['amarelo', 'Misto'];
}
function cartaoTermometro(m, detalhes) {
    const T = m && m.termometro;
    if (!T) return `<div class="cartao"><h2>Termômetro do ${nomeIndice()}</h2><p class="mudo">Sem dados do índice nesta coleta.</p></div>`;
    const [c, txt] = semaforo(T);
    const lin = (r, v, cl = '') => `<div class="linha"><span>${r}</span><span class="v ${cl}">${v}</span></div>`;
    return `<div class="cartao">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><h2 style="margin:0">Termômetro do ${esc(T.nome || nomeIndice())}</h2><span class="chip ${c}">${txt}</span></div>
        <div class="peq mudo" style="margin-top:6px">12 meses ${pctN(T.ret12m)} · ${T.rendaFixa ? esc(T.rendaFixa.nome) + ' ' + pctN(T.rendaFixa.ret12m) : ''} · queda do topo ${pctN(T.quedaTopo ? -T.quedaTopo : 0)}</div>
        <details style="margin-top:8px"${detalhes ? ' open' : ''}><summary>Ver detalhes</summary>
            ${lin('Acima da média de 10 meses?', T.acimaMM10m === null ? '—' : T.acimaMM10m ? 'Sim' : 'Não', T.acimaMM10m ? 'alta' : 'baixa')}
            ${lin('Distância da média de 200 dias', pctN(T.distMM200), corN(T.distMM200))}
            ${lin('Queda desde o topo (52 semanas)', pctN(T.quedaTopo52 ? -T.quedaTopo52 : 0))}
            ${lin('Retorno 1 mês · 3 meses', `${pctN(T.ret1m)} · ${pctN(T.ret3m)}`)}
            ${lin('Volatilidade anualizada', pctN(T.vol, 0))}
            <p class="mini mudo" style="margin:8px 0 0">Descreve o mercado; não prevê. A regra da média de 10 meses foi testada como sinal e reprovada (veja Laboratório).</p>
        </details></div>`;
}
function alertasCarteira() {
    const al = [];
    if (R && !R.vazio) {
        const B = C.rebalancear(R, ESTADO.metas, 0);
        B.classes.filter(c => c.fora).forEach(c => al.push(['amarelo', `${c.nome} fora da faixa: ${nf(c.peso * 100, 1)}% para meta de ${nf(c.meta * 100, 1)}%.`, 'carteira']));
        const mes = hojeISO().slice(0, 7), ant = C.addDias(mes + '-01', -1).slice(0, 7);
        C.impostoMensal(R.vendas).filter(m => m.mes === ant || m.mes === mes).forEach(m => { const v = m.darfBolsa + m.impCripto; if (v > 0) al.push(['vermelho', `DARF de ${R$(v)} referente a ${m.mes.split('-').reverse().join('/')}, vence ${dBR(m.vencimento)}.`, 'ir']); });
        if (R.avisos && R.avisos.length) al.push(['amarelo', `${R.avisos.length} ${R.avisos.length > 1 ? 'pontos' : 'ponto'} da carteira para conferir.`, 'resumo']);
        const meus = new Set(R.posicoes.map(p => p.ativo));
        for (const mk of ['br', 'us']) {
            const m = mercadoAg(mk); if (!m) continue;
            (m.balancosProximos || []).filter(([, t]) => meus.has(t)).forEach(([d, t]) => al.push(['', `${t} divulga balanço em ${dBR(d)}.`, 'ativo:' + t + ':' + mk]));
            (m.vendidos || []).filter(([t, dias]) => meus.has(t) && dias >= 5).forEach(([t, dias]) => al.push(['amarelo', `${t}: posição vendida alta (${nf(dias, 1)} dias de volume).`, 'ativo:' + t + ':' + mk]));
        }
    }
    if (AG && AG.saude && AG.saude.dadosVelhos) al.unshift(['amarelo', `Dados de mercado com ${AG.saude.diasUteisDesdeUltimoPregao ?? '?'} dias úteis de atraso.`, '']);
    return al;
}
function telaInicio() {
    const el = document.getElementById('tela-inicio'); if (!el) return;
    const m = mercadoAg();
    let pat = `<div class="cartao"><div class="mudo peq">Patrimônio</div><div class="grande">—</div><p class="mudo peq">Lance seus aportes na aba Carteira para ver o patrimônio aqui.</p><button class="botao" data-aba="carteira" data-sub="lancar">Lançar</button></div>`;
    if (R && !R.vazio) {
        const M = R.metricas, p = M.m12 || M.total;
        pat = `<div class="cartao">
            <div style="display:flex;justify-content:space-between;align-items:center"><span class="mudo peq">Patrimônio hoje</span><button class="botao sec" id="btn-olho" style="padding:4px 10px" aria-label="Esconder valores">${document.body.classList.contains('oculto') ? '🙈' : '👁'}</button></div>
            <div class="grande">${din(R$(R.patrimonio))}</div>
            <div class="peq">Ganho ${din(`<span class="${cor(R.patrimonio - R.aportado)}">${R$(R.patrimonio - R.aportado)}</span>`)} · real ${din(`<span class="${cor(R.patrimonio - R.aportesCorrigidos)}">${R$(R.patrimonio - R.aportesCorrigidos)}</span>`)}</div>
            <div class="grade" style="margin-top:10px">
                <div class="dado"><div class="r">${M.m12 ? 'Carteira, 12 meses' : 'Carteira, desde o início'}</div><div class="v ${cor(p.nominal)}">${pct(p.nominal)}</div><div class="mini mudo">real ${pct(p.real)}</div></div>
                <div class="dado"><div class="r">Referência 1/3 no mesmo período</div><div class="v ${corN(p.ref)}">${pctN(p.ref)}</div><div class="mini mudo">CDI ${pct(p.cdi)} · IPCA ${pct(p.ipca)}</div></div>
            </div>
            <p class="mini mudo" style="margin:8px 0 0">Referência = 1/3 BOVA11 + 1/3 IVVB11 + 1/3 CDI, rebalanceada a cada trimestre. Compare sempre antes de agir.</p>
        </div>`;
    }
    const amp = m && m.amplitude;
    const al = alertasCarteira();
    el.innerHTML = `${pat}
        ${cartaoTermometro(m)}
        <div class="cartao"><h2>Amplitude do mercado</h2>${amp ? `<div class="grande" style="font-size:28px">${nf(amp.acimaMM200 * 100, 0)}%</div><div class="peq mudo">dos ${amp.papeis} papéis acompanhados estão acima da média de 200 dias</div>` : '<p class="mudo">Sem dados.</p>'}</div>
        <div class="cartao"><h2>Alertas</h2>${al.length ? al.map(([c, t, alvo]) => `<button class="item-alerta" ${alvo ? `data-alvo="${esc(alvo)}"` : ''}><span class="chip ${c}" style="margin-right:6px">•</span>${esc(t)}</button>`).join('') : '<p class="mudo peq">Nada pedindo atenção hoje.</p>'}</div>
        <div class="cartao"><h2>Analista (agente)</h2><p class="peq">Peça no Claude: <b>"analisa o mercado hoje"</b>, <b>"analisa PETR4"</b> ou <b>"revisa minha carteira"</b>. Ele lê o resumo do dia que este app publica.</p><p class="mini mudo" style="margin:0">Parecer não validado: o placar do agente começa a contar agora (Laboratório → Ideias testadas).</p></div>`;
}

// ---------- MERCADO: o que está acontecendo? ----------
const NOMES_LISTA = { altas: 'Maiores altas do dia', quedas: 'Maiores quedas do dia', maisNegociados: 'Mais negociados', longeDoTopo: 'Mais longe do topo', maisVolateis: 'Mais voláteis' };
function cartaoLista(titulo, itens, fmt, mk = MERC) {
    if (!itens || !itens.length) return '';
    return `<div class="cartao"><h2>${titulo}</h2><div class="carrossel">${itens.map(([t, v, extra]) => `<button class="mini-card" data-ativo="${esc(t)}" data-m="${mk}"><b>${esc(t)}</b><span>${fmt(v, extra)}</span></button>`).join('')}</div></div>`;
}
function telaMercado() {
    const el = document.getElementById('tela-mercado'); if (!el) return;
    const m = mercadoAg();
    if (!m) { el.innerHTML = `<div class="cartao vazio"><p class="mudo">Sem dados de mercado ${MERC === 'us' ? 'dos EUA' : 'do Brasil'} nesta coleta.</p></div>`; return; }
    const L = m.listas || {};
    const fP = (v) => `<span class="${corN(v)}">${pctN(v)}</span>`;
    const watch = (ESTADO.acompanhar || []).filter(Boolean);
    const W = (AG && AG.watchlist) || {};
    el.innerHTML = `
        ${cartaoLista(NOMES_LISTA.altas, L.altas, fP)}
        ${cartaoLista(NOMES_LISTA.quedas, L.quedas, fP)}
        ${cartaoLista(NOMES_LISTA.maisNegociados, L.maisNegociados, (v) => `${nf(v, 0)} mi`)}
        ${cartaoLista('Mais vendidos', m.vendidos, (d, v) => `${nf(d, 1)} dias${v !== null && v !== undefined ? ` · ${pctN(v / 100, 0)}` : ''}`)}
        ${cartaoLista(NOMES_LISTA.longeDoTopo, L.longeDoTopo, (v) => `<span class="baixa">${pctN(-v, 0)}</span>`)}
        ${cartaoLista(NOMES_LISTA.maisVolateis, L.maisVolateis, (v) => `${pctN(v, 0)} a.a.`)}
        <div class="cartao"><h2>Watchlist</h2>${watch.length ? watch.map(t => { const w = W[t] || (m.papeis || {})[t]; return `<button class="item-alerta" data-ativo="${esc(t)}" data-m="${W[t] && W[t].moeda === 'USD' ? 'us' : MERC}"><b>${esc(t)}</b> <span class="mudo">${w ? `${pctN(w.d1)} hoje · ${pctN(w.a1)} em 12 meses${w.alavancado ? ' · alavancado' : ''}` : 'sem dados'}</span></button>`; }).join('') : '<p class="mudo peq">Nenhum papel. Adicione em Carteira → Resumo → Acompanhando.</p>'}</div>
        <div class="cartao"><h2>Balanços nos próximos 14 dias</h2>${(() => { const b = m.balancosProximos || []; if (!b.length) return '<p class="mudo peq">Nenhum anunciado.</p>'; const it = ([d, t]) => `<button class="item-alerta" data-ativo="${esc(t)}" data-m="${MERC}">${dBR(d)} · <b>${esc(t)}</b></button>`; return b.slice(0, 8).map(it).join('') + (b.length > 8 ? `<details><summary class="mini mudo">ver todos (${b.length})</summary>${b.slice(8).map(it).join('')}</details>` : ''); })()}</div>
        <p class="mini mudo">Fonte: coleta do Invest (${m.saude.papeis} papéis${MERC === 'us' ? ', os 500 mais negociados' : ', Ibovespa'}). ${(m.saude.vendidos || {}).fonte ? `Vendidos: ${esc(m.saude.vendidos.fonte)} de ${dBR(m.saude.vendidos.data)}. ` : ''}Listas descrevem o dia; não são indicação.</p>`;
}

// ---------- FICHA DO ATIVO ----------
function buscarAtivo(txt) {
    const t = (txt || '').trim().toUpperCase().replace(/\.SA$/, ''); if (!t) return;
    for (const mk of [MERC, MERC === 'br' ? 'us' : 'br']) { const m = mercadoAg(mk); if (m && m.papeis && m.papeis[t]) return abrirAtivo(t, mk); }
    if ((AG && AG.watchlist && AG.watchlist[t]) || (DADOS.ativos && DADOS.ativos[t]) || (R && !R.vazio && R.posicoes.some(p => p.ativo === t))) return abrirAtivo(t, mercadoDoCodigo(t));
    toast(`${t} não está nos dados do app (Ibovespa, 500 mais negociados dos EUA, carteira e watchlist).`);
}
function mercadoDoCodigo(t) {
    const a = DADOS.ativos && DADOS.ativos[t];
    if (a && a.moeda) return a.moeda === 'USD' ? 'us' : 'br';
    if (t === 'BTC') return MERC;
    return /^[A-Z]{4}\d{1,2}$/.test(t) ? 'br' : 'us';
}
function abrirAtivo(t, mk) {
    const atual = document.querySelector('.tela.ativa'); if (atual && atual.id !== 'tela-ativo') voltarPara = atual.dataset.aba || 'mercado';
    ATIVO = { t, mk: mk || MERC }; abaAtivo = 'resumo'; telaAtivo(); mostrarTela('ativo');
}
function telaAtivo() {
    const el = document.getElementById('tela-ativo'); if (!el || !ATIVO) return;
    const { t, mk } = ATIVO, m = mercadoAg(mk);
    const p = (m && m.papeis && m.papeis[t]) || (AG && AG.watchlist && AG.watchlist[t]) || null;
    const pos = R && !R.vazio ? R.posicoes.find(x => x.ativo === t) : null;
    const serie = DADOS.ativos && DADOS.ativos[t];
    const fm = p && p.moeda === 'USD' ? US$ : moedaMerc(mk);
    const T = m && m.termometro;
    const vend = m && (m.vendidos || []).find(v => v[0] === t);
    const abas = [['resumo', 'Resumo'], ['indicadores', 'Indicadores'], ['vendidos', 'Vendidos'], ['posicao', 'Minha posição']];
    const lin = (r, v, cl = '') => `<div class="linha"><span>${r}</span><span class="v ${cl}">${v}</span></div>`;
    let corpo = '';
    if (abaAtivo === 'resumo') {
        corpo = p ? `${lin('Hoje', pctN(p.d1), corN(p.d1))}${lin('1 mês', pctN(p.m1), corN(p.m1))}${lin('12 meses', pctN(p.a1), corN(p.a1))}${T ? lin(`${esc(T.nome)} em 12 meses`, pctN(T.ret12m), corN(T.ret12m)) : ''}
            ${lin('Distância da média de 200 dias', pctN(p.mm200), corN(p.mm200))}${lin('Queda desde a máxima de 52 semanas', pctN(p.topo52 ? -p.topo52 : 0))}${lin('Volatilidade anualizada', pctN(p.vol, 0))}
            ${p.volFinMi !== undefined ? lin('Volume financeiro médio', `${nf(p.volFinMi, 1)} mi/dia`) : ''}${p.balanco ? lin('Próximo balanço', dBR(p.balanco)) : ''}
            ${p.alerta8k ? `<p class="aviso peq">⚠ Evento corporativo relevante recente (8-K). Confira no site de RI.</p>` : ''}
            ${serie ? `<div id="graf-ativo" style="margin-top:10px">${graficoAtivo(serie)}</div>` : `<p class="mini mudo">Gráfico completo deste papel: <a href="antigo/?mercado=${mk}" style="color:var(--acento)">app de análise</a>.</p>`}`
            : '<p class="mudo">Sem dados de mercado para este papel nesta coleta.</p>';
    } else if (abaAtivo === 'indicadores') {
        const f = (k, n, fmt) => p && p[k] !== undefined ? lin(n, fmt(p[k])) : '';
        const x = (v) => nf(v, 1), pc = (v) => pctN(v, 1);
        corpo = p ? `${p.setor ? lin('Setor', esc(p.setor)) : ''}${f('pl', 'P/L', x)}${f('pvp', 'P/VP', x)}${f('roe', 'ROE', pc)}${f('margem', 'Margem líquida', pc)}${f('cresc', 'Crescimento da receita', pc)}${f('divPl', 'Dívida / PL', x)}${f('lpa', 'LPA', x)}${f('vpa', 'VPA', x)}${f('dy', 'Dividend yield', pc)}
            ${pos || serie ? `<p class="mini mudo">Preço justo de Graham e Bazin: Carteira → Resumo → ficha (informação, <b>não testado</b>).</p>` : ''}
            <p class="mini mudo">Fundamentos vêm do Yahoo e da SEC/CVM e podem estar defasados. Seleção por fundamentos foi testada e reprovada no Invest: use como contexto.</p>` : '<p class="mudo">Sem indicadores.</p>';
    } else if (abaAtivo === 'vendidos') {
        const v = p && p.vendido;
        corpo = v || vend ? `${lin('Dias de volume para zerar a posição vendida', nf((v && v.dias) ?? vend[1], 1))}${v && v.variacaoPct !== undefined ? lin('Variação desde a última apuração', pctN(v.variacaoPct / 100, 0)) : ''}
            <p class="mini mudo">${mk === 'us' ? 'Short interest da FINRA (quinzenal).' : 'Aluguel de ações em aberto na B3.'} Muita posição vendida aumenta a volatilidade nos dois sentidos; não é sinal de alta.</p>` : '<p class="mudo">Sem posição vendida relevante registrada.</p>';
    } else {
        corpo = pos ? `${lin('Quantidade', qf(pos.qtd))}${lin('Preço médio', din(pos.conta === 'EUA' ? US$(pos.pmUSD) : R$(pos.pm)))}${lin('Vale hoje', din(R$(pos.valor)))}${lin('Resultado', din(`<span class="${cor(pos.resultado)}">${R$(pos.resultado)} (${pct(pos.resultadoPct)})</span>`))}${lin('Peso na carteira', pct(pos.peso, 1).replace('+', ''))}
            <button class="botao sec cheio" data-aba="carteira" data-sub="lancar" style="margin-top:8px">Lançar compra ou venda</button>` : '<p class="mudo">Você não tem este papel na carteira.</p>';
    }
    el.innerHTML = `<button class="botao sec" data-voltar style="padding:6px 12px;margin-bottom:10px">← Voltar</button>
        <div class="cartao"><div class="mudo peq">${mk === 'us' ? 'EUA' : 'Brasil'}${pos ? ' · na sua carteira' : ''}</div>
            <div style="display:flex;justify-content:space-between;align-items:baseline;gap:10px"><h2 style="margin:0;font-size:24px">${esc(t)}</h2><span class="grande" style="font-size:24px">${p && p.p !== undefined ? fm(p.p) : serie && serie.fech.length ? (serie.moeda === 'USD' ? US$ : R$)(serie.fech[serie.fech.length - 1]) : '—'}</span></div>
            ${p ? `<div class="peq"><span class="${corN(p.d1)}">${pctN(p.d1)} hoje</span> · 12 meses <span class="${corN(p.a1)}">${pctN(p.a1)}</span>${T ? ` × índice ${pctN(T.ret12m)}` : ''}</div>` : ''}
        </div>
        <div class="abas">${abas.map(([k, n]) => `<button data-aba-ativo="${k}" class="${abaAtivo === k ? 'ativa' : ''}">${n}</button>`).join('')}</div>
        <div class="cartao">${corpo}</div>`;
}
function graficoAtivo(a) {
    const n = a.fech.length, k = Math.max(0, n - 260), v = a.fech.slice(k), d = a.datas.slice(k);
    const min = Math.min(...v), max = Math.max(...v), W = 320, H = 120;
    const pts = v.map((x, i) => `${(i / (v.length - 1 || 1) * W).toFixed(1)},${(H - (x - min) / (max - min || 1) * H).toFixed(1)}`).join(' ');
    return `<svg viewBox="0 0 ${W} ${H + 14}" width="100%" role="img" aria-label="Preço em 1 ano"><polyline fill="none" stroke="var(--acento)" stroke-width="1.6" points="${pts}"/><text x="0" y="${H + 12}">${dBR(d[0])}</text><text x="${W}" y="${H + 12}" text-anchor="end">${dBR(d[d.length - 1])}</text></svg><div class="mini mudo">Último ano, em ${a.moeda === 'USD' ? 'dólares' : 'reais'}.</div>`;
}

// ---------- LABORATÓRIO: o que eu estou estudando? ----------
const IDEIAS = [
    ['Estratégia técnica do app (score, 31 estratégias, Relatório)', 'congelada', 'Perdeu para o índice em 04/11/2026. Teste para frente até 04/11/2027.', 'congelamento.md'],
    ['A · Momento de 12 meses', 'reprovada', 'EUA com queda de 34% contra 8% do índice; Brasil perdeu do BOVA11.', 'hipotese-momento-tendencia.md'],
    ['B · Tendência no índice (média de 10 meses)', 'reprovada', 'EUA perde em 2010–2026; Brasil perde do CDI.', 'hipotese-momento-tendencia.md'],
    ['Controle de exposição pela volatilidade', 'reprovada', 'Igual a uma exposição fixa menor.', null],
    ['C · Seleção por fundamentos (EUA e Brasil)', 'reprovada', 'Não confirmou fora da amostra.', 'hipotese-fundamentos.md'],
    ['D · Surpresa do balanço', 'só informação', 'Aprovada com ressalvas; a confirmação falhou.', 'hipotese-deriva-confirmacao.md'],
    ['Q-BR · Qualidade (ROE + passivo/ativo)', 'reprovada', 'Falhou em 2012–2019.', 'hipotese-qualidade-brasil.md'],
    ['H · ETFs de dividendos no lugar do índice', 'reprovada', 'Nenhum substitui o índice.', 'hipotese-holding-dividendos.md'],
    ['Opções O1 a O7 (travas, strangle, wheel, box, VRP…)', 'reprovada', 'Todas reprovadas; nada de opções na carteira.', 'opcoes/relatorio-testes.md'],
    ['K · Regras de trade em cripto', 'reprovada', 'Não vencem o acaso.', 'hipotese-cripto.md'],
    ['5% de BTC na carteira 1/3', 'acompanhar', 'Passou nos critérios, mas o ganho se concentra em 2018–21. Só para frente, sem dinheiro real.', 'hipotese-cripto.md'],
    ['Queda ≥ 30% + estratégia Otimista', 'reprovada', 'Cenário sem vantagem no Brasil e nos EUA.', 'cenario-queda-reversao.md'],
    ['Agente analista (parecer a favor / contra a tese)', 'em teste', 'Placar com critérios escritos antes: 60 pareceres com 120 pregões.', 'protocolo-agente.md'],
];
function telaLab() {
    const el = document.getElementById('tela-lab'); if (!el) return;
    const chip = { reprovada: 'vermelho', congelada: 'amarelo', 'só informação': '', acompanhar: 'verde', 'em teste': 'amarelo' };
    const placar = (mk) => { const m = mercadoAg(mk), P = m && m.testeParaFrente; if (!P) return `<div class="linha"><span>${mk === 'us' ? 'EUA' : 'Brasil'}</span><span class="v mudo">sem diário</span></div>`;
        return `<div class="linha"><span>${mk === 'us' ? 'EUA' : 'Brasil'}<br><span class="mini mudo">desde ${dBR(P.inicio)} · ${P.abertos} abertos${P.regrasDesligadas.length ? ` · ${P.regrasDesligadas.length} regras desligadas` : ''}</span></span><span class="v">${P.fechados} / ${P.metaFechados} fechados<br><span class="mini">${P.retMedio !== undefined ? `média ${pct(P.retMedio)} × índice ${pctN(P.indiceMesmasDatas)}` : 'sem fechados'}</span></span></div>`; };
    el.innerHTML = `<div class="cartao"><h2>Teste para frente</h2>
            <p class="peq mudo" style="margin-top:0">Estratégia técnica congelada, medida contra o índice até ${dBR('2027-11-04')}. Reprova se falhar qualquer critério.</p>
            ${placar('br')}${placar('us')}
            <p class="mini mudo" style="margin:8px 0 0">5% de BTC na carteira 1/3: acompanhe em Carteira → Resumo → Comparação ("referência com BTC").</p></div>
        <div class="cartao congelado"><h2>Estratégia técnica (congelada)</h2>
            <p class="peq"><b>Perdeu para o índice em 04/11/2026.</b> Ranking, simulação, backtest, walk-forward, screener, correlação e relatório continuam abertos só para o teste para frente. Não é recomendação.</p>
            <a class="botao sec cheio" href="antigo/?mercado=${MERC}">Abrir as ferramentas congeladas</a></div>
        <div class="cartao"><h2>Ideias testadas</h2>
            <p class="peq mudo" style="margin-top:0">Cada ideia teve as regras escritas antes do teste. Reprovada não se reabre com outros parâmetros.</p>
            ${IDEIAS.map(([n, v, r, doc]) => `<div class="linha"><span>${esc(n)}<br><span class="mini mudo">${esc(r)}</span>${doc ? ` <a class="mini" href="docs/${doc}" style="color:var(--acento)">registro</a>` : ''}</span><span class="v"><span class="chip ${chip[v] || ''}">${v}</span></span></div>`).join('')}</div>
        <div class="cartao"><h2>Estudos</h2><p class="peq" style="margin:0">Opções (O1 a O7), cripto e a volatilidade dos papéis quânticos: registros em <a href="docs/opcoes/relatorio-testes.md" style="color:var(--acento)">opções</a> e <a href="docs/hipotese-cripto.md" style="color:var(--acento)">cripto</a>.</p></div>`;
}

function desenharNovas() { desenharTopo(); telaInicio(); telaMercado(); telaLab(); if (ATIVO) telaAtivo(); }
