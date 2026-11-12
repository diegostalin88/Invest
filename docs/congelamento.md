# Estratégia congelada em 04/11/2026

Decisão do Diego, depois da auditoria adversarial independente de 04/11/2026: **congelar as regras e testar só para frente**.
Este arquivo foi escrito **antes** de qualquer resultado do período novo. Os critérios abaixo não podem ser mudados depois de ver os números.

## Por que congelar

A auditoria (reproduzida com o mesmo motor do app, com os índices reais) mostrou:

- **Sem vantagem sobre o índice.** No período fora da amostra, o SPY rendeu +19% (queda máxima de 9%), e o sistema +2% a +18% (quedas de 20% a 31%). O BOVA11 rendeu +28%, e o sistema +10% a +27%, com risco igual ou maior.
- **"Confirmados" é efeito de seleção.** Em dados de puro acaso, o próprio app dá fator de lucro 1,42 nos confirmados. A estimativa honesta é de 1,2.
- **O Score não acrescenta nada além de "preço acima da MME200".** O Brasil não se distingue de entradas aleatórias.
- **O período de teste já está gasto.** Ele foi usado em mais de 8 estudos de ajuste.

Detalhes: parecer em Claude Docs (seções de 04/11) e scripts `coleta/motor_node.js` e `coleta/medir_adversarial.js`.

## O que está congelado

O motor e a seleção do Relatório, como estavam no commit em que este arquivo entrou na `main`:

| Item | Valor |
|---|---|
| Score mínimo | 2 |
| Pesos das estratégias | `strategyWeights` |
| Stop inicial | o mais próximo entre 2,5 ATR e 8% |
| Stop móvel | fechamento − 2,5 ATR, só sobe |
| Risco por operação | 1% |
| Custo | 0,1% por perna |
| Filtro de amplitude | ≥ 50% dos papéis acima da MME200 |
| Escolha da regra | 6 regras; escolha nos 60% iniciais; confirmação com ≥ 3 operações e FL ≥ 1 no teste |
| Veredito | mínimo de 15 operações; entrada atrasada até 2 pregões e 0,5 ATR; a resistência é só informação |

Continuam funcionando, porque foram definidos **antes** e só usam dados do passado em cada data:

- a recalibração mensal automática de alvo e prazo;
- o desligamento automático de regra pelo diário de sinais.

**Problemas conhecidos que ficam como estão,** para não mudar o sistema no meio do teste:

- sem teto de posição no backtest (na simulação, a compra é limitada ao caixa);
- o sinal `Double_Bottom` nunca dispara no motor;
- o universo é escolhido pela liquidez atual.

**Não quebra o congelamento:** telas, avisos, coleta e a comparação com o índice.

**Quebra o congelamento:** qualquer mudança em sinais, pesos, stops, saídas, seleção ou travas do veredito. Se isso acontecer, o teste recomeça do zero, com nova data.

## Como é medido daqui para frente

- **Diário de sinais:** cada sinal encerrado é comparado com o índice principal do mercado (SPY nos EUA, BOVA11 no Brasil), do fechamento do dia do sinal até o fechamento da saída.
- **Simulação:** cada operação é comparada com o mesmo valor aplicado no índice, do fechamento anterior à entrada até a saída.

Os índices são coletados toda noite (`coleta/indices.py` → `indice.json`).

## Quando reavaliar

Em **04/11/2027**, por mercado, se o diário tiver pelo menos **100 sinais encerrados** desde 04/11/2026. Se não tiver, o teste continua até chegar a 100, com limite de 04/11/2028.

## Critérios de aprovação (todos, por mercado)

1. **Diário:** a média real por sinal é maior que a média do índice nas mesmas datas.
2. **Contra o acaso, só com dados posteriores a 04/11/2026:** rodando `medir_adversarial.js` com o teste começando em 05/11/2026, o fator de lucro dos grupos "só treino" e "todos" fica acima do percentil 95 das entradas aleatórias. Com custo ×2 e com deslize de 0,1 ATR, ele continua ≥ 1,0.
3. **Carteira:** na carteira com capital limitado (mediana de 30 sorteios da ordem dos sinais), no mesmo período novo, o retorno é maior ou igual ao do índice real, com queda máxima não maior.

**Se qualquer critério falhar, a estratégia é descartada naquele mercado.** Ela não pode ser "salva" com ajuste de parâmetro. Uma ideia nova precisa de um teste novo, separado, em dados que este teste não usou.

## Desvios registrados (escritos antes de ver os resultados do período)

### 12/11/2026: universo menor e coleta parada de 07/11 a 12/11

- **O que mudou:** a VM Oracle deixou de baixar os ~3.400 papéis dos EUA. Desde 12/11/2026 a coleta usa os **500 papéis
  de maior volume financeiro** (média de 60 pregões, lista refeita a cada coleta e renovada uma vez por mês com a tela de
  ações da Nasdaq; `coleta/universo_liquido.py`). O Brasil continua com a carteira do Ibovespa inteira. Motivo: evitar o
  limite do Yahoo com o IP da Oracle (decisão do Diego, 12/11/2026).
- **Coleta parada:** de 07/11 a 12/11/2026 a coleta de mercado ficou desligada. Os sinais desses pregões não foram anotados.
  Os sinais já anotados continuam sendo acompanhados normalmente, porque o motor refaz o resultado a partir dos preços.
- **O que NÃO mudou:** sinais, pesos, stops, saídas, regra de escolha, travas do veredito e a recalibração. O relatório e o
  diário continuam rodando **todo pregão**.
- **Efeito esperado:** menos sinais por dia nos EUA. A meta de 100 sinais encerrados pode só ser alcançada mais tarde
  (o limite de 04/11/2028 continua valendo). A amostra passa a ser de papéis mais líquidos, o que deve ser lembrado na
  leitura do critério 2.
- **Como avaliar:** os três critérios continuam os mesmos. Na reavaliação, o resultado dos EUA será lido como
  "estratégia congelada aplicada aos 500 mais negociados", e não como o sistema original de ~3.400 papéis.
