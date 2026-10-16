import { Suspense } from 'react'
import type { Metadata } from 'next'
import { AuthShell } from '@/components/auth/auth-shell'
import { VerifyEmailForm } from '@/components/auth/verify-email-form'

export const metadata: Metadata = {
  title: 'Verify your email — LumoraAI',
  description: 'Enter the 6-digit code we emailed you to activate your LumoraAI account.',
}

export default function VerifyEmailPage() {
  return (
    <AuthShell>
      <Suspense>
        <VerifyEmailForm />
      </Suspense>
    </AuthShell>
  )
}
