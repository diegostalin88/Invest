# Hipótese P: dividir o aporte por HRP em vez de 1/3 fixo (registro prévio)

Registrado em 15/11/2026, **antes de rodar qualquer teste**. Segue `docs/protocolo-laboratorio.md`.
Até passar, **nada muda** na divisão do aporte do app (continua pela meta e pela regra da faixa).

## Pergunta

Dividir a carteira por **paridade de risco hierárquica** (HRP, López de Prado 2016; implementação do
PyPortfolioOpt) dá um resultado melhor, ajustado ao risco, que a divisão fixa de 1/3 BOVA11 + 1/3 IVVB11 + 1/3 CDI?

Alerta dos livros-base: otimização de carteira tende a ficar ótima no passado e pior à frente (o erro de estimar
covariâncias entra no peso). HRP foi criado justamente para errar menos que a otimização de média-variância, mas
continua sendo um ajuste: por isso o teste é fora da amostra e com o Sharpe deflacionado.

## Dados

- BOVA11 e IVVB11 (Yahoo, fechamento ajustado), CDI diário (BCB série 12). Mesmos dados da carteira do app.
- Período: do primeiro trimestre com 252 pregões de IVVB11 até o último trimestre fechado. Metades: as duas
  metades em número de trimestres.

## Regras (fixas)

| Código | Regra |
|---|---|
| P0 | 1/3 BOVA11 + 1/3 IVVB11 + 1/3 CDI, rebalanceada no último pregão de cada trimestre (referência) |
| P-HRP | No último pregão de cada trimestre, pesos HRP com a covariância dos **252 pregões anteriores** (retornos diários, ligação "single", como o padrão do PyPortfolioOpt), sem posição vendida; mantém até o próximo trimestre |
| P-IV | Igual a P-HRP, mas peso inverso da variância (a versão mais simples de paridade de risco; serve de controle) |

O CDI entra como um "ativo" de variância quase zero. Para não virar 100% CDI, o peso do CDI fica **limitado a 1/3**
nas duas regras (o que sobra vai para BOVA11 e IVVB11 na proporção da regra). Essa trava faz parte do registro.

Execução: pesos calculados com dados até o fechamento do último pregão do trimestre, operados no fechamento do
pregão seguinte. Custo por lado 0,10% (dobrado: 0,20%). IR não modelado (igual para todas).

## Critérios (todos; P-HRP e P-IV contra P0)

1. Sharpe (sobre o CDI) maior que o de P0 no período inteiro e em cada metade.
2. Queda máxima no máximo 2 pontos percentuais pior que a de P0.
3. Com custo dobrado, acima do percentil 95 de 1.000 sorteios de pesos ao acaso (Dirichlet, mesma trava do CDI,
   mesmo calendário de rebalanceamento).
4. Sharpe deflacionado ≥ 95% com o contador do projeto (62 + 2 desta hipótese = **64 tentativas**).

## O que fazer com o resultado

- Reprovou: registrado, não se reabre com outra janela, outra ligação ou outra trava.
- Aprovou: vira teste para frente (2 anos), mostrado no Laboratório lado a lado com P0. A divisão do aporte do app
  só muda depois disso e com a decisão do Diego.

## Onde roda

Na VM, fora do horário da coleta (22:30 UTC), num ambiente separado do da coleta (PyPortfolioOpt puxa scipy e
cvxpy). Ainda **não rodado**: aguarda o pacote e a autorização.
