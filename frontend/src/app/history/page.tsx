"use client";

import { useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowDown,
  ArrowUp,
  Brain,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Eye,
  Filter,
  Gauge,
  History as HistoryIcon,
  Search,
  Server,
  SlidersHorizontal,
  Sparkles,
  Timer,
  TrafficCone,
  TrendingDown,
  TrendingUp,
  X,
  XCircle,
} from "lucide-react";

import Sidebar from "@/components/Sidebar";

type SimulationStatus = "Completed" | "Running" | "Failed" | "Cancelled";

type TrafficLevel = "Low" | "Medium" | "High";

type DecisionType =
  | "Extend Green"
  | "Reduce Green"
  | "Phase Shift"
  | "Keep Current"
  | "Emergency Adjustment";

interface HistoryRecord {
  id: string;
  timestamp: string;
  intersection: string;
  trafficLevel: TrafficLevel;
  vehicleCount: number;
  queueLength: number;
  avgSpeed: number;
  waitingTime: number;

  decision: DecisionType;
  decisionDescription: string;

  currentGreen: number;
  recommendedGreen: number;

  improvement: number;
  queueReduction: number;
  waitingReduction: number;
  throughputIncrease: number;

  status: SimulationStatus;

  simulationDuration: number;
  confidence: number;

  forecast: string;
  model: string;
}

