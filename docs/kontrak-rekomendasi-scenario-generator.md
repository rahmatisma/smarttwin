# Kontrak Recommendation Scenario Generator — untuk integrasi frontend

Dokumen serah-terima backend → frontend. Tidak mengubah bentuk endpoint:

```text
POST /recommendation
```

Field `recommendation.source` menentukan asal keputusan:

| Nilai | Arti | Metrik SUMO |
|---|---|---|
| `scenario-generator` | Pemenang kandidat yang benar-benar diuji melalui SUMO dan dibaca dari cache segar | Tersedia |
| `rule-based+forecast` | Estimasi langsung RuleBasedEngine dengan 70% state aktual + 30% forecast | `null` |
| `rule-based` | Estimasi langsung tanpa forecast | `null` |
| `fallback` | TrafficState tidak tersedia / jalur aman | `null` |

Field performa bersifat opsional/null-safe:

| Field | Type | Makna |
|---|---|---|
| `avgDelaySeconds` | `number \| null` | Proxy rata-rata accumulated waiting time SUMO |
| `avgQueueLengthM` | `number \| null` | Estimasi peak halted vehicles × 7 meter |
| `los` | `string \| null` | LOS A–F dari delay |
| `candidateId` | `string \| null` | `baseline`, `aggressive`, atau `balanced` |

Aturan konsumsi: tampilkan badge/metrik SUMO hanya ketika
`source === "scenario-generator"` dan field terkait tidak null. Frontend tidak
boleh menganggap field hilang sebagai angka nol.

Contoh hasil cache segar:

```json
{
  "source": "scenario-generator",
  "recommendedPhase": "south",
  "recommendedGreenSeconds": 22,
  "avgDelaySeconds": 13.37,
  "avgQueueLengthM": 35.0,
  "los": "B",
  "candidateId": "balanced"
}
```

Backend tetap kompatibel dengan frontend lama karena semua field performa baru
opsional dan field lama tidak dihapus atau diganti nama.

Jika worker dijalankan dengan `--full-cycle`, `cyclePlan` juga berasal dari
kandidat empat-lengan pemenang dan `cyclePlan.source` bernilai
`scenario-generator`. Tanpa mode itu, cycle plan tetap berasal dari jalur
RuleBasedEngine yang sudah ada.
