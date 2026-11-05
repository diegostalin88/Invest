# Opções: o histórico público da B3 serve para calcular IV?

Registrado em **05/11/2026, antes de rodar**. Estudo só de leitura, separado do app e da estratégia congelada
(`docs/congelamento.md`). Faz parte da fase 2 (dados) do estudo de opções por cenário.

## Pergunta

Os arquivos anuais do COTAHIST (B3, gratuitos) trazem dados de opções suficientes para reconstruir, dia a dia, a
volatilidade implícita (IV) de ~30 dias e o IV Rank de 252 pregões, sem depender de fonte paga?

## Método (`opcoes/cotahist.py`)

- **Universo:** PETR4, VALE3, BOVA11, ITUB4, BBAS3, PRIO3. Anos 2018 a 2026.
- **Opções do dia:** calls (mercado 070) e puts (080) com a mesma raiz do ativo e a mesma classe (ON, PN, CI), para
  separar PETR3 de PETR4.
- **Escolha:** vencimento entre 20 e 60 dias corridos, o mais perto de 30; nesse vencimento, a call e a put com
  strike mais perto do fechamento à vista; pelo menos 5 negócios no dia e preço ≥ R$ 0,03.
- **IV:** Black-Scholes sem dividendos, com o CDI do dia (série 12 do Banco Central), média da call e da put.
- **Limitações conhecidas:** o último negócio da opção pode ser de horário diferente do fechamento à vista; as calls
  são americanas; o strike usado é o do arquivo daquele dia (já ajustado por proventos).

## Critério (fixado antes)

O COTAHIST **serve** se, para pelo menos 4 dos 6 ativos, a IV sair em **≥ 80% dos pregões** de cada ano desde
2019 e a IV mediana anual ficar entre 15% e 80% ao ano (faixa plausível para esses papéis). Caso contrário, a fase 2
precisa de outra fonte (paga ou coleta diária própria a partir de agora).

## Resultado

(preenchido depois da execução do workflow "Opções - verificar histórico da B3")
