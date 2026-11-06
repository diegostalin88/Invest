# Hipótese O3: ordem limite no meio das ofertas e levar até o vencimento (B3)

Registrado em **05/11/2026, antes de rodar qualquer número**, depois das reprovações da O1
(`hipotese-travas-credito.md`) e da O2 (`hipotese-travas-debito.md`). As regras e os critérios abaixo não mudam
depois de ver o resultado. Estudo só de leitura, separado do app e da estratégia congelada (`docs/congelamento.md`).

## Por que este teste

Nas duas hipóteses anteriores a perda veio, antes de tudo, da diferença entre as ofertas de compra e venda: entrar
pela oferta e sair pela oferta custava de 40% a 190% do prêmio, e o stop curto disparava logo depois da entrada.
Este teste muda só a **execução**, nas mesmas regras de entrada:

1. **Entrada com ordem limite no meio das ofertas**, que só conta como executada se o mercado de fato negociou a
   opção naquele preço ou melhor no dia.
2. **Sem stop e sem alvo:** a trava fica até o vencimento e é liquidada pelo valor intrínseco. Assim não se paga a
   diferença entre as ofertas na saída.

Se nem assim houver resultado, o problema não é a execução, e a linha de travas com dados diários se encerra.

## Versões

Só as versões simples (o gatilho técnico não acrescentou nada na O1 nem na O2, e testar menos versões diminui a
chance de uma passar por sorte).

| Versão | Regras de entrada | Montagem |
| --- | --- | --- |
| Crédito | As da versão simples da O1: ADX(14) < 20 → iron condor (IV Rank ≥ 60); acima da MME200 → trava de alta com put; abaixo → trava de baixa com call (IV Rank ≥ 50) | Vendida com delta mais perto de 0,25 (0,16 no condor), comprada com largura perto de 5% do preço |
| Débito | As da versão simples da O2: ADX(14) ≥ 20; acima da MME200 → trava de alta com call; abaixo → trava de baixa com put; IV Rank ≤ 35 | Comprada no dinheiro, vendida com largura perto de 5% do preço |

Vencimento entre 25 e 50 dias corridos, o mais perto de 35. Uma posição por ativo. Mesmos papéis e períodos da O1:
PETR4, VALE3, BOVA11, ITUB4, BBAS3 e PRIO3 (este a partir de 2022); dentro da amostra 2019 a 2022; **fora da
amostra 01/2023 a 10/2026, de onde sai o veredito.**

## Execução

- **Sinal** no fechamento do pregão D. No mesmo fechamento, escolhem-se as pernas pela cadeia de D, e o **preço
  limite de cada perna é o meio entre as ofertas de D** (tudo conhecido em D, sem olhar para frente).
- **Pregão D+1:** a perna vendida é executada se a opção foi negociada a um preço **maior ou igual** ao limite
  (máxima do dia, PREMAX ≥ limite); a comprada, se foi negociada a um preço **menor ou igual** ao limite (mínima do
  dia, PREMIN ≤ limite). Só entra se **todas** as pernas forem executadas, pelo preço limite. Se alguma não for, a
  ordem é cancelada e não se tenta de novo; o ativo volta a poder dar sinal no fechamento de D+1.
- **Saída:** nenhuma antes do vencimento. No dia do vencimento (ou no primeiro pregão depois dele), a trava vale o
  valor intrínseco pelo fechamento do papel.
- **Custo:** R$ 0,005 por opção por perna na entrada e outro tanto no vencimento (exercício).
- **Tamanho:** perda máxima de 1% do capital por operação (crédito: largura − crédito; débito: o débito pago).
  Capital inicial de R$ 100 mil; o que não está em risco rende CDI.
- **Marcação diária** (só para a curva e a queda máxima): pelo meio das ofertas.

Limitações conhecidas, a favor da estratégia: supõe que a ordem seria atendida sempre que houve negócio no preço
(sem fila), e que as pernas saem juntas, sem risco de executar uma e não a outra. No vencimento, supõe liquidação
pelo intrínseco, sem o custo de comprar ou vender o papel no exercício. A auditoria mede o peso das duas primeiras.

## Comparações

1. CDI acumulado e BOVA11 comprado e mantido.
2. **Mesmas regras sem filtro de IV Rank**, para cada versão (teste da tese do IV Rank).
3. **Informativo:** entrada pelas ofertas (como na O1 e na O2), também até o vencimento. Separa o efeito do stop do
   efeito da ordem limite.

