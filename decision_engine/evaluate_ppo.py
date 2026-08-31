from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

from stable_baselines3 import PPO

if __package__:
    from .ppo_env import DEFAULT_DATA, DEFAULT_DENSITY_DATA, SmartTwinSumoEnv
else:
    # Mendukung eksekusi langsung dari folder decision_engine.
    root = Path(__file__).resolve().parents[1]
    for import_dir in (root, root / "backend"):
        if str(import_dir) not in sys.path:
            sys.path.insert(0, str(import_dir))
    from decision_engine.ppo_env import DEFAULT_DATA, DEFAULT_DENSITY_DATA, SmartTwinSumoEnv


# Metrik lalu lintas SENGAJA berbentuk LAJU / RATA-RATA PER KENDARAAN, bukan
# total mentah. Satu langkah keputusan = satu rotasi penuh yang panjangnya
# dipilih agent sendiri (76-256 detik), jadi dua kebijakan yang menjalankan
# jumlah langkah sama BELUM TENTU mensimulasikan jumlah detik yang sama.
#
# Versi sebelumnya memakai `total_throughput_veh` (jumlah mentah) dan
# menyimpulkan PPO kalah throughput ~15% di 3 seed. Terukur, itu artefak:
# rule-based memilih siklus lebih panjang sehingga mendapat 18-20% lebih
# banyak detik simulasi. Setelah dinormalkan per detik, selisihnya
# +1,0% / +0,0% / +2,2% -- praktis seri. Lihat Bug F di
# docs/audit-bug-ppo-sebelum-training-ke-5.md.
METRIC_RULES = {
    "mean_reward": "higher",
    "mean_queue_veh": "lower",
    "mean_wait_per_vehicle_s": "lower",
    "throughput_veh_per_hour": "higher",
}
TRAFFIC_METRICS = (
    "mean_queue_veh",
    "mean_wait_per_vehicle_s",
    "throughput_veh_per_hour",
)
# Selisih di bawah ambang ini dianggap SERI, bukan kemenangan. Tanpa ini,
# selisih 0,01% pun tercatat sebagai "PPO unggul" dan gerbang kualitas bisa
# lolos karena noise. 2% dipilih karena selisih throughput per detik yang
# terukur antar-seed (+0,0% s/d +2,2%) memang berada di rentang itu.
TIE_THRESHOLD_PERCENT = 2.0

# Anggaran waktu simulasi per episode. 1.800 detik = 30 menit simulasi --
# cukup panjang supaya sisa langkah terakhir (yang diselesaikan utuh, maks
# 256 detik) tidak lebih dari ~14% anggaran, sehingga kedua kebijakan
# benar-benar mendapat durasi yang setara.
DEFAULT_SECONDS_PER_EPISODE = 1_800


def compare_results(ppo: dict[str, float], rule_based: dict[str, float]) -> dict:
    """Bandingkan metrik operasional tanpa menyamakan reward dengan kualitas lalu lintas."""
    metrics = {}
    for name, direction in METRIC_RULES.items():
        ppo_value = float(ppo[name])
        baseline_value = float(rule_based[name])
        delta = ppo_value - baseline_value
        # Persentase reward negatif mudah menyesatkan (mis. -0,1 vs -0,3
        # terlihat sebagai perubahan >100%). Persentase hanya bermakna untuk
        # metrik lalu lintas dengan skala fisik.
        delta_percent = (
            None
            if name == "mean_reward" or baseline_value == 0
            else (delta / abs(baseline_value)) * 100.0
        )
        ppo_better = ppo_value >= baseline_value if direction == "higher" else ppo_value <= baseline_value
        # Selisih sangat kecil dilaporkan apa adanya sebagai SERI supaya tidak
        # terbaca sebagai kemenangan. Reward dikecualikan (skalanya bukan fisik).
        is_tie = (
            name != "mean_reward"
            and delta_percent is not None
            and abs(delta_percent) < TIE_THRESHOLD_PERCENT
        )
        metrics[name] = {
            "ppo": ppo_value,
            "rule_based": baseline_value,
            "direction": direction,
            "delta": delta,
            "delta_percent": delta_percent,
            "ppo_better_or_equal": ppo_better,
            "tie": is_tie,
        }

    traffic_wins = sum(
        bool(metrics[name]["ppo_better_or_equal"]) and not metrics[name]["tie"]
        for name in TRAFFIC_METRICS
    )
    traffic_ties = sum(bool(metrics[name]["tie"]) for name in TRAFFIC_METRICS)
    quality_gate = traffic_wins == len(TRAFFIC_METRICS)
    return {
        "metrics": metrics,
        "traffic_metrics_won": traffic_wins,
        "traffic_metrics_tied": traffic_ties,
        "traffic_metrics_total": len(TRAFFIC_METRICS),
        "quality_gate_passed": quality_gate,
        "recommended_for_activation": quality_gate,
        "verdict": (
            "PPO memenuhi seluruh metrik lalu lintas."
            if quality_gate
            else "PPO belum boleh diaktifkan; gunakan rule-based fallback."
        ),
    }


