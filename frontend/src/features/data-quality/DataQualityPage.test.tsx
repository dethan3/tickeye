import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'
import type {
  DataQualityItemSchema,
  DataQualityResponse,
  MarketRefreshResponse,
} from '../../api/generated'

function qualityResponse(items: DataQualityItemSchema[]): DataQualityResponse {
  return {
    data: { items },
    as_of: items[0]?.last_observation_date ?? null,
    calculated_at: '2026-08-24T04:00:00Z',
    coverage: {
      tracked_count: items.length,
      available_count: items.filter((item) => item.last_observation_date !== null).length,
      problem_count: items.filter(
        (item) => item.status !== 'good' && item.status !== 'not_applicable',
      ).length,
    },
    warnings: [],
    methodology_version: 'data-quality-v1',
  }
}

const missingItem: DataQualityItemSchema = {
  instrument_id: 1,
  code: '510300',
  name: '沪深300ETF',
  instrument_type: 'etf',
  status: 'missing',
  last_observation_date: null,
  latest_value: null,
  value_type: null,
  source: null,
  sample_count: 0,
  freshness_days: null,
  freshness_limit_days: 3,
  rejected_rate: null,
  last_refresh_at: null,
  last_refresh_status: null,
  failure_code: null,
  failure_message: null,
  limitations: [],
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
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
      <MemoryRouter initialEntries={['/data-quality']}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('DataQualityPage', () => {
  it('directs an empty portfolio to position entry', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse(qualityResponse([])))

    renderPage()

    expect(await screen.findByRole('heading', { name: '还没有需要检查的标的' }))
      .toBeInTheDocument()
    expect(screen.getByRole('link', { name: '录入持仓' })).toHaveAttribute(
      'href',
      '/portfolio',
    )
    expect(screen.getByRole('link', { name: '添加观察标的' })).toHaveAttribute(
      'href',
      '/watchlists',
    )
    expect(screen.getByRole('button', { name: '刷新全部行情' })).toBeDisabled()
  })

  it('shows transparent quality state and updates it after refresh', async () => {
    const refreshedItem: DataQualityItemSchema = {
      ...missingItem,
      status: 'short_history',
      last_observation_date: '2026-08-24',
      latest_value: '4.20000000',
      value_type: 'adjusted_close',
      source: 'akshare:fund_etf_hist_em:qfq',
      sample_count: 2,
      freshness_days: 0,
      rejected_rate: '0.3333',
      last_refresh_at: '2026-08-24T04:00:00Z',
      last_refresh_status: 'success',
      limitations: ['qfq_history_can_be_revised'],
    }
    const refreshedQuality = qualityResponse([refreshedItem])
    const refreshResponse: MarketRefreshResponse = {
      data: {
        results: [
          {
            instrument_id: 1,
            code: '510300',
            status: 'success',
            accepted_rows: 2,
            written_rows: 2,
            error_code: null,
            error_message: null,
          },
        ],
        quality: refreshedQuality,
      },
    }
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(qualityResponse([missingItem])))
      .mockResolvedValueOnce(jsonResponse(refreshResponse))
    const user = userEvent.setup()

    renderPage()
    expect(
      await screen.findByText('还没有成功取得这个标的的市场数据。'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '刷新全部行情' }))

    expect(await screen.findByText('样本不足')).toBeInTheDocument()
    expect(screen.getByText('33.33%')).toBeInTheDocument()
    expect(screen.getByText('前复权历史会随分红送配重新计算')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('1 个成功，0 个失败')
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/market-data/refresh')
    expect(fetchMock.mock.calls[1]?.[1]?.body).toBe(
      JSON.stringify({ instrument_ids: null }),
    )
  })

  it('keeps the page usable and explains a provider failure', async () => {
    const failedItem: DataQualityItemSchema = {
      ...missingItem,
      status: 'refresh_failed',
      last_refresh_at: '2026-08-24T04:00:00Z',
      last_refresh_status: 'error',
      failure_code: 'network_error',
      failure_message: '测试网络故障',
    }
    const failedQuality = qualityResponse([failedItem])
    const refreshResponse: MarketRefreshResponse = {
      data: {
        results: [{
          instrument_id: 1,
          code: '510300',
          status: 'error',
          accepted_rows: 0,
          written_rows: 0,
          error_code: 'network_error',
          error_message: '测试网络故障',
        }],
        quality: failedQuality,
      },
    }
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse(qualityResponse([missingItem])))
      .mockResolvedValueOnce(jsonResponse(refreshResponse))
    const user = userEvent.setup()

    renderPage()
    await user.click(await screen.findByRole('button', { name: '刷新全部行情' }))

    expect(await screen.findByText('刷新失败')).toBeInTheDocument()
    expect(screen.getByText('测试网络故障')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('0 个成功，1 个失败')
    expect(screen.getByRole('button', { name: '刷新全部行情' })).toBeEnabled()
  })
})
