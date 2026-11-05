# Invest — bússola de investimentos que se atualiza sozinha

**Endereço:** https://diegostalin88.github.io/Invest/

Depois da auditoria de 04/11/2026, os testes mostraram que a estratégia técnica do app **não vence o índice**
(nem nos EUA, nem no Brasil). Desde 05/11/2026 o app deixou de prometer previsão e virou uma bússola: descreve o
mercado e a carteira com números que se pode conferir, e cobra cada decisão contra o índice e contra o CDI.

O que o app mostra (barra de baixo: Início · Ativos · Carteira · Mais):

- **Termômetro do índice** (SPY / BOVA11): média de 10 meses, distância da média de 200 dias, queda desde o topo,
  retorno de 1, 3 e 12 meses, a renda fixa (CDI / T-bill) no mesmo período e a volatilidade. Descreve; não prevê.
- **Amplitude do mercado:** quantos papéis estão acima da média de 200 dias.
- **Ativos:** o mercado todo, por volume, altas, quedas, distância do topo ou volatilidade (sem score).
- **Tela do papel:** retorno de 1 ano contra o índice, oscilação, queda do topo, peso na sua carteira, fundamentos e,
  nos EUA, os **últimos 12 balanços trimestrais** (SEC), com a data de divulgação e a reação do preço.
- **Carteira:** saúde (concentração, papéis "efetivos", setor, correlação, beta, queda máxima), o mesmo dinheiro de
  cada compra no índice e no CDI, e um **plano de alocação** (renda fixa, fundo de índice, ações escolhidas) com
  faixas de rebalanceamento e a divisão do próximo aporte.
- **Diário das decisões:** cada compra e venda anotada na hora, com o placar contra o índice e o CDI.
- **Imposto das vendas do mês (Brasil):** isenção de R$ 20 mil, prejuízo a compensar e DARF.
- **O que já foi testado:** cada ideia com registro prévio e o veredito (`docs/`).
- **Avançado:** a estratégia técnica congelada (ranking, simulação, backtest), mantida só para o teste para frente
  até 11/2027. O app antigo, com todos os módulos técnicos, abre em `?classico=1`.

> ⚠️ **Não é recomendação de investimento.** É uma ferramenta de apoio à análise, com dados de fontes
> gratuitas que podem vir incompletos, defasados ou (raramente) errados. Confira sempre a fonte primária
> (site de RI da empresa, filings na SEC) antes de decidir qualquer operação.

## Como funciona a atualização automática

```
GitHub Actions (seg–sex, 22:30 UTC, depois do fechamento)
  └─ coleta/fetch_all.py
       1. lista de tickers (nasdaqtrader.com), sem ETFs e sem emissores com problema financeiro
       2. preços OHLCV ajustados de 5 anos (Yahoo, via yfinance), em lotes
       3. pré-filtro: ≥ 250 pregões e volume financeiro médio 20d ≥ US$ 2 mi
       4. fundamentos + sinais extras para quem tem volume ≥ US$ 10 mi (cache de 7 dias)
       5. radar de 8-K (SEC) para esse mesmo grupo, todo dia
       6. grava site/data/: manifest.json, precos_000.json, precos_001.json…, fundamentos.json
       7. portão de qualidade: se os dados parecerem quebrados, o job falha e NADA é publicado
       8. Brasil: carteira atual do IBOVESPA (site da B3; se falhar, coleta/ibovespa_reserva.txt), preços e
          fundamentos do Yahoo com sufixo .SA, gravados em site/data/br/. Sem radar de 8-K (é da SEC).
          Se o Brasil falhar, os dados do Brasil já publicados são mantidos e os EUA saem normalmente.
  └─ copia app/ para site/
  └─ coleta/vendidos.py: posições vendidas (aluguel de ações da B3 e short interest da FINRA) → vendidos.json
  └─ coleta/gerar_relatorio.js: abre o app num Chromium invisível e roda os backtests com o MESMO motor do
       navegador → relatorio.json (melhor regra por papel escolhida em 60% do histórico e confirmada nos 40%
       finais; entradas do próximo pregão; operações abertas; alerta de short squeeze)
       Vendidos e relatório são opcionais: se falharem, o site sai do mesmo jeito e o app oferece "Gerar agora".
  └─ publica no GitHub Pages
```

- O navegador não consegue buscar esses dados direto (Yahoo, SEC e nasdaqtrader não liberam CORS, e a SEC
  exige um `User-Agent` identificado). Por isso a coleta roda nos servidores do GitHub.
- **Os dados não ficam no git.** Eles vivem só no site publicado; o repositório guarda apenas o código.
- O app, ao abrir, baixa `data/manifest.json`, depois os arquivos de preço em paralelo e o `fundamentos.json`,
  todos do mesmo endereço do site.
- **Cache de fundamentos:** a cada execução, a coleta parte do `fundamentos.json` já publicado e só re-busca no
  Yahoo o que tem mais de 7 dias ou é novo. Se a busca de um ativo falhar, o valor anterior é mantido. Na
  primeira execução isso pode levar até ~90 minutos; o que não couber fica para os dias seguintes.
- **Portão de qualidade:** o job falha (e o site anterior continua no ar) se a quantidade de ativos cair mais de
  30% em relação à execução anterior, se o último pregão tiver mais de 5 dias corridos, ou se nenhum
  fundamento vier preenchido. Isso cobre o caso de o Yahoo bloquear acessos vindos do GitHub.
