import type {
  AddScenarioOperationRequest,
  CreateScenarioRequest,
  ScenarioComparisonResponse,
  ScenarioListResponse,
} from './generated'
import { apiRequest } from './request'

export function getScenarios(signal?: AbortSignal): Promise<ScenarioListResponse> {
  return apiRequest<ScenarioListResponse>('/api/v1/scenarios', { signal })
}

export function createScenario(payload: CreateScenarioRequest): Promise<ScenarioComparisonResponse> {
  return apiRequest<ScenarioComparisonResponse>('/api/v1/scenarios', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function getScenarioComparison(
  scenarioId: number,
  signal?: AbortSignal,
): Promise<ScenarioComparisonResponse> {
  return apiRequest<ScenarioComparisonResponse>(
    `/api/v1/scenarios/${scenarioId}/comparison`,
    { signal },
  )
}

export function addScenarioOperation(
  scenarioId: number,
  payload: AddScenarioOperationRequest,
): Promise<ScenarioComparisonResponse> {
  return apiRequest<ScenarioComparisonResponse>(
    `/api/v1/scenarios/${scenarioId}/operations`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
}
