# Confirmação da hipótese D (deriva depois do balanço)

Registrado em **05/11/2026, por volta de 00:45 UTC**, depois do resultado de D (`docs/hipotese-fundamentos.md`) e **antes de escrever ou rodar qualquer código desta confirmação**. As regras e os critérios não mudam depois do resultado.

**Por que existe.** D passou nos três critérios registrados, mas com três ressalvas:
- quase nenhum efeito na 1ª metade;
- viés de sobrevivência na comparação com o SPY;
- efeito pequeno.

Esta confirmação ataca as três. Usa os mesmos dados, os mesmos eventos, a mesma surpresa e os mesmos quintis por trimestre de D. Nada de parâmetro novo na definição do sinal.

## Testes

1. **Contra o próprio universo.**
   - Em cada trimestre, a deriva de 60 pregões do quintil alto menos a deriva média de **todos** os eventos do mesmo trimestre.
   - Média sobre os eventos, depois de 0,2% de custo (ida e volta).
   - Isso tira o mercado e o viés de sobrevivência comum a todos.
2. **Ano a ano.** A diferença alto − baixo da deriva de 60 pregões, por ano civil do evento (anos com pelo menos 100 eventos).
3. **Só grandes.** O mesmo spread alto − baixo, só com os eventos de papéis entre os **200** mais negociados no fim do mês anterior (em vez de 500).
4. **Carteira contínua** (o que uma pessoa conseguiria fazer):
   - compra cada evento do quintil alto no fechamento de 1 pregão depois da divulgação e vende no fechamento de 61 pregões depois;
   - pesos iguais entre as posições abertas no dia, rebalanceado diariamente entre elas;
   - custo de 0,2% por posição (0,1% na entrada, 0,1% na saída);
   - sem posição aberta, fica parado (retorno zero).

   Mesma construção para **todos** os eventos (carteira de referência do mesmo universo). Compara-se com o SPY nas mesmas datas.

## Critérios (todos)

1. O teste 1 dá excesso **positivo** e acima do **percentil 95** de 500 embaralhamentos da surpresa dentro de cada trimestre (mesmo embaralhamento de D).
2. No teste 2, o spread é positivo em **pelo menos 60%** dos anos.
3. No teste 3, o spread é **positivo**.
4. No teste 4, a carteira do quintil alto rende mais ao ano que a carteira de todos os eventos **e** que o SPY, nas duas metades do período, com queda máxima até 1,5× a do SPY.

Se passar, a surpresa do balanço entra no app como "evidência a favor", mas continua sem ordem de compra (o app não recomenda operação real). Se falhar, D fica registrada como "efeito fraco, não aproveitável", e o app mostra a surpresa só como informação.

## Resultado (rodado em 05/11/2026, 00:52 UTC; execução 41942834429)

Mesmos 25.940 balanços de D.

1. **Contra o próprio universo:** o quintil alto rendeu **+0,74 ponto** acima da média do mesmo trimestre em 60 pregões, depois do custo. O embaralhado deu p50 −0,21 e p95 0,21. ✅
2. **Ano a ano:** o spread foi positivo em **11 de 18 anos (61%)**, no limite do critério. ✅
   - Anos negativos: 2009, 2011, 2012, 2014, 2016, 2018 e 2025.
   - De 2019 a 2024, positivo todo ano.
3. **Só os 200 mais negociados** (10.794 balanços): spread de **+1,58 ponto**. ✅
4. **Carteira contínua**, de 14/07/2009 a 04/11/2026: ❌

   | carteira | ao ano | queda máxima |
   |---|---|---|
   | quintil alto | 16,96% | 34,1% |
   | todos os balanços | 15,57% | 38,7% |
   | SPY | 15,20% | 33,7% |

   | metade | quintil alto | todos | SPY |
   |---|---|---|---|
   | 1ª | 17,86% | **17,96%** | 15,98% |
   | 2ª | 16,06% | 13,24% | 14,43% |

   Na 1ª metade, o quintil alto perdeu para a carteira de todos os balanços.

**Veredito: NÃO CONFIRMADA** (o critério 4 falhou).

**Leitura.** O efeito existe nos dados: o preço continua andando na direção da surpresa do lucro. Mas ele é pequeno e irregular. Como carteira que uma pessoa conseguiria seguir, o ganho sobre comprar todos os balanços do mesmo universo foi de cerca de 1,4 ponto ao ano no período todo, e zero na primeira metade.

A carteira de todos os balanços também bateu o SPY. Isso é o viés de sobrevivência: só entram empresas que existem hoje. Por isso, a vantagem real sobre o índice é menor que esses números.

No app, a surpresa do balanço fica como **informação** na aba Balanços, sem sinal de compra.
