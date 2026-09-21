import type { Message } from '@/lib/types'

interface Props {
  messages: Message[]
}

export default function ChatView({ messages }: Props) {
  if (messages.length === 0) {
    return <div className="text-center py-8 text-gray-400">No messages yet.</div>
  }

  return (
    <div className="flex flex-col gap-3 p-4 overflow-y-auto max-h-[60vh]">
      {messages.map((m, i) => (
        <div
          key={i}
          className={`flex ${m.role === 'user' ? 'justify-start' : 'justify-end'}`}
        >
          <div
            className={`max-w-xs lg:max-w-md px-4 py-2 rounded-2xl text-sm shadow-sm ${
              m.role === 'user'
                ? 'bg-white text-gray-900 border border-gray-200'
                : 'bg-blue-600 text-white'
            }`}
          >
            <p>{m.message}</p>
            <p className={`text-xs mt-1 ${m.role === 'user' ? 'text-gray-400' : 'text-blue-200'}`}>
              {new Date(m.timestamp).toLocaleTimeString('pt-BR')}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}
