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

## Resultado (07/11/2026, [run 42331755030](https://github.com/diegostalin88/Invest/actions/runs/42331755030))

**Veredito: nenhum ETF de dividendos substitui o índice no núcleo.** Retorno total com dividendos reinvestidos,
comprando e segurando.

| ETF × régua | Período | Ao ano | Sharpe | Queda máx. | Critérios 1 / 2 / 3 |
| --- | --- | --- | --- | --- | --- |
| DIVO11 × BOVA11 | 2012–2026 | 9,8% × 7,0% | 0,11 × 0,01 | −56% × −47% | passa / **falha** / passa |
| SCHD × SPY | 2011–2026 | 13,6% × 14,7% | 0,80 × 0,81 | −33% × −34% | falha / passa / falha |
| VIG × SPY | 2006–2026 | 10,2% × 10,8% | 0,56 × 0,54 | −47% × −55% | falha (2ª metade) / passa / passa |
| DVY × SPY | 2003–2026 | 9,0% × 10,8% | 0,46 × 0,55 | −63% × −55% | falha / falha / falha |
| SDY × SPY | 2005–2026 | 9,1% × 10,9% | 0,47 × 0,55 | −55% × −55% | falha / passa / falha |
| HDV × SPY | 2011–2026 | 11,1% × 13,6% | 0,69 × 0,74 | −37% × −34% | falha / falha / falha |
| NOBL × SPY | 2013–2026 | 10,8% × 13,8% | 0,61 × 0,73 | −35% × −34% | falha / falha / falha |

- **Brasil:** o DIVO11 rendeu mais que o BOVA11 (+290% contra +167%) e teve Sharpe maior nas duas metades, mas caiu
  mais no pior momento (−56% contra −47%). Pelo critério registrado, não substitui. **Os dois perderam para o CDI**
  (+298% no mesmo período). O 50/50 (informação): 8,4% ao ano, queda de −48%.
- **EUA:** os ETFs de dividendos pagam mais renda (SCHD, DVY e HDV cerca de 3% ao ano contra 1–2% do SPY), mas
  todos renderam menos que o SPY no total. O VIG foi o mais perto: caiu menos (−47% contra −55%) e quase empatou
  no Sharpe, mas perdeu na 2ª metade.
- Os ETFs brasileiros de ações **reinvestem** os dividendos dentro da cota (renda medida = 0); quem quer renda em
  dinheiro no Brasil recebe das ações diretamente ou de FIIs.

**Leitura:** dividendo não é retorno extra; é parte do retorno que sai em dinheiro (o preço cai no valor pago). A
carteira de dividendos troca crescimento por renda e por um perfil diferente de risco, sem ganhar do índice. Para o
núcleo da holding, o índice continua sendo a régua. O DIVO11 pode entrar como **parte** do núcleo brasileiro para quem
aceita uma queda maior, sabendo que não foi aprovado como substituto.
