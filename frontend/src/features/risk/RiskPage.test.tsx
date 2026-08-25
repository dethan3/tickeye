import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'
import type { EventResponse, RiskResponse } from '../../api/generated'

function riskResponse(isCurrent = true): RiskResponse {
  const coverage = {
    total_positions: 2,
    valued_positions: 2,
    historical_positions: 1,
    known_portfolio_value: '2000.00',
    valued_position_ratio: '1.00000000',
    historical_value_ratio: '0.50000000',
  }
  return {
    data: {
      snapshot_id: 3,
      portfolio_revision: 1,
      is_current: isCurrent,
      stale_reasons: isCurrent ? [] : ['portfolio_changed'],
      analysis: {
        status: 'available',
        portfolio_as_of: '2026-08-24',
        market_data_as_of: '2026-08-24',
        positions: [
          {
            position_id: 1,
            instrument_id: 1,
            account_name: '长期账户',
            code: '510300',
            name: '沪深300ETF',
            instrument_type: 'etf',
            asset_class: 'equity',
            value: '1000.00',
            weight: '0.50000000',
            valuation_source: 'market_data',
            value_as_of: '2026-08-24',
          },
          {
            position_id: 2,
            instrument_id: 2,
            account_name: '现金账户',
            code: 'CASH-CNY',
            name: '人民币现金',
            instrument_type: 'cash',
            asset_class: 'cash',
            value: '1000.00',
            weight: '0.50000000',
            valuation_source: 'cash_balance',
            value_as_of: '2026-08-24',
          },
        ],
        instrument_exposures: [
          { key: '1', label: '沪深300ETF (510300)', value: '1000.00', weight: '0.50000000' },
          { key: '2', label: '人民币现金 (CASH-CNY)', value: '1000.00', weight: '0.50000000' },
        ],
        asset_class_exposures: [
          { key: 'cash', label: 'cash', value: '1000.00', weight: '0.50000000' },
          { key: 'equity', label: 'equity', value: '1000.00', weight: '0.50000000' },
        ],
        coverage,
        metrics: {
          aligned_observations: 130,
          return_samples: 129,
          window_start: '2026-04-17',
          window_end: '2026-08-24',
          annualized_volatility: '0.12340000',
          downside_volatility: '0.08200000',
          max_drawdown: '0.15000000',
          current_drawdown: '0.03000000',
        },
        correlations: [],
        evidence: [],
        assumptions: ['使用当前估值权重回放历史，每个观测日按固定权重重新平衡。'],
        limitations: ['qfq_history_can_be_revised'],
        methodology_version: 'historical-risk-v1',
      },
    },
    as_of: '2026-08-24',
    calculated_at: '2026-08-24T04:00:00Z',
    coverage,
    warnings: isCurrent ? [] : ['持仓已在快照生成后发生变化，请重新计算。'],
    methodology_version: 'historical-risk-v1',
  }
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function eventResponse(count = 0): EventResponse {
  return {
    data: {
      items: Array.from({ length: count }, (_, index) => ({
        event_id: count - index,
        event_type: index === 0 ? 'state_changed' : 'detected',
        finding_key: `policy:${index + 1}`,
        from_state: index === 0 ? 'watch' : null,
        to_state: 'breached',
        severity: 'breached',
        occurred_at: `2026-08-${24 - index}T08:00:00Z`,
        finding: {
          finding_key: `policy:${index + 1}`,
          dimension: 'instrument_concentration',
          state: 'breached',
          title: `风险变化 ${index + 1}`,
          message: '当前值已经超过用户设置的边界。',
          current_value: '0.55',
          boundary_low: null,
          boundary_high: '0.50',
          contributor_key: '510300',
          contributor_label: '沪深300ETF',
          policy_rule_id: index + 1,
        },
      })),
    },
    calculated_at: '2026-08-24T08:00:00Z',
    warnings: [],
    methodology_version: 'insight-events-v1',
  }
}

function mockRiskPage(response: RiskResponse, events = eventResponse()) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input) => Promise.resolve(
    jsonResponse(String(input) === '/api/v1/events' ? events : response),
  ))
}

