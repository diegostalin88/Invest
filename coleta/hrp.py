"""Paridade de risco hierárquica (HRP, López de Prado 2016) só com numpy e scipy (16/11/2026).

É a mesma conta do HRPOpt do PyPortfolioOpt (que o registro da hipótese P cita), sem instalar o PyPortfolioOpt,
porque ele puxa o cvxpy, pesado para a VM de 1 GB. O teste `test_hrp.py` confere peso a peso contra o PyPortfolioOpt
quando ele está instalado (fora da VM).

Passos: (1) distância entre ativos = sqrt((1 - correlação) / 2); (2) árvore de agrupamento (scipy, ligação "single"
por padrão); (3) ordena os ativos pelas folhas da árvore; (4) bisseção recursiva: cada metade recebe peso
inversamente proporcional à sua variância (variância da carteira de variância inversa dentro da metade).
"""
import numpy as np
import scipy.cluster.hierarchy as sch
import scipy.spatial.distance as ssd


def _var_cluster(cov, itens):
    c = cov[np.ix_(itens, itens)]
    w = 1 / np.diag(c)
    w /= w.sum()
    return float(w @ c @ w)


def pesos_hrp(retornos, ligacao='single'):
    """retornos: matriz (períodos × ativos). Devolve um vetor de pesos (soma 1, sem venda a descoberto)."""
    r = np.asarray(retornos, dtype=float)
    cov = np.cov(r, rowvar=False)
    corr = np.corrcoef(r, rowvar=False)
    dist = np.sqrt(np.clip((1.0 - corr) / 2.0, 0.0, 1.0))
    arvore = sch.linkage(ssd.squareform(dist, checks=False), ligacao)
    ordem = sch.to_tree(arvore, rd=False).pre_order()
    w = np.ones(r.shape[1])
    grupos = [ordem]
    while grupos:
        grupos = [g[a:b] for g in grupos for a, b in ((0, len(g) // 2), (len(g) // 2, len(g))) if len(g) > 1]
        for i in range(0, len(grupos), 2):
            v1, v2 = _var_cluster(cov, grupos[i]), _var_cluster(cov, grupos[i + 1])
            alfa = 1 - v1 / (v1 + v2)
            w[grupos[i]] *= alfa
            w[grupos[i + 1]] *= 1 - alfa
    return w
