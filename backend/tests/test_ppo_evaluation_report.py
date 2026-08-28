from decision_engine.evaluate_ppo import compare_results


def _metrics(*, reward, queue, wait, throughput):
    return {
        "mean_reward": reward,
        "mean_queue_veh": queue,
        "mean_accumulated_wait_s": wait,
        "total_throughput_veh": throughput,
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
    comparison = compare_results(
        _metrics(reward=-0.2, queue=9, wait=90, throughput=101),
        _metrics(reward=-0.1, queue=10, wait=100, throughput=100),
    )

    assert comparison["traffic_metrics_won"] == 3
    assert comparison["quality_gate_passed"] is True
    assert comparison["recommended_for_activation"] is True
