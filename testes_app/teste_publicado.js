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
    if (process.env.LIBS_LOCAIS) {  // só para rodar localmente sem acesso aos CDNs
        const local = { 'cdn.tailwindcss.com': 'tailwind.js', 'cdn.plot.ly': 'plotly.min.js', 'xlsx.full.min.js': 'xlsx.full.min.js', 'FileSaver.min.js': 'FileSaver.min.js', 'lightweight-charts': 'lightweight-charts.standalone.production.js', 'jspdf': 'jspdf.umd.min.js' };
        await page.route(/^https:\/\/(cdn\.tailwindcss\.com|cdn\.plot\.ly|cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net|unpkg\.com|s3\.tradingview\.com)\//, rt => {
            const k = Object.keys(local).find(c => rt.request().url().includes(c));
            return k ? rt.fulfill({ status: 200, contentType: 'application/javascript', body: fs.readFileSync(path.join(process.env.LIBS_LOCAIS, local[k])) }) : rt.fulfill({ status: 200, contentType: 'application/javascript', body: '' });
        });
        await page.route(/^https:\/\/fonts\.(googleapis|gstatic)\.com\//, rt => rt.fulfill({ status: 200, contentType: 'text/css', body: '' }));
    }
    const erros = []; page.on('console', x => { if (x.type() === 'error') erros.push(x.text()); }); page.on('pageerror', e => erros.push(String(e)));
    await page.goto(`${BASE}?mercado=${m}`);
    await page.waitForSelector('#am-top .am-linha', { state: 'attached', timeout: 180000 });
    // Bússola: termômetro com a renda fixa, lista de ativos e histórico de balanços (EUA e Brasil)
    await page.waitForSelector('#am-termometro [data-termometro]', { timeout: 60000 });
    const T = await page.evaluate(() => { const I = window.investDebug, t = I.termometroIndice(); return t && { nome: t.nome, data: t.data, ret12m: t.ret12m, rf12m: t.rf12m, nomeRF: t.nomeRF, distMM200: t.distMM200, quedaPico52: t.quedaPico52, vol: t.vol, acimaMM10: t.acimaMM10 }; });
    console.log(`${m}: termômetro ${JSON.stringify(T)}`);
    ok(T && T.rf12m !== null && T.rf12m > 0.01 && T.rf12m < 0.2, `${m}: termômetro com ${T && T.nomeRF} de 12 meses plausível (${T && T.rf12m})`);
    await page.click('.am-nav [data-ir-pagina="ranking"]');
    const nAt = await page.$$eval('#am-ranking .am-linha', l => l.length);
    ok(nAt >= 30 && !(await page.$('#am-ranking .am-chip')), `${m}: Ativos lista ${nAt} papéis sem score`);
    {
        await page.evaluate(() => window.investDebug.carregarBalancos());
        const bal = await page.evaluate(() => { const B = window.investDebug.balancos; if (!B) return null; const ts = Object.keys(B.ativos); const t = ['AAPL', 'MSFT', 'NVDA', 'PETR4', 'VALE3', 'ITUB4'].find(x => B.ativos[x]) || ts[0]; const q = B.ativos[t].tri.slice(-1)[0]; return { n: ts.length, t, q: { fim: q.fim, divulgado: q.divulgado, receita: q.receita, lucro: q.lucro, receitaAno: q.receitaAno, quinto: q.quinto }, reacao: window.investDebug.reacaoBalanco(t, q.divulgado) }; });
        console.log(`${m}: balanços ${JSON.stringify(bal)}`);
        ok(bal && bal.n >= (m === 'us' ? 500 : 50), `${m}: histórico de balanços publicado (${bal && bal.n} papéis)`);
        if (bal) {
            await page.fill('#am-busca', bal.t); await page.click(`#am-ranking .am-linha[data-ativo="${bal.t}"]`);
            await page.click('#am-abas [data-aba="balancos"]');
            await page.waitForSelector('[data-balancos] [data-balanco]', { timeout: 30000 });
            ok((await page.$$('[data-balancos] [data-balanco]')).length >= 8, `${m}: aba Balanços de ${bal.t} com os trimestres`);
            await page.goBack();
        }
    }
    await page.click('.am-nav [data-ir-pagina="inicio"]');
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
    // Simulação com os dados publicados: ordem dada no pregão anterior já tem de estar comprada na abertura do último
    // pregão; ordem dada hoje fica aguardando a próxima coleta. Usa uma cópia e devolve o que havia no aparelho.
    const sim = await page.evaluate(() => {
        const I = window.investDebug, R = I.relatorio, chaves = Object.keys(localStorage), guardado = {}; chaves.forEach(k => guardado[k] = localStorage.getItem(k));
        try {
            const a = R.ativos.find(x => ['entrar', 'atrasado'].includes(I.vereditoEntrada(x).estado)) || R.ativos.find(x => I.vereditoEntrada(x).estado === 'ja' && x.atrEntrada > 0 && x.desde < I.allData[x.t].dates[I.allData[x.t].dates.length - 2]); if (!a) return { semCandidato: true };
            localStorage.removeItem('invest-simulacao');
            const r1 = I.seguirNaSimulacao(a.t); const s = I.lerSim(); const hoje = s.ordens[0].dataTela;
            const d = I.allData[a.t], ult = d.dates[d.dates.length - 1], penult = d.dates[d.dates.length - 2];
            const eHoje = I.estadoSim(); const antes = eHoje.ordens[0].estado;
            s.ordens[0].dataTela = penult; if (s.ordens[0].tipo === 'entrar') s.ordens[0].sistema.dataSinal = penult; I.gravarSim(s);
            const e = I.estadoSim(); const o = e.ordens[0];
            return { t: a.t, tipo: s.ordens[0].tipo, ok: r1.ok, hoje, ult, antes, depois: o.estado, dataEnt: o.dataEnt, precoEnt: o.precoEnt, abertura: d.open[d.dates.length - 1], motivo: o.motivo || null };
        } finally { localStorage.clear(); Object.entries(guardado).forEach(([k, v]) => localStorage.setItem(k, v)); }
    });
    console.log(`${m}: simulação ${JSON.stringify(sim)}`);
    if (!sim.semCandidato) {
        ok(sim.ok && sim.antes === 'aguardando', `${m}: ordem dada hoje (${sim.t}) fica aguardando a abertura do próximo pregão, que só entra na coleta da noite`);
        ok(['aberta', 'fechada', 'cancelada'].includes(sim.depois) && (sim.depois === 'cancelada' || sim.dataEnt === sim.ult), `${m}: ordem dada no pregão anterior foi executada na abertura de ${sim.ult} (${sim.depois}${sim.motivo ? ': ' + sim.motivo : ''})`);
    }
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
