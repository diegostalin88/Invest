# Relatório dos testes de opções na B3 (O1 a O7)

**Projeto:** Invest (repositório `diegostalin88/Invest`), estudo de opções em `opcoes/` e `docs/opcoes/`.
**Período dos testes:** 05 e 06/11/2026. **Autor do relatório:** Claude (Claude Code), a pedido do Diego.
**Código e registros:** pull request #3 do repositório (branch `claude/project-thread-ouh2hk`).

## 1. Resumo

Foram testadas sete ideias de operação com opções na B3. As de O5 a O7 vieram de propostas de outra IA, trazidas pelo
Diego. **As sete foram reprovadas** fora da amostra (01/2023 a 10/2026). Duas ficaram ligeiramente acima do CDI
(O6 e O7 nos 6 papéis), mas nenhuma das duas se distinguiu do acaso no placebo, e a da O6 depende de uma suposição
de execução que os dados não confirmam.

| Teste | O que testa | Resultado por operação | Retorno da carteira | CDI | Veredito |
| --- | --- | --- | --- | --- | --- |
| O1 simples | Travas de crédito e iron condor com IV Rank alto, saída por alvo/stop | −22% do risco | 0,8% | 59,8% | Reprovada |
| O1 técnica | Idem, com gatilhos técnicos (Keltner, IFR, Bollinger) | −21% | 42,2% | 59,8% | Reprovada |
| O2 simples | Travas de débito direcionais com IV Rank baixo (ADX + MME200) | −70% | −84,4% | 59,8% | Reprovada |
| O2 técnica | Idem, com rompimento de 20 dias com volume | −65% | −8,4% | 59,8% | Reprovada |
| O3 crédito | Entradas da O1, ordem limite no meio, até o vencimento | −4,4% | 55,0% | 59,8% | Reprovada |
| O3 débito | Entradas da O2, ordem limite no meio, até o vencimento | −6,7% | 47,7% | 59,8% | Reprovada |
| O4 box | Box de 4 pontas como renda fixa | taxa 7 p.p./ano abaixo do CDI | 56,5% | 59,8% | Reprovada |
| O5 wheel | Venda de put 8–12% fora do dinheiro com caixa no CDI; call coberta se exercida | prêmio 0,2% do strike/mês | 58,8% (queda de 46%) | 59,8% | Reprovada |
| O6 BOVA11 | Trava de alta com put, VRP ≥ 4, ordem estruturada, alvo de 25% | 1 operação em 4 anos | 59,9% | 59,8% | Reprovada |
| O6 6 papéis | Idem nos 6 papéis | +18% (27 operações) | 67,1% | 59,8% | Reprovada |
| O7 BOVA11 | Strangle comprado com metade dos juros do mês, IV Rank < 20 | opções +2% | 59,7% | 59,8% | Reprovada |
| O7 6 papéis | Idem nos 6 papéis | opções +9% | 60,9% | 59,8% | Reprovada |

**Principais conclusões:**

1. **A diferença entre as ofertas de compra e venda é o maior custo.** Montar e desmontar uma trava pelas ofertas
   do fechamento custa, na mediana, de 0,5 a 2 vezes o prêmio da operação. Com stop curto, o stop dispara logo depois
   da entrada só por causa disso (O1 e O2).
2. **Sem esse custo, também não há vantagem.** Com ordem limite no meio e até o vencimento (O3), a perda cai para
   perto de zero, mas não vira lucro, e o capital em risco deixa de render CDI.
3. **Nenhum filtro escolheu dias melhores que o acaso** com a folga exigida (percentil 95 no placebo). IV Rank,
   sinais técnicos, VRP e Bollinger ficaram entre os percentis 0 e 85. Os dois melhores (O6 e O7, 6 papéis) ficaram
   no 85.
4. **Vender put a seco não é renda (O5).** O prêmio de uma put 8–12% fora do dinheiro é pequeno demais; quando
   exercida, a carteira vira ações e herda a queda delas (46%). Perde para o CDI e para comprar e manter as ações.
