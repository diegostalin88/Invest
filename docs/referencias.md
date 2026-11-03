# Referências do projeto (livros do Diego)

Livros e textos que o Diego usou para montar o GRAFICO16, na pasta do Drive
"Invest" (`1WpEUwDfxKik70qhpnNUbAYSffF1Fivz7`). Este arquivo liga cada um ao
que o app faz hoje e ao que ainda falta. **Nada da lista "Lacunas" foi
implementado:** cada item muda a lógica quantitativa e precisa do aval do Diego.

> Quanto foi lido: a ferramenta do Drive só devolve o começo de PDFs grandes.
> Foram lidos o sumário e os primeiros capítulos de cada livro; Fitschen até
> o capítulo 5 (saídas); a dissertação de Pereira inteira. O resto vem do
> conhecimento geral dessas obras e está marcado como tal.

## Os livros e o que o app já usa de cada um

| Livro | Ideia central | Onde já está no app |
|---|---|---|
| **Perry Kaufman — *Trading Systems and Methods*** (TSaM.pdf) | Enciclopédia de indicadores e de medidas de sistema (conhecimento geral). | Expectativa de Kaufman no Backtest; Keltner, ATR, DMI, Donchian, SAR nos motores. |
| **Perry Kaufman — *A Guide to Creating a Successful Algorithmic Trading Strategy*** (L-0005005850) | Regras simples; robustez em vários parâmetros e mercados; custos reais; testar dentro e fora da amostra; tendência sem alvo de lucro, curto prazo com alvo; evitar ações de preço baixo e volatilidade extrema. | Custos por perna; risco fixo de 1% por trade ("equal opportunity"); filtro de clima; Walk-Forward. |
| **Keith Fitschen — *Building Reliable Trading Systems*** (Fitschen) | "Caminho de menor resistência": ação no diário tende a **reverter** (comprar queda), commodity tende a seguir tendência. Quatro saídas: sinal reverso, stop, **saída por tempo**, **alvo de lucro**. Stop protege contra perda grande, mas raramente aumenta o lucro; trailing stop quase nunca ajudou no curto prazo. Liquidez mínima de US$ 20 mi/dia. | Walk-Forward (Módulo 4); liquidez mínima (US$ 50 mi / R$ 10 mi); execução no open seguinte. |
| **Ernest Chan — *Algorithmic Trading*** (L-G-0000806890) | Evitar **look-ahead** (usar o futuro sem querer) e **data snooping** (ajustar demais ao passado); poucos parâmetros; viés de sobrevivência; reversão à média × momentum; Kelly e Monte Carlo para risco. | Pivôs só valem depois de confirmados; ordem no open seguinte; correlação de Pearson (Módulo 5). |
| **Rivadavila Malheiros — *Operando com Trading Systems na Bolsa*** (Operando_com_trading) | Perfil do trader (tempo gráfico); **perfil gráfico do ativo** (tendência × acumulação); volatilidade não pode vir de pouca liquidez; três stops: perda, **objetivo** e móvel; expectativa matemática; teste de carteira. Capítulos de Donchian, médias, HiLo, TRIX, candles, estocástico, CCI, Keltner, Bollinger, Aroon, DMI e volume. | Stop fixo + stop móvel; boa parte das 31 estratégias da v14 vem desses capítulos. |
| **Barbara Rockefeller — *Análise Técnica para Leigos*** | Base dos indicadores e candles (conhecimento geral). | Padrões de candle e indicadores clássicos. |
| **Otavio Pereira — dissertação "Perfect Order Strategy"** (TEGI0570) | Médias exponenciais alinhadas acham tendência cedo, mas o sistema teve 24% de acerto e perdeu para o S&P 500 por causa de **stop mal posicionado** (perto demais ou longe demais) e **falta de realização de lucro**. | O stop inicial do app já é o mais protetor entre ATR e Stop Fixo, o que evita o stop "longe demais". |
| Attar et al. — *Algorithmic Trading System* (ATS.pdf) | Artigo introdutório sobre sistemas automáticos. | Contexto geral. |
| `sinais_quantitativos.xlsx` | Saída de uma versão antiga (sinais de Martelo e Engolfo de Alta no IBOVESPA). | Hoje em "Candles de Reversão" na v14. |

