"use client";

import { PieChart, Pie, Cell } from "recharts";

export type DonutSegment = { value: number; color: string };

export default function DonutRing({
  segments,
  size = 64,
  thickness = 8,
}: {
  segments: DonutSegment[];
  size?: number;
  thickness?: number;
}) {
  const outerRadius = size / 2;
  const innerRadius = Math.max(outerRadius - thickness, 4);

  return (
    <PieChart width={size} height={size}>
      <Pie
        data={segments}
        dataKey="value"
        cx="50%"
        cy="50%"
        innerRadius={innerRadius}
        outerRadius={outerRadius}
        startAngle={90}
        endAngle={-270}
        stroke="none"
        isAnimationActive={false}
      >
        {segments.map((s, i) => (
          <Cell key={i} fill={s.color} />
        ))}
      </Pie>
    </PieChart>
  );
}
