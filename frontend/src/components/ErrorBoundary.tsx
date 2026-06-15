import { Component, type ErrorInfo, type ReactNode } from "react"

type Props = { children: ReactNode; fallback?: (error: Error) => ReactNode }
type State = { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface to the console for the interview demo; don't leak elsewhere.
    console.error("[ErrorBoundary]", error, info)
  }

  reset = () => this.setState({ error: null })

  render() {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback(this.state.error)
      return (
        <div className="rounded-md border border-destructive/50 bg-destructive/5 p-3 text-sm text-destructive">
          <div className="font-medium">Something went wrong.</div>
          <div className="mt-1 text-destructive/80">{this.state.error.message}</div>
          <button
            type="button"
            onClick={this.reset}
            className="mt-2 text-xs underline underline-offset-2"
          >
            try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