## Critério de aprovação (fora da amostra, todos, para cada versão)

1. Retorno total acima do CDI acumulado.
2. Fator de lucro ≥ 1,2.
3. Pelo menos 50 operações encerradas.
4. Queda máxima da carteira ≤ 15%.
5. Sem o ativo de melhor resultado, o retorno ainda fica acima do CDI.
6. Com filtro de IV Rank, o resultado por operação é melhor que sem filtro (da mesma versão).

Uma versão aprovada vale como indício, a confirmar no teste para frente (paper trading), porque é o terceiro teste
sobre os mesmos dados fora da amostra.

## Resultado

**Veredito: as duas versões REPROVADAS.** Execução de 05/11/2026
([run 42131554510](https://github.com/diegostalin88/Invest/actions/runs/42131554510)), com o CDI real.

Fora da amostra (01/2023 a 10/2026), capital de R$ 100 mil, caixa livre rendendo CDI:

| Versão | Operações | Acerto | Fator de lucro | P&L ÷ risco | Retorno | CDI | BOVA11 | Queda máx. | Ordens: executadas / parciais / sem execução |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Crédito | 62 | 73% | 0,68 | −5,2% | 54,1% | 59,8% | 58,9% | 2,2% | 66 / 95 / 10 |
| Débito | 117 | 39% | 0,96 | −2,2% | 55,1% | 59,8% | 58,9% | 6,9% | 118 / 117 / 7 |
| Crédito sem filtro de IV Rank | 222 | 72% | 0,48 | −9,8% | 29,6% | 59,8% | 58,9% | 4,2% | 227 / 382 / 23 |
| Débito sem filtro de IV Rank | 162 | 40% | 1,05 | +2,5% | 63,1% | 59,8% | 58,9% | 15,8% | 168 / 147 / 12 |
| Crédito pelas ofertas, até o vencimento | 68 | 71% | 0,43 | −8,6% | 50,9% | 59,8% | 58,9% | 2,1% | – |
| Débito pelas ofertas, até o vencimento | 130 | 39% | 0,70 | −16,8% | 29,4% | 59,8% | 58,9% | 8,2% | – |

Critérios: as duas falham em ficar acima do CDI, no fator de lucro ≥ 1,2 e sem o melhor ativo acima do CDI. O filtro
de IV Rank ajuda no crédito (−5,2% contra −9,8% sem filtro) e atrapalha no débito (−2,2% contra +2,5% sem filtro).
Dentro da amostra (2019 a 2022) o quadro é o mesmo: crédito −5,0%, débito +0,1% por operação, os dois abaixo do CDI.

**O que mudou em relação à O1 e à O2:** a perda por operação caiu muito (crédito de −22% para −5%; débito de −70%
para −2%). Ou seja, a maior parte da perda das hipóteses anteriores vinha mesmo da execução pelas ofertas e do stop
curto. Mas, tirando esse custo, **não sobra vantagem**: as travas ficam no zero a zero e perdem para o CDI, porque
o dinheiro em risco deixa de render juros.

A única linha com P&L positivo (débito sem filtro, +2,5% por operação, fator de lucro 1,05) não foi registrada como
versão a aprovar, fica abaixo do fator de lucro mínimo e, pela auditoria, não se distingue do acaso. Não muda o
veredito.

A auditoria está em `docs/opcoes/auditoria-o3.md`.

### Reexecução com o ajuste de strike por proventos (06/11/2026)

Com a correção do strike das pernas abertas depois de proventos (ver `hipotese-travas-credito.md`), reexecutado
([run 42144260799](https://github.com/diegostalin88/Invest/actions/runs/42144260799)). Aqui a mudança é maior,
porque as travas ficam abertas até o vencimento e passam por mais datas ex:

| Versão | Operações | Acerto | Fator de lucro | P&L ÷ risco | Retorno (CDI 59,8%) |
| --- | --- | --- | --- | --- | --- |
| Crédito | 62 | 77% | 0,73 | −4,4% | 55,0% |
| Débito | 117 | 39% | 0,88 | −6,7% | 47,7% |
| Débito sem filtro de IV Rank | 162 | 40% | 1,02 | +0,9% | 58,5% |

Na auditoria: placebo nos percentis 62 (crédito) e 38 (débito); limite otimista −0,2% e +26%; ordens parciais
iguais (95 e 117). **Veredito mantido**, com o débito agora mais claramente negativo.
