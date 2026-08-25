import type {
  ImportConfirmedResponse,
  ImportPreviewResponse,
  PortfolioResponse,
  PositionInputSchemaInput,
} from './generated'
import { apiRequest } from './request'

export function getPortfolio(signal?: AbortSignal): Promise<PortfolioResponse> {
  return apiRequest<PortfolioResponse>('/api/v1/portfolio', { signal })
}

export function replacePositions(
  expectedRevision: number,
  positions: PositionInputSchemaInput[],
): Promise<PortfolioResponse> {
  return apiRequest<PortfolioResponse>('/api/v1/portfolio/positions', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      expected_revision: expectedRevision,
      positions,
    }),
  })
}

export function previewPortfolioCsv(csvContent: string): Promise<ImportPreviewResponse> {
  return apiRequest<ImportPreviewResponse>('/api/v1/portfolio/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: 'preview', csv_content: csvContent }),
  })
}

export function confirmPortfolioCsv(
  csvContent: string,
  previewToken: string,
  expectedRevision: number,
): Promise<ImportConfirmedResponse> {
  return apiRequest<ImportConfirmedResponse>('/api/v1/portfolio/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      mode: 'confirm',
      csv_content: csvContent,
      preview_token: previewToken,
      expected_revision: expectedRevision,
    }),
  })
}
