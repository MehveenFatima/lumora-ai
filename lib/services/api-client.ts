/**
 * Standardized API client module for LumoraAI frontend.
 * Re-exports the authoritative tutorApiClient for consistent usage across services and pages.
 */
import { tutorApiClient, BackendTutorResponse } from '@/lib/api/tutor-api-client'

export { tutorApiClient }
export type { BackendTutorResponse }

export const apiClient = tutorApiClient
export default tutorApiClient
