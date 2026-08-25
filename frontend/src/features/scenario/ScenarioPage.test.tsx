import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'
import type {
  PortfolioResponse,
  RiskAnalysisSchema,
  ScenarioComparisonResponse,
  ScenarioListResponse,
} from '../../api/generated'

const coverage = {
  total_positions: 2,
  valued_positions: 2,
  historical_positions: 1,
  known_portfolio_value: '2000.00',
  valued_position_ratio: '1',
  historical_value_ratio: '0.5',
}

function analysis(maxWeight: string): RiskAnalysisSchema {
  return {
    status: 'available',
    portfolio_as_of: '2026-08-25',
    market_data_as_of: '2026-08-25',
    positions: [],
    instrument_exposures: [
      { key: '1', label: '沪深300ETF (510300)', value: '1000', weight: maxWeight },
    ],
    asset_class_exposures: [
      { key: 'equity', label: 'equity', value: '1000', weight: maxWeight },
      { key: 'cash', label: 'cash', value: '1000', weight: '0.5' },
    ],
    coverage,
    metrics: {
      aligned_observations: 130,
      return_samples: 129,
      window_start: '2026-04-18',
      window_end: '2026-08-25',
      annualized_volatility: '0.10',
      downside_volatility: '0.06',
      max_drawdown: '0.12',
      current_drawdown: '0.02',
    },
    correlations: [],
    evidence: [],
    assumptions: [],
    limitations: [],
    methodology_version: 'historical-risk-v1',
  }
}

function comparison(operationCount: number): ScenarioComparisonResponse {
  const before = {
    analysis: analysis('0.50'),
    policy: { state: 'within' as const, findings: [], methodology_version: 'policy-evaluation-v1' },
    stressed_value: null,
  }
  const after = {
    analysis: analysis(operationCount ? '0.45' : '0.50'),
    policy: { state: 'within' as const, findings: [], methodology_version: 'policy-evaluation-v1' },
    stressed_value: null,
  }
  return {
    data: {
      scenario_id: 1,
      name: '降低集中度',
      base_portfolio_revision: 1,
      candidate_instrument_id: null,
      policy_revision: 0,
      operation_count: operationCount,
      operations: operationCount ? [{
        sequence: 1,
        operation_type: 'sell',
        instrument_id: 1,
        amount: '100.00',
        target_weight: null,
        estimated_cost: '1.00',
      }] : [],
      comparison_window: { start: '2026-04-18', end: '2026-08-25', observations: 130 },
      before,
      after,
      stress_assumptions: [],
      total_estimated_cost: operationCount ? '1.00' : '0.00',
      summary: {
        confidence: 'high',
        improvements: operationCount ? ['最大单一标的权重从 50.00% 变为 45.00%。'] : [],
        worsenings: [],
        objections: ['历史风险回放不能预测未来收益。'],
      },
      warnings: ['这是未执行的方案比较，不会修改实际持仓。'],
      methodology_version: 'scenario-comparison-v1',
      comparison_id: operationCount + 1,
    },
    as_of: '2026-08-25',
    calculated_at: '2026-08-25T08:00:00Z',
    coverage: { before: coverage, after: coverage },
    warnings: ['这是未执行的方案比较，不会修改实际持仓。'],
    methodology_version: 'scenario-comparison-v1',
  }
}

const list: ScenarioListResponse = {
  data: { items: [{
    scenario_id: 1,
    name: '降低集中度',
    status: 'evaluated',
    base_portfolio_revision: 1,
    candidate_instrument_id: null,
    operation_count: 0,
    created_at: '2026-08-25T08:00:00Z',
    updated_at: '2026-08-25T08:00:00Z',
  }] },
  as_of: null,
  calculated_at: '2026-08-25T08:00:00Z',
  coverage: { scenario_count: 1 },
  warnings: [],
  methodology_version: 'scenario-comparison-v1',
}

const portfolio: PortfolioResponse = {
  data: {
    profile_id: 1,
    profile_name: '我的投资组合',
    base_currency: 'CNY',
    revision: 1,
    positions: [{
      id: 1,
      account_id: 1,
      account_name: '长期账户',
      institution: null,
      account_currency: 'CNY',
      instrument_id: 1,
      code: '510300',
      name: '沪深300ETF',
      instrument_type: 'etf',
      market: 'CN',
      instrument_currency: 'CNY',
      asset_class: 'equity',
      region: '中国',
      quantity: '10',
      manual_value: null,
      cost: null,
      as_of: '2026-08-25',
    }],
    latest_snapshot_at: '2026-08-25T08:00:00Z',
  },
  as_of: '2026-08-25',
  calculated_at: '2026-08-25T08:00:00Z',
  coverage: { account_count: 1, position_count: 1 },
  warnings: [],
  methodology_version: 'portfolio-facts-v1',
}

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => vi.restoreAllMocks())

describe('ScenarioPage', () => {
  it('adds an operation and renders both the NO_ACTION baseline and result', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      if (url === '/api/v1/portfolio') return Promise.resolve(jsonResponse(portfolio))
      if (url === '/api/v1/scenarios') return Promise.resolve(jsonResponse(list))
      if (init?.method === 'POST') return Promise.resolve(jsonResponse(comparison(1)))
      return Promise.resolve(jsonResponse(comparison(0)))
    })
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
    const user = userEvent.setup()

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/scenarios']}><App /></MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByRole('heading', { name: '降低集中度' })).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('操作'), 'sell')
    await user.selectOptions(screen.getByLabelText('标的'), '1')
    await user.type(screen.getByLabelText('金额（元）'), '100')
    await user.type(screen.getByLabelText('估计交易成本（元）'), '1')
    await user.click(screen.getByRole('button', { name: '应用调整并比较风险' }))

    expect(await screen.findByText('最大单一标的权重从 50.00% 变为 45.00%。')).toBeInTheDocument()
    expect(screen.getByText('保持不变 / 调整前')).toBeInTheDocument()
    expect(screen.getByText('模拟调整 / 调整后')).toBeInTheDocument()
    expect(screen.getByText('沪深300ETF (510300) · ¥100.00 · 成本 ¥1.00')).toBeInTheDocument()
    const post = fetchMock.mock.calls.find((call) => call[1]?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
      operation_type: 'sell',
      instrument_id: 1,
      amount: '100',
      estimated_cost: '1',
    })
  })
})
