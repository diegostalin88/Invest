# Hipótese H: carteira de holding com dividendos (comprar e segurar)

Registrado em **07/11/2026, antes de escrever o código e de ver qualquer número**. As regras e os critérios abaixo
não mudam depois de ver o resultado. Estudo só de leitura, separado do app e da estratégia congelada
(`docs/congelamento.md`).

## Por que este teste

Depois que day trade e swing trade foram reprovados, o Diego perguntou qual é a melhor forma de montar uma carteira
de **longo prazo (holding)**, com a opção de focar em **pagadoras de dividendos**.

O que já sabemos:

- **Escolher papéis por lucro/preço e dividendos** (C-BR) ganhou do acaso em 2020–2026, mas ficou no percentil 32
  das carteiras sorteadas em 2012–2020 e perdeu para os pesos iguais do mesmo universo. Reprovada.
- **Valor + qualidade nos EUA** (C) ficou abaixo da mediana do acaso. Reprovada.
- **O índice** (SPY e BOVA11) venceu quase tudo o que testamos.

Então este teste **não escolhe papéis**. Ele mede os jeitos prontos e baratos de ter uma carteira de dividendos (os
ETFs que seguem índices de dividendos) contra o índice amplo, comprando e segurando. ETFs não têm viés de
sobrevivência dentro deles (a regra do índice é pública e a cota existe desde a data de lançamento), o que evita o
problema que afetou C e C-BR.

## Carteiras

Comprar e segurar, dividendos reinvestidos (fechamento ajustado por proventos do Yahoo Finance), sem
rebalanceamento. A taxa de administração já está no preço da cota.

**Brasil (régua: BOVA11)**

- **BOVA11**: Ibovespa.
- **DIVO11**: ETF do IDIV (índice de dividendos da B3).
- **50/50**: metade BOVA11 e metade DIVO11, rebalanceado uma vez por ano no último pregão do ano, custo de 0,1% sobre
  o giro.

**EUA (régua: SPY)**

- **SPY**: S&P 500.
- **SCHD**, **VIG**, **DVY**, **SDY**, **HDV**, **NOBL**: os seis ETFs de dividendos mais conhecidos, cada um
  desde a sua primeira cota.

**Caixa para o Sharpe:** CDI (Banco Central, série SGS 12) no Brasil; T-bill de 3 meses (^IRX) nos EUA.

## Período

Para cada ETF, o período comum com a sua régua: da primeira cota com fechamento do ETF até o último pregão
disponível. As **metades** dividem esse período ao meio, pelo número de pregões.

## O que se mede

- Retorno total e ao ano; volatilidade; Sharpe (excesso sobre o caixa); queda máxima; pior janela de 12 meses.
- **Renda:** dividendos pagos nos últimos 12 meses ÷ preço de hoje (sem ajuste) e a média anual no período.
- Ano a ano contra a régua.

## Critérios para um ETF de dividendos poder **substituir o índice no núcleo** (todos)

1. Sharpe maior ou igual ao da régua no período inteiro **e** em cada metade.
2. Queda máxima no período inteiro não pior que a da régua.
3. Retorno ao ano no período inteiro até no máximo 1 ponto abaixo da régua (renda não compensa perder muito
   crescimento).

Nos EUA são **seis candidatos**: escolher o melhor entre seis já favorece achar um que passa. Por isso, se algum
passar, ele vira **candidato**, não aprovado: precisa ser confirmado nos próximos 12 meses contra o SPY antes de
entrar no app como sugestão.

**Se nenhum passar:** o índice continua sendo o núcleo, e o ETF de dividendos fica só como opção de **renda**, para
quem prefere receber dinheiro na conta, sabendo quanto custa em retorno e em risco.

O 50/50 do Brasil é medido só como informação (não entra nos critérios).

## Limitações conhecidas antes de rodar

- **Históricos curtos:** DIVO11, SCHD, HDV e NOBL têm cerca de 11 a 15 anos; um ou dois ciclos.
- **Preço ajustado do Yahoo:** pode ter falhas em proventos de ETFs brasileiros. A renda dos 12 meses é conferida
  contra o fechamento sem ajuste.
- **Imposto fora:** no Brasil, ETF de ações não tem isenção de R$ 20 mil por mês nas vendas (15% sobre o ganho), e os
  dividendos recebidos pelo ETF são reinvestidos dentro dele. Para quem segura e não vende, o efeito é pequeno.
- **ETFs que fecharam** não aparecem; os seis dos EUA são os sobreviventes mais populares.
