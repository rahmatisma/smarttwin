import { Bike, Car, Bus, Truck, Video } from "lucide-react";
import type { VehicleClassCount, VehicleClass } from "@/types/traffic";

type CameraStatus = { label: string; online: boolean };

const ICONS: Record<VehicleClass, React.ReactNode> = {
  motorcycle: <Bike className="h-3.5 w-3.5" />,
  car: <Car className="h-3.5 w-3.5" />,
  bus: <Bus className="h-3.5 w-3.5" />,
  truck: <Truck className="h-3.5 w-3.5" />,
};

const LABELS: Record<VehicleClass, string> = {
  motorcycle: "Motorcycle",
  car: "Car",
  bus: "Bus",
  truck: "Truck",
};

export default function CameraFeedPanel({
  counts,
  cameraStatus,
}: {
  counts: VehicleClassCount[];
  cameraStatus: CameraStatus[];
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold text-text">Camera Feed</h2>
        <span className="text-xs text-text-muted">CAM 01</span>
      </div>

      <div className="flex gap-3">
        <div className="flex aspect-square w-2/5 shrink-0 items-center justify-center rounded-md border border-border bg-surface-2">
          <div className="flex flex-col items-center gap-1.5 px-2 text-center text-text-muted">
            <Video className="h-5 w-5" />
            <span className="text-[10px] leading-tight">Belum tersambung</span>
          </div>
        </div>

        <div className="flex flex-1 flex-col justify-between gap-3">
          <div className="space-y-1">
            {counts.map((c) => (
              <div key={c.vehicleClass} className="flex items-center gap-1.5 text-xs">
                <span className="text-text-secondary">{ICONS[c.vehicleClass]}</span>
                <span className="text-text-secondary">{LABELS[c.vehicleClass]}</span>
                <span className="ml-auto font-mono tabular-nums text-text">{c.count}</span>
              </div>
            ))}
          </div>

          <div className="space-y-1 border-t border-border pt-2">
            {cameraStatus.map((cam) => (
              <div key={cam.label} className="flex items-center gap-1.5 text-[10px]">
                <span className="truncate text-text-secondary">{cam.label}</span>
                <span
                  className={`ml-auto h-1.5 w-1.5 shrink-0 rounded-full ${
                    cam.online ? "bg-signal-green" : "bg-signal-red"
                  }`}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
