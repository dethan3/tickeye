import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('App', () => {
  it('opens on the risk workspace empty state', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          data: null,
          as_of: null,
          calculated_at: '2026-08-24T01:00:00Z',
          coverage: null,
          warnings: ['尚未生成风险快照。'],
          methodology_version: 'historical-risk-v1',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    renderApp()

    expect(screen.getByText('正在读取风险快照…')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: /你的钱.*现在安全吗/ }))
      .toBeInTheDocument()
    expect(screen.getByRole('link', { name: '先检查数据' })).toHaveAttribute(
      'href',
      '/data-quality',
    )
  })

  it('lets the user retry a failed risk snapshot request', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockRejectedValueOnce(new Error('无法连接服务'))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            data: null,
            as_of: null,
            calculated_at: '2026-08-24T01:00:00Z',
            coverage: null,
            warnings: [],
            methodology_version: 'historical-risk-v1',
          }),
          { status: 200 },
        ),
      )

    renderApp()

    expect(await screen.findByText('无法读取风险快照')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '重新读取' }))
    expect(await screen.findByRole('button', { name: '生成第一份风险快照' }))
      .toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
