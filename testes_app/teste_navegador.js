// Teste do app em navegador real (Playwright + Chromium).
// USO: node testes_app/teste_navegador.js <url_base_do_site_exemplo> [pasta_screenshots]
// O site de exemplo é gerado por testes_app/gerar_site_exemplo.py e servido com `python -m http.server`.
// Se a máquina não alcança os CDNs (Tailwind, Plotly, SheetJS, FileSaver), defina LIBS_LOCAIS=<pasta> com
// tailwind.js, plotly.min.js, xlsx.full.min.js e FileSaver.min.js baixados do npm: o teste serve essas cópias.
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const LIBS = process.env.LIBS_LOCAIS;
const CDN_LOCAL = {
    'cdn.tailwindcss.com': 'tailwind.js',
    'cdn.plot.ly': 'plotly.min.js',
    'xlsx.full.min.js': 'xlsx.full.min.js',
    'FileSaver.min.js': 'FileSaver.min.js',
    'lightweight-charts': 'lightweight-charts.standalone.production.js',
};
// O widget do TradingView é substituído por um dublê que só registra o símbolo pedido.
const TV_FALSO = 'window.TradingView={widget:function(o){window.__tvSimbolo=o.symbol;document.getElementById(o.container_id).textContent="TV:"+o.symbol;}};';

const BASE = (process.argv[2] || 'http://127.0.0.1:8765/').replace(/\/?$/, '/');
const SHOTS = process.argv[3] || '.';
// Aviso conhecido e aceito: o Tailwind via CDN avisa que não deve ser usado em produção.
const IGNORAR = [/cdn\.tailwindcss\.com should not be used in production/i, /browser build of Tailwind CSS should not be used in production/i];

let falhas = 0;
function ok(cond, msg) { console.log(`${cond ? '✅' : '❌'} ${msg}`); if (!cond) falhas++; }

async function abrir(browser, url, bloquearManifesto = false, viewport = { width: 1440, height: 1000 }) {
    const page = await browser.newPage({ viewport });
    const erros = [];
    page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') erros.push(`${m.type()}: ${m.text()}`); });
    page.on('pageerror', e => erros.push(`pageerror: ${e.message}`));
    page.on('dialog', d => { erros.push(`dialog inesperado: ${d.message()}`); d.dismiss(); });
    if (LIBS) {
        await page.route(/^https:\/\/(cdn\.tailwindcss\.com|cdn\.plot\.ly|cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net)\//, r => {
            const chave = Object.keys(CDN_LOCAL).find(k => r.request().url().includes(k));
            if (!chave) return r.abort();
            r.fulfill({ status: 200, contentType: 'application/javascript', body: fs.readFileSync(path.join(LIBS, CDN_LOCAL[chave])) });
        });
        await page.route('https://s3.tradingview.com/tv.js', r => r.fulfill({ status: 200, contentType: 'application/javascript', body: TV_FALSO }));
        await page.route(/^https:\/\/fonts\.(googleapis|gstatic)\.com\//, r => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));
    }
    if (bloquearManifesto) await page.route(bloquearManifesto === true ? '**/data/manifest.json' : bloquearManifesto, r => r.fulfill({ status: 404, body: 'not found' }));
    await page.goto(url);
    return { page, erros };
}