function renderRisk() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('RiskPage', () => {
  it('labels metrics as a simulation and exposes valuation evidence', async () => {
    mockRiskPage(riskResponse())

    renderRisk()

    expect(await screen.findByText('历史风险可计算')).toBeInTheDocument()
    expect(screen.getByText('12.34%')).toBeInTheDocument()
    expect(screen.getByText('15.00%')).toBeInTheDocument()
    expect(screen.getByText('市场数据')).toBeInTheDocument()
    expect(screen.getByText('前复权历史可能因分红送配重新计算')).toBeInTheDocument()
    expect(screen.getByText(/不是账户收益/)).toBeInTheDocument()
    expect(screen.getByText('历史风险已有数据，但尚无个人边界结论')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '按需设置风险边界' })).toHaveAttribute(
      'href',
      '/policies',
    )
  })

  it('shows only the three most recent recorded changes on the risk homepage', async () => {
    mockRiskPage(riskResponse(), eventResponse(4))

    renderRisk()

    expect(await screen.findByText('风险变化 1')).toBeInTheDocument()
    expect(screen.getByText('风险变化 2')).toBeInTheDocument()
    expect(screen.getByText('风险变化 3')).toBeInTheDocument()
    expect(screen.queryByText('风险变化 4')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '查看完整记录' })).toHaveAttribute(
      'href',
      '/events',
    )
    expect(screen.getByText(/不维护已读或未读状态/)).toBeInTheDocument()
  })

  it('prioritizes a confirmed policy breach over general data actions', async () => {
    const response = riskResponse()
    if (response.data === null) throw new Error('fixture must contain a snapshot')
    response.data.evaluation = {
      evaluation_id: 4,
      policy_revision: 2,
      state: 'breached',
      calculated_at: '2026-08-24T04:00:00Z',
      findings: [],
    }
    mockRiskPage(response)

    renderRisk()

    expect(await screen.findByText('先处理已经越过的风险边界')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '模拟风险调整' })).toHaveAttribute(
      'href',
      '/scenarios',
    )
    expect(screen.getByRole('link', { name: '查看变化事件' })).toHaveAttribute(
      'href',
      '/events',
    )
  })

  it('routes incomplete evidence to data quality without calling it low risk', async () => {
    const response = riskResponse()
    if (response.data === null) throw new Error('fixture must contain a snapshot')
    response.data.analysis.status = 'unknown'
    response.data.analysis.coverage.valued_positions = 1
    response.data.analysis.coverage.valued_position_ratio = '0.50000000'
    mockRiskPage(response)

    renderRisk()

    expect(await screen.findByText('先补齐风险判断所需的数据')).toBeInTheDocument()
    expect(screen.getByText(/不要把无法计算理解成低风险/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '检查并刷新数据' })).toHaveAttribute(
      'href',
      '/data-quality',
    )
  })

  it('marks an old snapshot and replaces it only after explicit recalculation', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url === '/api/v1/events') return Promise.resolve(jsonResponse(eventResponse()))
      return Promise.resolve(jsonResponse(
        url === '/api/v1/risk/recalculate' ? riskResponse(true) : riskResponse(false),
      ))
    })
    const user = userEvent.setup()

    renderRisk()
    expect(await screen.findByRole('alert')).toHaveTextContent('这份快照已经过期')
    await user.click(screen.getByRole('button', { name: '重新计算' }))

    expect(await screen.findByText('历史风险可计算')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    const recalculateCall = fetchMock.mock.calls.find(
      ([input]) => String(input) === '/api/v1/risk/recalculate',
    )
    expect(recalculateCall?.[0]).toBe('/api/v1/risk/recalculate')
    expect(recalculateCall?.[1]?.method).toBe('POST')
  })
})