const HISTORY_DATA: HistoryRecord[] = [
  {
    id: "SIM-20260823-0132",
    timestamp: "23 Aug 2026, 01:32",
    intersection: "Simpang 4 Pingit",
    trafficLevel: "High",
    vehicleCount: 486,
    queueLength: 42,
    avgSpeed: 24,
    waitingTime: 87,
    decision: "Extend Green",
    decisionDescription:
      "Extend north-south green phase because of high queue density.",
    currentGreen: 40,
    recommendedGreen: 55,
    improvement: 12.4,
    queueReduction: 19,
    waitingReduction: 22,
    throughputIncrease: 11,
    status: "Completed",
    simulationDuration: 38,
    confidence: 94,
    forecast: "High congestion expected in the next 10 minutes.",
    model: "PPO v1.0 + LSTM v1.2",
  },
  {
    id: "SIM-20260823-0058",
    timestamp: "23 Aug 2026, 00:58",
    intersection: "Simpang 2",
    trafficLevel: "Medium",
    vehicleCount: 318,
    queueLength: 31,
    avgSpeed: 29,
    waitingTime: 64,
    decision: "Extend Green",
    decisionDescription:
      "Slightly extend the green phase to reduce queue accumulation.",
    currentGreen: 35,
    recommendedGreen: 43,
    improvement: 8.7,
    queueReduction: 14,
    waitingReduction: 17,
    throughputIncrease: 8,
    status: "Completed",
    simulationDuration: 31,
    confidence: 89,
    forecast: "Moderate traffic increase expected.",
    model: "PPO v1.0 + LSTM v1.2",
  },
  {
    id: "SIM-20260823-0021",
    timestamp: "23 Aug 2026, 00:21",
    intersection: "Simpang 1",
    trafficLevel: "High",
    vehicleCount: 524,
    queueLength: 48,
    avgSpeed: 21,
    waitingTime: 96,
    decision: "Phase Shift",
    decisionDescription:
      "Shift signal phase to prioritize the heavily congested approach.",
    currentGreen: 30,
    recommendedGreen: 45,
    improvement: 16.2,
    queueReduction: 27,
    waitingReduction: 25,
    throughputIncrease: 15,
    status: "Completed",
    simulationDuration: 44,
    confidence: 96,
    forecast: "Severe congestion predicted on the east approach.",
    model: "PPO v1.0 + LSTM v1.2",
  },
  {
    id: "SIM-20260822-2354",
    timestamp: "22 Aug 2026, 23:54",
    intersection: "Simpang 4 Pingit",
    trafficLevel: "Medium",
    vehicleCount: 274,
    queueLength: 24,
    avgSpeed: 34,
    waitingTime: 51,
    decision: "Keep Current",
    decisionDescription:
      "Current signal timing provides sufficient traffic performance.",
    currentGreen: 40,
    recommendedGreen: 40,
    improvement: 2.8,
    queueReduction: 4,
    waitingReduction: 5,
    throughputIncrease: 3,
    status: "Completed",
    simulationDuration: 26,
    confidence: 82,
    forecast: "Traffic condition expected to remain stable.",
    model: "PPO v1.0 + LSTM v1.2",
  },
  {
    id: "SIM-20260822-2318",
    timestamp: "22 Aug 2026, 23:18",
    intersection: "Simpang 3",
    trafficLevel: "Low",
    vehicleCount: 148,
    queueLength: 11,
    avgSpeed: 41,
    waitingTime: 28,
    decision: "Reduce Green",
    decisionDescription:
      "Reduce green duration because traffic demand is currently low.",
    currentGreen: 45,
    recommendedGreen: 32,
    improvement: 7.4,
    queueReduction: 9,
    waitingReduction: 13,
    throughputIncrease: 5,
    status: "Completed",
    simulationDuration: 24,
    confidence: 87,
    forecast: "Low traffic condition expected to continue.",
    model: "PPO v1.0 + LSTM v1.2",
  },
  {
    id: "SIM-20260822-2242",
    timestamp: "22 Aug 2026, 22:42",
    intersection: "Simpang 2",
    trafficLevel: "High",
    vehicleCount: 462,
    queueLength: 44,
    avgSpeed: 23,
    waitingTime: 91,
    decision: "Emergency Adjustment",
    decisionDescription:
      "Rapid signal adjustment triggered by sudden queue growth.",
    currentGreen: 30,
    recommendedGreen: 50,
    improvement: 18.6,
    queueReduction: 31,
    waitingReduction: 29,
    throughputIncrease: 18,
    status: "Completed",
    simulationDuration: 52,
    confidence: 97,
    forecast: "Rapid congestion growth detected.",
    model: "PPO v1.0 + LSTM v1.2",
  },
  {
    id: "SIM-20260822-2145",
    timestamp: "22 Aug 2026, 21:45",
    intersection: "Simpang 1",
    trafficLevel: "Medium",
    vehicleCount: 302,
    queueLength: 27,
    avgSpeed: 31,
    waitingTime: 58,
    decision: "Extend Green",
    decisionDescription:
      "Increase green duration to handle growing traffic demand.",
    currentGreen: 35,
    recommendedGreen: 42,
    improvement: 9.3,
    queueReduction: 15,
    waitingReduction: 18,
    throughputIncrease: 9,
    status: "Completed",
    simulationDuration: 33,
    confidence: 91,
    forecast: "Traffic volume is expected to increase.",
    model: "PPO v1.0 + LSTM v1.2",
  },
  {
    id: "SIM-20260822-2059",
    timestamp: "22 Aug 2026, 20:59",
    intersection: "Simpang 4 Pingit",
    trafficLevel: "High",
    vehicleCount: 491,
    queueLength: 46,
    avgSpeed: 22,
    waitingTime: 93,
    decision: "Phase Shift",
    decisionDescription:
      "Change signal phase order to prioritize the longest queue.",
    currentGreen: 35,
    recommendedGreen: 48,
    improvement: 14.8,
    queueReduction: 23,
    waitingReduction: 26,
    throughputIncrease: 14,
    status: "Failed",
    simulationDuration: 19,
    confidence: 92,
    forecast: "High congestion expected.",
    model: "PPO v1.0 + LSTM v1.2",
  },
];