(async () => {
    const proxy = process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY, bypass: '127.0.0.1,localhost' } : undefined;
    const browser = await chromium.launch(proxy ? { proxy } : {});

    // 1) Carregamento automático + Screener + Módulo 6 sem nenhum clique
    const { page, erros } = await abrir(browser, BASE);
    await page.waitForSelector('#screener-results-container table', { timeout: 120000 });
    ok(true, 'carregou sozinho e rodou o Screener automaticamente');
    const nLinhas = await page.$$eval('#screener-results-container tbody tr', trs => trs.length);
    ok(nLinhas > 0, `shortlist com ${nLinhas} ativos`);
    const visiveis = await page.$$eval('#screener-results-container tbody tr', trs => trs.filter(t => t.offsetParent !== null).length);
    ok(nLinhas <= 10 || visiveis === 10, `lista começa com os 10 primeiros (${visiveis} de ${nLinhas})`);
    if (nLinhas > 10) {
        await page.click('#screener-mostrar-todos');
        ok(await page.$$eval('#screener-results-container tbody tr', trs => trs.filter(t => t.offsetParent !== null).length) === nLinhas, '"Mostrar todos" abre a lista inteira');
    }
    await page.click('#sec-vetor h3');
    ok(await page.isHidden('#screener-results-container'), 'Vetor de Ativos Aprovados minimiza pelo título');
    await page.click('#sec-vetor h3');
    ok(await page.isVisible('#screener-results-container'), 'e abre de novo');
    const banner = await page.textContent('#data-freshness-banner');
    ok(/Dados até \d{2}\/\d{2}\/\d{4}/.test(banner) && /Fundamentos de \d+ ativos/.test(banner) && /Atualizado em/.test(banner), `cabeçalho de status: "${banner.trim()}"`);
    ok(await page.isHidden('#load-progress'), 'barra de progresso some ao terminar');
    const shortlist = await page.$$eval('#screener-results-container tbody tr td:first-child b', tds => tds.map(td => td.textContent.trim()));
    ok(shortlist.includes('CRIT'), 'ativo crítico (CRIT) passou no Screener técnico');

    await page.waitForSelector('#melhores-opcoes-resumo .result-metric', { timeout: 60000 });
    const topResumo = await page.$$eval('#melhores-opcoes-resumo .result-metric .text-lg', els => els.map(e => e.textContent.trim()));
    ok(topResumo.length > 0 && !topResumo.includes('CRIT'), `"Melhores Opções" visível ao abrir, sem o CRIT: ${topResumo.join(', ')}`);
    await page.screenshot({ path: path.join(SHOTS, 'app_inicio.png'), fullPage: true });

    // Fundamentos no Screener e painel "Por que foi selecionado"
    const cab = await page.$$eval('#screener-results-container thead th', ths => ths.map(t => t.textContent.trim()));
    ok(cab.includes('Fund.') && cab.includes('P/L') && cab.includes('ROE'), `Screener mostra fundamentos: ${cab.join(' | ')}`);
    const valorCard = (await page.textContent('#melhores-opcoes-resumo [data-explicar] .value')).trim();
    const tickerCard = (await page.textContent('#melhores-opcoes-resumo [data-explicar] .text-lg')).trim();
    await page.click('#melhores-opcoes-resumo [data-explicar]');
    await page.waitForSelector('#explicacao-modal:not(.hidden)', { timeout: 5000 });
    const corpo = await page.textContent('#explicacao-corpo');
    ok(/Por que foi selecionado/.test(await page.textContent('#explicacao-titulo')) && (await page.textContent('#explicacao-titulo')).includes(tickerCard), `clicar no card ${tickerCard} abre o "por quê"`);
    ok(/Score técnico/.test(corpo) && /Nota fundamentalista/.test(corpo) && /P\/L/.test(corpo), 'painel mostra técnica e fundamentos, critério a critério');
    ok(corpo.includes(`= ${valorCard}`), `painel fecha a conta do Score Combinado (${valorCard})`);
    await page.screenshot({ path: path.join(SHOTS, 'app_por_que.png'), fullPage: false });
    await page.click('#explicacao-fechar');
    ok(await page.isHidden('#explicacao-modal'), 'painel fecha no ✕');
    await page.click('#screener-results-container tbody tr [data-explicar]');
    ok(await page.isVisible('#explicacao-modal'), 'botão 🔎 do Screener abre o painel');
    await page.keyboard.press('Escape');
    ok(await page.isHidden('#explicacao-modal'), 'painel fecha com Esc');

    await page.click('button[data-tab="fundamentals"]');
    const topMod6 = await page.$$eval('#fundamentals-results-container .result-metric .text-lg', els => els.map(e => e.textContent.trim()));
    ok(topMod6.length > 0 && !topMod6.includes('CRIT'), 'Módulo 6: CRIT fora das "Melhores Opções"');
    const linhaCrit = await page.$$eval('#fundamentals-results-container tbody tr', trs => (trs.find(tr => tr.querySelector('td:nth-child(2) b')?.textContent === 'CRIT') || {}).innerText || '');
    ok(/excluído do ranking: evento corporativo crítico/.test(linhaCrit), 'Módulo 6: linha do CRIT marcada como excluída por evento crítico');
    await page.screenshot({ path: path.join(SHOTS, 'app_modulo6.png'), fullPage: false });

    // B. Screener de Estratégias (motor da v14) roda sob demanda e não mexe no shortlist do Módulo 1
    await page.click('button[data-tab="screener"]');
    const antes = await page.$$eval('#screener-results-container tbody tr', t => t.length);
    await page.selectOption('#confluence-select', 'all');
    await page.click('#run-filter-btn');
    await page.waitForFunction(() => /B\. Sinais Isolados \(Todos\): \d+ ativo/.test(document.getElementById('estrategias-results').textContent), null, { timeout: 60000 });
    const nB = await page.$$eval('#estrategias-results tbody tr', t => t.length);
    ok(nB > 0, `B. Screener de Estratégias ("Sinais Isolados"): ${nB} ativos`);
    await page.selectOption('#confluence-select', 'volume_strength');
    await page.click('#run-filter-btn');
    await page.waitForFunction(() => /B\. Força do Volume/.test(document.getElementById('estrategias-results').textContent), null, { timeout: 60000 });
    const volB = await page.$$eval('#estrategias-results tbody tr td:first-child', t => t.map(x => x.textContent.trim()));
    ok(volB.includes('CRIT') && volB.includes('BOA1'), `B. "Força do Volume" pega os ativos com spike de volume: ${volB.join(', ')}`);
    // "Otimista": o sinal IFR_Cross_SMA_Up agora existe, então a estratégia consegue disparar
    const otim = await page.evaluate(() => {
        const { allData, getIndicatorParameters, v14_precomputarIndicadores, v14_analisarSinais, estrategiasV14 } = window.investDebug;
        const params = getIndicatorParameters(); let diasIfr = 0, diasOtimista = 0;
        for (const t of Object.keys(allData)) {
            const d = allData[t]; if (d.close.length < 201) continue;
            const ind = v14_precomputarIndicadores(d, params);
            for (let i = 201; i < d.close.length; i++) {
                const b = v14_analisarSinais(d, ind, i).buy;
                if (b.IFR_Cross_SMA_Up) diasIfr++;
                if (estrategiasV14.optimistic_buy.buy.every(k => b[k])) diasOtimista++;
            }
        }
        return { diasIfr, diasOtimista };
    });
    ok(otim.diasIfr > 0 && otim.diasOtimista > 0, `"Otimista" dispara no histórico (IFR cruzou a média em ${otim.diasIfr} dias; os 3 sinais juntos em ${otim.diasOtimista})`);
    await page.selectOption('#confluence-select', 'optimistic_buy');
    await page.click('#run-filter-btn');
    await page.waitForFunction(() => /B\. Otimista \(ADL\+Mom\+IFR\): \d+ ativo/.test(document.getElementById('estrategias-results').textContent), null, { timeout: 60000 });
    ok(true, `B. "Otimista" roda: ${(await page.textContent('#estrategias-results h4')).trim()}`);
    ok((await page.$$eval('#screener-results-container tbody tr', t => t.length)) === antes, 'B não altera o shortlist do motor de pontuação');
    ok(await page.$('#param-blacklist') === null, 'Guilhotina Macro (Blacklist) removida');
    await page.screenshot({ path: path.join(SHOTS, 'app_screener_estrategias.png'), fullPage: false });

    // Botões continuam funcionando: mudar filtro não roda sozinho; clicar em Executar roda de novo
    await page.click('button[data-tab="screener"]');
    await page.fill('#filter-adtv', '999999999999');
    await page.waitForTimeout(500);
    ok((await page.$$eval('#screener-results-container tbody tr', t => t.length)) === nLinhas, 'mudar filtro não re-executa sozinho');
    await page.click('#run-strategy-scoring-btn');
    await page.waitForFunction(() => /Nenhum ativo sobreviveu/.test(document.getElementById('screener-results-container').textContent), null, { timeout: 60000 });
    ok(true, 'botão "Executar Motor de Rastreio" roda de novo com o filtro novo');

    // Backtest e Walk-Forward continuam funcionando
    await page.click('button[data-tab="backtest"]');
    await page.selectOption('#ticker-select', 'BOA1');
    await page.click('#run-backtest-btn');
    await page.waitForSelector('#backtest-results-container .result-metric', { timeout: 30000 });
    ok(true, 'Backtest roda');
    await page.waitForFunction(() => /Robusta|Mais ou menos|Frágil/.test((document.getElementById('bt-robustez') || {}).textContent || ''), null, { timeout: 30000 });
    const livros = await page.textContent('#bt-livros');
    ok(/Monte Carlo/.test(livros) && /Perfil do papel/.test(livros) && /sobrevivência/.test(livros), 'Backtest: Monte Carlo, perfil do papel, robustez e aviso de sobrevivência');
    const opcoes = await page.evaluate(() => {
        const I = window.investDebug; const d = I.allData['BOA1']; const base = I.getBacktestRiskParams();
        const r0 = I.runCoreBacktest(d, base);
        const r1 = I.runCoreBacktest(d, { ...base, alvoAtr: 2, saidaDias: 10 });
        const r2 = I.runCoreBacktest(d, { ...base, precoMin: 1e9 });
        const fechados = r1.saidas.stop + r1.saidas.alvo + r1.saidas.tempo;
        return { padraoSoStop: r0.saidas.alvo === 0 && r0.saidas.tempo === 0, somaBate: fechados === r1.trades, usouAlvoOuTempo: r1.saidas.alvo + r1.saidas.tempo > 0, filtroPreco: r2.trades === 0 };
    });
    ok(opcoes.padraoSoStop && opcoes.somaBate && opcoes.usouAlvoOuTempo && opcoes.filtroPreco, `Backtest: opções dos livros (alvo, tempo, preço mínimo) funcionam e ficam desligadas por padrão ${JSON.stringify(opcoes)}`);
    await page.click('#bt-carteira-btn');
    await page.waitForFunction(() => /Teste na carteira/.test(document.getElementById('bt-carteira').textContent), null, { timeout: 120000 });
    ok((await page.$$('#bt-carteira tbody tr')).length === 6, 'Backtest: teste na carteira compara 6 regras (inclui Tendência + recuo)');
    await page.click('button[data-tab="walkforward"]');
    await page.click('#run-walkforward-btn');
    await page.waitForSelector('#walkforward-summary .result-metric', { timeout: 30000 });
    ok(true, 'Walk-Forward roda');

    // Módulo 2: gráfico interativo com sinais do app + aba TradingView
    await page.click('button[data-tab="screener"]');
    await page.fill('#filter-adtv', '50000000');
    await page.click('#run-strategy-scoring-btn');
    await page.waitForSelector('#screener-results-container table', { timeout: 60000 });
    await page.click('button[data-tab="analysis"]');
    await page.selectOption('#ticker-select', 'BOA1');
    await page.waitForSelector('#analysis-chart canvas', { timeout: 30000 });
    const nGraf = await page.evaluate(() => window.investDebug.graficos.length);
    ok(nGraf === 2, `gráfico desenhado: preço + painel do IFR (${nGraf} gráficos)`);
    const leg = await page.textContent('#chart-legenda');
    ok(/F \d/.test(leg) && /Score \d/.test(leg), `legenda com preço e score do motor: "${leg.trim().slice(0, 120)}…"`);
    ok(/Fundamentos/.test(await page.textContent('#chart-fundamentos')) && /\d\/5/.test(await page.textContent('#chart-fundamentos')), 'quadro de fundamentos ao lado do gráfico');
    await page.check('.indicator-cb[value="MACD"]');
    ok(await page.evaluate(() => window.investDebug.graficos.length) === 3, 'ligar MACD adiciona um painel');
    await page.click('.periodo-btn[data-meses="0"]');
    await page.screenshot({ path: path.join(SHOTS, 'app_grafico.png'), fullPage: false });
    const antesNav = await page.inputValue('#ticker-select');
    await page.click('#next-chart-btn');
    ok(await page.inputValue('#ticker-select') !== antesNav && /no shortlist/.test(await page.textContent('#chart-ticker-label')), 'botão > anda pelo shortlist');
    await page.click('#chart-fundamentos [data-explicar]');
    ok(await page.isVisible('#explicacao-modal'), 'quadro de fundamentos abre o "por quê"');
    await page.click('#explicacao-fechar');
    await page.selectOption('#ticker-select', 'BOA1');
    await page.click('.grafico-modo-btn[data-modo="tv"]');
    await page.waitForFunction(() => /TV:BOA1/.test(document.getElementById('tv-widget').textContent), null, { timeout: 15000 });
    ok(true, 'aba TradingView abre o widget com o ativo escolhido');
    await page.click('.grafico-modo-btn[data-modo="app"]');
    await page.waitForSelector('#analysis-chart canvas', { timeout: 30000 });
    ok(await page.isHidden('#grafico-tv'), 'volta para o gráfico com sinais do app');

    // PWA: service worker registrado e sem nenhum arquivo de dados no cache
    await page.evaluate(() => navigator.serviceWorker.ready);
    await page.reload();
    await page.waitForSelector('#screener-results-container table', { timeout: 120000 });
    const pwa = await page.evaluate(async () => {
        const urls = [];
        for (const nome of await caches.keys()) for (const req of await (await caches.open(nome)).keys()) urls.push(req.url);
        return { controlado: !!navigator.serviceWorker.controller, urls };
    });
    ok(pwa.controlado && pwa.urls.length > 0 && !pwa.urls.some(u => u.includes('/data/')),
       `PWA: service worker ativo; cache só com o app (${pwa.urls.length} arquivos, nenhum de data/)`);

    const errosReais = erros.filter(e => !IGNORAR.some(r => r.test(e)));
    ok(errosReais.length === 0, `console sem erros (além do aviso do Tailwind)${errosReais.length ? ': ' + errosReais.join(' | ') : ''}`);
    await page.close();

    // 2) Mercado Brasil (IBOVESPA): troca pelo botão, lembra a escolha, moeda e volume mínimo em R$
    const br = await abrir(browser, BASE);
    await br.page.waitForSelector('#screener-results-container table', { timeout: 120000 });
    ok(/EUA \(Nasdaq\/NYSE\)/.test(await br.page.textContent('#data-freshness-banner')), 'abre nos EUA por padrão');
    await Promise.all([br.page.waitForURL(/mercado=br/), br.page.click('.mercado-btn[data-mercado="br"]')]);
    await br.page.waitForFunction(() => /Brasil \(IBOVESPA\)/.test(document.getElementById('data-freshness-banner').textContent), null, { timeout: 120000 });
    const bannerBr = await br.page.textContent('#data-freshness-banner');
    ok(/Brasil \(IBOVESPA\)/.test(bannerBr) && /Dados até/.test(bannerBr), `Brasil: cabeçalho "${bannerBr.trim()}"`);
    const tickersBr = await br.page.$$eval('#ticker-select option', o => o.map(x => x.value));
    ok(tickersBr.includes('PETR4') && !tickersBr.includes('CRIT'), `Brasil: só ativos do IBOVESPA (${tickersBr.length})`);
    ok(await br.page.inputValue('#filter-adtv') === '10000000' && (await br.page.textContent('.moeda-simbolo')) === 'R$', 'Brasil: volume mínimo padrão R$ 10 mi');
    ok(await br.page.getAttribute('.mercado-btn[data-mercado="br"]', 'aria-pressed') === 'true', 'Brasil: botão marcado');
    await br.page.screenshot({ path: path.join(SHOTS, 'app_brasil.png'), fullPage: false });
    await br.page.click('button[data-tab="backtest"]');
    await br.page.selectOption('#ticker-select', 'PETR4');
    await br.page.click('#run-backtest-btn');
    await br.page.waitForSelector('#backtest-results-container .result-metric', { timeout: 30000 });
    ok(/R\$/.test(await br.page.textContent('#backtest-results-container')), 'Brasil: Backtest em reais');
    await br.page.click('button[data-tab="analysis"]');
    await br.page.click('.grafico-modo-btn[data-modo="tv"]');
    await br.page.waitForFunction(() => /TV:BMFBOVESPA:PETR4/.test(document.getElementById('tv-widget').textContent), null, { timeout: 15000 });
    ok(true, 'Brasil: TradingView com BMFBOVESPA:PETR4');
    await br.page.goto(BASE);   // sem ?mercado: lembra a última escolha
    await br.page.waitForFunction(() => /Brasil \(IBOVESPA\)/.test(document.getElementById('data-freshness-banner').textContent), null, { timeout: 120000 });
    ok(/Brasil \(IBOVESPA\)/.test(await br.page.textContent('#data-freshness-banner')), 'lembra o mercado escolhido ao reabrir');
    await Promise.all([br.page.waitForURL(/mercado=us/), br.page.click('.mercado-btn[data-mercado="us"]')]);
    await br.page.waitForSelector('#screener-results-container table', { timeout: 120000 });
    ok(/EUA/.test(await br.page.textContent('#data-freshness-banner')) && await br.page.inputValue('#filter-adtv') === '50000000', 'volta para os EUA (US$ 50 mi)');
    const errosBr = br.erros.filter(e => !IGNORAR.some(r => r.test(e)));
    ok(errosBr.length === 0, `console sem erros na troca de mercado${errosBr.length ? ': ' + errosBr.join(' | ') : ''}`);
    await br.page.close();

    // Celular: casca nova (Início / Ranking / Testes / Mais), tela do ativo e gráfico em tela cheia
    const cel = await abrir(browser, BASE + '?mercado=br', false, { width: 390, height: 844 });
    await cel.page.waitForSelector('#am-top .am-linha', { timeout: 120000 });
    ok(await cel.page.isVisible('.am-nav') && await cel.page.isHidden('#tabs'), 'celular: barra de baixo com Início / Ranking / Testes / Mais');
    ok(/Brasil/.test(await cel.page.textContent('#am-sub')) && (await cel.page.$$('#am-melhores .am-opcao')).length > 0, 'celular: Início com data dos dados, clima e Melhores Opções');
    const larg = await cel.page.evaluate(() => ({ doc: document.documentElement.scrollWidth, sw: document.getElementById('market-switch').getBoundingClientRect().right }));
    ok(larg.doc <= 390 && larg.sw <= 390, `celular: sem rolagem lateral (${JSON.stringify(larg)})`);
    await cel.page.screenshot({ path: path.join(SHOTS, 'celular_inicio.png'), fullPage: false });
    await cel.page.click('.am-nav [data-ir-pagina="ranking"]');
    const nRank = await cel.page.$$eval('#am-ranking .am-linha', l => l.length);
    ok(nRank > 0, `celular: Ranking com ${nRank} linhas`);
    await cel.page.fill('#am-busca', 'PETR');
    ok((await cel.page.$$eval('#am-ranking .am-linha', l => l.map(x => x.dataset.ativo))).includes('PETR4'), 'celular: busca acha PETR4');
    await cel.page.fill('#am-busca', '');
    await cel.page.click('#am-abrir-filtros');
    ok(await cel.page.isVisible('#filter-adtv'), 'celular: filtros num painel que sobe de baixo');
    await cel.page.fill('#filter-adtv', '0');
    await cel.page.click('#am-aplicar-filtros');
    await cel.page.waitForFunction(() => /aprovados/.test(document.getElementById('am-ranking-info').textContent), null, { timeout: 60000 });
    ok(true, 'celular: "Aplicar" roda o ranking de novo');
    // Tela do ativo
    await cel.page.click('#am-ranking .am-linha');
    await cel.page.waitForSelector('#am-ativo.aberta #am-mini canvas', { timeout: 15000 });
    ok(/R\$/.test(await cel.page.textContent('#am-ativo-cab')), 'celular: tela do ativo com preço em R$');
    const toque = await cel.page.evaluate(() => { const r = document.getElementById('am-mini-toque').getBoundingClientRect(); const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return el && el.id; });
    ok(toque === 'am-mini-toque', 'celular: gráfico compacto não prende o dedo (camada de toque por cima)');
    await cel.page.waitForTimeout(400);
    await cel.page.screenshot({ path: path.join(SHOTS, 'celular_ativo.png'), fullPage: false });
    await cel.page.click('#am-abas [data-aba="tecnica"]');
    ok(/Score técnico/.test(await cel.page.textContent('#am-aba-conteudo')), 'celular: aba Técnica explica o score');
    await cel.page.click('#am-abas [data-aba="fundamentos"]');
    ok(/Nota fundamentalista/.test(await cel.page.textContent('#am-aba-conteudo')), 'celular: aba Fundamentos');
    await cel.page.click('#am-abas [data-aba="plano"]');
    const plano = await cel.page.textContent('#am-aba-conteudo');
    ok(/(Em operação|Sinal de entrada hoje|Sem sinal de entrada hoje)/.test(plano) && /Suporte mais próximo/.test(plano) && /Fator de lucro/.test(plano), 'celular: aba Plano com sinal de hoje, stops, suporte e histórico');
    await cel.page.waitForTimeout(300);
    await cel.page.screenshot({ path: path.join(SHOTS, 'celular_plano.png'), fullPage: false });
    // Gráfico em tela cheia
    await cel.page.click('#am-abrir-grafico');
    await cel.page.waitForSelector('#am-grafico.aberta #analysis-chart canvas', { timeout: 30000 });
    const altG = await cel.page.evaluate(() => document.getElementById('analysis-chart').getBoundingClientRect().height);
    ok(altG > 300, `celular: gráfico em tela cheia (${Math.round(altG)} px de altura)`);
    await cel.page.waitForTimeout(400);
    await cel.page.screenshot({ path: path.join(SHOTS, 'celular_grafico.png'), fullPage: false });
    await cel.page.goBack();
    ok(await cel.page.isHidden('#am-grafico') && await cel.page.isVisible('#am-ativo'), 'celular: botão voltar do celular fecha o gráfico');
    await cel.page.goBack();
    ok(await cel.page.isHidden('#am-ativo'), 'celular: voltar de novo fecha o ativo');
    // Relatório: sem o arquivo da noite, oferece "Gerar agora" no aparelho
    await cel.page.click('.am-nav [data-ir-pagina="mais"]');
    ok(!(await cel.page.isVisible('[data-sub="dados"]')) && !/Dados e atualiza/.test(await cel.page.textContent('[data-pagina="mais"]')), 'celular: Mais sem "Dados e atualização"');
    const ordemMais = await cel.page.evaluate(() => [...document.querySelectorAll('[data-pagina="mais"] [data-sub]')].map(b => b.dataset.sub));
    ok(ordemMais.indexOf('relatorio') === ordemMais.indexOf('correlacao') + 1, `celular: Relatório logo abaixo de Correlação no Mais (${ordemMais.join(', ')})`);
    await cel.page.click('[data-sub="relatorio"]');
    ok(await cel.page.isVisible('#am-relatorio [data-gerar-relatorio]'), 'celular: Relatório sem arquivo oferece "Gerar agora"');
    await cel.page.click('#am-relatorio [data-gerar-relatorio]');
    await cel.page.waitForFunction(() => /Último teste/.test(document.getElementById('am-relatorio').textContent), null, { timeout: 120000 });
    const relTxt = await cel.page.textContent('#am-relatorio');
    ok(/Entrar na próxima abertura/.test(relTxt) && /Em operação: não entrar agora/.test(relTxt) && /Saída que ganhou/.test(relTxt) && /Confiabilidade/.test(relTxt), 'celular: Relatório com vereditos (entrar, em operação), confiabilidade e saída vencedora');
    // Vereditos: travas aplicadas em todos os papéis do relatório
    const vered = await cel.page.evaluate(() => {
        const I = window.investDebug, R = I.relatorio; const erros = []; const cont = {};
        for (const a of R.ativos) {
            const v = I.vereditoEntrada(a); cont[v.estado] = (cont[v.estado] || 0) + 1;
            const n = a.nTotal || 0;
            if (v.estado === 'entrar' && !(a.confirmada && n >= 15 && a.situacao === 'entrada' && (!a.resistencia || a.resistencia - a.entrada >= a.entrada - a.stop))) erros.push('entrar indevido ' + a.t);
            if ((!a.confirmada || n < 15) && a.regra && v.estado !== 'nao') erros.push('deveria ser não operar ' + a.t);
            if (a.confirmada && n >= 15 && a.situacao === 'posicao' && v.estado !== 'ja') erros.push('deveria ser já em operação ' + a.t);
        }
        // sinal velho vira "esperar": simula uma consulta 3 dias úteis depois
        const e = R.ativos.find(a => a.situacao === 'entrada' && a.confirmada && (a.nTotal || 0) >= 15);
        let velho = null; if (e) { const x = new Date(e.dataSinal + 'T12:00:00'); x.setDate(x.getDate() + 5); velho = I.vereditoEntrada(e, x).estado; }
        return { erros, cont, velho };
    });
    ok(vered.erros.length === 0 && (vered.velho === null || vered.velho === 'esperar'), `celular: vereditos seguem as travas ${JSON.stringify(vered.cont)}${vered.erros.length ? ' ' + vered.erros.slice(0, 3).join('; ') : ''} · sinal velho → ${vered.velho}`);
    // Diário de sinais: anota, acompanha com o mesmo motor e desliga regra que vai mal na vida real
    const diar = await cel.page.evaluate(() => {
        const I = window.investDebug, R = I.relatorio, D = I.allData;
        const novo = I.atualizarDiario(null, R);
        const nSinaisHoje = R.ativos.filter(a => a.situacao === 'entrada' && a.confirmada && (a.nTotal || 0) >= 15).length;
        // um sinal antigo que o motor executou: precisa sair "fechado" com o mesmo resultado do backtest
        const a = R.ativos.find(x => x.confirmada && x.regra); const regras = { stop: 0, alvo: 1, tempo: 2, alvo_tempo: 3, recuo: 4, recuo_tempo: 5 };
        const rp = (() => { const b = I.getBacktestRiskParams(); return null; })();
        const res = I.runCoreBacktest(D[a.t], window.investDebug.regraRp(a.regra));
        const tr = res.tradesDet[res.tradesDet.length - 2];
        const ant = { versao: 1, mercado: R.mercado, inicio: '2020-01-01', regras: {}, sinais: [{ id: 'x', t: a.t, regra: a.regra, dataSinal: D[a.t].dates[tr.ent - 1], veredito: 'entrar', estado: 'aguardando' }] };
        const d2 = I.atualizarDiario(ant, R); const s0 = d2.sinais.find(x => x.id === 'x');
        // 12 sinais encerrados muito ruins na regra de a → desligada → veredito "não operar"
        const ruins = Array.from({ length: 12 }, (_, k) => ({ id: 'r' + k, t: a.t, regra: a.regra, dataSinal: '2025-01-0' + (k % 9 + 1), veredito: 'entrar', estado: 'fechado', ret: -0.25 }));
        const d3 = I.atualizarDiario({ ...ant, sinais: ruins }, R);
        I.diario = d3; const v = I.vereditoEntrada(a); I.diario = null;
        return { novos: novo.sinais.length, nSinaisHoje, aguardando: novo.sinais.every(x => x.estado === 'aguardando'), fechado: s0.estado, retOk: Math.abs(s0.ret - tr.ret) < 1e-4, desl: d3.regras[a.regra].desligada, vered: v.estado, motivo: v.motivos[0] };
    });
    ok(diar.novos === diar.nSinaisHoje && diar.aguardando, `celular: diário anota os ${diar.nSinaisHoje} sinais confirmados de hoje, aguardando a abertura`);
    ok(diar.fechado === 'fechado' && diar.retOk, 'celular: diário acompanha um sinal antigo com o mesmo motor e o mesmo resultado');
    ok(diar.desl && diar.vered === 'nao' && /desligada pelo diário/.test(diar.motivo), `celular: regra que vai mal na vida real é desligada (${JSON.stringify(diar)})`);
    const relInfo = await cel.page.evaluate(() => { const R = window.investDebug.relatorio; return { n: R.ativos.length, sq: R.ativos.filter(a => a.squeeze).length, vend: !!R.vendidos }; });
    ok(relInfo.n > 0 && relInfo.vend && relInfo.sq > 0 && /short squeeze/.test(relTxt), `celular: alerta de short squeeze com os vendidos da B3 ${JSON.stringify(relInfo)}`);
    await cel.page.waitForTimeout(300);
    await cel.page.screenshot({ path: path.join(SHOTS, 'celular_relatorio.png'), fullPage: false });
    const cartao = await cel.page.$('#am-relatorio .rel-card[data-ativo]');
    if (cartao) { await cartao.click(); await cel.page.waitForSelector('#am-ativo.aberta', { timeout: 15000 }); ok(true, 'celular: tocar num papel do Relatório abre a tela do ativo'); await cel.page.goBack(); }
    await cel.page.goBack();   // fecha a tela do Relatório (abre por cima, como as outras do Mais)
    await cel.page.waitForSelector('#am-sub-tela', { state: 'hidden', timeout: 5000 });
    // Carteira: adicionar, ver o viés, editar, persistir e remover
    await cel.page.click('.am-nav [data-ir-pagina="carteira"]');
    ok(/está vazia/.test(await cel.page.textContent('[data-pagina="carteira"]')), 'celular: Carteira vazia convida a adicionar');
    const papelCart = await cel.page.evaluate(() => Object.keys(window.investDebug.allData)[0]);
    await cel.page.click('#am-carteira-add');
    await cel.page.fill('#am-cart-ticker', 'NAOEXISTE9');
    await cel.page.fill('#am-cart-qtd', '100'); await cel.page.fill('#am-cart-pm', '10');
    await cel.page.click('#am-cart-salvar');
    ok(/Não achei/.test(await cel.page.textContent('#am-cart-erro')), 'celular: Carteira recusa papel que não existe nos dados');
    await cel.page.fill('#am-cart-ticker', papelCart.toLowerCase());
    await cel.page.click('#am-cart-salvar');
    await cel.page.waitForSelector('#am-carteira [data-cart-editar]', { timeout: 10000 });
    const cartTxt = await cel.page.textContent('#am-carteira');
    ok(cartTxt.includes(papelCart) && /(Viés de alta|Viés de baixa|Neutro)/.test(cartTxt) && /Resultado/.test(cartTxt), `celular: Carteira mostra ${papelCart} com viés e resultado`);
    await cel.page.waitForTimeout(300);
    await cel.page.screenshot({ path: path.join(SHOTS, 'celular_carteira.png'), fullPage: false });
    await cel.page.click('#am-carteira [data-cart-editar]');
    await cel.page.fill('#am-cart-qtd', '250'); await cel.page.click('#am-cart-salvar');
    const salvo = await cel.page.evaluate(() => JSON.parse(localStorage.getItem('invest-carteira')));
    ok(salvo.length === 1 && salvo[0].qtd === 250 && salvo[0].t === papelCart, 'celular: editar a quantidade grava no aparelho');
    await cel.page.reload();
    await cel.page.waitForFunction(() => window.investDebug && Object.keys(window.investDebug.allData || {}).length > 0, null, { timeout: 60000 });
    await cel.page.click('.am-nav [data-ir-pagina="carteira"]');
    ok((await cel.page.textContent('#am-carteira')).includes(papelCart), 'celular: Carteira continua lá depois de recarregar');
    await cel.page.click('#am-carteira [data-cart-editar]');
    await cel.page.click('#am-cart-remover');
    ok(await cel.page.evaluate(() => JSON.parse(localStorage.getItem('invest-carteira')).length === 0), 'celular: remover tira o papel da Carteira');
    // Análise da carteira: um papel de viés de baixa, um de alta e concentração
    const montagem = await cel.page.evaluate(() => {
        const D = window.investDebug; const ts = Object.keys(D.allData).filter(t => D.allData[t].close.length >= 260);
        // monta com os primeiros 6 papéis; o 1º fica com ~60% do valor (concentrado)
        const esc = ts.slice(0, 6); const ult = t => D.allData[t].close.at(-1);
        const lista = esc.map((t, k) => ({ t, m: 'br', qtd: Math.round((k === 0 ? 9000 : 1200) / ult(t)) || 1, pm: ult(t), data: null }));
        localStorage.setItem('invest-carteira', JSON.stringify(lista)); return esc;
    });
    // gera o Relatório de novo (o recarregamento apagou o que foi gerado no aparelho)
    await cel.page.click('.am-nav [data-ir-pagina="mais"]'); await cel.page.click('[data-sub="relatorio"]');
    await cel.page.click('#am-relatorio [data-gerar-relatorio]');
    await cel.page.waitForFunction(() => /Último teste/.test(document.getElementById('am-relatorio').textContent), null, { timeout: 120000 });
    await cel.page.goBack(); await cel.page.waitForSelector('#am-sub-tela', { state: 'hidden', timeout: 5000 });
    await cel.page.click('.am-nav [data-ir-pagina="carteira"]');
    await cel.page.waitForSelector('#am-cart-analise', { timeout: 15000 });
    const A = await cel.page.evaluate(() => { const a = window.investDebug.analisarCarteira(); return { pos: a.posicoes.map(p => ({ t: p.t, acao: p.acao, vies: p.v && p.v.vies, peso: p.peso, conc: p.concentrada, val: !!(p.rel && p.rel.confirmada), op: !!(p.rel && p.rel.confirmada && p.rel.situacao === 'posicao') })), cand: a.candidatos.map(c => c.t), candOk: a.candidatos.every(c => c.entrada && c.v.vies === 'alta'), veredito: a.veredito, reforcar: a.reforcar && a.reforcar.t }; });
    const regrasOk = A.pos.every(p => (p.vies === 'baixa' && p.val && !p.op) ? p.acao === 'trocar' : p.conc ? p.acao === 'reduzir' : p.acao === ({ alta: 'manter', neutro: 'neutro', baixa: 'neutro' }[p.vies] || 'neutro'));
    ok(A.pos.length === montagem.length && regrasOk, `celular: análise da carteira aplica as regras (${A.pos.map(p => p.t + ':' + p.acao).join(', ')})`);
    ok(A.pos[0].conc && A.candOk && A.cand.every(t => !montagem.includes(t)), `celular: análise aponta concentração e só sugere papéis de fora (${A.cand.join(', ') || 'nenhum'})`);
    const anTxt = await cel.page.textContent('#am-cart-analise');
    ok(/Análise de \d\d\/\d\d\/\d{4}/.test(anTxt) && /(Trocar ou reduzir|Reduzir peso)/.test(anTxt) && /Não é recomendação/.test(anTxt), 'celular: análise mostra data, sugestões e aviso');
    // Caso "trocar": papel com viés de baixa e regra validada fora da operação (se existir nos dados de exemplo)
    const troca = await cel.page.evaluate(() => {
        const D = window.investDebug; const R = D.relatorio;
        const alvo = R.ativos.find(a => a.confirmada && a.situacao !== 'posicao' && D.allData[a.t] && D.allData[a.t].close.length >= 260
            && (() => { localStorage.setItem('invest-carteira', JSON.stringify([{ t: a.t, m: 'br', qtd: 10, pm: 10, data: null }])); const x = D.analisarCarteira(); return x.posicoes[0].v && x.posicoes[0].v.vies === 'baixa'; })());
        if (!alvo) return null;
        const x = D.analisarCarteira(); return { t: alvo.t, acao: x.posicoes[0].acao, cand: x.candidatos.length };
    });
    if (troca) {
        await cel.page.click('#am-cart-reanalisar');
        const tTxt = await cel.page.textContent('#am-cart-analise');
        ok(troca.acao === 'trocar' && /Trocar ou reduzir/.test(tTxt) && /(trocar por|ficar em caixa)/.test(tTxt), `celular: viés de baixa + regra validada fora → sugere trocar (${troca.t}, ${troca.cand} alternativa(s))`);
    } else console.log('ℹ️ dados de exemplo sem caso de troca; regra coberta só pela verificação geral');
    await cel.page.evaluate(() => document.getElementById('am-cart-analise').scrollIntoView());
    await cel.page.waitForTimeout(300);
    await cel.page.screenshot({ path: path.join(SHOTS, 'celular_carteira_analise.png'), fullPage: false });
    await cel.page.evaluate(() => localStorage.removeItem('invest-carteira'));
    // Testes e Mais
    await cel.page.click('.am-nav [data-ir-pagina="testes"]');
    await cel.page.click('#run-backtest-btn');
    await cel.page.waitForSelector('#backtest-results-container .result-metric', { timeout: 30000 });
    ok(true, 'celular: Backtest roda na aba Testes');
    await cel.page.click('.am-nav [data-ir-pagina="mais"]');
    await cel.page.click('[data-sub="fundamentos"]');
    ok(await cel.page.isVisible('#fundamentals-results-container'), 'celular: Mais → Técnica × Fundamentos');
    await cel.page.click('#fundamentals-results-container tbody tr[data-explicar]');
    ok(await cel.page.isVisible('#am-ativo'), 'celular: tocar numa linha do Módulo 6 abre a tela do ativo');
    const errosCel = cel.erros.filter(e => !IGNORAR.some(r => r.test(e)));
    ok(errosCel.length === 0, `celular: console sem erros${errosCel.length ? ': ' + errosCel.join(' | ') : ''}`);
    await cel.page.close();

    // Brasil ainda não publicado: aviso claro e atalho para os EUA (sem abrir o modo manual)
    const semBr = await abrir(browser, BASE + '?mercado=br', '**/data/br/manifest.json');
    await semBr.page.waitForSelector('#voltar-eua', { timeout: 30000 });
    ok(/ainda não foram publicados/.test(await semBr.page.textContent('#app-message')) && !(await semBr.page.evaluate(() => document.getElementById('manual-mode').open)), 'Brasil indisponível: aviso, sem modo manual');
    await Promise.all([semBr.page.waitForURL(/mercado=us/), semBr.page.click('#voltar-eua')]);
    await semBr.page.waitForSelector('#screener-results-container table', { timeout: 120000 });
    ok(true, 'Brasil indisponível: botão "Ver os EUA" carrega os EUA');
    await semBr.page.close();

    // 3) Modo manual quando não existe manifesto
    const m = await abrir(browser, BASE, true);
    await m.page.waitForFunction(() => document.getElementById('manual-mode').open === true, null, { timeout: 30000 });
    const motivo = await m.page.textContent('#manual-mode-reason');
    ok(/Não consegui carregar os dados automáticos/.test(motivo), 'sem manifesto: modo manual aberto com explicação');
    ok(await m.page.isVisible('#file-input') && await m.page.isVisible('#fundamentals-file-input'), 'inputs de preços e fundamentos visíveis no modo manual');
    // Upload manual no formato antigo {TICKER: {...}}
    const legado = await m.page.evaluate(async () => {
        const r = await fetch('data/precos_000.json'); const o = await r.json(); const s = {};
        for (const [t, a] of Object.entries(o.ativos)) s[t] = { dates: a.dates || o.datas.slice(a.i0, a.i0 + a.close.length), open: a.open, high: a.high, low: a.low, close: a.close, volume: a.volume };
        return JSON.stringify(s);
    });
    await m.page.setInputFiles('#file-input', { name: 'dados_mercado_FINAL.json', mimeType: 'application/json', buffer: Buffer.from(legado) });
    await m.page.waitForSelector('#screener-results-container table, #screener-results-container p', { timeout: 60000 });
    const nOpcoes = await m.page.$$eval('#ticker-select option', o => o.length);
    ok(nOpcoes > 0, `modo manual aceita o formato antigo (${nOpcoes} ativos carregados)`);
    await m.page.screenshot({ path: path.join(SHOTS, 'app_modo_manual.png'), fullPage: false });
    const errosManual = m.erros.filter(e => !IGNORAR.some(r => r.test(e)) && !/404/.test(e));
    ok(errosManual.length === 0, `console sem erros no modo manual${errosManual.length ? ': ' + errosManual.join(' | ') : ''}`);

    await browser.close();
    console.log(falhas ? `\n${falhas} verificação(ões) falharam.` : '\nTodas as verificações passaram.');
    process.exit(falhas ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
