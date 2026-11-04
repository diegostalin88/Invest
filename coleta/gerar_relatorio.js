// Gera o "Relatório" (melhor regra por papel, entradas do próximo pregão, operações abertas, short squeeze)
// abrindo o próprio app num Chromium invisível: usa EXATAMENTE o mesmo motor de backtest do navegador,
// sem duplicar a lógica quantitativa em outra linguagem.
//
// Uso: node coleta/gerar_relatorio.js site
//   Grava site/data/relatorio.json e site/data/br/relatorio.json (se houver dados do Brasil).
//   Falha de um mercado só gera aviso: o site é publicado do mesmo jeito.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const RAIZ = path.resolve(process.argv[2] || 'site');
const TIPOS = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.json': 'application/json', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml', '.webmanifest': 'application/manifest+json' };

function servir() {
    const srv = http.createServer((req, res) => {
        const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/^\/+/, '') || 'index.html';
        const arq = path.join(RAIZ, rel);
        if (!arq.startsWith(RAIZ) || !fs.existsSync(arq) || fs.statSync(arq).isDirectory()) { res.writeHead(404); res.end('not found'); return; }
        res.writeHead(200, { 'Content-Type': TIPOS[path.extname(arq)] || 'application/octet-stream' });
        fs.createReadStream(arq).pipe(res);
    });
    return new Promise(ok => srv.listen(0, '127.0.0.1', () => ok(srv)));
}

function resumo(linhas) {
    const texto = linhas.join('\n');
    console.log(texto);
    if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, texto + '\n');
}

(async () => {
    const srv = await servir();
    const base = `http://127.0.0.1:${srv.address().port}/`;
    const browser = await chromium.launch();
    const linhas = ['', '## 📋 Relatório automático', ''];
    for (const [mercado, pasta] of [['us', 'data'], ['br', 'data/br']]) {
        if (!fs.existsSync(path.join(RAIZ, pasta, 'manifest.json'))) { linhas.push(`- ${mercado.toUpperCase()}: sem dados; pulado.`); continue; }
        const inicio = Date.now();
        const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
        // Não usa o relatório anterior nem o widget do TradingView (só o motor importa aqui)
        await page.route(`**/${pasta}/relatorio.json`, r => r.fulfill({ status: 404, body: '' }));
        await page.route('https://s3.tradingview.com/**', r => r.fulfill({ status: 200, contentType: 'application/javascript', body: '' }));
        page.on('pageerror', e => console.warn(`[${mercado}] erro na página:`, e.message));
        if (process.env.LIBS_LOCAIS) {  // só para rodar localmente sem acesso aos CDNs (igual ao teste do navegador)
            const local = { 'cdn.tailwindcss.com': 'tailwind.js', 'cdn.plot.ly': 'plotly.min.js', 'xlsx.full.min.js': 'xlsx.full.min.js', 'FileSaver.min.js': 'FileSaver.min.js', 'lightweight-charts': 'lightweight-charts.standalone.production.js' };
            await page.route(/^https:\/\/(cdn\.tailwindcss\.com|cdn\.plot\.ly|cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net)\//, r => {
                const k = Object.keys(local).find(c => r.request().url().includes(c));
                return k ? r.fulfill({ status: 200, contentType: 'application/javascript', body: fs.readFileSync(path.join(process.env.LIBS_LOCAIS, local[k])) }) : r.abort();
            });
            await page.route(/^https:\/\/fonts\.(googleapis|gstatic)\.com\//, r => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));
        }
        try {
            await page.goto(`${base}index.html?mercado=${mercado}`);
            await page.waitForFunction(() => window.investDebug && Object.keys(window.investDebug.allData || {}).length > 0
                && document.querySelector('#screener-results-container table'), null, { timeout: 15 * 60 * 1000 });
            // Diário de sinais: continua o da publicação anterior (baixado pelo workflow) e acompanha os sinais
            const arqDiario = path.join(RAIZ, pasta, 'diario.json');
            let anterior = null; try { anterior = JSON.parse(fs.readFileSync(arqDiario, 'utf-8')); } catch (e) { /* primeiro dia */ }
            const { rel, diario, nEntrar } = await page.evaluate(async ant => {
                const I = window.investDebug; const rel = await I.gerarRelatorio();
                const diario = I.atualizarDiario(ant, rel); I.diario = diario;
                const nEntrar = rel.ativos.filter(a => I.vereditoEntrada(a).estado === 'entrar').length;
                return { rel, diario, nEntrar };
            }, anterior);
            fs.writeFileSync(path.join(RAIZ, pasta, 'relatorio.json'), JSON.stringify(rel));
            fs.writeFileSync(arqDiario, JSON.stringify(diario));
            const arqManifesto = path.join(RAIZ, pasta, 'manifest.json');   // avisa o app que os extras existem
            const m = JSON.parse(fs.readFileSync(arqManifesto, 'utf-8')); m.arquivoRelatorio = 'relatorio.json'; m.arquivoDiario = 'diario.json';
            fs.writeFileSync(arqManifesto, JSON.stringify(m, null, 2));
            const fech = diario.sinais.filter(x => x.estado === 'fechado').length, desl = Object.entries(diario.regras || {}).filter(([, r]) => r.desligada).map(([id]) => id);
            const linhaDiario = (`  - Diário: ${diario.sinais.length} sinais anotados desde ${diario.inicio} (${fech} encerrados)${anterior ? '' : ' — começou hoje'}${desl.length ? `; regras desligadas: ${desl.join(', ')}` : ''}.`);
            const conf = rel.ativos.filter(a => a.confirmada).length;
            const sq = rel.ativos.filter(a => a.squeeze).length;
            linhas.push(`- ${mercado.toUpperCase()}: ✅ ${rel.universo} papéis testados, ${conf} com regra confirmada, ${nEntrar} com veredito 🟢 entrar, ${sq} alertas de short squeeze (${Math.round((Date.now() - inicio) / 1000)} s).`, linhaDiario);
        } catch (e) {
            console.error(`[${mercado}] falhou:`, e);
            linhas.push(`- ${mercado.toUpperCase()}: ⚠️ não consegui gerar (${e.message.split('\n')[0]}). O app oferece "Gerar agora" no aparelho.`);
        } finally { await page.close(); }
    }
    await browser.close(); srv.close();
    resumo(linhas);
})().catch(e => { console.error(e); resumo(['', '## 📋 Relatório automático', '', `- ⚠️ falhou: ${e.message}`]); process.exit(0); });
