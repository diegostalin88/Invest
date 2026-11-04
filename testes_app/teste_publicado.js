// Teste de fumaça no site PUBLICADO (só leitura): abre o app como no celular, nos EUA e no Brasil, confere o
// Relatório da noite (cartões, avisos de MME 200 e de balanço, console sem erros) e baixa o PDF.
// Uso: node testes_app/teste_publicado.js https://usuario.github.io/Invest/ [pasta_pdf]
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const BASE = process.argv[2];
const PASTA = process.argv[3] || '.';
let falhas = 0;
const ok = (cond, msg) => { console.log(`${cond ? '✅' : '❌'} ${msg}`); if (!cond) falhas++; };

async function mercado(browser, m) {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, acceptDownloads: true });
    const erros = []; page.on('console', x => { if (x.type() === 'error') erros.push(x.text()); }); page.on('pageerror', e => erros.push(String(e)));
    await page.goto(`${BASE}?mercado=${m}`);
    await page.waitForSelector('#am-top .am-linha', { timeout: 180000 });
    await page.click('.am-nav [data-ir-pagina="mais"]'); await page.click('[data-sub="relatorio"]');
    await page.waitForFunction(() => /Último teste|Gerar agora/.test(document.getElementById('am-relatorio').textContent), null, { timeout: 120000 });
    if (await page.isVisible('#am-relatorio [data-gerar-relatorio]')) {
        ok(false, `${m}: relatório da noite não carregou (oferece "Gerar agora")`); await page.close(); return;
    }
    const r = await page.evaluate(() => {
        const I = window.investDebug, R = I.relatorio;
        const cards = [...document.querySelectorAll('#am-relatorio .rel-card[data-ativo]')].filter(c => /Confirmado fora da amostra/.test(c.textContent));
        const abaixo = cards.filter(c => { const v = I.vsMme200(c.dataset.ativo); return v !== null && v < 0; });
        const balanco = cards.filter(c => I.balancoProximo(c.dataset.ativo));
        const comChipMme = cards.filter(c => /Abaixo da média de 200 dias/.test(c.textContent)).length;
        const comChipBal = cards.filter(c => /📅 Balanço/.test(c.textContent)).length;
        const est = {}; R.ativos.forEach(a => { const e = I.vereditoEntrada(a).estado; est[e] = (est[e] || 0) + 1; });
        const comEstimativa = Object.values(I.fundamentos || {}).filter(f => f && f.balancoEstimado).length;
        const aaoi = cards.find(c => c.dataset.ativo === 'AAOI');
        return { ultimo: R.ultimoPregao, cards: cards.length, abaixo: abaixo.length, comChipMme, balanco: balanco.map(c => c.dataset.ativo + ':' + JSON.stringify(I.balancoProximo(c.dataset.ativo))), comChipBal, est, comEstimativa,
            aaoi: aaoi ? aaoi.textContent.replace(/\s+/g, ' ').trim().slice(0, 900) : null };
    });
    console.log(`${m}: dados de ${r.ultimo}; vereditos ${JSON.stringify(r.est)}; ${r.comEstimativa} papéis com balanço estimado; balanço próximo: ${r.balanco.join(' ') || 'nenhum'}`);
    ok(r.cards > 0, `${m}: Relatório publicado com ${r.cards} cartões`);
    ok(r.abaixo === r.comChipMme, `${m}: aviso "abaixo da MME 200" em ${r.comChipMme} de ${r.abaixo} cartões esperados`);
    ok(r.balanco.length === r.comChipBal, `${m}: aviso de balanço em ${r.comChipBal} de ${r.balanco.length} cartões esperados`);
    if (r.aaoi) console.log(`AAOI no cartão: ${r.aaoi}`);
    const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 60000 }), page.click('#am-relatorio [data-baixar-relatorio-pdf]')]);
    const destino = path.join(PASTA, dl.suggestedFilename()); await dl.saveAs(destino);
    const bytes = fs.readFileSync(destino);
    ok(bytes.slice(0, 5).toString() === '%PDF-' && bytes.length > 3000, `${m}: PDF baixado (${dl.suggestedFilename()}, ${Math.round(bytes.length / 1024)} KB)`);
    ok(erros.length === 0, `${m}: console sem erros${erros.length ? ': ' + erros.slice(0, 3).join(' | ') : ''}`);
    await page.close();
}

(async () => {
    const browser = await chromium.launch();
    for (const m of ['us', 'br']) { try { await mercado(browser, m); } catch (e) { ok(false, `${m}: ${e.message}`); } }
    await browser.close();
    console.log(falhas ? `\n${falhas} verificação(ões) falharam.` : '\nTodas as verificações passaram.');
    process.exit(falhas ? 1 : 0);
})();