def run(policy: str, model: PPO | None, episodes: int, seed: int,
        data_path: str | Path = DEFAULT_DATA,
        density_data_path: str | Path = DEFAULT_DENSITY_DATA,
        seconds_per_episode: int = DEFAULT_SECONDS_PER_EPISODE) -> dict[str, float]:
    """Jalankan satu kebijakan dengan ANGGARAN WAKTU SIMULASI tetap.

    Dulu fungsi ini berhenti setelah sejumlah LANGKAH tetap (12 per episode).
    Karena panjang satu langkah = satu rotasi penuh yang durasinya dipilih
    agent (76-256 detik), dua kebijakan bisa mensimulasikan jumlah detik yang
    sangat berbeda -- lalu totalnya dibandingkan seolah setara. Itu Bug F.

    Sekarang tiap episode berjalan sampai `seconds_per_episode` detik simulasi
    tercapai, apa pun panjang siklus yang dipilih. Langkah yang sedang berjalan
    diselesaikan utuh (tidak dipotong di tengah rotasi), jadi total detik bisa
    sedikit melewati anggaran -- selisihnya dilaporkan lewat `simulated_seconds`
    supaya ketidaksetaraan sekecil apa pun tetap terlihat, tidak tersembunyi.
    """
    rewards, queues, waits_per_vehicle, throughputs = [], [], [], []
    simulated_seconds = 0.0
    env = SmartTwinSumoEnv(
        split="eval",
        data_path=data_path,
        density_data_path=density_data_path,
    )
    try:
        for episode in range(episodes):
            obs, _ = env.reset(seed=seed + episode)
            episode_seconds = 0.0
            while episode_seconds < seconds_per_episode:
                action = env.rule_based_action() if policy == "rule-based" else model.predict(obs, deterministic=True)[0]
                obs, reward, terminated, truncated, info = env.step(action)
                rewards.append(reward)
                queues.append(info["queue"])
                # Waktu tunggu dinormalkan PER KENDARAAN. `info["waiting"]`
                # adalah jumlah akumulasi seluruh kendaraan yang sedang ada,
                # jadi nilainya ikut membesar hanya karena kendaraannya lebih
                # banyak -- bukan karena kebijakannya lebih buruk.
                waits_per_vehicle.append(info["waiting"] / max(1.0, info["vehicles"]))
                throughputs.append(info["throughput_interval"])
                episode_seconds += float(info["window_seconds"])
                if terminated or truncated:
                    # Anggaran waktu belum habis tapi episode env sudah penuh
                    # (episode_steps). Lanjutkan di episode baru dengan seed
                    # yang sama supaya profil permintaannya konsisten.
                    obs, _ = env.reset(seed=seed + episode)
            simulated_seconds += episode_seconds
    finally:
        env.close()
    return {
        "mean_reward": mean(rewards),
        "mean_queue_veh": mean(queues),
        "mean_wait_per_vehicle_s": mean(waits_per_vehicle),
        "throughput_veh_per_hour": sum(throughputs) / simulated_seconds * 3600.0,
        # Dilaporkan supaya kesetaraan perbandingan bisa DIPERIKSA, bukan
        # diasumsikan -- ini yang dulu tidak terlihat sehingga Bug F lolos.
        "simulated_seconds": simulated_seconds,
        "decision_steps": len(rewards),
        "total_throughput_veh": sum(throughputs),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Bandingkan PPO dengan baseline rule-based pada seed sama")
    parser.add_argument("--model", default="decision_engine/models/smarttwin_ppo.zip")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--density-data", default=str(DEFAULT_DENSITY_DATA))
    parser.add_argument("--seconds-per-episode", type=int, default=DEFAULT_SECONDS_PER_EPISODE,
                        help="Anggaran waktu SIMULASI per episode (detik). Kedua kebijakan "
                             "mendapat anggaran sama supaya perbandingannya setara.")
    parser.add_argument("--output", default="decision_engine/models/evaluation.json")
    args = parser.parse_args()
    model = PPO.load(args.model)
    result = {
        "episodes": args.episodes,
        "seed_start": args.seed,
        "seconds_per_episode": args.seconds_per_episode,
        "ppo": run("ppo", model, args.episodes, args.seed, args.data, args.density_data,
                   args.seconds_per_episode),
        "rule_based": run("rule-based", None, args.episodes, args.seed, args.data, args.density_data,
                          args.seconds_per_episode),
    }
    result["comparison"] = compare_results(result["ppo"], result["rule_based"])

    # Pemeriksaan kesetaraan yang GAGAL KERAS kalau kedua kebijakan ternyata
    # tetap mensimulasikan durasi yang jauh berbeda. Bug F dulu lolos justru
    # karena tidak ada pemeriksaan seperti ini -- angkanya ada, tapi tidak
    # pernah dibandingkan.
    ppo_seconds = result["ppo"]["simulated_seconds"]
    rule_seconds = result["rule_based"]["simulated_seconds"]
    skew = abs(ppo_seconds - rule_seconds) / max(ppo_seconds, rule_seconds) * 100.0
    result["fairness"] = {
        "ppo_simulated_seconds": ppo_seconds,
        "rule_based_simulated_seconds": rule_seconds,
        "skew_percent": skew,
        "comparable": skew < 5.0,
        "note": (
            "Kedua kebijakan mendapat anggaran waktu simulasi sama. Selisih kecil "
            "wajar karena langkah terakhir diselesaikan utuh (tidak dipotong di "
            "tengah rotasi). Kalau skew_percent >= 5, metrik laju masih bisa "
            "dipakai tapi jangan kutip total mentah."
        ),
    }

    target = Path(args.output); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2)); print(f"Laporan: {target.resolve()}")
    if not result["fairness"]["comparable"]:
        print(f"\n[PERINGATAN] Durasi simulasi kedua kebijakan berbeda {skew:.1f}% "
              f"(PPO {ppo_seconds:.0f}s vs rule-based {rule_seconds:.0f}s). "
              f"Naikkan --seconds-per-episode supaya selisihnya mengecil.")


if __name__ == "__main__":
    main()
