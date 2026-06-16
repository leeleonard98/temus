import "@testing-library/jest-dom/vitest"
import { afterEach } from "vitest"
import { cleanup } from "@testing-library/react"

afterEach(() => {
  cleanup()
  // Reset localStorage between tests so chat user/session state doesn't leak.
  if (typeof localStorage !== "undefined") {
    localStorage.clear()
  }
})
