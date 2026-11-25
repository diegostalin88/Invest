import numpy as np
import pytest

hrp = pytest.importorskip('hrp')


def _dados(n_ativos, semente):
    g = np.random.default_rng(semente)
    fatores = g.normal(0, 0.01, (300, 2))
    carga = g.uniform(-1, 1.5, (2, n_ativos))
    return fatores @ carga + g.normal(0, 0.012, (300, n_ativos)) * g.uniform(0.3, 2, n_ativos)


def test_soma_um_e_positivos():
    w = hrp.pesos_hrp(_dados(5, 1))
    assert abs(w.sum() - 1) < 1e-12 and (w > 0).all()


@pytest.mark.parametrize('n,semente,ligacao', [(3, 1, 'single'), (5, 2, 'single'), (8, 3, 'single'), (8, 4, 'ward')])
def test_igual_ao_pyportfolioopt(n, semente, ligacao):
    pd = pytest.importorskip('pandas')
    hp = pytest.importorskip('pypfopt.hierarchical_portfolio')
    if not hasattr(hp.sch, '_LINKAGE_METHODS'):   # PyPortfolioOpt 1.6 usa um nome interno que o scipy 1.18 tirou
        hp.sch._LINKAGE_METHODS = {'single': 0, 'complete': 1, 'average': 2, 'centroid': 3, 'median': 4, 'ward': 5, 'weighted': 6}
    r = _dados(n, semente)
    nomes = [f'A{k}' for k in range(n)]
    ref = hp.HRPOpt(pd.DataFrame(r, columns=nomes)).optimize(ligacao)
    w = hrp.pesos_hrp(r, ligacao)
    assert np.allclose(w, [ref[k] for k in nomes], atol=1e-10)
