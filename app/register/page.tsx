import type { Metadata } from 'next'
import { AuthShell } from '@/components/auth/auth-shell'
import { RegisterForm } from '@/components/auth/register-form'

export const metadata: Metadata = {
  title: 'Create account — LumoraAI',
  description: 'Create your free LumoraAI account and start learning smarter.',
}

export default function RegisterPage() {
  return (
    <AuthShell>
      <RegisterForm />
    </AuthShell>
  )
}
