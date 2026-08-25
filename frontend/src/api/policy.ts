import type {
  EventResponse,
  PolicyResponse,
  PolicyRuleInput,
} from './generated'
import { apiRequest } from './request'

export function getPolicies(signal?: AbortSignal): Promise<PolicyResponse> {
  return apiRequest<PolicyResponse>('/api/v1/policies', { signal })
}

export function replacePolicies(
  expectedRevision: number,
  rules: PolicyRuleInput[],
): Promise<PolicyResponse> {
  return apiRequest<PolicyResponse>('/api/v1/policies', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expected_revision: expectedRevision, rules }),
  })
}

export function getEvents(signal?: AbortSignal): Promise<EventResponse> {
  return apiRequest<EventResponse>('/api/v1/events', { signal })
}
