import Link from 'next/link'
import type { Conversation } from '@/lib/types'

const STAGE_COLORS: Record<string, string> = {
  greeting: 'bg-gray-100 text-gray-700',
  availability: 'bg-blue-100 text-blue-700',
  qualification: 'bg-yellow-100 text-yellow-700',
  pricing: 'bg-orange-100 text-orange-700',
  owner_takeover: 'bg-red-100 text-red-700',
}

const LEAD_COLORS: Record<string, string> = {
  new: 'bg-gray-100 text-gray-600',
  qualified: 'bg-green-100 text-green-700',
  unqualified: 'bg-red-100 text-red-600',
}

interface Props {
  conversations: Conversation[]
}

export default function ConversationsTable({ conversations }: Props) {
  if (conversations.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        No conversations found.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 bg-white rounded-lg shadow">
        <thead className="bg-gray-50">
          <tr>
            {['Phone', 'Name', 'Stage', 'Lead', 'Check-in', 'Check-out', 'Guests', 'Updated'].map(h => (
              <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                {h}
              </th>
            ))}
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {conversations.map(c => (
            <tr key={c.phone_number} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 text-sm font-mono">{c.phone_number}</td>
              <td className="px-4 py-3 text-sm">{c.name ?? '—'}</td>
              <td className="px-4 py-3">
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${STAGE_COLORS[c.stage] ?? 'bg-gray-100'}`}>
                  {c.stage}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${LEAD_COLORS[c.lead_status] ?? 'bg-gray-100'}`}>
                  {c.lead_status}
                </span>
              </td>
              <td className="px-4 py-3 text-sm">{c.checkin ?? '—'}</td>
              <td className="px-4 py-3 text-sm">{c.checkout ?? '—'}</td>
              <td className="px-4 py-3 text-sm text-center">{c.guests ?? '—'}</td>
              <td className="px-4 py-3 text-xs text-gray-400">
                {new Date(c.updated_at).toLocaleString('pt-BR')}
              </td>
              <td className="px-4 py-3">
                <Link
                  href={`/conversations?phone=${encodeURIComponent(c.phone_number)}`}
                  className="text-blue-600 hover:underline text-sm"
                >
                  View
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
