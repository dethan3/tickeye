import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'
import type { EventResponse } from '../../api/generated'

const response: EventResponse = {
  data: {
    items: [
      {
        event_id: 8,
        event_type: 'recovered',
        finding_key: 'policy:1',
        from_state: 'breached',
        to_state: 'within',
        severity: 'within',
        occurred_at: '2026-08-24T08:00:00Z',
        finding: {
          finding_key: 'policy:1',
          dimension: 'cash_liquidity',
          state: 'within',
          title: '现金最低比例',
          message: '当前值位于用户设定边界内。',
          current_value: '0.15',
          boundary_low: '0.10',
          boundary_high: null,
          contributor_key: 'cash',
          contributor_label: '现金',
          policy_rule_id: 1,
        },
      },
    ],
  },
  calculated_at: '2026-08-24T08:00:00Z',
  warnings: [],
  methodology_version: 'insight-events-v1',
}

afterEach(() => vi.restoreAllMocks())

describe('EventPage', () => {
  it('shows a recovered risk transition without presenting it as advice', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify(response), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }))
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/events']}><App /></MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByRole('heading', { name: '风险事件' })).toBeInTheDocument()
    expect(screen.getByText('恢复到边界内')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '现金最低比例' })).toBeInTheDocument()
    expect(screen.getByText('breached → within')).toBeInTheDocument()
  })
})
