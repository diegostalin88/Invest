# Relatório dos testes de opções na B3 (O1 a O4)

**Projeto:** Invest (repositório `diegostalin88/Invest`), estudo de opções em `opcoes/` e `docs/opcoes/`.
**Período dos testes:** 05/11/2026. **Autor do relatório:** Claude (Claude Code), a pedido do Diego.
**Código e registros:** pull request #3 do repositório (branch `claude/project-thread-ouh2hk`).

## 1. Resumo

Foram testadas quatro ideias de operação com opções na B3, todas com risco definido. **As quatro foram
reprovadas** fora da amostra (01/2023 a 10/2026). Nenhuma rendeu mais que o CDI.

| Teste | O que testa | Resultado por operação (P&L ÷ risco) | Retorno da carteira | CDI | Veredito |
| --- | --- | --- | --- | --- | --- |
| O1 simples | Travas de crédito e iron condor com IV Rank alto, saída por alvo/stop | −22% | 0,6% | 59,7% | Reprovada |
| O1 técnica | Idem, com gatilhos técnicos (Keltner, IFR, Bollinger) | −21% | 42,1% | 59,7% | Reprovada |
| O2 simples | Travas de débito direcionais com IV Rank baixo (ADX + MME200) | −70% | −84,4% | 59,7% | Reprovada |
| O2 técnica | Idem, com rompimento de 20 dias com volume | −65% | −8,4% | 59,7% | Reprovada |
| O3 crédito | Entradas da O1 simples, ordem limite no meio, até o vencimento | −5,2% | 54,1% | 59,8% | Reprovada |
| O3 débito | Entradas da O2 simples, ordem limite no meio, até o vencimento | −2,2% | 55,1% | 59,8% | Reprovada |
| O4 box | Box de 4 pontas como renda fixa | taxa 7 p.p./ano abaixo do CDI (mediana) | 56,5% | 59,8% | Reprovada |

**Principais conclusões:**

1. **A diferença entre as ofertas de compra e venda é o maior custo.** Montar e desmontar uma trava pelas ofertas
   do fechamento custa, na mediana, de 0,5 a 1,9 vez o prêmio da operação. Com stop curto, o stop dispara logo
   depois da entrada só por causa disso (O1 e O2).
2. **Sem esse custo, também não há vantagem.** Com ordem limite no meio das ofertas e levando até o vencimento
   (O3), a perda cai para perto de zero, mas não vira lucro, e o capital em risco deixa de render CDI.
3. **Nem o IV Rank nem os sinais técnicos escolhem dias melhores que o acaso.** Em todos os testes com placebo
   (entradas em dias sorteados), a estratégia original ficou entre os percentis 0 e 63, nunca perto de 95.
4. **Prever direção não ajudou**, o que bate com a auditoria anterior do motor técnico do Invest (04/11/2026), que
   já tinha mostrado que o score técnico não vence o índice.
5. **Rendimento "fixo" com opções existe (box), mas rende abaixo do CDI** para quem monta pela tela. Um rendimento
   fixo acima do CDI só é possível assumindo algum risco escondido.

## 2. Método (igual em todos os testes)

- **Registro prévio:** regras, critérios e auditoria escritos em `docs/opcoes/hipotese-*.md` e
  `docs/opcoes/auditoria-*.md` **antes** de rodar qualquer número. Nada foi ajustado depois de ver o resultado.
- **Dados:** COTAHIST anual da B3 (2018 a 2026), baixado e processado no GitHub Actions. Preço de cada opção pela
  melhor oferta no fechamento (PREOFC para vender, PREOFV para comprar); na O3, também a máxima e a mínima
  negociadas do dia (PREMAX, PREMIN). CDI diário do Banco Central (série SGS 12). BOVA11 pelo fechamento.
- **IV e IV Rank:** volatilidade implícita no dinheiro de ~30 dias reconstruída por Black-Scholes a partir das
  opções do COTAHIST; IV Rank sobre 252 pregões. Cobertura verificada antes (`docs/opcoes/verificacao-cotahist.md`):
  PETR4, VALE3, ITUB4, BBAS3 e BOVA11 com IV em 97 a 100% dos pregões desde 2018; PRIO3 desde 2021.
- **Papéis:** PETR4, VALE3, BOVA11, ITUB4, BBAS3 e PRIO3 (este a partir de 2022).
- **Períodos:** dentro da amostra 2019 a 2022 (2018 só forma o primeiro IV Rank); **fora da amostra 01/2023 a
  10/2026, de onde sai o veredito.**
- **Execução:** sinal no fechamento, execução no fechamento do pregão seguinte. Saída nunca no mesmo pregão da
  entrada.
- **Tamanho:** perda máxima de 1% do capital por operação (R$ 100 mil iniciais). O dinheiro fora de risco rende CDI.
- **Custo:** além das ofertas, R$ 0,005 por opção por perna em cada execução.
- **Critério de aprovação (O1 a O3), todos fora da amostra:** retorno acima do CDI; fator de lucro ≥ 1,2; ≥ 50
  operações; queda máxima ≤ 15%; sem o melhor ativo, ainda acima do CDI; com filtro de IV Rank, resultado por
  operação melhor que sem filtro.
