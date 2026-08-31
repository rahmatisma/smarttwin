from decision_engine.evaluate_ppo import TIE_THRESHOLD_PERCENT, compare_results


def _metrics(*, reward, queue, wait, throughput):
    """Metrik dalam bentuk LAJU / per kendaraan, bukan total mentah.

    Bentuk ini disengaja: satu langkah keputusan = satu rotasi penuh yang
    panjangnya dipilih agent (76-256 detik), jadi total mentah tidak bisa
    dibandingkan antar-kebijakan. Lihat Bug F di
    docs/audit-bug-ppo-sebelum-training-ke-5.md.
    """
    return {
        "mean_reward": reward,
        "mean_queue_veh": queue,
        "mean_wait_per_vehicle_s": wait,
        "throughput_veh_per_hour": throughput,
    }


def test_reward_win_does_not_pass_traffic_quality_gate():
    comparison = compare_results(
        _metrics(reward=-0.1, queue=11, wait=90, throughput=80),
        _metrics(reward=-0.3, queue=10, wait=100, throughput=100),
    )

    assert comparison["metrics"]["mean_reward"]["ppo_better_or_equal"] is True
    assert comparison["metrics"]["mean_reward"]["delta_percent"] is None
    assert comparison["traffic_metrics_won"] == 1
    assert comparison["quality_gate_passed"] is False
    assert comparison["recommended_for_activation"] is False


def test_quality_gate_requires_all_three_traffic_metrics():
    # Selisih sengaja dibuat di ATAS TIE_THRESHOLD_PERCENT (2%) -- kalau tidak,
    # ketiganya dihitung seri dan gerbang kualitas tidak lolos. Versi lama test
    # ini memakai throughput 101 vs 100 (+1%), yang sekarang benar dianggap seri.
    comparison = compare_results(
        _metrics(reward=-0.2, queue=9, wait=90, throughput=105),
        _metrics(reward=-0.1, queue=10, wait=100, throughput=100),
    )

    assert comparison["traffic_metrics_won"] == 3
    assert comparison["quality_gate_passed"] is True
    assert comparison["recommended_for_activation"] is True


def test_selisih_di_bawah_ambang_dihitung_seri_bukan_menang():
    # Regresi Bug F: throughput per detik yang terukur antar-seed cuma berbeda
    # +0,0% s/d +2,2%. Tanpa ambang seri, selisih sekecil itu tercatat sebagai
    # "PPO unggul" dan gerbang kualitas bisa lolos karena noise semata.
    comparison = compare_results(
        _metrics(reward=-0.2, queue=99.5, wait=99.5, throughput=100.5),
        _metrics(reward=-0.1, queue=100.0, wait=100.0, throughput=100.0),
    )

    for name in ("mean_queue_veh", "mean_wait_per_vehicle_s", "throughput_veh_per_hour"):
        assert abs(comparison["metrics"][name]["delta_percent"]) < TIE_THRESHOLD_PERCENT
        assert comparison["metrics"][name]["tie"] is True

    assert comparison["traffic_metrics_tied"] == 3
    assert comparison["traffic_metrics_won"] == 0
    assert comparison["quality_gate_passed"] is False


def test_selisih_di_atas_ambang_tetap_dihitung_menang():
    comparison = compare_results(
        _metrics(reward=-0.2, queue=90.0, wait=90.0, throughput=110.0),
        _metrics(reward=-0.1, queue=100.0, wait=100.0, throughput=100.0),
    )

    for name in ("mean_queue_veh", "mean_wait_per_vehicle_s", "throughput_veh_per_hour"):
        assert comparison["metrics"][name]["tie"] is False

    assert comparison["traffic_metrics_won"] == 3
    assert comparison["quality_gate_passed"] is True