export default function HistoryPage() {
  const [search, setSearch] = useState("");
  const [intersection, setIntersection] = useState("All Intersections");
  const [status, setStatus] = useState("All Status");
  const [traffic, setTraffic] = useState("All Traffic");
  const [selectedRecord, setSelectedRecord] =
    useState<HistoryRecord | null>(null);

  const filteredData = useMemo(() => {
    return HISTORY_DATA.filter((item) => {
      const searchMatch =
        item.id.toLowerCase().includes(search.toLowerCase()) ||
        item.intersection.toLowerCase().includes(search.toLowerCase()) ||
        item.decision.toLowerCase().includes(search.toLowerCase());

      const intersectionMatch =
        intersection === "All Intersections" ||
        item.intersection === intersection;

      const statusMatch =
        status === "All Status" || item.status === status;

      const trafficMatch =
        traffic === "All Traffic" || item.trafficLevel === traffic;

      return (
        searchMatch &&
        intersectionMatch &&
        statusMatch &&
        trafficMatch
      );
    });
  }, [search, intersection, status, traffic]);

  const completed = HISTORY_DATA.filter(
    (item) => item.status === "Completed"
  );

  const averageImprovement =
    completed.reduce((sum, item) => sum + item.improvement, 0) /
    completed.length;

  const averageQueueReduction =
    completed.reduce((sum, item) => sum + item.queueReduction, 0) /
    completed.length;

  return (
    <div className="flex min-h-screen bg-bg text-text">
      <Sidebar />

      <main className="min-w-0 flex-1 px-6 py-6">
        <div className="mx-auto max-w-[1600px] space-y-6">
        {/* HEADER */}
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <HistoryIcon className="h-6 w-6 text-text" />

              <h1 className="text-2xl font-bold tracking-tight">
                History
              </h1>
            </div>

            <p className="text-sm text-text-muted">
              Riwayat simulasi dan pengambilan keputusan Digital Twin.
            </p>
          </div>

          <button
            type="button"
            className="flex h-10 items-center justify-center gap-2 rounded-xl border border-border bg-surface px-4 text-sm font-medium text-text shadow-sm transition hover:bg-bg"
          >
            <CalendarDays className="h-4 w-4" />
            Last 24 Hours
            <ChevronDown className="h-4 w-4" />
          </button>
        </div>

        {/* SUMMARY CARDS */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <SummaryCard
            title="Total Simulations"
            value={HISTORY_DATA.length.toString()}
            subtitle="Recorded simulations"
            icon={<Activity className="h-5 w-5" />}
          />

          <SummaryCard
            title="AI Decisions"
            value={completed.length.toString()}
            subtitle="Successful decisions"
            icon={<Brain className="h-5 w-5" />}
          />

          <SummaryCard
            title="Avg. Improvement"
            value={`+${averageImprovement.toFixed(1)}%`}
            subtitle="Overall performance"
            icon={<TrendingUp className="h-5 w-5" />}
            positive
          />

          <SummaryCard
            title="Queue Reduction"
            value={`${averageQueueReduction.toFixed(1)}%`}
            subtitle="Average reduction"
            icon={<TrendingDown className="h-5 w-5" />}
            positive
          />
        </div>

        {/* FILTER */}
        <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-text-muted" />

            <h2 className="text-sm font-semibold">
              Filter History
            </h2>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
            {/* SEARCH */}
            <div className="relative xl:col-span-2">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />

              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search simulation, intersection..."
                className="h-10 w-full rounded-xl border border-border bg-bg pl-10 pr-3 text-sm outline-none transition placeholder:text-text-muted focus:border-slate-400 focus:bg-surface"
              />
            </div>

            <SelectFilter
              value={intersection}
              onChange={setIntersection}
              options={[
                "All Intersections",
                "Simpang 1",
                "Simpang 2",
                "Simpang 3",
                "Simpang 4 Pingit",
              ]}
            />

            <SelectFilter
              value={traffic}
              onChange={setTraffic}
              options={[
                "All Traffic",
                "Low",
                "Medium",
                "High",
              ]}
            />

            <SelectFilter
              value={status}
              onChange={setStatus}
              options={[
                "All Status",
                "Completed",
                "Running",
                "Failed",
                "Cancelled",
              ]}
            />
          </div>
        </div>

        {/* TABLE */}
        <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-sm">
          <div className="flex flex-col gap-3 border-b border-border px-5 py-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="font-semibold">
                Simulation History
              </h2>

              <p className="mt-1 text-xs text-text-muted">
                Showing {filteredData.length} of {HISTORY_DATA.length} records
              </p>
            </div>

            <button
              type="button"
              className="flex h-9 items-center gap-2 self-start rounded-lg border border-border px-3 text-xs font-medium text-text-secondary hover:bg-bg"
            >
              <Filter className="h-3.5 w-3.5" />
              Advanced Filter
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[1100px]">
              <thead>
                <tr className="border-b border-border bg-bg text-left">
                  <th className="px-5 py-3 text-xs font-semibold text-text-muted">
                    Time
                  </th>

                  <th className="px-5 py-3 text-xs font-semibold text-text-muted">
                    Intersection
                  </th>

                  <th className="px-5 py-3 text-xs font-semibold text-text-muted">
                    Traffic
                  </th>

                  <th className="px-5 py-3 text-xs font-semibold text-text-muted">
                    AI Decision
                  </th>

                  <th className="px-5 py-3 text-xs font-semibold text-text-muted">
                    Signal
                  </th>

                  <th className="px-5 py-3 text-xs font-semibold text-text-muted">
                    Result
                  </th>

                  <th className="px-5 py-3 text-xs font-semibold text-text-muted">
                    Improvement
                  </th>

                  <th className="px-5 py-3 text-xs font-semibold text-text-muted">
                    Status
                  </th>

                  <th className="px-5 py-3 text-right text-xs font-semibold text-text-muted">
                    Action
                  </th>
                </tr>
              </thead>

              <tbody>
                {filteredData.map((item) => (
                  <HistoryRow
                    key={item.id}
                    item={item}
                    onView={() => setSelectedRecord(item)}
                  />
                ))}
              </tbody>
            </table>

            {filteredData.length === 0 && (
              <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
                <Search className="mb-3 h-8 w-8 text-text-muted/50" />

                <h3 className="font-semibold text-text">
                  No history found
                </h3>

                <p className="mt-1 text-sm text-text-muted">
                  Coba ubah kata pencarian atau filter.
                </p>
              </div>
            )}
          </div>
        </div>
        </div>

        {/* DETAIL MODAL */}
        {selectedRecord && (
          <HistoryDetailModal
            record={selectedRecord}
            onClose={() => setSelectedRecord(null)}
          />
        )}
      </main>
    </div>
  );
}

/* =========================================================
   SUMMARY CARD
========================================================= */

interface SummaryCardProps {
  title: string;
  value: string;
  subtitle: string;
  icon: React.ReactNode;
  positive?: boolean;
}

function SummaryCard({
  title,
  value,
  subtitle,
  icon,
  positive,
}: SummaryCardProps) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-text-muted">
            {title}
          </p>

          <p className="mt-2 text-2xl font-bold tracking-tight">
            {value}
          </p>

          <p
            className={`mt-1 text-xs ${
              positive ? "text-emerald-600" : "text-text-muted"
            }`}
          >
            {subtitle}
          </p>
        </div>

        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-bg text-text-secondary">
          {icon}
        </div>
      </div>
    </div>
  );
}