5. **O único lucro grande (O6) depende de a ordem estruturada ser atendida perto do meio das ofertas nas duas
   pontas.** Com o melhor preço do dia de cada perna, tudo dá certo (inclusive nos dias sorteados do placebo); pelas
   ofertas, nenhuma operação é possível. Só um teste para frente, com ordens reais ou simuladas, decide isso.
6. **O strangle financiado pelos juros (O7) é seguro por construção, mas não teve vantagem.** O capital nunca sai do
   CDI e o pior caso é render metade do CDI no mês. Ficou praticamente igual ao CDI, com resultado das opções
   dependente de poucos acertos (35% de acerto, anos alternando entre +93% e −47%).
7. **Rendimento "fixo" com opções existe (box), mas rende abaixo do CDI** para quem monta pela tela.

## 2. Método (igual em todos os testes)

- **Registro prévio:** regras, critérios e auditoria escritos em `docs/opcoes/hipotese-*.md` e
  `docs/opcoes/auditoria-*.md` **antes** de rodar qualquer número. Nada foi ajustado depois de ver o resultado. (Na
  O6, os parâmetros exatos da proposta chegaram um minuto depois do envio da primeira versão; o registro foi revisado
  antes de qualquer número, e a primeira versão ficou como comparação.)
- **Dados:** COTAHIST anual da B3 (2018 a 2026), baixado e processado no GitHub Actions. Preço de cada opção pela
  melhor oferta no fechamento (PREOFC para vender, PREOFV para comprar) e, a partir da O3, também a máxima e a mínima
  negociadas do dia (PREMAX, PREMIN). CDI diário do Banco Central (série SGS 12), obrigatório.
- **IV, IV Rank e VRP:** volatilidade implícita no dinheiro de ~30 dias reconstruída por Black-Scholes; IV Rank sobre
  252 pregões; VRP = IV de 30 dias − volatilidade realizada de 21 pregões. Cobertura verificada antes
  (`docs/opcoes/verificacao-cotahist.md`).
- **Proventos:** a B3 reduz o strike das opções em aberto quando o papel paga provento. Os simuladores atualizam o
  strike das pernas abertas pela cadeia do dia (ver seção 4).
- **Papéis:** PETR4, VALE3, BOVA11, ITUB4, BBAS3 e PRIO3 (este a partir de 2022); a O5 usa PETR4, VALE3, ITUB4 e
  BBAS3.
- **Períodos:** dentro da amostra 2019 a 2022; **fora da amostra 01/2023 a 10/2026, de onde sai o veredito.**
- **Execução:** sinal no fechamento, execução no pregão seguinte. Saída nunca no mesmo pregão da entrada.
- **Tamanho:** travas com perda máxima de 1% do capital por operação (R$ 100 mil iniciais). O dinheiro fora de risco
  rende CDI.
- **Custo:** além das ofertas, R$ 0,005 por opção por perna em cada execução.
- **Auditoria adversarial** depois de cada backtest (pedido do Diego): reprodução, execução atrasada, custo × 4,
  placebo, resultado por ano, conferência à mão, e testes de execução específicos de cada hipótese.

## 3. Resultados por hipótese

### O1: travas de crédito filtradas por IV Rank alto

**Regras (versão simples):** ADX(14) < 20 → iron condor (IV Rank ≥ 60, vendidas com delta 0,16); acima da MME200 →
trava de alta com put; abaixo → trava de baixa com call (IV Rank ≥ 50, vendida com delta 0,25). Largura ~5% do
preço, vencimento 25 a 50 dias. Saída: recompra ≤ 50% do crédito (ganho), ≥ 2× o crédito (perda) ou 21 dias para o
vencimento. **Versão técnica:** condor com Bollinger estreito; trava de alta quando a mínima toca a banda inferior de
Keltner acima da MME200; trava de baixa com IFR(14) > 70.

| Versão | Operações | Fator de lucro | P&L ÷ risco | Retorno | Queda máx. |
| --- | --- | --- | --- | --- | --- |
| Simples | 226 | 0,02 | −22% | 0,8% | 13,6% |
| Técnica | 65 | 0,03 | −21% | 42,2% | 2,6% |

Auditoria: reproduz; com tudo no meio das ofertas só empata; ida e volta pelas ofertas ≈ 1,9 vez o crédito; placebo
nos percentis 0 e 2 (o filtro foi **pior** que o acaso); todos os anos negativos.

