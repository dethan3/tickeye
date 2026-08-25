import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'
import type { PortfolioResponse, PositionSchema } from '../../api/generated'

const position: PositionSchema = {
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
  quantity: '100.00000000',
  manual_value: '400.00',
  cost: null,
  as_of: '2026-08-24',
}

function portfolioResponse(positions: PositionSchema[], revision: number): PortfolioResponse {
  return {
    data: {
      profile_id: 1,
      profile_name: '我的投资组合',
      base_currency: 'CNY',
      revision,
      positions,
      latest_snapshot_at: positions.length ? '2026-08-24T01:00:00Z' : null,
    },
    as_of: positions.length ? '2026-08-24' : null,
    calculated_at: '2026-08-24T01:00:00Z',
    coverage: { account_count: positions.length ? 1 : 0, position_count: positions.length },
    warnings: [],
    methodology_version: 'portfolio-facts-v1',
  }
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderPortfolio() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/portfolio']}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('PortfolioPage', () => {
  it('adds a position using the current portfolio revision', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(portfolioResponse([], 0)))
      .mockResolvedValueOnce(jsonResponse(portfolioResponse([position], 1)))
    const user = userEvent.setup()

    renderPortfolio()
    await screen.findByRole('heading', { name: '我的持仓' })
    await user.type(screen.getByLabelText('账户名称'), '长期账户')
    await user.type(screen.getByLabelText('标的代码'), '510300')
    await user.type(screen.getByLabelText('标的名称'), '沪深300ETF')
    await user.selectOptions(screen.getByLabelText('标的类型'), 'etf')
    await user.type(screen.getByLabelText('数量'), '100')
    await user.type(screen.getByLabelText('手工市值（元）'), '400')
    await user.click(screen.getByRole('button', { name: '保存并创建快照' }))

    expect(await screen.findByText('沪深300ETF')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('持仓已新增并生成快照')
    const request = fetchMock.mock.calls[1]
    const body = JSON.parse(String(request?.[1]?.body)) as {
      expected_revision: number
      positions: Array<{ code: string }>
    }
    expect(body.expected_revision).toBe(0)
    expect(body.positions[0]?.code).toBe('510300')
  })

  it('explains an empty portfolio and makes the new-position action visible', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      jsonResponse(portfolioResponse([], 0)),
    )
    const user = userEvent.setup()

    renderPortfolio()

    expect(await screen.findByRole('heading', { name: '还没有持仓数据' }))
      .toBeInTheDocument()
    expect(screen.getByText(/风险分析目前只能返回“信息不足”/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '新增持仓' }))

    expect(screen.getByLabelText('账户名称')).toHaveFocus()
    expect(screen.getByRole('status')).toHaveTextContent('新增持仓表单已准备好')
  })

  it('previews a CSV before confirming the replacement', async () => {
    const preview = {
      mode: 'preview',
      data: {
        preview_token: 'a'.repeat(64),
        valid: true,
        duplicate_import: false,
        positions: [{ ...position, id: null }],
        issues: [],
      },
    }
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(portfolioResponse([], 0)))
      .mockResolvedValueOnce(jsonResponse(preview))
      .mockResolvedValueOnce(
        jsonResponse({ mode: 'confirm', portfolio: portfolioResponse([position], 1) }),
      )
    const user = userEvent.setup()
    const file = new File(['csv-data'], 'positions.csv', { type: 'text/csv' })
    Object.defineProperty(file, 'text', { value: async () => 'csv-data' })

    renderPortfolio()
    await screen.findByRole('heading', { name: 'CSV 预览导入' })
    await user.upload(screen.getByLabelText('选择 CSV 文件'), file)
    await user.click(screen.getByRole('button', { name: '预览并校验' }))
    expect(await screen.findByText('可导入 1 条持仓')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '确认替换当前持仓' }))
    expect(await screen.findByText('沪深300ETF')).toBeInTheDocument()

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    const previewBody = JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body)) as { mode: string }
    const confirmBody = JSON.parse(String(fetchMock.mock.calls[2]?.[1]?.body)) as {
      mode: string
      expected_revision: number
    }
    expect(previewBody.mode).toBe('preview')
    expect(confirmBody).toMatchObject({ mode: 'confirm', expected_revision: 0 })
  })
})
