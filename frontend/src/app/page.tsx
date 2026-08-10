import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import StatsRow from "@/components/StatsRow";
import DigitalTwinPanel from "@/components/DigitalTwinPanel";
import CameraFeedPanel from "@/components/CameraFeedPanel";
import SignalStatusPanel from "@/components/SignalStatusPanel";
import RecommendationPanel from "@/components/RecommendationPanel";
import ForecastChart from "@/components/ForecastChart";
import {
  mockApproachStates,
  mockVehicleClassCounts,
  mockSignalStatus,
  mockRecommendation,
  mockForecast,
  mockIntersection,
  mockOccupancyPct,
  mockWeather,
  mockCameraStatus,
} from "@/lib/mockData";

export default function DashboardPage() {
  return (
    <div className="flex min-h-screen bg-bg">
      <Sidebar />

      <div className="flex-1">
        <Header locationName={mockIntersection.name} coords={mockIntersection.coords} />
        <StatsRow
          approaches={mockApproachStates}
          occupancyPct={mockOccupancyPct}
          weather={mockWeather}
        />

        <div className="flex flex-col gap-4 px-6 pb-6">
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr]">
            <DigitalTwinPanel approaches={mockApproachStates} signal={mockSignalStatus} />
            <div className="flex flex-col gap-4">
              <CameraFeedPanel counts={mockVehicleClassCounts} cameraStatus={mockCameraStatus} />
              <SignalStatusPanel signal={mockSignalStatus} />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <RecommendationPanel recommendation={mockRecommendation} />
            <ForecastChart data={mockForecast} />
          </div>
        </div>
      </div>
    </div>
  );
}
