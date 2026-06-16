import { Link, NavLink, Route, BrowserRouter as Router, Routes } from "react-router-dom"
import { useState } from "react"
import { ImageIcon, LayoutDashboard, MessageSquare } from "lucide-react"

import { ChatPanel } from "@/features/chat/ChatPanel"
import { PortfolioDashboard } from "@/features/portfolio/PortfolioDashboard"
import { UploadsPage } from "@/features/uploads/UploadsPage"
import { cn } from "@/lib/utils"

function NavLinks() {
  const linkCls = ({ isActive }: { isActive: boolean }) =>
    cn(
      "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-sm font-medium transition",
      isActive
        ? "bg-foreground text-background"
        : "text-muted-foreground hover:bg-muted",
    )
  return (
    <nav className="flex items-center gap-1">
      <NavLink to="/" className={linkCls} end>
        <MessageSquare className="h-4 w-4" /> Chat
      </NavLink>
      <NavLink to="/portfolio" className={linkCls}>
        <LayoutDashboard className="h-4 w-4" /> Portfolio
      </NavLink>
      <NavLink to="/uploads" className={linkCls}>
        <ImageIcon className="h-4 w-4" /> Uploads
      </NavLink>
    </nav>
  )
}

function PortfolioRoute() {
  // The dashboard publishes a UI snapshot via this state; future iterations
  // can pass it into a chat drawer here to ground AC4 questions.
  const [, setUiContext] = useState<object | null>(null)
  return <PortfolioDashboard onUiContextChange={setUiContext} />
}

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-background text-foreground">
        <header className="border-b">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
            <Link to="/" className="text-xl font-semibold tracking-tight">
              AuraWealth
            </Link>
            <NavLinks />
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-6">
          <Routes>
            <Route path="/" element={<ChatPanel />} />
            <Route path="/portfolio" element={<PortfolioRoute />} />
            <Route path="/uploads" element={<UploadsPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}