/* =========================================================
   SELECT FILTER
========================================================= */

interface SelectFilterProps {
  value: string;
  onChange: (value: string) => void;
  options: string[];
}

function SelectFilter({
  value,
  onChange,
  options,
}: SelectFilterProps) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 w-full appearance-none rounded-xl border border-border bg-bg px-3 pr-9 text-sm text-text-secondary outline-none transition focus:border-slate-400 focus:bg-surface"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>

      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
    </div>
  );
}

/* =========================================================
   HISTORY ROW
========================================================= */

interface HistoryRowProps {
  item: HistoryRecord;
  onView: () => void;
}

function HistoryRow({ item, onView }: HistoryRowProps) {
  return (
    <tr className="border-b border-border transition hover:bg-bg">
      <td className="px-5 py-4">
        <div className="flex items-center gap-2">
          <Clock3 className="h-4 w-4 text-text-muted" />

          <div>
            <p className="whitespace-nowrap text-sm font-medium text-text">
              {item.timestamp}
            </p>

            <p className="mt-0.5 font-mono text-[10px] text-text-muted">
              {item.id}
            </p>
          </div>
        </div>
      </td>

      <td className="px-5 py-4">
        <div className="flex items-center gap-2">
          <TrafficCone className="h-4 w-4 text-text-muted" />

          <span className="whitespace-nowrap text-sm font-medium text-text">
            {item.intersection}
          </span>
        </div>
      </td>

      <td className="px-5 py-4">
        <TrafficBadge level={item.trafficLevel} />
      </td>

      <td className="px-5 py-4">
        <div>
          <p className="whitespace-nowrap text-sm font-semibold text-text">
            {item.decision}
          </p>

          <p className="mt-1 max-w-[220px] truncate text-xs text-text-muted">
            {item.decisionDescription}
          </p>
        </div>
      </td>

      <td className="px-5 py-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">
            {item.currentGreen}s
          </span>

          <ArrowUp className="h-3.5 w-3.5 text-text-muted" />

          <span className="text-sm font-semibold text-text">
            {item.recommendedGreen}s
          </span>
        </div>
      </td>

      <td className="px-5 py-4">
        <div>
          <p className="text-sm font-semibold text-text">
            Queue ↓ {item.queueReduction}%
          </p>

          <p className="mt-1 text-xs text-text-muted">
            Wait ↓ {item.waitingReduction}%
          </p>
        </div>
      </td>

      <td className="px-5 py-4">
        <div className="flex items-center gap-1.5">
          <TrendingUp className="h-4 w-4 text-emerald-500" />

          <span className="text-sm font-bold text-emerald-600">
            +{item.improvement}%
          </span>
        </div>
      </td>

      <td className="px-5 py-4">
        <StatusBadge status={item.status} />
      </td>

      <td className="px-5 py-4 text-right">
        <button
          type="button"
          onClick={onView}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border px-3 text-xs font-semibold text-text-secondary transition hover:bg-bg"
        >
          <Eye className="h-3.5 w-3.5" />
          View
        </button>
      </td>
    </tr>
  );
}

