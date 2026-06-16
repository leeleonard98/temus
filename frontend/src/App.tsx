import { ChatPanel } from "@/features/chat/ChatPanel"

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <h1 className="text-xl font-semibold tracking-tight">AuraWealth</h1>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-6">
        <ChatPanel />
      </main>
    </div>
  )
}
