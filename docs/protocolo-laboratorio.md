# Protocolo do Laboratório: como uma ideia é testada (15/11/2026)

Vale para toda ideia nova a partir de 15/11/2026. As ideias já testadas continuam com os critérios com que foram
registradas, e **nenhuma reprovada é reaberta** por causa deste protocolo (nem por ferramenta nova).

## 1. Registro antes do teste

Um arquivo `docs/hipotese-<nome>.md` escrito **antes de rodar qualquer coisa**, com: pergunta, dados e período,
regras com parâmetros fixos, referência de comparação, custo (normal e dobrado), metades do período e critérios.
Depois de ver o resultado, nada muda; um ajuste vira uma **nova tentativa** e entra no contador.

## 2. Critérios mínimos (além dos específicos de cada hipótese)

1. Sharpe (sobre o CDI) maior que o da referência no período inteiro **e** em cada metade.
2. Queda máxima não pior que a da referência (ou a margem escrita no registro).
3. Com custo dobrado, acima do percentil 95 do acaso (sorteios que mantêm exposição e giro).
4. **Sharpe deflacionado ≥ 95%** (`coleta/sharpe_deflacionado.py`), com retornos mensais em excesso ao CDI e
   `--testes` = o contador acumulado abaixo. Ele responde: "depois de tantas tentativas no projeto, qual a chance de
   este Sharpe não ser só a melhor das sortes?". Bailey e López de Prado (2014).

Aprovou em tudo: vira **teste para frente sem dinheiro real** (≥ 100 sinais fechados ou 2 anos), como as regras
congeladas. Reprovou: fica registrado e não se reabre com outros parâmetros.

## 3. Contador de tentativas do projeto

O Sharpe deflacionado fica mais exigente a cada tentativa. O contador é o **mínimo** que dá para contar pelos
registros; o número real de variações olhadas é maior, então ele é otimista a favor das ideias.

| Registro | Tentativas (mínimo) |
|---|---|
| Estratégia técnica do app (31 estratégias do ranking) | 31 |
| A e B: momento de 12 meses e tendência no índice, EUA e Brasil | 4 |
| Controle de exposição pela volatilidade | 1 |
| C: fundamentos EUA, Brasil e confirmação | 3 |
| D: surpresa do balanço e confirmação | 2 |
| Q-BR: qualidade | 1 |
| H: ETFs de dividendos | 3 |
| Opções O1 a O7 | 7 |
| K: cripto (T1–T3, M1–M2, P1–P2) | 7 |
| Queda ≥ 30% + Otimista, Brasil e EUA | 2 |
| Direção intradiária dos papéis quânticos | 1 |
| **Total em 15/11/2026** | **62** |

Cada hipótese nova soma aqui o número de variantes que testar (ex.: 3 janelas = 3) **antes** de rodar.

## 4. Ferramentas

- `coleta/sharpe_deflacionado.py`: só biblioteca padrão; roda na VM.
- Estudo de fatores (alphalens): usar o fork mantido `alphalens-reloaded`, só em estudo fora do horário da coleta
  (22:30 UTC), nunca na coleta diária. Um fator com bom "IC" no alphalens ainda precisa passar nos critérios acima.
- Desempenho da carteira e do placar do agente: as mesmas contas no app (Carteira → Comparação → Risco no período),
  mensais, sempre ao lado da referência 1/3.