/* =========================================================
   TRAFFIC BADGE
========================================================= */

function TrafficBadge({
  level,
}: {
  level: TrafficLevel;
}) {
  const styles = {
    Low: "bg-bg text-text-secondary",
    Medium: "bg-amber-50 text-amber-700",
    High: "bg-red-50 text-red-600",
  };

  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ${styles[level]}`}
    >
      {level}
    </span>
  );
}

/* =========================================================
   STATUS BADGE
========================================================= */

function StatusBadge({
  status,
}: {
  status: SimulationStatus;
}) {
  if (status === "Completed") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-600">
        <CheckCircle2 className="h-3 w-3" />
        Completed
      </span>
    );
  }

  if (status === "Running") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-600">
        <Activity className="h-3 w-3" />
        Running
      </span>
    );
  }

  if (status === "Failed") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-2.5 py-1 text-[11px] font-semibold text-red-600">
        <XCircle className="h-3 w-3" />
        Failed
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-bg px-2.5 py-1 text-[11px] font-semibold text-text-muted">
      <AlertCircle className="h-3 w-3" />
      Cancelled
    </span>
  );
}

/* =========================================================
   DETAIL MODAL
========================================================= */

interface HistoryDetailModalProps {
  record: HistoryRecord;
  onClose: () => void;
}

function HistoryDetailModal({
  record,
  onClose,
}: HistoryDetailModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm">
      <div className="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl">
        {/* MODAL HEADER */}
        <div className="flex items-start justify-between border-b border-border px-6 py-5">
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-bg">
                <HistoryIcon className="h-5 w-5 text-text-secondary" />
              </div>

              <div>
                <h2 className="text-lg font-bold">
                  Simulation Details
                </h2>

                <p className="mt-0.5 font-mono text-xs text-text-muted">
                  {record.id}
                </p>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-text-muted transition hover:bg-bg hover:text-text"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* MODAL BODY */}
        <div className="overflow-y-auto p-6">
          <div className="space-y-6">
            {/* OVERVIEW */}
            <section>
              <SectionTitle
                icon={<Server className="h-4 w-4" />}
                title="Simulation Overview"
              />

              <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
                <InfoBox
                  label="Intersection"
                  value={record.intersection}
                />

                <InfoBox
                  label="Timestamp"
                  value={record.timestamp}
                />

                <InfoBox
                  label="Duration"
                  value={`${record.simulationDuration}s`}
                />

                <InfoBox
                  label="Model"
                  value={record.model}
                />
              </div>
            </section>

            {/* TRAFFIC STATE */}
            <section>
              <SectionTitle
                icon={<Activity className="h-4 w-4" />}
                title="Traffic State Before Decision"
              />

              <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
                <MetricBox
                  label="Vehicles"
                  value={record.vehicleCount.toString()}
                  suffix="vehicles"
                  icon={<TrafficCone className="h-4 w-4" />}
                />

                <MetricBox
                  label="Queue Length"
                  value={record.queueLength.toString()}
                  suffix="vehicles"
                  icon={<Activity className="h-4 w-4" />}
                />

                <MetricBox
                  label="Average Speed"
                  value={record.avgSpeed.toString()}
                  suffix="km/h"
                  icon={<Gauge className="h-4 w-4" />}
                />

                <MetricBox
                  label="Waiting Time"
                  value={record.waitingTime.toString()}
                  suffix="seconds"
                  icon={<Timer className="h-4 w-4" />}
                />
              </div>
            </section>

            {/* DECISION */}
            <section>
              <SectionTitle
                icon={<Brain className="h-4 w-4" />}
                title="AI Decision"
              />

              <div className="mt-3 rounded-xl border border-border bg-bg p-5">
                <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wider text-text-muted">
                      Recommended Action
                    </p>

                    <h3 className="mt-1 text-xl font-bold text-slate-800">
                      {record.decision}
                    </h3>

                    <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">
                      {record.decisionDescription}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-3">
                    <Sparkles className="h-4 w-4 text-text-muted" />

                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-text-muted">
                        Confidence
                      </p>

                      <p className="text-sm font-bold">
                        {record.confidence}%
                      </p>
                    </div>
                  </div>
                </div>

                <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
                  <SignalCard
                    label="Current Green"
                    value={`${record.currentGreen}s`}
                  />

                  <SignalCard
                    label="Recommended Green"
                    value={`${record.recommendedGreen}s`}
                    highlight
                  />

                  <SignalCard
                    label="Change"
                    value={`${
                      record.recommendedGreen -
                      record.currentGreen >
                      0
                        ? "+"
                        : ""
                    }${
                      record.recommendedGreen -
                      record.currentGreen
                    }s`}
                  />
                </div>
              </div>
            </section>

            {/* FORECAST */}
            <section>
              <SectionTitle
                icon={<Sparkles className="h-4 w-4" />}
                title="Forecast"
              />

              <div className="mt-3 rounded-xl border border-border bg-surface p-4">
                <p className="text-sm text-text-secondary">
                  {record.forecast}
                </p>

                <div className="mt-3 flex items-center gap-2 text-xs text-text-muted">
                  <Brain className="h-3.5 w-3.5" />
                  LSTM Forecast Model
                </div>
              </div>
            </section>

            {/* RESULTS */}
            <section>
              <SectionTitle
                icon={<TrendingUp className="h-4 w-4" />}
                title="Simulation Result"
              />

              <div className="mt-3 overflow-hidden rounded-xl border border-border">
                <table className="w-full">
                  <thead>
                    <tr className="bg-bg text-left">
                      <th className="px-4 py-3 text-xs font-semibold text-text-muted">
                        Metric
                      </th>

                      <th className="px-4 py-3 text-xs font-semibold text-text-muted">
                        Before
                      </th>

                      <th className="px-4 py-3 text-xs font-semibold text-text-muted">
                        After
                      </th>

                      <th className="px-4 py-3 text-xs font-semibold text-text-muted">
                        Change
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    <ComparisonRow
                      label="Queue Length"
                      before={`${record.queueLength} vehicles`}
                      after={`${Math.round(
                        record.queueLength *
                          (1 - record.queueReduction / 100)
                      )} vehicles`}
                      change={`-${record.queueReduction}%`}
                    />

                    <ComparisonRow
                      label="Waiting Time"
                      before={`${record.waitingTime}s`}
                      after={`${Math.round(
                        record.waitingTime *
                          (1 - record.waitingReduction / 100)
                      )}s`}
                      change={`-${record.waitingReduction}%`}
                    />

                    <ComparisonRow
                      label="Throughput"
                      before="420 veh/h"
                      after={`${Math.round(
                        420 *
                          (1 +
                            record.throughputIncrease / 100)
                      )} veh/h`}
                      change={`+${record.throughputIncrease}%`}
                    />

                    <ComparisonRow
                      label="Overall Performance"
                      before="Baseline"
                      after="Optimized"
                      change={`+${record.improvement}%`}
                    />
                  </tbody>
                </table>
              </div>
            </section>

            {/* DECISION PIPELINE */}
            <section>
              <SectionTitle
                icon={<Activity className="h-4 w-4" />}
                title="Decision Pipeline"
              />

              <div className="mt-4 flex flex-col md:flex-row md:items-center">
                <PipelineStep
                  number="01"
                  title="Traffic Data"
                  description="CV Detection"
                />

                <PipelineConnector />

                <PipelineStep
                  number="02"
                  title="Forecast"
                  description="LSTM"
                />

                <PipelineConnector />

                <PipelineStep
                  number="03"
                  title="AI Decision"
                  description="PPO"
                />

                <PipelineConnector />

                <PipelineStep
                  number="04"
                  title="Simulation"
                  description="SUMO"
                />

                <PipelineConnector />

                <PipelineStep
                  number="05"
                  title="Result"
                  description="Metrics"
                />
              </div>
            </section>
          </div>
        </div>

        {/* MODAL FOOTER */}
        <div className="flex items-center justify-between border-t border-border bg-bg px-6 py-4">
          <StatusBadge status={record.status} />

          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

/* =========================================================
   SECTION TITLE
========================================================= */

function SectionTitle({
  icon,
  title,
}: {
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <div className="text-text-muted">{icon}</div>

      <h3 className="text-sm font-bold text-slate-800">
        {title}
      </h3>
    </div>
  );
}

/* =========================================================
   INFO BOX
========================================================= */

function InfoBox({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-bg p-4">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
        {label}
      </p>

      <p className="mt-1 text-sm font-semibold text-text">
        {value}
      </p>
    </div>
  );
}

/* =========================================================
   METRIC BOX
========================================================= */

function MetricBox({
  label,
  value,
  suffix,
  icon,
}: {
  label: string;
  value: string;
  suffix: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center gap-2 text-text-muted">
        {icon}

        <span className="text-xs font-medium">
          {label}
        </span>
      </div>

      <div className="mt-3 flex items-end gap-1.5">
        <span className="text-xl font-bold">
          {value}
        </span>

        <span className="mb-0.5 text-xs text-text-muted">
          {suffix}
        </span>
      </div>
    </div>
  );
}

/* =========================================================
   SIGNAL CARD
========================================================= */

function SignalCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-4 ${
        highlight
          ? "border-slate-300 bg-surface"
          : "border-border bg-surface"
      }`}
    >
      <p className="text-xs text-text-muted">
        {label}
      </p>

      <p
        className={`mt-1 text-lg font-bold ${
          highlight
            ? "text-text"
            : "text-text"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

/* =========================================================
   COMPARISON ROW
========================================================= */

function ComparisonRow({
  label,
  before,
  after,
  change,
}: {
  label: string;
  before: string;
  after: string;
  change: string;
}) {
  return (
    <tr className="border-t border-border">
      <td className="px-4 py-3 text-sm font-medium text-text">
        {label}
      </td>

      <td className="px-4 py-3 text-sm text-text-muted">
        {before}
      </td>

      <td className="px-4 py-3 text-sm font-semibold text-text">
        {after}
      </td>

      <td className="px-4 py-3">
        <span className="inline-flex items-center gap-1 text-xs font-bold text-emerald-600">
          <ArrowDown className="h-3 w-3" />
          {change.replace("-", "")}
        </span>
      </td>
    </tr>
  );
}

/* =========================================================
   PIPELINE
========================================================= */

function PipelineStep({
  number,
  title,
  description,
}: {
  number: string;
  title: string;
  description: string;
}) {
  return (
    <div className="flex items-center gap-3 md:flex-1 md:flex-col md:gap-2">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white">
        {number}
      </div>

      <div className="md:text-center">
        <p className="text-xs font-bold text-text">
          {title}
        </p>

        <p className="mt-0.5 text-[10px] text-text-muted">
          {description}
        </p>
      </div>
    </div>
  );
}

function PipelineConnector() {
  return (
    <div className="ml-5 h-6 w-px bg-slate-200 md:ml-0 md:h-px md:w-full" />
  );
}