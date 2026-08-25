import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { WatchlistResponse } from '../../api/generated'
import WatchlistPage from './WatchlistPage'

const candidate = {
  item_id: 1,
  instrument_id: 8,
  code: '159915',
  name: '创业板ETF',
  instrument_type: 'etf' as const,
  market: 'CN',
  currency: 'CNY',
  asset_class: 'equity' as const,
  region: '中国',
  reason: '等待估值回落后再比较',
  tags: ['候选', '成长'],
  held: false,
  created_at: '2026-08-25T08:00:00Z',
  updated_at: '2026-08-25T08:00:00Z',
}

function response(withCandidate = false): WatchlistResponse {
  return {
    data: { items: [{
      watchlist_id: 1,
      name: '待比较',
      items: withCandidate ? [candidate] : [],
      created_at: '2026-08-25T08:00:00Z',
      updated_at: '2026-08-25T08:00:00Z',
    }] },
    as_of: null,
    calculated_at: '2026-08-25T08:00:00Z',
    coverage: { watchlist_count: 1, item_count: withCandidate ? 1 : 0, held_item_count: 0 },
    warnings: ['观察列表来自用户主动录入，不代表推荐、排名或适合买入。'],
    methodology_version: 'user-watchlists-v1',
  }
}

const quality = {
  data: { items: [] },
  as_of: null,
  calculated_at: '2026-08-25T08:00:00Z',
  coverage: { tracked_count: 0, available_count: 0, problem_count: 0 },
  warnings: [],
  methodology_version: 'market-data-quality-v1',
}

function json(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/watchlists']}>
        <Routes>
          <Route path="/watchlists" element={<WatchlistPage />} />
          <Route path="/scenarios" element={<h1>风险方案目标页</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => vi.restoreAllMocks())

describe('WatchlistPage', () => {
  it('adds a user-selected candidate without presenting a recommendation', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      if (url === '/api/v1/watchlists/1/items' && init?.method === 'POST') {
        return Promise.resolve(json(response(true)))
      }
      if (url === '/api/v1/watchlists') return Promise.resolve(json(response(false)))
      return Promise.resolve(json(quality))
    })
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByRole('heading', { name: '待比较' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('代码'), '159915')
    await user.type(screen.getByLabelText('名称'), '创业板ETF')
    await user.type(screen.getByLabelText('观察理由'), '等待估值回落后再比较')
    await user.type(screen.getByLabelText('标签'), '候选，成长')
    await user.click(screen.getByRole('button', { name: '加入当前分组' }))

    expect(await screen.findByText('等待估值回落后再比较')).toBeInTheDocument()
    expect(screen.getByText('观察列表来自用户主动录入，不代表推荐、排名或适合买入。')).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(
      ([input, init]) => String(input).endsWith('/items') && init?.method === 'POST',
    )
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      code: '159915', reason: '等待估值回落后再比较', tags: ['候选', '成长'],
    })
  })

  it('creates a frozen Scenario for an unheld watched candidate', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      if (url === '/api/v1/watchlists') return Promise.resolve(json(response(true)))
      if (url === '/api/v1/scenarios' && init?.method === 'POST') {
        return Promise.resolve(json({ data: { scenario_id: 12 } }))
      }
      return Promise.resolve(json(quality))
    })
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: '模拟调整风险' }))
    expect(await screen.findByRole('heading', { name: '风险方案目标页' })).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(
      ([input, init]) => String(input) === '/api/v1/scenarios' && init?.method === 'POST',
    )
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      name: '创业板ETF 风险调整模拟',
      candidate_instrument_id: 8,
    })
  })
})
