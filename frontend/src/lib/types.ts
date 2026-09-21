export type ConversationStage =
  | 'greeting'
  | 'availability'
  | 'qualification'
  | 'pricing'
  | 'owner_takeover'

export type LeadStatus = 'new' | 'qualified' | 'unqualified'

export interface Conversation {
  phone_number: string
  name: string | null
  stage: ConversationStage
  checkin: string | null
  checkout: string | null
  guests: number | null
  purpose: string | null
  customer_profile: string | null
  rules_accepted: boolean
  price_estimate: number | null
  lead_status: LeadStatus
  owner_notified: boolean
  created_at: string
  updated_at: string
}

export type MessageRole = 'user' | 'assistant'

export interface Message {
  phone_number: string
  timestamp: string
  role: MessageRole
  message: string
  message_type: string
}

export type ReservationStatus = 'confirmed' | 'cancelled'

export interface Reservation {
  reservation_id: string
  phone_number: string
  guest_name: string
  checkin: string
  checkout: string
  guests: number
  price: number
  status: ReservationStatus
  created_at: string
}
