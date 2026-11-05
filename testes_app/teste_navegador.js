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
    'jspdf': 'jspdf.umd.min.js',
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
    // Desde 05/11/2026 a bússola é a tela de qualquer tamanho; os testes de computador usam o app antigo (?classico=1)
    if (viewport.width >= 1024 && !/[?&]bussola/.test(url)) url += (url.includes('?') ? '&' : '?') + 'classico=1';
    url = url.replace(/[?&]bussola=1/, '');
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
    await br.page.goto(BASE + '?classico=1');   // sem ?mercado: lembra a última escolha
    await br.page.waitForFunction(() => /Brasil \(IBOVESPA\)/.test(document.getElementById('data-freshness-banner').textContent), null, { timeout: 120000 });
    ok(/Brasil \(IBOVESPA\)/.test(await br.page.textContent('#data-freshness-banner')), 'lembra o mercado escolhido ao reabrir');
    await Promise.all([br.page.waitForURL(/mercado=us/), br.page.click('.mercado-btn[data-mercado="us"]')]);
    await br.page.waitForSelector('#screener-results-container table', { timeout: 120000 });
    ok(/EUA/.test(await br.page.textContent('#data-freshness-banner')) && await br.page.inputValue('#filter-adtv') === '50000000', 'volta para os EUA (US$ 50 mi)');
    const errosBr = br.erros.filter(e => !IGNORAR.some(r => r.test(e)));
    ok(errosBr.length === 0, `console sem erros na troca de mercado${errosBr.length ? ': ' + errosBr.join(' | ') : ''}`);
    await br.page.close();

    // Computador: a bússola também é a tela padrão (coluna central); o app antigo fica em ?classico=1
    const pc = await abrir(browser, BASE + '?mercado=us&bussola=1');
    await pc.page.waitForSelector('#am-termometro [data-termometro]', { timeout: 120000 });
    const pcL = await pc.page.evaluate(() => { const a = document.getElementById('app-movel').getBoundingClientRect(), n = document.querySelector('.am-nav').getBoundingClientRect(); return { w: a.width, nav: Math.abs((n.left + n.right) / 2 - window.innerWidth / 2), classico: document.querySelector('.max-w-screen-2xl').offsetParent !== null }; });
    ok(pcL.w <= 562 && pcL.nav < 2 && !pcL.classico, `computador: abre a bússola numa coluna central (${JSON.stringify(pcL)})`);
    ok((await pc.page.getAttribute('#am-link-classico', 'href')) === '?classico=1', 'computador: Mais tem o atalho para o app antigo');
    await pc.page.screenshot({ path: path.join(SHOTS, 'computador_bussola.png'), fullPage: false });
    await pc.page.close();

    // Celular: casca nova (Início / Ranking / Testes / Mais), tela do ativo e gráfico em tela cheia
    const cel = await abrir(browser, BASE + '?mercado=br', false, { width: 390, height: 844 });
    await cel.page.waitForSelector('#am-top .am-linha', { state: 'attached', timeout: 120000 });
    const navTxt = await cel.page.textContent('.am-nav');
    ok(await cel.page.isVisible('.am-nav') && await cel.page.isHidden('#tabs') && /Ativos/.test(navTxt) && !/Testes|Ranking/.test(navTxt), 'celular: barra de baixo com Início / Ativos / Carteira / Mais');
    ok(/Brasil/.test(await cel.page.textContent('#am-sub')) && (await cel.page.$$('#am-melhores .am-opcao')).length > 0, 'celular: Início com data dos dados, clima e Melhores Opções');
    const termo = await cel.page.textContent('#am-termometro');
    ok(/Termômetro do BOVA11/.test(termo) && /média de 10 meses/.test(termo) && /Volatilidade/.test(termo) && /não prevê/.test(termo), 'celular: Início abre com o termômetro do índice (contexto, sem previsão)');
    ok(!(await cel.page.$('[data-pagina="inicio"] #am-melhores')) && !/Score/.test(await cel.page.textContent('[data-pagina="inicio"]')), 'celular: Início sem ranking técnico (foi para o Avançado)');
    const T = await cel.page.evaluate(() => { const t = window.investDebug.termometroIndice(); const s = window.investDebug.indice.series['BOVA11.SA']; const c = s.close, n = c.length; let m = 0; for (let i = n - 200; i < n; i++) m += c[i]; return { ok: Math.abs(t.distMM200 - (c[n - 1] / (m / 200) - 1)) < 1e-9 && Math.abs(t.quedaPico - (1 - c[n - 1] / Math.max(...c))) < 1e-9 && t.volPct > 0 && t.volPct <= 1 }; });
    ok(T.ok, 'celular: termômetro confere com o cálculo à mão (MME200 e queda do topo)');
    const rfOk = await cel.page.evaluate(() => { const D = window.investDebug; const s = D.indice.series.CDI; const n = s.dates.length; const r = D.retornoRendaFixa(s.dates[n - 253], s.dates[n - 1]); return Math.abs(r - (Math.pow(1.0005, 252) - 1)) < 1e-6 && Math.abs(D.termometroIndice().rf12m - r) < 1e-12; });
    ok(rfOk && /CDI em 12 meses/.test(termo), 'celular: termômetro mostra o CDI de 12 meses (conta confere)');
    const tol = await cel.page.evaluate(() => { const j = window.investDebug.lerJsonTolerante('{"series":{"SPY":{"dates":["a","b","c"],"close":[1,NaN,2]}},"x":Infinity}'); return JSON.stringify(j); });
    ok(tol === '{"series":{"SPY":{"dates":["a","c"],"close":[1,2]}},"x":null}', `celular: índice com NaN (pregão sem fechamento) não derruba o arquivo (${tol})`);
    const larg = await cel.page.evaluate(() => ({ doc: document.documentElement.scrollWidth, sw: document.getElementById('market-switch').getBoundingClientRect().right }));
    ok(larg.doc <= 390 && larg.sw <= 390, `celular: sem rolagem lateral (${JSON.stringify(larg)})`);
    await cel.page.screenshot({ path: path.join(SHOTS, 'celular_inicio.png'), fullPage: false });
    await cel.page.click('.am-nav [data-ir-pagina="ranking"]');
    const nRank = await cel.page.$$eval('#am-ranking .am-linha', l => l.length);
    ok(nRank > 0 && !(await cel.page.$('#am-ranking .am-chip')), `celular: Ativos com ${nRank} linhas, sem score`);
    const ordemAtivos = await cel.page.evaluate(() => { const D = window.investDebug; const ts = [...document.querySelectorAll('#am-ranking .am-linha')].map(x => x.dataset.ativo); const v = ts.map(D.volFinanceiro); return v.every((x, k) => k === 0 || v[k - 1] >= x); });
    ok(ordemAtivos, 'celular: Ativos começa pelos mais negociados');
    await cel.page.click('#am-ordem [data-ordem="topo"]');
    const topoOk = await cel.page.evaluate(() => { const D = window.investDebug; const v = [...document.querySelectorAll('#am-ranking .am-linha')].map(x => D.quedaDoTopo(x.dataset.ativo)); return v.length > 0 && v.every((x, k) => k === 0 || v[k - 1] >= x); });
    ok(topoOk, 'celular: "Longe do topo" ordena pela queda da máxima de 1 ano');
    await cel.page.click('#am-ordem [data-ordem="liquidez"]');
    await cel.page.fill('#am-busca', 'PETR');
    ok((await cel.page.$$eval('#am-ranking .am-linha', l => l.map(x => x.dataset.ativo))).includes('PETR4'), 'celular: busca acha PETR4');
    await cel.page.fill('#am-busca', '');
    await cel.page.click('.am-nav [data-ir-pagina="mais"]');
    await cel.page.click('[data-pagina="mais"] [data-sub="sinais"]');
    ok((await cel.page.$$('#am-melhores .am-opcao')).length > 0 && (await cel.page.$$('#am-top .am-linha')).length > 0, 'celular: Avançado → Ranking técnico com Melhores opções e Top 10');
    await cel.page.click('#am-abrir-filtros');
    ok(await cel.page.isVisible('#filter-adtv'), 'celular: filtros num painel que sobe de baixo');
    await cel.page.fill('#filter-adtv', '0');
    await cel.page.click('#am-aplicar-filtros');
    await cel.page.waitForFunction(() => /aprovados/.test(document.getElementById('am-sinais-info').textContent), null, { timeout: 60000 });
    ok(true, 'celular: "Aplicar" roda o ranking de novo');
    await cel.page.goBack(); await cel.page.waitForSelector('#am-sub-tela', { state: 'hidden', timeout: 5000 });
    // Tela do ativo
    await cel.page.click('.am-nav [data-ir-pagina="ranking"]');
    await cel.page.click('#am-ranking .am-linha');
    await cel.page.waitForSelector('#am-ativo.aberta #am-mini canvas', { timeout: 15000 });
    ok(/R\$/.test(await cel.page.textContent('#am-ativo-cab')), 'celular: tela do ativo com preço em R$');
    const resumo = await cel.page.textContent('#am-aba-conteudo');
    ok(/Retorno em 1 ano/.test(resumo) && /BOVA11 em 1 ano/.test(resumo) && /Abaixo da máxima/.test(resumo) && !/Score técnico/.test(resumo) && !/Por que foi selecionado/.test(resumo), 'celular: Resumo do papel compara com o índice, sem score');
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
    const ganhoOk = await cel.page.evaluate(() => { const R = window.investDebug.relatorio; const c = R.ativos.filter(a => a.confirmada);
        return c.length > 0 && c.every(a => a.teste.mediaOp !== undefined && (a.teste.mediaGanho === null || a.teste.mediaGanho > 0) && (a.teste.mediaPerda === null || a.teste.mediaPerda <= 0)) && document.querySelectorAll('#am-relatorio .rel-ganho').length > 0; });
    ok(/🏢 Fundamentos \d\/\d/.test(relTxt) && /não entra no veredito/.test(relTxt), 'celular: cartões do Relatório mostram a nota fundamentalista só como contexto');
    const mme = await cel.page.evaluate(() => { const cards = [...document.querySelectorAll('#am-relatorio .rel-card[data-ativo]')].filter(c => /Confirmado fora da amostra/.test(c.textContent));
        const esperado = cards.filter(c => { const v = window.investDebug.vsMme200(c.dataset.ativo); return v !== null && v < 0; }).length;
        const achados = cards.filter(c => /Abaixo da média de 200 dias/.test(c.textContent)).length; return { esperado, achados, total: cards.length }; });
    ok(mme.total > 0 && mme.esperado === mme.achados, `celular: cartões abaixo da MME 200 mostram o aviso só como contexto (${mme.achados} de ${mme.total})`);
    const bal = await cel.page.evaluate(() => { const I = window.investDebug, F = I.fundamentos;
        const t = document.querySelector('#am-relatorio .rel-card[data-ativo]').dataset.ativo;
        const em = n => { const d = new Date(); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };
        const antes = { ...F[t] }; F[t].nextEarningsDate = null; F[t].balancoEstimado = em(30);
        const longe = I.balancoProximo(t); F[t].balancoEstimado = em(3); const perto = I.balancoProximo(t);
        F[t].nextEarningsDate = em(2); const inf = I.balancoProximo(t); I.desenharRelatorio();
        const card = [...document.querySelectorAll('#am-relatorio .rel-card[data-ativo]')].find(c => c.dataset.ativo === t);
        const txt = card ? card.textContent : ''; Object.keys(F[t]).forEach(k => delete F[t][k]); Object.assign(F[t], antes); I.desenharRelatorio();
        return { longe, perto, inf, txt }; });
    ok(bal.longe === null && bal.perto && bal.perto.estimado && bal.inf && !bal.inf.estimado && bal.inf.dias === 2 && /Balanço em 2 dias/.test(bal.txt) && /Só aviso/.test(bal.txt),
        'celular: cartão do Relatório avisa balanço nos próximos dias (data do Yahoo ou estimada pela SEC), só como aviso');
    ok(ganhoOk && /Ganho possível/.test(relTxt), 'celular: cartões do Relatório destacam o ganho possível (alvo ou média medida no teste) e o risco até o stop');
    {
        const [dl] = await Promise.all([cel.page.waitForEvent('download', { timeout: 15000 }), cel.page.click('#am-relatorio button[data-baixar-relatorio]')]);
        const conteudo = JSON.parse(fs.readFileSync(await dl.path(), 'utf8'));
        const nAtivos = await cel.page.evaluate(() => window.investDebug.relatorio.ativos.length);
        ok(/^relatorio-(us|br)-.+\.json$/.test(dl.suggestedFilename()) && conteudo.ativos.length === nAtivos && conteudo.vereditos.length === nAtivos && conteudo.vereditos.every(v => v.t && v.estado),
            `celular: botão "Baixar relatório" entrega o .json com os ${nAtivos} papéis e o veredito de cada um (${dl.suggestedFilename()})`);
    }
    {
        const [dl] = await Promise.all([cel.page.waitForEvent('download', { timeout: 30000 }), cel.page.click('#am-relatorio [data-baixar-relatorio-pdf]')]);
        const bytes = fs.readFileSync(await dl.path());
        const esperado = await cel.page.evaluate(() => { const I = window.investDebug; return I.relatorio.ativos.filter(a => ['entrar', 'atrasado', 'esperar', 'ja'].includes(I.vereditoEntrada(a).estado)).length; });
        ok(/^relatorio-(us|br)-.+\.pdf$/.test(dl.suggestedFilename()) && bytes.slice(0, 5).toString() === '%PDF-' && bytes.length > 3000,
            `celular: botão "Baixar relatório (PDF)" entrega um PDF de verdade (${dl.suggestedFilename()}, ${Math.round(bytes.length / 1024)} KB, ${esperado} papéis com veredito)`);
        if (process.env.PDF_SAIDA) fs.copyFileSync(await dl.path(), process.env.PDF_SAIDA);
    }
    // Ordem: padrão por ganho possível (decrescente); tocar em outra ordem reorganiza
    const ordemOk = await cel.page.evaluate(() => {
        const lerG = () => [...document.querySelectorAll('#am-relatorio details[data-secao="operacao"] .rel-ganho .g')].map(x => parseFloat(x.textContent.replace('+', '').replace(',', '.')));
        const g = lerG(); return { n: g.length, desc: g.every((v, i) => i === 0 || g[i - 1] >= v) };
    });
    await cel.page.click('[data-rel-ordem="pf"]');
    const ordemPf = await cel.page.evaluate(() => document.querySelector('[data-rel-ordem="pf"]').classList.contains('verde') && localStorage.getItem('invest-rel-ordem') === 'pf');
    await cel.page.click('[data-rel-ordem="ganho"]');
    ok(ordemOk.n > 1 && ordemOk.desc && ordemPf, `celular: Relatório ordenado pelo ganho possível, do maior para o menor (${ordemOk.n} cartões), com opção de outra ordem`);
    // Vereditos: travas aplicadas em todos os papéis do relatório
    const vered = await cel.page.evaluate(() => {
        const I = window.investDebug, R = I.relatorio; const erros = []; const cont = {};
        const noite = new Date(R.ultimoPregao + 'T23:30:00Z');   // a noite do último pregão, quando o relatório sai
        for (const a of R.ativos) {
            const v = I.vereditoEntrada(a, noite); cont[v.estado] = (cont[v.estado] || 0) + 1;
            const n = a.nTotal || 0;
            if (v.estado === 'entrar' && !(a.confirmada && n >= 15 && a.situacao === 'entrada')) erros.push('entrar indevido ' + a.t);
            if ((!a.confirmada || n < 15) && a.regra && v.estado !== 'nao') erros.push('deveria ser não operar ' + a.t);
            if (v.motivos.some(m => /vezes o ganho até a resistência|maior que o espaço até a resistência/.test(m))) erros.push('resistência barrando entrada ' + a.t);
            if (a.confirmada && n >= 15 && a.situacao === 'entrada' && v.estado === 'esperar' && I.vereditoEntrada(a, new Date(R.ultimoPregao + 'T23:30:00Z')).motivos.every(m => !/sinal é de|abertura de hoje/.test(m))) erros.push('esperar sem motivo de tempo ' + a.t);
            if (a.confirmada && n >= 15 && a.situacao === 'posicao' && !['ja', 'atrasado'].includes(v.estado)) erros.push('deveria ser já em operação ou atrasado ' + a.t);
            if (v.estado === 'atrasado') {
                const d = I.allData[a.t], preg = d.close.length - d.dates.indexOf(a.desde);
                if (!(preg <= 2 && a.atrEntrada > 0 && (a.preco - a.entrada) / a.atrEntrada <= 0.5)) erros.push('atrasado indevido ' + a.t);
                if (!v.rr || !v.motivos.some(m => /risco até o stop/.test(m))) erros.push('atrasado sem risco/retorno ' + a.t);
                // dias depois, a mesma operação deixa de ser "atrasado"
                const x = new Date(a.desde + 'T12:00:00'); x.setDate(x.getDate() + 7); if (I.vereditoEntrada(a, x).estado !== 'ja') erros.push('atrasado velho ' + a.t);
                cont.atrasadoOk = (cont.atrasadoOk || 0) + 1;
            }
            if (v.estado === 'ja' && !v.motivos.some(m => /risco até o stop|sem resistência/.test(m))) erros.push('já sem risco/retorno ' + a.t);
        }
        // sinal velho vira "esperar": simula uma consulta 3 dias úteis depois
        const e = R.ativos.find(a => a.situacao === 'entrada' && a.confirmada && (a.nTotal || 0) >= 15);
        let velho = null; if (e) { const x = new Date(e.dataSinal + 'T12:00:00'); x.setDate(x.getDate() + 5); velho = I.vereditoEntrada(e, x).estado; }
        return { erros, cont, velho };
    });
    ok(vered.erros.length === 0 && (vered.velho === null || vered.velho === 'esperar'), `celular: vereditos seguem as travas ${JSON.stringify(vered.cont)}${vered.erros.length ? ' ' + vered.erros.slice(0, 3).join('; ') : ''} · sinal velho → ${vered.velho}`);
    // Estratégia congelada (04/11/2026): aviso no Relatório e comparação com o índice nas mesmas datas
    const cong = await cel.page.evaluate(() => {
        const I = window.investDebug, R = I.relatorio;
        const avisos = [...document.querySelectorAll('.relatorio-alvo')].map(el => !!el.querySelector('[data-congelada]'));
        const t = R.ativos[0].t, d = I.allData[t], n = d.dates.length;
        const antes = I.indice;
        I.indice = { principal: 'IDX', series: { IDX: { nome: 'Índice teste', dates: d.dates.slice(), close: d.dates.map((_, k) => 100 * (1 + 0.001 * k)) } } };
        const r = I.retornoIndice(d.dates[n - 11], d.dates[n - 1]), esperado = (100 * (1 + 0.001 * (n - 1))) / (100 * (1 + 0.001 * (n - 11))) - 1;
        const fimDeSemana = I.retornoIndice('2000-01-01', d.dates[n - 1]);   // antes do início da série: sem dado
        const c = I.comparacaoIndiceSim({ ordens: [{ estado: 'fechada', t, iEnt: n - 10, dataSai: d.dates[n - 3], custoTotal: 1000, resultado: 50 }, { estado: 'cancelada', t }] });
        const rOp = I.retornoIndice(d.dates[n - 11], d.dates[n - 3]);
        const dAntes = I.diario;
        I.diario = { mercado: R.mercado, inicio: d.dates[n - 20], sinais: [{ id: 'x', t, regra: R.ativos[0].regra || 'stop', estado: 'fechado', dataSinal: d.dates[n - 11], dataEntrada: d.dates[n - 10], dataSaida: d.dates[n - 3], ret: 0.5 }], regras: {} };
        const html = I.htmlDiario();
        I.indice = antes; I.diario = dAntes;
        return { avisos, r, esperado, fimDeSemana, c, ind: c && c.ind, indEsperado: 1000 * rOp, diarioOk: /data-diario-indice/.test(html) && /1 de 1 sinais venceram/.test(html) };
    });
    ok(cong.avisos.length > 0 && cong.avisos.every(Boolean), `celular: Relatório mostra o aviso de estratégia congelada (${cong.avisos.length} lugar(es))`);
    ok(Math.abs(cong.r - cong.esperado) < 1e-9 && cong.fimDeSemana === null && cong.c && cong.c.n === 1 && Math.abs(cong.ind - cong.indEsperado) < 1e-6 && cong.diarioOk,
        `celular: índice nas mesmas datas na simulação (${cong.c ? cong.c.n : 0} op., índice ${cong.ind && cong.ind.toFixed(2)}) e no diário`);
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
    // Recalibragem por Walk-Forward: só adota se confirmar depois do corte; senão mantém a atual
    const cal = await cel.page.evaluate(async () => {
        const I = window.investDebug; const c = await I.recalibrar(null);
        const linha = (a, d) => c.tabela.find(x => x.alvo === a && x.dias === d);
        const validas = c.tabela.filter(x => x.treino.n >= 50); const melhor = validas.reduce((m, x) => x.treino.pf > m.treino.pf ? x : m, validas[0]);
        const atual = linha(3, 10); const adotou = c.alvo !== 3 || c.dias !== 10;
        const coerente = adotou ? (c.alvo === melhor.alvo && c.dias === melhor.dias && melhor.teste.pf >= 1 && melhor.teste.pf >= atual.teste.pf)
                                : !(melhor.teste.pf >= 1 && melhor.teste.pf >= atual.teste.pf && melhor.teste.n >= 20 && (melhor.alvo !== 3 || melhor.dias !== 10));
        I.calibracao = { ...c, alvo: 4, dias: 20 };
        const nomes = I.regraRp('alvo_tempo');
        I.calibracao = null;
        return { n: c.tabela.length, coerente, adotou, alvo: c.alvo, dias: c.dias, motivo: c.motivo, usa: nomes.alvoAtr === 4 && nomes.saidaDias === 20, corte: c.corte };
    });
    ok(cal.n === 9 && cal.coerente && cal.usa, `celular: recalibragem testa 9 combinações na carteira e só adota o que se confirma depois de ${cal.corte} (${cal.alvo}×ATR, ${cal.dias} pregões: ${cal.motivo})`);
    // Simulação: a saída simulada é a mesma do Backtest, e o caixa fecha a conta
    const simT = await cel.page.evaluate(() => {
        const I = window.investDebug, D = I.allData, R = I.relatorio; let n = 0, dif = 0;
        for (const a of R.ativos.filter(x => x.regra).slice(0, 12)) {
            const d = D[a.t], rp = I.regraRp(a.regra), res = I.runCoreBacktest(d, rp), ind = I.precomputeAllIndicators(d, I.getIndicatorParameters());
            for (const x of res.tradesDet) {
                const s = I.simularSaida(d, x.ent, d.open[x.ent] * (1 + rp.costPct / 100), ind.ATR[x.ent - 1], rp); n++;
                if (s.iSai !== x.sai || Math.abs(s.preco / (d.open[x.ent] * (1 + rp.costPct / 100)) - 1 - x.ret) > 1e-9) dif++;
            }
        }
        // Ordens fictícias de 30 pregões atrás (entrar) e de uma operação aberta (atrasado): preenche, dimensiona e fecha
        const comAberta = R.ativos.filter(a => a.situacao === 'posicao' && a.atrEntrada > 0);
        const t0 = R.ativos.find(a => a.regra && D[a.t])?.t; const d0 = D[t0], k = d0.dates.length - 30;
        const rp0 = I.regraRp(R.ativos.find(a => a.t === t0).regra), ind0 = I.precomputeAllIndicators(d0, I.getIndicatorParameters());
        const base = { modoEntrada: rp0.modoEntrada, atrMult: rp0.atrMult, stopLossPct: rp0.stopLossPct, alvoAtr: rp0.alvoAtr, saidaDias: rp0.saidaDias || 5, costPct: rp0.costPct, riskTrade: 1 };
        const ordens = [{ id: 'a', t: t0, regra: 'tempo', tipo: 'entrar', dataTela: d0.dates[k], sistema: { dataSinal: d0.dates[k], atr: ind0.ATR[k] }, rp: base }];
        { const t3 = R.ativos.filter(a => a.regra && D[a.t] && a.t !== t0)[1]?.t || t0, d3 = D[t3], k3 = d3.dates.length - 4, i3 = I.precomputeAllIndicators(d3, I.getIndicatorParameters());
          ordens.push({ id: 'd', t: t3, regra: 'alvo_tempo', tipo: 'entrar', dataTela: d3.dates[k3], sistema: { dataSinal: d3.dates[k3], atr: i3.ATR[k3] }, rp: { ...base, alvoAtr: 6, saidaDias: 30, atrMult: 4, stopLossPct: 15 } }); }
        ordens.push({ ...ordens[0], id: 'c', valor: 20000, dataTela: d0.dates[k + 12], sistema: { dataSinal: d0.dates[k + 12], atr: ind0.ATR[k + 12] } });
        if (comAberta[0]) { const a = comAberta[0], dA = D[a.t]; ordens.push({ id: 'b', t: a.t, regra: a.regra, tipo: 'fora', dataTela: dA.dates[dA.dates.indexOf(a.desde)], sistema: { desde: a.desde, entrada: a.entrada, atr: a.atrEntrada }, rp: { ...base, saidaDias: 0 } }); }
        I.gravarSim({ inicio: d0.dates[k], saldoInicial: 100000, ordens });
        const E = I.estadoSim(); const fech = E.fechadas.reduce((s2, o) => s2 + o.resultado, 0), custoAbertas = E.abertas.reduce((s2, o) => s2 + o.custoTotal, 0);
        return { n, dif, estados: E.ordens.map(o => o.estado + ':' + (o.qtd || 0)), conta: Math.abs(E.caixa + custoAbertas - (100000 + fech)) < 1e-6, porRegra: Object.keys(E.porRegra).length, ref: E.referencia !== null, progresso: (() => { const o = E.ordens.find(x => x.id === 'd'); return o && o.estado === 'aberta' && o.alvo > 0; })(), valorEscolhido: (o => o && o.custoTotal <= 20000 && o.custoTotal > 20000 - o.precoEnt && o.patrimonioEnt > 0)(E.ordens.find(o => o.id === 'c')), controle: E.dentro.n + E.fora.n === E.fechadas.length && Object.values(E.porRegra).reduce((x, r) => x + r.n, 0) === E.dentro.n && E.fora.n === E.fechadas.filter(o => o.tipo === 'fora').length, selos: [{ n: 5, ganhos: 9, perdas: 1, resultado: 8 }, { n: 12, ganhos: 30, perdas: 10, resultado: 20 }, { n: 12, ganhos: 5, perdas: 10, resultado: -5 }, { n: 12, ganhos: 11, perdas: 10, resultado: 1 }].map(r => I.seloSim(r).ico).join('') };
    });
    ok(simT.n > 20 && simT.dif === 0, `celular: saída da simulação igual à do Backtest (${simT.n} operações, ${simT.dif} diferentes)`);
    ok(simT.progresso, 'celular: simulação mantém uma operação aberta com alvo para acompanhar o progresso');
    ok(simT.valorEscolhido, 'celular: simulação respeita o valor escolhido pela pessoa e mostra quanto foi aplicado');
    ok(simT.controle, 'celular: entradas fora das travas (🔵) ficam num placar de controle e não contam no selo da estratégia');
    ok(simT.selos === '⏳✅❌➖', `celular: selo da simulação com critério fixo (10 operações; FL ≥ 1,2) ${simT.selos}`);
    ok(simT.conta && simT.estados.every(e => /^(aberta|fechada):[1-9]/.test(e)) && simT.ref, `celular: simulação preenche na abertura, dimensiona pelo risco e o caixa fecha a conta (${simT.estados.join(', ')})`);
    const relInfo = await cel.page.evaluate(() => { const R = window.investDebug.relatorio; return { n: R.ativos.length, sq: R.ativos.filter(a => a.squeeze).length, vend: !!R.vendidos }; });
    ok(relInfo.n > 0 && relInfo.vend && relInfo.sq > 0 && /short squeeze/.test(relTxt), `celular: alerta de short squeeze com os vendidos da B3 ${JSON.stringify(relInfo)}`);
    await cel.page.waitForTimeout(300);
    const botaoSeguir = await cel.page.$('#am-relatorio [data-seguir]');
    if (botaoSeguir) {
        const guardado = await cel.page.evaluate(() => { const g = { sim: localStorage.getItem('invest-simulacao'), sec: [...document.querySelectorAll('#am-relatorio details.rel-secao')].map(d => d.open) }; localStorage.removeItem('invest-simulacao'); document.querySelectorAll('#am-relatorio details.rel-secao').forEach(d => d.open = true); return g; });
        const tSeg = await botaoSeguir.getAttribute('data-seguir'); await botaoSeguir.click();
        const painelTxt = await cel.page.textContent(`.rel-seguir-painel[data-painel="${tSeg}"]`);
        await cel.page.click(`.rel-seguir-painel[data-painel="${tSeg}"] [data-seguir-ok="sugerido"]`);
        const ordem = await cel.page.evaluate(t => (window.investDebug.lerSim() || { ordens: [] }).ordens.find(o => o.t === t), tSeg);
        ok(/Quanto aplicar/.test(painelTxt) && /Sugerido/.test(painelTxt) && ordem && !ordem.valor, `celular: "Seguir na simulação" pergunta quanto aplicar e mostra o sugerido (${tSeg})`);
        await cel.page.evaluate(g => { if (g.sim) localStorage.setItem('invest-simulacao', g.sim); else localStorage.removeItem('invest-simulacao'); document.querySelectorAll('#am-relatorio details.rel-secao').forEach((d, i) => d.open = g.sec[i]); }, guardado);
        await cel.page.waitForTimeout(250); await cel.page.evaluate(() => localStorage.removeItem('invest-rel-secoes'));
    } else ok(true, 'celular: sem cartão 🟢/🔵 com botão de seguir nestes dados (painel não testado)');
    await cel.page.screenshot({ path: path.join(SHOTS, 'celular_relatorio.png'), fullPage: false });
    // Seções com setinha: abre e fecha ao tocar no título e lembra a escolha
    const sec = await cel.page.evaluate(() => [...document.querySelectorAll('#am-relatorio details.rel-secao')].map(d => d.dataset.secao + ':' + (d.open ? 1 : 0)));
    await cel.page.click('#am-relatorio details[data-secao="operacao"] > summary');
    await cel.page.waitForTimeout(250);   // o evento toggle chega depois do clique
    const abriu = await cel.page.evaluate(() => document.querySelector('#am-relatorio details[data-secao="operacao"]').open && JSON.parse(localStorage.getItem('invest-rel-secoes') || '{}').operacao === true);
    ok(sec.includes('entrar:1') && sec.includes('operacao:0') && abriu, `celular: seções do Relatório com setinha (${sec.join(', ')}); tocar abre e o app lembra`);
    const cartao = await cel.page.$('#am-relatorio .rel-card[data-ativo]:visible');
    if (cartao) { await cartao.click(); await cel.page.waitForSelector('#am-ativo.aberta', { timeout: 15000 }); ok(true, 'celular: tocar num papel do Relatório abre a tela do ativo'); await cel.page.goBack(); }
    await cel.page.goBack();   // fecha a tela do Relatório (abre por cima, como as outras do Mais)
    await cel.page.waitForSelector('#am-sub-tela', { state: 'hidden', timeout: 5000 });
    // Carteira: adicionar, ver o viés, editar, persistir e remover
    await cel.page.click('.am-nav [data-ir-pagina="carteira"]');
    ok(/está vazia/.test(await cel.page.textContent('[data-pagina="carteira"]')), 'celular: Carteira vazia convida a adicionar');
    await cel.page.click('.am-nav [data-ir-pagina="mais"]');
    await cel.page.click('[data-pagina="mais"] [data-sub="simulacao"]');
    const simTxt = await cel.page.textContent('#am-simulacao');
    ok(await cel.page.isVisible('#am-simulacao') && /Patrimônio simulado/.test(simTxt) && /Abertas|Encerradas/.test(simTxt) && /Por estratégia|Abertas/.test(simTxt) && /O que funcionou na simulação/.test(simTxt) && /do caminho/.test(simTxt) && /Pregão \d+ de 30/.test(simTxt) && (await cel.page.$('#am-simulacao .sim-barra')) !== null, 'celular: aba Simulação mostra patrimônio, placar, progresso até o alvo (barra, status, pregões) e estratégias');
    ok(/Estratégia congelada/.test(simTxt) && /Não use dinheiro real/.test(simTxt) && !/Comprar todos os papéis do app/.test(simTxt), 'celular: Simulação mostra o aviso de estratégia congelada e não usa mais a referência dos papéis de hoje');
    await cel.page.screenshot({ path: path.join(SHOTS, 'celular_simulacao.png'), fullPage: false });
    await cel.page.click('#am-sim-zerar'); await cel.page.click('#am-sim-zerar');
    ok(/Como funciona/.test(await cel.page.textContent('#am-simulacao')) && /100[.,]000/.test(await cel.page.textContent('#am-simulacao')), 'celular: zerar a simulação (com confirmação) volta aos 100 mil');
    await cel.page.goBack(); await cel.page.waitForSelector('#am-sub-tela', { state: 'hidden', timeout: 5000 });
    await cel.page.click('.am-nav [data-ir-pagina="carteira"]');
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
    ok(!/object Object/.test(cartTxt), "celular: nota fundamentalista da Carteira aparece como número (sem [object Object])");
    ok(cartTxt.includes(papelCart) && /% da carteira/.test(cartTxt) && /Resultado/.test(cartTxt) && !/Viés de|Score técnico/.test(cartTxt), `celular: Carteira mostra ${papelCart} com peso e resultado, sem sinal técnico`);
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
    // A antiga "análise da carteira" (trocar/reduzir pelos sinais da estratégia congelada) saiu em 05/11/2026
    ok(!(await cel.page.$('#am-cart-analise')) && !(await cel.page.$('[data-sinais-tecnicos]')), 'celular: Carteira sem sugestões de troca pela estratégia técnica');
    // Saúde da carteira: concentração, risco e o mesmo dinheiro no índice
    const saude = await cel.page.evaluate(() => {
        const D = window.investDebug; const ts = Object.keys(D.allData).filter(t => D.allData[t].close.length >= 260).slice(0, 4);
        const datas = D.allData[ts[0]].dates; const dia = datas[datas.length - 120];
        const lista = ts.map((t, k) => ({ t, m: 'br', qtd: k === 0 ? 100 : 10, pm: D.allData[t].close[D.allData[t].dates.indexOf(dia)], data: dia }));
        localStorage.setItem('invest-carteira', JSON.stringify(lista));
        const S = D.saudeCarteira(); const ult = t => D.allData[t].close.at(-1);
        const atual = lista.reduce((s, x) => s + x.qtd * ult(x.t), 0), inv = lista.reduce((s, x) => s + x.qtd * x.pm, 0);
        const esperado = inv * (1 + D.retornoIndice(dia, datas[datas.length - 1]));
        return { conta: Math.abs(S.vsIndice.atual - atual) < 1e-6 && Math.abs(S.vsIndice.noIndice - esperado) < 1e-6, pesos: Math.abs(S.pos.reduce((s, p) => s + p.peso, 0) - 1) < 1e-9, nEf: S.nEfetivo, maior: S.maior.peso };
    });
    ok(saude.conta && saude.pesos && saude.nEf >= 1 && saude.nEf <= 4, `celular: saúde da carteira confere a conta contra o índice e os pesos (efetivos ${saude.nEf.toFixed(2)})`);
    await cel.page.click('.am-nav [data-ir-pagina="inicio"]'); await cel.page.click('.am-nav [data-ir-pagina="carteira"]');
    const sTxt = await cel.page.textContent('[data-saude-carteira]');
    ok(/Saúde da carteira/.test(sTxt) && /Se o mesmo dinheiro de cada compra/.test(sTxt) && /No CDI, sem risco/.test(sTxt) && (saude.maior > 0.2 ? /⚠️/.test(sTxt) : true), 'celular: saúde da carteira aparece com a comparação e os alertas');
    await cel.page.waitForTimeout(400); await cel.page.screenshot({ path: path.join(SHOTS, 'celular_saude_carteira.png'), fullPage: false });
    // Plano de alocação: conta pura e tela
    const P = await cel.page.evaluate(() => {
        const D = window.investDebug; const preco = t => ({ AAA: 10, BOVA11: 100 })[t];
        const c = D.calcularPlano({ rf: 40, indice: 40, acoes: 20, valorRF: 2000, valorIndice: 0 }, [{ t: 'AAA', qtd: 500 }, { t: 'BOVA11', qtd: 30 }], preco, 1000);
        return c && { total: c.total, pesos: c.classes.map(x => +x.peso.toFixed(4)), fora: c.classes.map(x => x.fora), div: c.classes.map(x => +c.divisao[x.k].toFixed(2)), soma: Object.values(c.divisao).reduce((a, b) => a + b, 0) };
    });
    // total 2000 + 3000 + 5000 = 10000 → 20% rf, 30% índice, 50% ações; com +1000: faltam 2400 em rf e 1400 no índice → divide 1000 na proporção 24:14
    ok(P && P.total === 10000 && P.pesos.join() === '0.2,0.3,0.5' && P.fora.join() === 'true,true,true' && Math.abs(P.soma - 1000) < 1e-6 && Math.abs(P.div[0] - 631.58) < 0.01 && P.div[2] === 0, `celular: plano de alocação calcula pesos, faixas e divide o aporte só no que está abaixo da meta (${JSON.stringify(P)})`);
    await cel.page.fill('#plano-rf', '50'); await cel.page.fill('#plano-indice', '30'); await cel.page.fill('#plano-acoes', '30');
    await cel.page.click('[data-plano-salvar]');
    ok(/somar 100%/.test(await cel.page.textContent('#plano-erro')), 'celular: plano recusa metas que não somam 100%');
    await cel.page.fill('#plano-acoes', '20'); await cel.page.fill('#plano-valorRF', '5000'); await cel.page.fill('#plano-aporte', '1000');
    await cel.page.click('[data-plano-salvar]');
    const plTxt = await cel.page.textContent('[data-plano]');
    ok(/Renda fixa e reserva/.test(plTxt) && /meta 50%/.test(plTxt) && /Para o aporte de/.test(plTxt) && JSON.parse(await cel.page.evaluate(() => localStorage.getItem('invest-plano'))).br.rf === 50, 'celular: plano salvo mostra barras, meta e divisão do aporte');
    ok(/Maior setor/.test(await cel.page.textContent('[data-saude-carteira]')), 'celular: saúde mostra o setor de maior peso');
    await cel.page.evaluate(() => document.querySelector('[data-plano]').scrollIntoView());
    await cel.page.waitForTimeout(300); await cel.page.screenshot({ path: path.join(SHOTS, 'celular_plano_alocacao.png'), fullPage: false });
    await cel.page.evaluate(() => localStorage.removeItem('invest-carteira'));
    // Diário das minhas decisões e "O que já foi testado"
    await cel.page.click('.am-nav [data-ir-pagina="mais"]'); await cel.page.click('[data-pagina="mais"] [data-sub="decisoes"]');
    await cel.page.fill('#dec-t', 'PETR4'); await cel.page.fill('#dec-motivo', 'teste <b>');
    const dia = await cel.page.evaluate(() => { const d = window.investDebug.allData.PETR4.dates; return d[d.length - 60]; });
    await cel.page.fill('#dec-data', dia); await cel.page.click('#dec-salvar');
    const decTxt = await cel.page.textContent('[data-sub-slot="decisoes"]');
    const decOk = await cel.page.evaluate(dia => { const D = window.investDebug; const x = D.lerDecisoes()[0]; const a = D.avaliarDecisao(x); const d = D.allData.PETR4; const i0 = d.dates.indexOf(dia); return x.t === 'PETR4' && Math.abs(a.ret - (d.close.at(-1) / d.close[i0] - 1)) < 1e-9; }, dia);
    ok(decOk && /Placar das suas decisões/.test(decTxt) && /teste &lt;b&gt;|teste <b>/.test(decTxt) && !(await cel.page.$('[data-sub-slot="decisoes"] b:text("teste")')), 'celular: diário de decisões grava, calcula contra o índice e escapa o texto');
    await cel.page.click('[data-decisao-apagar="0"]');
    ok(await cel.page.evaluate(() => window.investDebug.lerDecisoes().length === 0), 'celular: apagar decisão');
    await cel.page.goBack(); await cel.page.waitForSelector('#am-sub-tela', { state: 'hidden', timeout: 5000 });
    await cel.page.click('[data-pagina="mais"] [data-sub="testado"]');
    const tsTxt = await cel.page.textContent('[data-sub-slot="testado"]');
    ok(/REPROVADA/.test(tsTxt) && /Momento de 12 meses/.test(tsTxt) && /Mind the Gap/.test(tsTxt), 'celular: "O que já foi testado" lista os testes com veredito');
    await cel.page.goBack(); await cel.page.waitForSelector('#am-sub-tela', { state: 'hidden', timeout: 5000 });
    // Testes e Mais
    await cel.page.click('.am-nav [data-ir-pagina="mais"]');
    await cel.page.click('[data-pagina="mais"] [data-ir-pagina="testes"]');
    await cel.page.click('#run-backtest-btn');
    await cel.page.waitForSelector('#backtest-results-container .result-metric', { timeout: 30000 });
    ok(true, 'celular: Backtest roda na aba Testes');
    await cel.page.click('.am-nav [data-ir-pagina="mais"]');
    await cel.page.click('[data-sub="fundamentos"]');
    ok(await cel.page.isVisible('#fundamentals-results-container'), 'celular: Mais → Técnica × Fundamentos');
    await cel.page.click('#fundamentals-results-container tbody tr[data-explicar]');
    ok(await cel.page.isVisible('#am-ativo'), 'celular: tocar numa linha do Módulo 6 abre a tela do ativo');
    // Imposto das vendas do mês (Brasil): contas e tela
    const IR = await cel.page.evaluate(() => {
        const C = window.investDebug.calcularIR, v = (tipo, qtd, preco, pm) => ({ t: 'X', tipo, qtd, preco, pm });
        const a = C([v('acao', 100, 150, 120)], 0, 0, '2026-11');                       // vendeu 15 mil, lucro 3 mil: isento
        const b = C([v('acao', 200, 150, 135)], 1000, 0, '2026-11');                    // vendeu 30 mil, lucro 3 mil − prejuízo 1 mil → 15% de 2 mil
        const c = C([v('acao', 100, 95, 100), v('etf', 10, 200, 100)], 0, 0, '2026-12'); // mês isento com perda de 500 + lucro de ETF de 1.000 → 15% de 500
        const d = C([v('fii', 10, 200, 100)], 0, 200, '2026-11');                       // FII: 20% de (1.000 − 200)
        const e = C([v('etf', 1, 133, 100)], 0, 0, '2026-11');                          // R$ 4,95: abaixo de R$ 10, sem DARF
        const f = C([v('acao', 300, 100, 110)], 0, 0, '2026-11');                       // prejuízo de 3 mil fica para os próximos meses
        return { a: [a.isento, a.total, a.lucroIsento], b: [b.isento, +b.total.toFixed(2), b.vencimento], c: [+c.total.toFixed(2), c.vencimento], d: +d.total.toFixed(2), e: [+e.total.toFixed(2), e.pagar], f: f.prejComumDepois };
    });
    ok(JSON.stringify(IR) === JSON.stringify({ a: [true, 0, 3000], b: [false, 300, '2026-12-31'], c: [75, '2027-01-29'], d: 160, e: [4.95, false], f: 3000 }), `celular: imposto do mês segue isenção de 20 mil, prejuízo, ETF, FII e DARF mínimo (${JSON.stringify(IR)})`);
    for (let k = 0; k < 4 && await cel.page.$('.am-tela.aberta'); k++) { await cel.page.goBack(); await cel.page.waitForTimeout(200); }
    await cel.page.click('.am-nav [data-ir-pagina="mais"]');
    await cel.page.click('[data-pagina="mais"] [data-sub="imposto"]');
    await cel.page.fill('#ir-mes', '2026-11'); await cel.page.dispatchEvent('#ir-mes', 'change');
    await cel.page.fill('#ir-t', 'PETR4'); await cel.page.fill('#ir-qtd', '1000'); await cel.page.fill('#ir-preco', '40'); await cel.page.fill('#ir-pm', '30');
    await cel.page.click('#ir-salvar');
    const irTxt = await cel.page.textContent('[data-ir-resultado]');
    ok(/Tem DARF/.test(irTxt) && /1\.500,00/.test(irTxt) && /6015/.test(irTxt) && /31\/12\/2026/.test(irTxt), 'celular: venda de R$ 40 mil com lucro de R$ 10 mil mostra DARF de R$ 1.500 até 31/12/2026');
    await cel.page.click('[data-ir-apagar="0"]');
    ok(/Sem DARF/.test(await cel.page.textContent('[data-ir-resultado]')), 'celular: apagar a venda zera o imposto');
    await cel.page.goBack(); await cel.page.waitForSelector('#am-sub-tela', { state: 'hidden', timeout: 5000 });
    // Histórico de balanços (EUA): aba Balanços na tela do ativo
    await cel.page.goto(BASE + '?mercado=us');
    await cel.page.waitForFunction(() => window.investDebug && Object.keys(window.investDebug.allData || {}).length > 0, null, { timeout: 60000 });
    await cel.page.click('.am-nav [data-ir-pagina="ranking"]');
    await cel.page.fill('#am-busca', 'R000');
    await cel.page.click('#am-ranking .am-linha[data-ativo="R000"]');
    await cel.page.click('#am-abas [data-aba="balancos"]');
    await cel.page.waitForSelector('[data-balancos] [data-balanco]', { timeout: 15000 });
    const balTxt = await cel.page.textContent('#am-aba-conteudo');
    const B = await cel.page.evaluate(() => {
        const D = window.investDebug, a = D.balancos.ativos.R000, d = D.allData.R000;
        const q = a.tri.filter(x => D.reacaoBalanco('R000', x.divulgado)).slice(-2)[0]; const r = D.reacaoBalanco('R000', q.divulgado);
        const i = d.dates.findIndex(x => x >= q.divulgado);
        const quintos = Object.values(D.balancos.ativos).flatMap(x => x.tri.map(y => y.quinto)).filter(Boolean);
        return { reacaoOk: Math.abs(r.reacao - (d.close[i + 1] / d.close[i - 2] - 1)) < 1e-12, anoOk: q.receitaAno !== null && Math.abs(q.surpresa - (q.lucro - q.lucroAnt) / 5e9) < 1e-12,
                 q5: quintos.filter(x => x === 5).length, q1: quintos.filter(x => x === 1).length, n: quintos.length, linhas: document.querySelectorAll('[data-balancos] [data-balanco]').length };
    });
    ok(B.reacaoOk && B.anoOk && B.linhas === 12 && B.q5 > 0.15 * B.n && B.q5 < 0.25 * B.n, `celular: aba Balanços com 12 trimestres, reação e surpresa conferidas (quintos: ${B.q5}/${B.n} no de cima)`);
    ok(/Lucro líquido por trimestre/.test(balTxt) && /Reação \(2 dias antes a 1 depois\)/.test(balTxt) && /não como sinal de compra/.test(balTxt), 'celular: aba Balanços explica a fonte, a reação e o limite do teste');
    await cel.page.waitForTimeout(300); await cel.page.screenshot({ path: path.join(SHOTS, 'celular_balancos.png'), fullPage: false });
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