- **Tamanho:** preços arredondados (2 casas, ou 4 abaixo de US$ 1), datas gravadas uma vez por arquivo e
  arquivos de até ~20 MB. Se o total passar de 80 MB, o histórico cai de 5 para 3 anos (isso afeta Backtest e
  Walk-Forward) e o resumo da execução avisa.
- Todo mês um job leve atualiza `status/ultima_execucao.txt`, porque o GitHub desativa agendamentos de
  repositórios públicos depois de 60 dias sem atividade.

As constantes (cortes de liquidez, validade do cache, anos de histórico, limites) ficam no topo de
[`coleta/fetch_all.py`](coleta/fetch_all.py).

## Rodar a coleta manualmente (pelo GitHub)

**Actions → "Atualizar dados" → "Run workflow"**.

- Deixe `ticker_limit` vazio para o universo completo.
- Preencha `ticker_limit` (ex.: `100`) para um **modo teste** rápido, que processa só os primeiros N tickers.
  Atenção: depois que o site já tiver os dados completos, o modo teste é bloqueado de propósito pelo portão de
  qualidade (a queda de tickers passa de 30%), para não substituir o site bom por um pequeno.

- Marque `somente_app` para só republicar o app com os dados já publicados (sem nova coleta, ~1 minuto). Isso
  também acontece sozinho a cada commit que mexe em `app/`.

Ao final de cada execução, o resumo do job mostra: último pregão, quantidade de ativos, fundamentos
atualizados, alertas críticos, tamanho dos arquivos, tempo de execução e avisos.

## Rodar no seu computador

Requer Python 3.11+ (o GitHub usa 3.13).

```bash
pip install -r coleta/requirements.txt

# Linux/Mac
export SEC_USER_AGENT="InvestDiego seu-email@exemplo.com"
export TICKER_LIMIT=50            # opcional: modo teste
python coleta/fetch_all.py --saida site/data

# Windows (PowerShell)
$env:SEC_USER_AGENT="InvestDiego seu-email@exemplo.com"
$env:TICKER_LIMIT="50"
python coleta/fetch_all.py --saida site/data
```

Depois, copie o app e sirva a pasta (abrir o `index.html` com duplo clique não funciona, porque o navegador
bloqueia a leitura de arquivos via `file://`; nesse caso o app abre o "Modo manual"):

```bash
cp -r app/. site/
python -m http.server 8000 --directory site
# abra http://localhost:8000
```

**Modo manual (avançado):** no topo do app há um bloco recolhível para carregar arquivos à mão (o JSON de preços
no formato antigo `{TICKER: {dates, open, high, low, close, volume}}` ou um `precos_NNN.json`, e o
`fundamentos.json`). Ele abre sozinho se os dados automáticos não estiverem disponíveis.

## Testes

```bash
# Coleta (sem rede: Yahoo, SEC e nasdaqtrader são simulados)
python -m pytest -q coleta/tests

# App em navegador real (Playwright para Node + Chromium)
python testes_app/gerar_site_exemplo.py /tmp/site_exemplo
python -m http.server 8765 --directory /tmp/site_exemplo &
node testes_app/teste_navegador.js http://127.0.0.1:8765/ .
```

Os testes da coleta também rodam no workflow, antes de cada coleta.

## Limitações

- **Fontes gratuitas.** Yahoo Finance (via `yfinance`, que é raspagem não oficial) e SEC EDGAR. Podem mudar,
  limitar acesso ou trazer dados incompletos. Fundamentos do Yahoo podem estar defasados em um trimestre.
- **O Yahoo pode bloquear** acessos vindos de IPs de nuvem, como os do GitHub. O portão de qualidade evita
  publicar dados quebrados, mas aí o site fica com os dados do último dia bom até a coleta voltar a funcionar.
  O cabeçalho do app fica amarelo/vermelho quando os dados estão velhos.
- **Viés de sobrevivência.** A lista de ativos é a de hoje. Empresas que faliram ou foram deslistadas nos
  últimos anos não aparecem, então backtests tendem a ser otimistas.
- **Universo filtrado.** Só entram ativos com volume financeiro médio ≥ US$ 2 mi/dia (o Screener usa US$ 50 mi
  por padrão). Isso também afeta o termômetro de regime (% de ativos acima da MME200), que deixa de contar as
  micro-caps.
- **Radar de 8-K** cobre só empresas que arquivam na SEC e olha os últimos 180 dias.
- **Não é recomendação de investimento.**

## Estrutura

```
app/                         o app (index.html, PWA: manifest, ícones, service worker)
coleta/fetch_all.py          coleta única (preços, fundamentos, radar de 8-K, manifesto, portão)
coleta/brasil.py             coleta do IBOVESPA (chamada no fim do fetch_all.py; --sem-brasil desliga)
coleta/requirements.txt      dependências com versões fixadas
coleta/tests/                testes da coleta, sem rede
testes_app/                  site de exemplo sintético + teste em navegador (Playwright)
.github/workflows/           workflow "Atualizar dados"
legado/                      GRAFICO16.html, fetch_data4.py e fetch_fundamentals.py originais (referência)
docs/referencias.md          livros que embasam a estratégia, o que o app já usa de cada um e o que falta
status/                      arquivinho atualizado mensalmente para manter o agendamento ativo
```
