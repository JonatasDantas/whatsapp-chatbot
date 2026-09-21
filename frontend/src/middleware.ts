import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Middleware runs on the edge; Amplify session is client-side.
// We protect routes client-side in components instead.
// This file exports a no-op matcher to satisfy Next.js.
export function middleware(_request: NextRequest) {
  return NextResponse.next()
}

export const config = {
  matcher: [],
}
