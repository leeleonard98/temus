import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts"

import type { AllocationSlice } from "@/lib/portfolio-api"

type Props = {
  allocation: AllocationSlice[]
}

// Three-color palette so the chart stays readable; remaining slices fall back
// to a muted neutral.
const COLORS: Record<string, string> = {
  equity: "#10b981", // emerald-500
  bond: "#6366f1", // indigo-500
  cash: "#f59e0b", // amber-500
  crypto: "#ef4444", // red-500
  alt: "#a855f7", // purple-500
}

const FALLBACK = "#94a3b8" // slate-400

/**
 * Donut chart of asset-class weights.
 *
 * Receives normalized weights (sum ≈ 1) from the portfolio endpoint and
 * renders a recharts donut. Three primary colors per the spec; we keep five
 * mapped so adding crypto/alt later doesn't break.
 */
export function AllocationChart({ allocation }: Props) {
  if (allocation.length === 0) {
    return (
      <div
        data-testid="allocation-empty"
        className="flex h-40 items-center justify-center text-sm text-muted-foreground"
      >
        No positions yet — your allocation chart will appear here.
      </div>
    )
  }

  const data = allocation.map((a) => ({
    name: a.asset_class,
    value: Math.round(a.weight * 1000) / 10, // % with one decimal
    fill: COLORS[a.asset_class] ?? FALLBACK,
  }))

  return (
    <div data-testid="allocation-chart" className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius={45}
            outerRadius={80}
            paddingAngle={2}
            stroke="none"
          >
            {data.map((d) => (
              <Cell key={d.name} fill={d.fill} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value, name) => [`${value as number}%`, String(name)] as [string, string]}
          />
        </PieChart>
      </ResponsiveContainer>
      <ul className="mt-2 flex flex-wrap justify-center gap-3 text-xs text-muted-foreground">
        {data.map((d) => (
          <li key={d.name} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-sm" style={{ backgroundColor: d.fill }} />
            <span className="capitalize">{d.name}</span>
            <span className="font-medium text-foreground">{d.value}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
