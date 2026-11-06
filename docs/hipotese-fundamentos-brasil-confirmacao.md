# Confirmação da hipótese C-BR em 2012 a 2020

Registrado em **06/11/2026, antes de baixar os dados novos e de rodar qualquer número**, depois do resultado da C-BR
(`docs/hipotese-fundamentos-brasil.md`), que foi aprovada em 06/2020 a 09/2026. As regras e os critérios abaixo não
mudam depois de ver o resultado. Estudo só de leitura.

## Por que este teste

A C-BR só cobriu seis anos, porque a CVM só publica a composição do capital nos ITR/DFP a partir de 2020. O período
de 2012 a 2020 **não foi visto** pelo teste e é diferente: CDI alto em 2012–2016, recessão em 2015–2016, recuperação
em 2016–2019 e a queda da pandemia em 2020. Se a vantagem for real, ela aparece aqui também.

## O que muda

Só a fonte da quantidade de ações antes de 2020: o **Formulário de Referência (FRE)** da CVM, entregue uma vez por
ano, que tem o capital social com a quantidade total de ações desde 2010
(`dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE`).

- Vale o capital **integralizado** (se não houver, o emitido). Ações em tesouraria não são descontadas (o FRE não
  traz a tesouraria no mesmo arquivo); a diferença costuma ser pequena.
- Um FRE só vale a partir do pregão seguinte à data de entrega à CVM. Se a data de entrega não estiver no arquivo,
  vale a partir de 30 de junho do ano do formulário (o prazo de entrega é até o fim de maio).
- A mesma correção de escala da C-BR: valor de mercado abaixo de R$ 1 bilhão → ações tratadas como em milhares.

Todo o resto é igual à C-BR: universo (carteira atual do IBOVESPA, sem units, um código por empresa), indicadores
(lucro/preço e dividendos), 15 papéis, rebalanceamento trimestral, custos, sorteios e robustez.

## Período

Rebalanceamentos de **03/2012 a 03/2020**; a última carteira é mantida até 30/06/2020, onde a C-BR começa. Datas com
menos de 30 elegíveis ficam de fora, como na C-BR.

## Critérios de confirmação (todos)

1. O retorno total fica acima do **percentil 95** das carteiras sorteadas.
2. O retorno anual fica acima do BOVA11, com queda máxima até 1,5 × a do BOVA11.
3. Vence a carteira de todos os elegíveis com pesos iguais **nas duas metades** do período.
4. Com custo × 2, continua acima do BOVA11.
5. O retorno total fica acima do CDI acumulado no mesmo período.
6. Pelo menos 24 trimestres com 30 elegíveis ou mais (6 dos 8 anos). Se não houver, o resultado é **inconclusivo**,
   não aprovado nem reprovado.

Se confirmar, a carteira passa a candidata a entrar no app como informação, a ser acompanhada para frente. Se não
confirmar, a C-BR fica como resultado de um período só, sem uso.

## Limitações conhecidas antes de rodar

- **O viés de sobrevivência é maior aqui:** voltando no tempo, a carteira atual do IBOVESPA inclui empresas que só
  ficaram grandes depois, e não inclui as que quebraram ou encolheram no período. As comparações com o acaso e os
  pesos iguais do mesmo universo continuam valendo como controle, mas não eliminam o viés.
- **Menos papéis elegíveis no início:** muitas empresas da carteira atual abriram o capital depois de 2012.

## Resultado (06/11/2026, [run 42212966317](https://github.com/diegostalin88/Invest/actions/runs/42212966317))

**Veredito: REPROVADA.** Passou nos critérios 2, 4, 5 e 6; falhou no 1 e no 3. Período de 30/03/2012 a 30/06/2020,
33 trimestres, ~37 elegíveis por data.

| Carteira | Retorno | Ao ano | Queda máx. |
| --- | --- | --- | --- |
| **Lucro/preço + dividendos (15 papéis)** | **167,8%** | **12,7%** | 36,1% |
| BOVA11 | 43,4% | 4,5% | 37,7% |
| CDI | 104,1% | | 0,0% |
| Pesos iguais, todos os elegíveis | 204,4% | | |
| Acaso (200 carteiras de 15) | p5 105,9%, mediana 192,4%, p95 289,1% | | |
| Só lucro/preço | 182,5% | | |
| Só dividendos | 182,0% | | |
| 10 papéis | 213,4% | | |
| 20 papéis | 149,0% | | |
| Custo × 2 | 164,5% | | |

- **Critério 1 (acaso):** percentil 32. A carteira ficou abaixo da mediana das carteiras sorteadas.
- **Critério 3 (pesos iguais nas duas metades):**
  - 2012 a 2016: carteira −1,0% contra pesos iguais 16,6% (BOVA11 −23,9%, CDI 47,0%). Perdeu.
  - 2016 a 2020: carteira 170,4% contra pesos iguais 161,0% (BOVA11 88,4%, CDI 38,8%). Ganhou.
- Por ano (carteira): 2012 4,6%; 2013 −5,4%; 2014 −6,5%; 2015 −12,5%; 2016 52,4%; 2017 38,1%; 2018 32,9%;
  2019 45,6%; 2020 (até jun.) −18,7%.
- Correções de escala: 4 datas (DIRR3, MGLU3, PRIO3).
- O rebalanceamento semestral desta execução saiu errado (somava carteiras depois de 30/06/2020) e foi
  desconsiderado; o erro foi corrigido no código. Era só informativo e não entra nos critérios.

**Leitura:** ganhar do BOVA11 aqui não diz muito, porque o universo é a carteira atual do IBOVESPA, cheia de empresas
que sobreviveram e cresceram. O controle certo é escolher ao acaso dentro do mesmo universo, e a regra de lucro e
dividendos não fez melhor que isso. A vantagem de 2020 a 2026 foi de um período só. A C-BR não vira candidata ao app.