- **Auditoria adversarial** depois de cada backtest (pedido do Diego): reprodução, execução atrasada, custo × 4,
  placebo com 100 sorteios, resultado por ano, conferência à mão, e testes de execução específicos de cada hipótese.

## 3. Resultados por hipótese

### O1: travas de crédito filtradas por IV Rank alto

**Regras (versão simples):** ADX(14) < 20 → iron condor (IV Rank ≥ 60, vendidas com delta 0,16); acima da MME200 →
trava de alta com put; abaixo → trava de baixa com call (IV Rank ≥ 50, vendida com delta 0,25). Largura ~5% do
preço, vencimento 25 a 50 dias. Saída: recompra ≤ 50% do crédito (ganho), ≥ 2× o crédito (perda) ou 21 dias para o
vencimento. **Versão técnica:** condor com Bollinger estreito; trava de alta quando a mínima toca a banda inferior de
Keltner acima da MME200; trava de baixa com IFR(14) > 70.

| Versão | Operações | Acerto | Fator de lucro | P&L ÷ risco | Retorno | Queda máx. |
| --- | --- | --- | --- | --- | --- | --- |
| Simples | 226 | 15% | 0,02 | −22% | 0,6% | 13,8% |
| Técnica | 65 | 15% | 0,03 | −21% | 42,1% | 2,6% |

Auditoria: reproduz; com tudo no meio das ofertas só empata (+0,5% e +0,3% por operação, retorno igual ao CDI);
ida e volta pelas ofertas ≈ 1,9 vez o crédito; placebo nos percentis 0 e 2 (o filtro foi **pior** que o acaso);
todos os anos negativos.

**Erro encontrado e corrigido:** na 1ª execução, a regra de saída era checada no próprio pregão da entrada, e o
stop disparava na hora por causa da diferença entre as ofertas (271 de 303 operações no stop). Corrigido, documentado
e coberto por teste; o resultado válido é o da 2ª execução.

### O2: travas de débito direcionais com IV Rank baixo

**Regras:** IV Rank ≤ 35. Simples: ADX(14) ≥ 20, acima da MME200 → trava de alta com call, abaixo → trava de baixa
com put. Técnica: rompimento da máxima/mínima de 20 pregões com volume ≥ 1,5 × a média. Compra no dinheiro, vende
~5% fora. Saída: trava ≥ 75% da largura (ganho), ≤ 50% do débito (perda) ou 7 dias para o vencimento.

| Versão | Operações | Acerto | Fator de lucro | P&L ÷ risco | Retorno | Queda máx. |
| --- | --- | --- | --- | --- | --- | --- |
| Simples | 399 | 4% | 0,04 | −70% | −84,4% | 84,5% |
| Técnica | 92 | 5% | 0,04 | −65% | −8,4% | 15,4% |

Auditoria: reproduz; 0 de 4 anos positivos nas duas versões; placebo nos percentis 9 e 51; ida e volta ≈ 0,4 a 0,5
do débito, então a trava vale metade do que custou logo após a entrada e o stop em 50% dispara (379 de 399 saídas
pelo stop); no meio das ofertas, a simples empata (−0,8%) e a técnica perde (−11%).

**Erro encontrado e corrigido:** a 1ª execução usou CDI de reserva de 10% ao ano porque o download do Banco Central
falhou. Os scripts passaram a abortar sem o CDI real; o resultado válido é o da 2ª execução.

### O3: mesma montagem, ordem limite no meio e até o vencimento

**Regras:** entradas das versões simples da O1 (crédito) e da O2 (débito). No fechamento do sinal, o preço limite de
cada perna é o meio das ofertas; no pregão seguinte, a perna é executada se a opção foi negociada nesse preço ou
melhor (máxima ≥ limite na vendida, mínima ≤ limite na comprada). Só entra se todas as pernas forem executadas. Sem
stop e sem alvo: liquida no vencimento pelo valor intrínseco.

| Versão | Operações | Acerto | Fator de lucro | P&L ÷ risco | Retorno | Queda máx. |
| --- | --- | --- | --- | --- | --- | --- |
| Crédito | 62 | 73% | 0,68 | −5,2% | 54,1% | 2,2% |
| Débito | 117 | 39% | 0,96 | −2,2% | 55,1% | 6,9% |
| Crédito pelas ofertas, até o vencimento (comparação) | 68 | 71% | 0,43 | −8,6% | 50,9% | 2,1% |
| Débito pelas ofertas, até o vencimento (comparação) | 130 | 39% | 0,70 | −16,8% | 29,4% | 8,2% |

Auditoria: reproduz; placebo nos percentis 63 e 55; execução estrita (negócio estritamente melhor que o limite)
−3,2% e −5,0%; **em mais da metade das ordens só parte das pernas teria sido executada** (95 de 171 no crédito, 117
de 242 no débito), o que na prática deixaria pernas soltas; débito com 2 anos positivos e 2 negativos (2026 −23%).
Com toda ordem executada no meio, o débito daria +28% por operação, mas esse preço não aparece na tela com
frequência suficiente para ser operável.

