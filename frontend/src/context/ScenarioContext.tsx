"use client";

import React, { createContext, useContext, useState, ReactNode } from "react";

export type ScenarioType = "Traffic Realtime" | "Baseline" | "Aggressive" | "Balanced";

interface ScenarioContextType {
  scenario: ScenarioType;
  setScenario: (scenario: ScenarioType) => void;
}

const ScenarioContext = createContext<ScenarioContextType | undefined>(undefined);

export function ScenarioProvider({ children }: { children: ReactNode }) {
  const [scenario, setScenario] = useState<ScenarioType>("Traffic Realtime");

  return (
    <ScenarioContext.Provider value={{ scenario, setScenario }}>
      {children}
    </ScenarioContext.Provider>
  );
}

export function useScenario() {
  const context = useContext(ScenarioContext);
  if (!context) {
    return { scenario: "Traffic Realtime" as ScenarioType, setScenario: () => {} };
  }
  return context;
}
