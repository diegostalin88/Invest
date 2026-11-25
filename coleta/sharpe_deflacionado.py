"""Sharpe deflacionado (15/11/2026): critério extra do Laboratório contra "testei muitas ideias até uma dar certo".

Bailey e López de Prado (2014), "The Deflated Sharpe Ratio". Duas contas:

  PSR (Sharpe probabilístico): a chance de o Sharpe verdadeiro ser maior que um limite `sr0`, dado o Sharpe medido,
      o número de períodos e a forma dos retornos (assimetria e curtose: caudas gordas pioram a confiança).
  DSR (Sharpe deflacionado): o PSR usando como limite o MAIOR Sharpe que se esperaria só por sorte depois de
      `n_testes` tentativas. Quanto mais ideias testadas, mais alto o limite.

Tudo em Sharpe POR PERÍODO (ex.: mensal, sem anualizar). Só biblioteca padrão (cabe na VM de 1 GB).
Regra do protocolo (docs/protocolo-laboratorio.md): DSR >= 0,95 com n_testes = contador acumulado do projeto.

Uso: python coleta/sharpe_deflacionado.py retornos.txt --testes 40 [--rf cdi.txt] [--var-sharpe 0.01]
     (um retorno por linha, em fração; rf opcional com a mesma quantidade de linhas)
"""
import argparse
import math
import sys
from statistics import NormalDist

EULER = 0.5772156649015329
N = NormalDist()


def momentos(r):
    """média, desvio amostral, assimetria e curtose (não excesso: normal = 3)."""
    n = len(r)
    if n < 3:
        raise ValueError('precisa de pelo menos 3 retornos')
    m = sum(r) / n
    d = [x - m for x in r]
    m2 = sum(x * x for x in d) / n
    if m2 <= 0:
        raise ValueError('retornos sem variação')
    m3 = sum(x ** 3 for x in d) / n
    m4 = sum(x ** 4 for x in d) / n
    return m, math.sqrt(m2 * n / (n - 1)), m3 / m2 ** 1.5, m4 / m2 ** 2


def sharpe(r, rf=None):
    ex = [x - (rf[k] if rf else 0.0) for k, x in enumerate(r)]
    m, s, _, _ = momentos(ex)
    return m / s


def psr(sr, sr0, n, assimetria=0.0, curtose=3.0):
    """Probabilidade de o Sharpe verdadeiro superar sr0 (Sharpe por período, n períodos)."""
    den = 1 - assimetria * sr + (curtose - 1) / 4 * sr * sr
    if den <= 0:
        return float('nan')
    return N.cdf((sr - sr0) * math.sqrt(n - 1) / math.sqrt(den))


def sharpe_maximo_por_sorte(n_testes, var_sharpe):
    """Sharpe máximo esperado entre n_testes ideias SEM vantagem nenhuma, com variância var_sharpe entre elas."""
    if n_testes < 2:
        return 0.0
    return math.sqrt(var_sharpe) * ((1 - EULER) * N.inv_cdf(1 - 1 / n_testes) + EULER * N.inv_cdf(1 - 1 / (n_testes * math.e)))


def deflacionado(r, n_testes, rf=None, var_sharpe=None):
    """Devolve {sharpe, sr0, psr0, dsr, n, assimetria, curtose}. var_sharpe: variância dos Sharpes das tentativas;
    sem ela, usa a variância do próprio estimador ((1 + sr²/2)/(n-1)), que é o mínimo razoável."""
    ex = [x - (rf[k] if rf else 0.0) for k, x in enumerate(r)]
    m, s, a, k = momentos(ex)
    sr, n = m / s, len(ex)
    v = var_sharpe if var_sharpe is not None else (1 + sr * sr / 2) / (n - 1)
    sr0 = sharpe_maximo_por_sorte(n_testes, v)
    return {'sharpe': sr, 'n': n, 'assimetria': a, 'curtose': k, 'nTestes': n_testes, 'varSharpe': v,
            'sr0': sr0, 'psr0': psr(sr, 0.0, n, a, k), 'dsr': psr(sr, sr0, n, a, k)}


def ler(caminho):
    with open(caminho, encoding='utf-8') as f:
        return [float(l.strip().replace(',', '.')) for l in f if l.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('retornos')
    ap.add_argument('--testes', type=int, required=True, help='contador acumulado de tentativas do projeto')
    ap.add_argument('--rf')
    ap.add_argument('--var-sharpe', type=float)
    a = ap.parse_args(argv)
    r = ler(a.retornos)
    rf = ler(a.rf) if a.rf else None
    if rf and len(rf) != len(r):
        print('retornos e rf com tamanhos diferentes')
        return 1
    o = deflacionado(r, a.testes, rf, a.var_sharpe)
    print(f"Sharpe por período {o['sharpe']:.4f} em {o['n']} períodos (assimetria {o['assimetria']:.2f}, curtose {o['curtose']:.2f})")
    print(f"Chance de Sharpe verdadeiro > 0: {o['psr0']:.1%}")
    print(f"Limite da sorte com {a.testes} tentativas: {o['sr0']:.4f} por período")
    print(f"Sharpe deflacionado: {o['dsr']:.1%}  ->  {'PASSA' if o['dsr'] >= 0.95 else 'NÃO passa'} (critério: 95%)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