**Leitura:** tirar a diferença entre as ofertas e o stop curto reduziu a perda de −22%/−70% para −5%/−2%. A maior
parte da perda anterior era execução, mas, sem ela, a estratégia fica no zero a zero.

### O4: box de 4 pontas como renda fixa

**Regras:** compra call K1, vende call K2, compra put K2, vende put K1 (mesmo vencimento, 20 a 70 dias), pelas
ofertas do fechamento. No vencimento vale K2 − K1. No segundo pregão de cada mês, para cada papel, compra o box de
maior taxa (se positiva), até 1/6 do capital; resto no CDI. Critério: retorno acima do CDI, ≥ 50% dos boxes acima
do CDI do mesmo período, ≥ 50 boxes, nenhum com prejuízo nominal.

| Variante | Boxes | Retorno | Boxes acima do CDI | Taxa − CDI (mediana) |
| --- | --- | --- | --- | --- |
| Base | 16 | 56,5% | 0% | −7,0 p.p. ao ano |
| Compra 1 pregão depois | 10 | 34,3% | 0% | −51,2 p.p. |
| Custo × 4 | 9 | 57,1% | 0% | −10,2 p.p. |
| Só pernas negociadas no dia | 16 | 56,5% | 0% | −7,0 p.p. |
| Terceiro melhor box | 8 | 57,4% | 0% | −10,2 p.p. |

Em 46 meses × 6 papéis, só 16 vezes havia algum box com taxa positiva pelas ofertas, e nenhum rendeu mais que o CDI
(ex.: BOVA11 110/124, 06/03 a 17/04/2025, pago R$ 13,88 para receber R$ 13,99: 6,9% ao ano contra 13,8% do CDI).
Considerando todos os ~19 mil boxes possíveis nos dias de escolha, o típico paga mais do que devolve. Nenhum box da
regra base teve prejuízo nominal: o box funciona como renda fixa, mas abaixo do CDI. O preço no meio das ofertas
dá taxas absurdas (pernas fundas com ofertas muito largas) e foi descartado como sem significado.

## 4. Limitações

- **Dados diários:** só o fechamento e a melhor oferta do fim do dia. Não há livro de ofertas nem negócios ao longo
  do dia, então não dá para simular com precisão uma ordem limite (a O3 usa a máxima e a mínima do dia como
  aproximação, a favor da estratégia: supõe que a ordem seria atendida sempre que houve negócio no preço, sem fila).
- **Execução por pernas:** a B3 permite enviar travas como estrutura em algumas plataformas, com preço único; isso
  pode reduzir o risco de perna. Não foi simulado.
- **Imposto e corretagem real** ficaram fora (corretagem só como R$ 0,005 por opção por perna).
- **Exercício antecipado** das calls americanas não foi modelado.
- **Seis papéis**, os mais líquidos. Outros papéis têm opções menos líquidas, o que só pioraria a diferença entre
  as ofertas.
- **Múltiplos testes** sobre o mesmo período fora da amostra: mesmo uma aprovação valeria só como indício.

## 5. O que os testes sugerem para o próximo passo

- **Não automatizar nenhuma dessas estratégias.** Nenhuma passou no critério, e todas as auditorias confirmaram que
  a reprovação é real.
- Se o estudo continuar, o ponto a atacar é a **execução**, com dados intradiários (livro de ofertas, negócios) e
  ordens de estrutura com preço único, antes de testar qualquer nova regra de entrada. Sem isso, os resultados com
  dados diários indicam que a diferença entre as ofertas consome qualquer vantagem.
- Para renda fixa, o box não compensa contra um CDB ou Tesouro Selic para o investidor pessoa física.

## 6. Arquivos

| Arquivo | Conteúdo |
| --- | --- |
| `docs/opcoes/verificacao-cotahist.md` | Verificação dos dados da B3 (cobertura de IV) |
| `docs/opcoes/hipotese-travas-credito.md` e `auditoria-o1.md` | O1: registro, resultado e auditoria |
| `docs/opcoes/hipotese-travas-debito.md` e `auditoria-o2.md` | O2 |
| `docs/opcoes/hipotese-vencimento.md` e `auditoria-o3.md` | O3 |
| `docs/opcoes/hipotese-box.md` | O4 (registro, resultado e auditoria no mesmo arquivo) |
| `opcoes/cotahist.py` | Leitura do COTAHIST, IV e IV Rank, CDI do Banco Central |
| `opcoes/travas.py`, `debito.py`, `vencimento.py`, `box.py` | Simuladores das hipóteses |
| `opcoes/auditoria_o1.py` | Auditoria adversarial (`--hipotese o1`, `o2` ou `o3`) |
| `opcoes/tests/` | 21 testes sem rede (dados sintéticos) |
| `.github/workflows/opcoes-*.yml` | Execuções no GitHub Actions |
