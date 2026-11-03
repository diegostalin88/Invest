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
};

const BASE = (process.argv[2] || 'http://127.0.0.1:8765/').replace(/\/?$/, '/');
const SHOTS = process.argv[3] || '.';
// Aviso conhecido e aceito: o Tailwind via CDN avisa que não deve ser usado em produção.
const IGNORAR = [/cdn\.tailwindcss\.com should not be used in production/i, /browser build of Tailwind CSS should not be used in production/i];

let falhas = 0;
function ok(cond, msg) { console.log(`${cond ? '✅' : '❌'} ${msg}`); if (!cond) falhas++; }

async function abrir(browser, url, bloquearManifesto = false) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const erros = [];
    page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') erros.push(`${m.type()}: ${m.text()}`); });
    page.on('pageerror', e => erros.push(`pageerror: ${e.message}`));
    page.on('dialog', d => { erros.push(`dialog inesperado: ${d.message()}`); d.dismiss(); });
    if (LIBS) {
        await page.route(/^https:\/\/(cdn\.tailwindcss\.com|cdn\.plot\.ly|cdnjs\.cloudflare\.com)\//, r => {
            const chave = Object.keys(CDN_LOCAL).find(k => r.request().url().includes(k));
            if (!chave) return r.abort();
            r.fulfill({ status: 200, contentType: 'application/javascript', body: fs.readFileSync(path.join(LIBS, CDN_LOCAL[chave])) });
        });
        await page.route(/^https:\/\/fonts\.(googleapis|gstatic)\.com\//, r => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));
    }
    if (bloquearManifesto) await page.route('**/data/manifest.json', r => r.fulfill({ status: 404, body: 'not found' }));
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
    const banner = await page.textContent('#data-freshness-banner');
    ok(/Dados até \d{2}\/\d{2}\/\d{4}/.test(banner) && /Fundamentos de \d+ ativos/.test(banner) && /Atualizado em/.test(banner), `cabeçalho de status: "${banner.trim()}"`);
    ok(await page.isHidden('#load-progress'), 'barra de progresso some ao terminar');
    const shortlist = await page.$$eval('#screener-results-container tbody tr td:first-child', tds => tds.map(td => td.textContent.trim()));
    ok(shortlist.includes('CRIT'), 'ativo crítico (CRIT) passou no Screener técnico');

    await page.waitForSelector('#melhores-opcoes-resumo .result-metric', { timeout: 60000 });
    const topResumo = await page.$$eval('#melhores-opcoes-resumo .result-metric .text-lg', els => els.map(e => e.textContent.trim()));
    ok(topResumo.length > 0 && !topResumo.includes('CRIT'), `"Melhores Opções" visível ao abrir, sem o CRIT: ${topResumo.join(', ')}`);
    await page.screenshot({ path: path.join(SHOTS, 'app_inicio.png'), fullPage: true });

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
    await page.click('button[data-tab="walkforward"]');
    await page.click('#run-walkforward-btn');
    await page.waitForSelector('#walkforward-summary .result-metric', { timeout: 30000 });
    ok(true, 'Walk-Forward roda');

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

    // 2) Modo manual quando não existe manifesto
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
