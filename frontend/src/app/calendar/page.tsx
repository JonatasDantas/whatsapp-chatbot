'use client'
import { useEffect, useState } from 'react'
import useSWR from 'swr'
import { useRouter } from 'next/navigation'
import { getCurrentUser } from 'aws-amplify/auth'
import CalendarView from '@/components/CalendarView'
import type { Reservation } from '@/lib/types'
import { fetcher } from '@/lib/api'

export default function CalendarPage() {
  const router = useRouter()
  const [authChecked, setAuthChecked] = useState(false)
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth())

  useEffect(() => {
    getCurrentUser()
      .then(() => setAuthChecked(true))
      .catch(() => router.push('/login'))
  }, [router])

  const { data, isLoading } = useSWR<{ reservations: Reservation[] }>(
    authChecked ? '/api/reservations' : null,
    (url: string) => fetcher(url)
  )

  function prevMonth() {
    if (month === 0) { setMonth(11); setYear(y => y - 1) }
    else setMonth(m => m - 1)
  }

  function nextMonth() {
    if (month === 11) { setMonth(0); setYear(y => y + 1) }
    else setMonth(m => m + 1)
  }

  if (!authChecked || isLoading) {
    return <div className="flex min-h-screen items-center justify-center text-gray-500">Loading...</div>
  }

  const reservations = data?.reservations ?? []

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-3 flex items-center gap-4 shadow-sm">
        <a href="/" className="text-sm text-blue-600 hover:underline">← Dashboard</a>
        <h1 className="text-lg font-semibold">Calendar</h1>
      </nav>

      <main className="max-w-4xl mx-auto px-6 py-8">
        <CalendarView
          reservations={reservations}
          year={year}
          month={month}
          onPrev={prevMonth}
          onNext={nextMonth}
        />

        <section className="mt-6 bg-white rounded-lg shadow p-4">
          <h2 className="font-semibold mb-3">Upcoming Reservations</h2>
          {reservations.length === 0 ? (
            <p className="text-gray-400 text-sm">No reservations.</p>
          ) : (
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 text-xs uppercase border-b">
                  <th className="pb-2 pr-4">Guest</th>
                  <th className="pb-2 pr-4">Check-in</th>
                  <th className="pb-2 pr-4">Check-out</th>
                  <th className="pb-2 pr-4">Guests</th>
                  <th className="pb-2">Price</th>
                </tr>
              </thead>
              <tbody>
                {reservations.map(r => (
                  <tr key={r.reservation_id} className="border-b last:border-0">
                    <td className="py-2 pr-4 font-medium">{r.guest_name}</td>
                    <td className="py-2 pr-4">{r.checkin}</td>
                    <td className="py-2 pr-4">{r.checkout}</td>
                    <td className="py-2 pr-4">{r.guests}</td>
                    <td className="py-2">R$ {r.price.toLocaleString('pt-BR')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </main>
    </div>
  )
}