### O2: travas de débito direcionais com IV Rank baixo

**Regras:** IV Rank ≤ 35. Simples: ADX(14) ≥ 20, acima da MME200 → trava de alta com call, abaixo → trava de baixa
com put. Técnica: rompimento da máxima/mínima de 20 pregões com volume ≥ 1,5 × a média. Compra no dinheiro, vende
~5% fora. Saída: trava ≥ 75% da largura (ganho), ≤ 50% do débito (perda) ou 7 dias para o vencimento.

| Versão | Operações | Fator de lucro | P&L ÷ risco | Retorno | Queda máx. |
| --- | --- | --- | --- | --- | --- |
| Simples | 399 | 0,04 | −70% | −84,4% | 84,5% |
| Técnica | 92 | 0,04 | −65% | −8,4% | 15,4% |

Auditoria: reproduz; 0 de 4 anos positivos; placebo nos percentis 7 e 51; a trava vale metade do que custou logo
depois da entrada e o stop em 50% dispara; no meio das ofertas, a simples empata e a técnica perde (−11%).

### O3: mesma montagem, ordem limite no meio e até o vencimento

**Regras:** entradas das versões simples da O1 (crédito) e da O2 (débito). Preço limite de cada perna no meio das
ofertas do fechamento do sinal; no pregão seguinte, a perna executa se a opção negociou nesse preço ou melhor. Só
entra se todas as pernas executarem. Sem stop e sem alvo: liquida no vencimento pelo valor intrínseco.

| Versão | Operações | Acerto | Fator de lucro | P&L ÷ risco | Retorno | Queda máx. |
| --- | --- | --- | --- | --- | --- | --- |
| Crédito | 62 | 77% | 0,73 | −4,4% | 55,0% | 2,1% |
| Débito | 117 | 39% | 0,88 | −6,7% | 47,7% | 6,9% |

Auditoria: reproduz; placebo nos percentis 62 e 38; **em mais da metade das ordens só parte das pernas teria sido
executada**, o que na prática deixaria pernas soltas. Com toda ordem executada no meio, o débito daria +26% por
operação, mas esse preço não aparece na tela com frequência suficiente para ser operável.

### O4: box de 4 pontas como renda fixa

**Regras:** compra call K1, vende call K2, compra put K2, vende put K1 (mesmo vencimento, 20 a 70 dias), pelas
ofertas. No vencimento vale K2 − K1. Uma vez por mês, por papel, compra o box de maior taxa (se positiva).

| Variante | Boxes | Retorno | Boxes acima do CDI | Taxa − CDI (mediana) |
| --- | --- | --- | --- | --- |
| Base | 16 | 56,5% | 0% | −7,0 p.p. ao ano |
| Compra 1 pregão depois | 10 | 34,3% | 0% | −51,2 p.p. |
| Custo × 4 | 9 | 57,1% | 0% | −10,2 p.p. |

Em 46 meses × 6 papéis, só 16 vezes havia box com taxa positiva pelas ofertas, e nenhum rendeu mais que o CDI. O box
funciona como renda fixa (nenhum prejuízo nominal), mas abaixo do CDI.

### O5: venda de put com o caixa no CDI ("wheel")

**Regras:** PETR4, VALE3, ITUB4 e BBAS3, ¼ do capital cada, todo no CDI (inclusive a garantia). Vende put com strike
8–12% abaixo do preço (delta ~0,14), 25 a 50 dias, pela oferta de compra, quantidade coberta pelo caixa. Se
exercida, fica com as ações e vende call coberta acima do custo e 5% acima do preço; se a call é exercida, volta para
a put. Dividendos creditados. Critério: acima do CDI, queda ≤ 20%, ≥ 30 puts, 3 de 4 anos acima do CDI.

| Variante | Retorno | CDI | Comprar e manter | Queda máx. | Puts | Exercidas |
| --- | --- | --- | --- | --- | --- | --- |
| Base | 58,8% | 59,8% | 82,4% | 45,9% | 105 | 13 |
| Ordem limite no meio | 68,5% | 59,8% | 82,4% | 47,1% | 72 | 13 |
| Venda 2 pregões depois | 54,5% | 59,8% | 82,4% | 45,9% | 101 | 12 |
| Put 12% a 16% abaixo | 47,2% | 59,8% | 82,4% | 10,0% | 131 | 7 |

