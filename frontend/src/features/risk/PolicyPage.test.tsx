import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'
import type { PolicyResponse, PortfolioResponse } from '../../api/generated'

const emptyPolicies: PolicyResponse = {
  data: { revision: 0, rules: [] },
  calculated_at: '2026-08-24T01:00:00Z',
  warnings: ['尚未设置用户风险边界；系统不会将当前组合解释为安全。'],
  methodology_version: 'policy-rules-v1',
}

const portfolio: PortfolioResponse = {
  data: {
    profile_id: 1,
    profile_name: '我的投资组合',
    base_currency: 'CNY',
    revision: 1,
    latest_snapshot_at: '2026-08-24T01:00:00Z',
    positions: [],
  },
  as_of: null,
  calculated_at: '2026-08-24T01:00:00Z',
  coverage: { account_count: 0, position_count: 0 },
  warnings: [],
  methodology_version: 'portfolio-facts-v1',
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderPolicies() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/policies']}><App /></MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => vi.restoreAllMocks())

describe('PolicyPage', () => {
  it('requires the user to enter every boundary and warning buffer', async () => {
    const saved: PolicyResponse = {
      ...emptyPolicies,
      data: {
        revision: 1,
        rules: [
          {
            id: 1,
            rule_type: 'cash_min_weight',
            subject_key: 'cash',
            subject_label: '现金',
            threshold: '0.10',
            tolerance: null,
            warning_ratio: '0.20',
            enabled: true,
          },
        ],
      },
      warnings: [],
    }
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      if (String(input) === '/api/v1/portfolio') return Promise.resolve(jsonResponse(portfolio))
      if (init?.method === 'PUT') return Promise.resolve(jsonResponse(saved))
      return Promise.resolve(jsonResponse(emptyPolicies))
    })
    const user = userEvent.setup()

    renderPolicies()
    expect(await screen.findByText(/尚未设置规则/)).toBeInTheDocument()
    expect(screen.getByLabelText('关注缓冲（%）')).toHaveValue(null)
    await user.selectOptions(screen.getByLabelText('规则类型'), 'cash_min_weight')
    await user.type(screen.getByLabelText('边界（%）'), '10')
    await user.type(screen.getByLabelText('关注缓冲（%）'), '20')
    await user.click(screen.getByRole('button', { name: '保存规则并重新评估' }))

    expect(await screen.findByText('10.0%')).toBeInTheDocument()
    const put = fetchMock.mock.calls.find((call) => call[1]?.method === 'PUT')
    const body = JSON.parse(String(put?.[1]?.body)) as {
      expected_revision: number
      rules: Array<{ threshold: string; warning_ratio: string }>
    }
    expect(body.expected_revision).toBe(0)
    expect(body.rules[0]).toMatchObject({ threshold: '0.1', warning_ratio: '0.2' })
  })
})
