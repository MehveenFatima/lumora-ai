import { Navbar } from '@/components/landing/navbar'
import { Hero } from '@/components/landing/hero'
import { TrustedBy } from '@/components/landing/trusted-by'
import { Features } from '@/components/landing/features'
import { Why } from '@/components/landing/why'
import { HowItWorks } from '@/components/landing/how-it-works'
import { Technology } from '@/components/landing/technology'
import { Testimonials } from '@/components/landing/testimonials'
import { CTA } from '@/components/landing/cta'
import { Footer } from '@/components/landing/footer'

export default function LandingPage() {
  return (
    <div className="min-h-dvh bg-background">
      <Navbar />
      <main>
        <Hero />
        <TrustedBy />
        <Features />
        <Why />
        <HowItWorks />
        <Technology />
        <Testimonials />
        <CTA />
      </main>
      <Footer />
    </div>
  )
}
