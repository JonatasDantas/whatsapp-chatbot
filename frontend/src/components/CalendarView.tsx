import type { Reservation } from '@/lib/types'

interface Props {
  reservations: Reservation[]
  year: number
  month: number // 0-indexed
  onPrev: () => void
  onNext: () => void
}

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate()
}

function getFirstDayOfWeek(year: number, month: number) {
  return new Date(year, month, 1).getDay()
}

function isDateInReservation(date: string, res: Reservation) {
  return date >= res.checkin && date <= res.checkout
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December']

export default function CalendarView({ reservations, year, month, onPrev, onNext }: Props) {
  const daysInMonth = getDaysInMonth(year, month)
  const firstDay = getFirstDayOfWeek(year, month)

  const cells: (number | null)[] = [...Array(firstDay).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)]

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <button onClick={onPrev} className="text-gray-500 hover:text-gray-900 px-2">‹</button>
        <h2 className="font-semibold text-lg">{MONTHS[month]} {year}</h2>
        <button onClick={onNext} className="text-gray-500 hover:text-gray-900 px-2">›</button>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-gray-400 mb-2">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => <div key={d}>{d}</div>)}
      </div>

      <div className="grid grid-cols-7 gap-1">
        {cells.map((day, idx) => {
          if (!day) return <div key={idx} />
          const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
          const activeReservations = reservations.filter(r => isDateInReservation(dateStr, r))
          const isToday = dateStr === new Date().toISOString().slice(0, 10)

          return (
            <div
              key={idx}
              title={activeReservations.map(r => `${r.guest_name} (${r.guests} guests)`).join('\n')}
              className={`rounded p-1 text-sm text-center min-h-[40px] flex flex-col items-center justify-start cursor-default
                ${isToday ? 'bg-blue-50 font-bold border border-blue-300' : ''}
                ${activeReservations.length > 0 ? 'bg-green-50 border border-green-200' : ''}
              `}
            >
              <span>{day}</span>
              {activeReservations.length > 0 && (
                <span className="text-xs text-green-700 truncate w-full text-center">
                  {activeReservations[0].guest_name}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
