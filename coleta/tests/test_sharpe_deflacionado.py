import math
import random

import pytest

import sharpe_deflacionado as sd


def test_psr_simetrico_e_normal():
    # Sharpe medido igual ao limite: 50%
    assert sd.psr(0.2, 0.2, 60) == pytest.approx(0.5)
    # retornos normais (assimetria 0, curtose 3): fórmula fechada
    sr, n = 0.25, 120
    z = sr * math.sqrt(n - 1) / math.sqrt(1 + sr * sr / 2)
    assert sd.psr(sr, 0.0, n) == pytest.approx(sd.N.cdf(z))


def test_caudas_gordas_e_assimetria_negativa_reduzem_confianca():
    base = sd.psr(0.3, 0.0, 60)
    assert sd.psr(0.3, 0.0, 60, assimetria=-1.0, curtose=8.0) < base


def test_limite_da_sorte_cresce_com_tentativas():
    v = 0.01
    l = [sd.sharpe_maximo_por_sorte(n, v) for n in (2, 10, 100, 1000)]
    assert l == sorted(l) and l[0] > 0
    # valor de referência do artigo (Bailey e López de Prado 2014): com N=100 e V=1, E[max] ≈ 2,53
    assert sd.sharpe_maximo_por_sorte(100, 1.0) == pytest.approx(2.53, abs=0.01)
    assert sd.sharpe_maximo_por_sorte(1, v) == 0.0


def test_deflacionado_pune_muitas_tentativas():
    rng = random.Random(7)
    r = [rng.gauss(0.01, 0.04) for _ in range(120)]       # Sharpe mensal ~0,25
    um = sd.deflacionado(r, 1)
    muitos = sd.deflacionado(r, 200)
    assert um['dsr'] == pytest.approx(um['psr0'])
    assert muitos['dsr'] < um['dsr'] and muitos['sr0'] > 0


def test_sem_vantagem_nao_passa_mesmo_com_poucas_tentativas():
    rng = random.Random(1)
    r = [rng.gauss(0.0, 0.05) for _ in range(60)]
    assert sd.deflacionado(r, 20)['dsr'] < 0.95


def test_rf_e_erros():
    r = [0.02, 0.01, 0.03, -0.01, 0.015]
    rf = [0.01] * 5
    assert sd.sharpe(r, rf) < sd.sharpe(r)
    with pytest.raises(ValueError):
        sd.momentos([0.01, 0.01, 0.01])
    with pytest.raises(ValueError):
        sd.momentos([0.01, 0.02])


def test_cli(tmp_path, capsys):
    p = tmp_path / 'r.txt'
    p.write_text('\n'.join(str(x) for x in [0.02, -0.01, 0.03, 0.01, -0.02, 0.025, 0.0, 0.015]))
    assert sd.main([str(p), '--testes', '30']) == 0
    assert 'Sharpe deflacionado' in capsys.readouterr().out
