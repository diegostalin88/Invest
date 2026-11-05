# Hipótese O1: travas de crédito filtradas por IV Rank (B3)

Registrado em **05/11/2026, antes de rodar qualquer número**. O Diego escolheu testar as duas versões do gatilho
lado a lado (simples e técnica). As regras e os critérios abaixo não mudam depois de ver o resultado.

Estudo só de leitura, separado do app e da estratégia congelada (`docs/congelamento.md`). Usa os dados validados
em `docs/opcoes/verificacao-cotahist.md`.

## Pergunta

Vender volatilidade com risco definido (travas de crédito e iron condor) **só quando a IV está cara** (IV Rank alto)
rende mais que o CDI, com risco aceitável, fora da amostra? E o filtro de IV Rank acrescenta algo em relação a
montar as mesmas estruturas sempre?

## Dados

- **Opções e ativos:** COTAHIST anual da B3, 2018 a 2026. Preços de execução pela **melhor oferta no fechamento**:
  vende pela melhor oferta de compra (PREOFC) e compra pela melhor oferta de venda (PREOFV). Sem as duas ofertas, a
  perna não é negociável naquele dia.
- **IV e IV Rank:** como em `opcoes/cotahist.py` (IV no dinheiro de ~30 dias; IV Rank de 252 pregões).
- **CDI:** série 12 do Banco Central. **BOVA11:** fechamento do COTAHIST.

## Universo e períodos

- PETR4, VALE3, BOVA11, ITUB4, BBAS3 e PRIO3 (este só a partir de 2022, quando já tem 252 pregões de IV).
- **Dentro da amostra:** 2019 a 2022 (2018 serve só para formar o primeiro IV Rank).
- **Fora da amostra:** 01/2023 a 10/2026. O veredito sai só daqui.

## Regras

Avaliação no fechamento de cada pregão, **execução no fechamento do pregão seguinte**.

### Versão simples

| Cenário do ativo | Condição | Estrutura | IV Rank mínimo |
| --- | --- | --- | --- |
| Lateral | ADX(14) < 20 | Iron condor | 60 |
| Alta | fechamento acima da MME200 | Trava de alta com put | 50 |
| Baixa | fechamento abaixo da MME200 | Trava de baixa com call | 50 |

A linha de cima tem prioridade. Abaixo do IV Rank mínimo, não entra.

### Versão técnica (sinais do estudo do Diego de 05/11/2026)

| Cenário | Condição | Estrutura | IV Rank mínimo |
| --- | --- | --- | --- |
| Canal estreito | ADX(14) < 20 **e** largura de Bollinger (20, 2) abaixo da mediana dos últimos 252 pregões | Iron condor | 60 |
| Defesa de suporte | fechamento acima da MME200 **e** a mínima do dia tocou a banda inferior de Keltner (MME20 − 2 × ATR10) | Trava de alta com put | 50 |
| Exaustão | IFR(14) acima de 70 | Trava de baixa com call | 50 |

Na ordem da tabela. Sem nenhuma condição, não entra. O suporte "físico" (desenhado no gráfico) não tem definição
objetiva, então fica representado pela banda de Keltner.

### Comum às duas

- **Vencimento:** entre 25 e 50 dias corridos, o mais perto de 35.
- **Perna vendida:** delta mais perto de 0,25 (Black-Scholes com a IV do dia). **Perna comprada:** strike mais
  distante cuja largura fique mais perto de 5% do preço à vista. No iron condor, as duas pernas vendidas usam delta
  mais perto de 0,16, no mesmo vencimento.
- **Uma posição por ativo** por vez.
- **Tamanho:** perda máxima de 1% do capital por operação (perda máxima = largura − crédito). Capital inicial de
  R$ 100 mil; o que não está em risco rende CDI.
- **Saída, a primeira que acontecer:** recompra custa ≤ 50% do crédito (ganho); recompra custa ≥ 2× o crédito
  (perda); faltam ≤ 21 dias para o vencimento. Sem oferta para recomprar, a posição segue; no vencimento, liquida
  pelo valor intrínseco.
- **Custo:** além de comprar na oferta de venda e vender na de compra, R$ 0,005 por opção por perna em cada execução.
- **Imposto:** fora do backtest (vai no relatório como observação).

## Comparações

1. **CDI** acumulado no mesmo período.
2. **BOVA11** comprado e mantido.
3. **Mesmas estruturas sem filtro de IV Rank** (entra sempre que o cenário pedir), para cada versão. É o teste da
   tese: se o filtro não melhorar o resultado, a ideia de "vender só a IV cara" não se sustenta.
4. **Técnica contra simples.** A técnica só é preferível se, além de aprovada, tiver resultado por operação
   (P&L ÷ risco) melhor que a simples.

## Critério de aprovação (fora da amostra, todos, para cada versão)

1. Retorno total acima do CDI acumulado.
2. Fator de lucro ≥ 1,2.
3. Pelo menos 50 operações encerradas.
4. Queda máxima da carteira ≤ 15%.
5. Sem o ativo de melhor resultado, o retorno ainda fica acima do CDI.
6. Com filtro de IV Rank, o resultado por operação é melhor que sem filtro (da mesma versão).

Testar as duas versões no mesmo período fora da amostra aumenta a chance de uma delas passar por sorte. Por isso a
aprovação de uma só versão vale como indício, a confirmar no teste para frente (paper trading).

As travas de débito, o straddle e o collar do estudo do Diego ficam para a hipótese O2.

## Robustez (só informativa, não muda o veredito; só na versão simples)

IV Rank mínimo 40 e 60; delta 0,20 e 0,30; largura 3% e 8%; custo × 2; saída aos 14 dias em vez de 21.

## Resultado

(preenchido depois da execução)

### 1ª execução (05/11/2026, run 42104514625): descartada por erro do simulador

Ambas as versões saíram reprovadas, com acerto de 7% a 13% e 271 de 303 operações encerradas pelo stop. Isso não
é plausível para travas vendidas com delta 0,25 (o esperado é acertar a maioria). A causa é um erro do simulador:
a regra de saída era verificada **no mesmo pregão da entrada**, com as mesmas ofertas. Como montar e desmontar na
hora custa a diferença entre as ofertas das duas pernas, e essa diferença costuma ser maior que o crédito, o stop
de 2× o crédito disparava logo na entrada.

**Correção:** a saída só é verificada a partir do pregão seguinte à entrada. Nenhuma outra regra mudou. O teste
`test_simulacao_ponta_a_ponta` agora exige que toda saída seja depois da entrada. O resultado válido é o da execução
seguinte.
