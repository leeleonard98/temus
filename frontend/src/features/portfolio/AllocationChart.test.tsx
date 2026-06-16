import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AllocationChart } from "./AllocationChart"

describe("AllocationChart", () => {
  it("renders an empty state when allocation is empty", () => {
    render(<AllocationChart allocation={[]} />)
    expect(screen.getByTestId("allocation-empty")).toBeInTheDocument()
  })

  it("renders a chart container when given allocation data", () => {
    render(
      <AllocationChart
        allocation={[
          { asset_class: "equity", weight: 0.7 },
          { asset_class: "bond", weight: 0.2 },
          { asset_class: "cash", weight: 0.1 },
        ]}
      />,
    )
    expect(screen.getByTestId("allocation-chart")).toBeInTheDocument()
  })
})
