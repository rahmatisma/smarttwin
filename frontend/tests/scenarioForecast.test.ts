import assert from "node:assert/strict";
import test from "node:test";
import { isScenarioForecastForState, type ScenarioForecastResponse } from "../src/lib/scenarioForecast.ts";

function projection(): ScenarioForecastResponse {
    return {
        status: "completed", trafficStateId: 42, horizonSeconds: 60,
        intersectionId: "simpang4-pingit", updatedAt: null, winnerId: null, message: null,
        initialPhase: "north", assumptions: [],
        inputTimestamp: "2026-08-15T00:00:00Z", predictionTimestamp: "2026-08-15T00:01:00Z",
        candidates: (["baseline", "aggressive", "balanced"] as const).map(candidateId => ({
            candidateId,
            phases: [], cycleLengthSeconds: 60, totalCycleSeconds: 76, busiestApproach: null,
            avgDelaySeconds: 10, avgQueueLengthM: 20, queueLengthVeh: 9, throughputVeh: 0, los: "B", isWinner: false,
            evaluation: { id: "test", trafficTimestamp: "2026-08-15T00:00:00Z", seed: 42,
                demandHash: "same", targetVehicles: 20, evaluatedAt: "2026-08-15T00:00:00Z",
                trafficStateId: 42, durationSeconds: 60, completedSteps: 60, demandSource: "traffic-state-snapshot" },
            finalQueueLengthVehByApproach: { north: 0, east: 2, south: 3, west: 4 },
        })),
    };
}

test("accepts a complete one-minute projection including a measured empty queue", () => {
    assert.equal(isScenarioForecastForState(projection(), 42), true);
});

test("rejects results for an older selection or an ordinary full-cycle evaluation", () => {
    assert.equal(isScenarioForecastForState(projection(), 43), false);
    const result = projection();
    result.candidates[0].evaluation!.durationSeconds = 120;
    assert.equal(isScenarioForecastForState(result, 42), false);
});

test("does not replace a missing terminal queue with a peak queue or zero", () => {
    const result = projection();
    result.candidates[0].queueLengthVehByApproach = { north: 10, east: 2, south: 3, west: 4 };
    delete result.candidates[0].finalQueueLengthVehByApproach!.north;
    assert.equal(isScenarioForecastForState(result, 42), false);
});

test("rejects an unfinished simulation and wrong prediction timestamp", () => {
    const result = projection();
    result.candidates[0].evaluation!.completedSteps = 59;
    assert.equal(isScenarioForecastForState(result, 42), false);
    result.candidates[0].evaluation!.completedSteps = 60;
    result.predictionTimestamp = "2026-08-15T00:02:00Z";
    assert.equal(isScenarioForecastForState(result, 42), false);
});
