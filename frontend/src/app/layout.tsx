'use client'
import './globals.css'
import { configureAmplify } from '@/lib/auth'

configureAmplify()

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="bg-gray-50 text-gray-900 min-h-screen">
        {children}
      </body>
    </html>
  )
}