Dois de quatro anos acima do CDI (2023 e 2025). Prêmio mediano de 0,2% do strike por mês. Placebo (vender em dias
sorteados): retorno mediano de 56,2%, igual ao da base. Dentro da amostra (CDI baixo, 2019 a 2022) a base rendeu
47% contra 27% do CDI; fora, com CDI alto, não.

### O6: trava de alta com put filtrada por VRP, ordem estruturada

**Regras (parâmetros exatos da proposta):** VRP ≥ 4 pontos; vendida delta ~0,15, comprada delta ~0,05, 35 a 56 dias;
crédito ≥ 12% da largura; ordem estruturada a preço líquido (executa se máxima da vendida − mínima da comprada ≥ o
crédito pedido); alvo de recompra estruturada a 25% do crédito; sem stop. Versões BOVA11 e 6 papéis.

| Versão | Operações | Acerto | P&L ÷ risco | Retorno | Queda máx. | Ordens executadas / não |
| --- | --- | --- | --- | --- | --- | --- |
| BOVA11 | 1 | 100% | +10% | 59,9% | 0,0% | 1 / 10 |
| 6 papéis | 27 | 100% | +18% | 67,1% | 0,8% | 27 / 136 |
| 6 papéis sem filtro de VRP | 57 | 100% | +15% | 73,2% | 0,9% | 59 / 423 |
| BOVA11 pelas ofertas | 0 | – | – | 59,8% | – | – |
| BOVA11, primeira versão (delta 0,25, largura 5%, sem alvo) | 16 | 81% | +3,9% | 60,4% | 0,7% | 17 / 2 |

Reprovada pelo número de operações (BOVA11 1 de 20; 6 papéis 27 de 50) e, na auditoria, pelo placebo (percentil 85).
Os outros testes da auditoria passaram nos 6 papéis (ordem 2 pregões depois +13%, custo × 4 +11%, os quatro anos
positivos).

**Por que o resultado não é confiável:** todas as operações saíram pelo alvo em poucos dias, e o placebo (dias
sorteados, sem VRP) também acerta 100%. O lucro vem da forma de simular a ordem estruturada: na entrada e no alvo, o
simulador usa o melhor preço do dia de cada perna, separadamente, preços que podem ter acontecido em horários
diferentes e em negócios pequenos. A diferença entre as ofertas, ida e volta, é 2 vezes o crédito, e pelas ofertas
nenhuma operação alcança o crédito mínimo. Com dados diários não dá para saber se essas ordens seriam atendidas.

### O7: strangle comprado com metade dos juros do CDI

**Regras:** capital todo no CDI; no começo de cada mês, orçamento de metade do CDI do mês anterior. Com IV Rank < 20,
compra call e put com |delta| ~0,20, 25 a 50 dias, pela oferta de venda, e leva até o vencimento. Um strangle por
mês. Critério: retorno acima do CDI, resultado das opções positivo, ≥ 20 strangles, placebo no percentil 95.

| Versão / variante | Strangles | Retorno | CDI | Opções (recebido − pago) ÷ pago | Acerto | Queda máx. |
| --- | --- | --- | --- | --- | --- | --- |
| BOVA11 | 20 | 59,7% | 59,8% | +2,4% | 35% | 0,9% |
| 6 papéis | 40 | 60,9% | 59,8% | +9,1% | 35% | 1,9% |
| 6 papéis, Bollinger estreito | 44 | 68,5% | 59,8% | +32% | 39% | 2,0% |
| BOVA11, Bollinger estreito | 26 | 58,4% | 59,8% | −10,5% | 27% | 1,1% |
| 6 papéis, compra 2 pregões depois | 38 | 62,7% | 59,8% | +17% | 32% | 2,0% |
| 6 papéis, custo × 4 | 40 | 60,1% | 59,8% | +6,0% | 35% | 1,9% |

