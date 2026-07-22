import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "LivePokerOPS",
  description: "Poker Club Operating System",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <nav className="border-b border-gray-800 bg-black/50 backdrop-blur">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-14 items-center">
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold text-green-500">♠️ LivePokerOPS</span>
              </div>
              <div className="flex items-center gap-4 text-sm text-gray-400">
                <span>Club Admin</span>
              </div>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </main>
      </body>
    </html>
  )
}