Arquivos pessoais da pasta (planilha de investimentos, ficha de terceiro,
relatório da XP, conversa exportada) **não foram lidos** e não entram aqui.

## Lacunas: o que os livros pedem e o app ainda não faz

1. **Saída só por stop.** Malheiros, Fitschen e Kaufman (curto prazo) usam
   também alvo de lucro e saída por tempo. Pereira mostra o custo de não
   realizar lucro. Proposta: opções no Backtest, desligadas por padrão, para
   comparar lado a lado.
2. **Perfil do ativo.** Malheiros e Fitschen: estratégia de tendência em papel
   que acumula (ou o contrário) não funciona. Chan dá testes estatísticos
   (Hurst, meia-vida) para classificar. Proposta: etiqueta "tendência" ou
   "reversão" por ativo e aviso quando a estratégia não combina.
3. **Viés de sobrevivência.** O Brasil usa a carteira *atual* do IBOVESPA, então
   o backtest só vê empresas que sobreviveram (Chan). Proposta: aviso no
   Backtest; corrigir de fato exige carteiras históricas.
4. **Significância.** Chan e Fitschen usam Monte Carlo (embaralhar os trades) para
   ver se o resultado pode ser sorte. Proposta: faixa de confiança no Backtest.
5. **Robustez de parâmetros.** Kaufman: o resultado não pode depender de um
   único valor. Proposta: testar Score Mínimo e ATR vizinhos e mostrar se o
   resultado se mantém.
6. **Preço baixo e volatilidade extrema.** Kaufman evita os dois. Proposta:
   filtros opcionais no bloco de liquidez.

## Confluência de sinais: o que a pesquisa diz (internet, 03/11/2026)

- **Regras técnicas isoladas perderam força.** Estudo com 6.406 regras em 41
  bolsas (Springer, 2023): o Brasil teve regras vencedoras em 1995–2001, mas
  deixou de ser previsível depois; com custos acima de 0,2% por operação quase
  nada sobrevive, e a melhor regra de um período costuma perder no seguinte.
  <https://link.springer.com/article/10.1007/s11408-023-00433-2>
- **Data snooping (testar regras demais até uma "dar certo")** é o maior risco
  de um score com muitas estratégias. Sullivan, Timmermann e White (1999).
  <https://econpapers.repec.org/RePEc:bla:jfinan:v:54:y:1999:i:5:p:1647-1691>
- **O que tem evidência longa:**
  - Filtro de tendência (preço acima da média longa): Faber, 10 meses, testado
    fora da amostra até 2016; AQR, um século de trend following.
    <https://www.etf.com/sections/index-investor-corner/swedroe-why-financial-trends-persist>
  - Média móvel funciona melhor em ações **mais voláteis** (Han, Yang e Zhou,
    2013). <https://alphaarchitect.com/technical-analysis-may-actually-work/>
  - Recuo dentro de tendência (Connors: IFR de 2 < 5–10 acima da MME200, saída
    na média de 5): acerto alto (~75%), mas ganho modesto e fora do mercado na
    maior parte do tempo.
    <https://backtrex.com/en/backtests/connors-rsi-2-nasdaq-100>,
    <https://cxoadvisory.com/technical-trading/a-few-notes-on-short-term-trading-strategies-that-work>
- **Combinar sinais ajuda quando eles são diferentes entre si** (contexto +
  gatilho + saída), não quando somam o mesmo tipo de sinal (contagem dobrada).
  Kaufman: "mais regras, menos oportunidades, menos sucesso".

**Conclusão aplicada ao app:** a confluência que tem respaldo é em camadas:
1. *contexto* (clima do mercado e preço acima da MME200);
2. *gatilho* coerente com o perfil do papel (recuo em ação que reverte,
   rompimento em ação de tendência);
3. *saída* definida (stop + alvo/tempo).

O score atual soma 7 estratégias e mistura tendência e reversão. A regra
"Tendência + recuo" foi adicionada como alternativa no Backtest (desligada por
padrão), para comparar as duas no "Testar na Carteira Inteira" com dados reais.