BOVA11: abaixo do CDI e placebo no percentil 67. 6 papéis: passa em três critérios, mas o placebo fica no
percentil 85 (mediana do placebo −16,5%). O resultado depende de poucos strangles que pagaram 5 a 7 vezes o custo;
por ano, as opções nos 6 papéis deram +15%, −47%, −26% e +93%. Não perde dinheiro de verdade, mas a vantagem não se
distingue do acaso.

## 4. Correção feita durante o estudo

- **O1:** na 1ª execução, a regra de saída era checada no próprio pregão da entrada. Corrigido; vale a 2ª execução.
- **O2:** a 1ª execução usou CDI de reserva de 10% ao ano porque o download do Banco Central falhou. Os scripts
  passaram a abortar sem o CDI real.
- **Ajuste de strike por proventos (06/11):** ao preparar a O5, apareceu que as pernas abertas guardavam o strike da
  entrada, mas a B3 reduz o strike das opções em aberto na data ex de um provento. Corrigido em todos os simuladores e
  O1 a O3 reexecutadas. O1 e O2 não mudaram; na O3 o débito piorou (de −2,2% para −6,7% por operação). Nenhum
  veredito mudou. Os números deste relatório já são os corrigidos.

## 5. Limitações

- **Dados diários:** só o fechamento, a máxima, a mínima e a melhor oferta do fim do dia. Não há livro de ofertas
  nem negócios ao longo do dia, então ordens limite e estruturadas são aproximadas, sempre a favor da estratégia.
- **Imposto e corretagem real** ficaram fora (corretagem só como R$ 0,005 por opção por perna).
- **Exercício antecipado** das calls americanas não foi modelado.
- **Seis papéis**, os mais líquidos. Outros papéis têm opções menos líquidas, o que só pioraria a diferença entre
  as ofertas.
- **Múltiplos testes** sobre o mesmo período fora da amostra (sete hipóteses, várias versões): mesmo uma aprovação
  valeria só como indício.

## 6. O que os testes sugerem para o próximo passo

- **Não automatizar nenhuma dessas estratégias.** Nenhuma passou no critério, e as auditorias confirmaram que a
  reprovação é real.
- **A pergunta que sobra é de execução, não de regra:** uma ordem estruturada a preço líquido perto do meio das
  ofertas é atendida na B3? Isso não se responde com histórico diário. O jeito barato de responder é um **teste para
  frente**: colocar ordens estruturadas reais (ou simuladas na plataforma da corretora) da O6 por alguns meses e
  anotar quantas são executadas e a que preço. Se forem atendidas com frequência, a O6 vale um novo registro.
- **O7 pode ser mantida como é, se o objetivo for proteger o capital:** o risco é muito baixo (pior caso: render
  metade do CDI no mês), mas não há evidência de que renda mais que o CDI.
- **Renda fixa:** o box e a venda de put não compensam contra um CDB ou Tesouro Selic para o investidor pessoa física.

## 7. Arquivos

| Arquivo | Conteúdo |
| --- | --- |
| `docs/opcoes/verificacao-cotahist.md` | Verificação dos dados da B3 (cobertura de IV) |
| `docs/opcoes/hipotese-travas-credito.md` e `auditoria-o1.md` | O1: registro, resultado e auditoria |
| `docs/opcoes/hipotese-travas-debito.md` e `auditoria-o2.md` | O2 |
| `docs/opcoes/hipotese-vencimento.md` e `auditoria-o3.md` | O3 |
| `docs/opcoes/hipotese-box.md` | O4 |
| `docs/opcoes/hipotese-wheel.md` | O5 |
| `docs/opcoes/hipotese-vrp.md` | O6 (registro, resultado e auditoria) |
| `docs/opcoes/hipotese-strangle.md` | O7 |
| `opcoes/cotahist.py` | Leitura do COTAHIST, IV e IV Rank, CDI do Banco Central |
| `opcoes/travas.py`, `debito.py`, `vencimento.py`, `box.py`, `wheel.py`, `vrp.py`, `strangle.py` | Simuladores |
| `opcoes/auditoria_o1.py` | Auditoria adversarial (`--hipotese o1`, `o2`, `o3` ou `o6`) |
| `opcoes/tests/` | 27 testes sem rede (dados sintéticos) |
| `.github/workflows/opcoes-*.yml` | Execuções no GitHub Actions |
