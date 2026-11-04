# Cenário: queda forte seguida de reversão

Registrado em **04/11/2026, 18h30, antes de rodar qualquer número**. Os parâmetros e critérios abaixo não mudam depois de ver o resultado.

Este é um estudo de cenário, só de leitura. Não muda o app, o Relatório nem a estratégia congelada.

**Motivação:** o trade da MOVI3 em março de 2025. A ação vinha de uma queda forte, apareceu um sinal "Otimista" e ela subiu mais de 100%.

**Pergunta:** quando esse tipo de situação aparece, ela é favorável? Ou seja, os poucos acertos pagam com folga os muitos erros?

## Definição (fixa)

- **Queda forte:** o fechamento do dia está pelo menos **30% abaixo** da maior máxima dos **60 pregões** anteriores, contando o dia.
- **Reversão:** a estratégia **Otimista** do app dispara no mesmo dia. Ela exige as três condições:
  - ADL acima da sua média de 5;
  - Momento(10) subindo;
  - IFR14 cruzando para cima a sua média de 9.

  É o mesmo motor `v14_analisarSinais`, copiado do `index.html` em tempo de execução.
- **Entrada:** na abertura do pregão seguinte, com custo de 0,1% por perna.
- **Saídas medidas:**
  1. **Saída do app:** stop inicial no mais próximo entre 2,5 ATR e 8%; stop móvel no fechamento − 2,5 ATR, que só sobe; gap abaixo do stop sai na abertura.
  2. **Horizontes fixos:** fechamento depois de 20, 40 e 60 pregões.
- **Sem repetição:** depois de um evento, o mesmo papel só pode gerar outro evento 20 pregões depois. Isso evita contar a mesma queda várias vezes.
- **Universos:**
  - Brasil: os 76 papéis publicados (Ibovespa atual, 5 anos).
  - EUA: os 400 mais líquidos do Relatório (3 anos).

## Comparações

1. **Acaso na mesma condição:** sorteia, nos mesmos papéis, dias com queda forte **sem exigir o sinal**, em número igual ao de eventos. Repete 500 vezes. Isso mede se a Otimista acrescenta algo à queda.
2. **Qualquer dia:** todos os dias dos mesmos papéis, com a mesma saída.
3. **Índice nas mesmas datas:** BOVA11 ou SPY, da entrada até a saída de cada evento.

## Critérios (todos, por mercado)

O cenário é **favorável** se valerem as três condições:

1. **Contra o acaso:** a média por operação, com a saída do app, fica acima do **percentil 95** do acaso na mesma condição.
2. **Expectativa positiva:** a média por operação com a saída do app é maior que zero, com custos, e maior que a média do índice nas mesmas datas.
3. **Robustez:** as variantes de queda de 25% e de 40% (a janela de 60 pregões continua) não ficam com média negativa.

**Se falhar em qualquer mercado:** o cenário não é favorável naquele mercado. Se der favorável, isso é só um indício a confirmar no Diário, não uma permissão para operar.

## Limitações conhecidas antes de rodar

- **Viés de sobrevivência forte neste cenário.** Ações que caíram e continuaram caindo até sair do índice ou da bolsa não estão nos dados. A própria MOVI3 saiu do Ibovespa e não está no universo. Isso **infla** o resultado de "comprar depois da queda".
- **Histórico curto:** 5 anos no Brasil e 3 nos EUA.
- **Eventos não independentes:** quedas fortes se concentram nos mesmos meses de crise. Por isso também é informado o número de meses distintos com evento.

## Resultado (04/11/2026, rodado depois do registro acima, sem nenhum ajuste)

Script: `coleta/estudar_cenario.js`. Dados publicados até 03/11/2026. O índice é o `indice.json` (BOVA11 / SPY).

| | Brasil (set/2022–out/2026, 76 papéis) | EUA (set/2024–nov/2026, 400 papéis) |
|---|---|---|
| Eventos com queda ≥ 30% + Otimista | 107 (30 papéis, 36 meses) | 479 (169 papéis, 26 meses) |
| Média por operação, saída do app | +2,12% | +2,23% |
| Mediana | −4,47% | −8,09% |
| Acerto | 37% | 32% |
| Ganho médio / perda média | +16,8% / −6,6% (paga 2,5 por 1) | +23,6% / −7,6% (paga 3,1 por 1) |
| **Acaso: dias com a mesma queda, sem o sinal (p50 / p95)** | **+0,28% / +3,35%** | **+4,30% / +6,21%** |
| Índice nas mesmas datas | +1,16% | +1,08% |
| Variante 25% / 40% (média) | +2,24% / +4,77% | +1,91% / +3,83% |
| Qualquer dia, mesma saída | +0,69% | +1,18% |

**Critérios:**

| Critério | Brasil | EUA |
|---|---|---|
| 1. Acima do p95 do acaso | **não** | **não** |
| 2. Expectativa > 0 e acima do índice | sim | sim |
| 3. Variantes não negativas | sim | sim |
| **Veredito** | **NÃO FAVORÁVEL** | **NÃO FAVORÁVEL** |

**Leitura:**

- **A Otimista não acrescenta nada à queda.** No Brasil, o resultado fica entre a mediana e o p95 dos dias sorteados com a mesma queda. Nos EUA, fica **abaixo da mediana** dos sorteados: comprar a queda em dia sorteado rendeu mais (+4,3%) que esperar o sinal (+2,2%).
- **O perfil é de loteria nos dois mercados:** mediana negativa, acerto de 1 em 3, alguns ganhos enormes (melhores: +145% nos EUA, +72% no Brasil).
- **Nos EUA, "comprar a queda" parece bom (+4,3% por operação), mas por dois motivos que não se repetem:**
  1. Os maiores ganhos são quase todos do repique de abril de 2025 (crise das tarifas): 70 eventos só nesse mês.
  2. O universo é o dos 400 mais líquidos **de hoje**, ou seja, quem caiu e se recuperou. Quem caiu e continuou caindo não está nos dados.

## Réplica independente (04/11/2026, à noite)

O script original da auditoria não veio junto. Por isso, `coleta/estudar_cenario.js` foi reescrito do zero, só a partir da definição acima. Ele usa os indicadores e o `v14_analisarSinais` copiados do app.

Execução: https://github.com/diegostalin88/Invest/actions/runs/41919405850

| | Brasil | EUA |
|---|---|---|
| Eventos | 108 (30 papéis, 37 meses) | 481 (169 papéis, 27 meses) |
| Média / mediana | +2,01% / −4,47% | +2,07% / −8,09% |
| Acerto · ganho médio / perda média | 37% · +16,8% / −6,7% | 31% · +23,6% / −7,6% |
| Acaso na mesma queda (p50 / p95) | +1,46% / +5,12% | +4,49% / +6,36% |
| Índice nas mesmas datas | +1,14% | +1,03% |
| Veredito | **não favorável** | **não favorável** |

**Comparação com o resultado original:** os eventos, a média e a distribuição batem com o original. O acaso do Brasil saiu mais alto na réplica, porque aqui ele sorteia com reposição entre todos os dias de queda, sem a regra dos 20 pregões. O veredito é o mesmo nos dois mercados.
