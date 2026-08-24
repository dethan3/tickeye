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
  it('shows the backend and database as ready', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          status: 'ok',
          service: 'tickeye-api',
          version: '2.0.0.dev0',
          database: { status: 'ok' },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    renderApp()

    expect(screen.getByText('正在连接本地服务…')).toBeInTheDocument()
    expect(await screen.findByText('系统已就绪')).toBeInTheDocument()
    expect(screen.getByText('数据库正常')).toBeInTheDocument()
  })

  it('lets the user retry a failed connection', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockRejectedValueOnce(new Error('无法连接服务'))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: 'ok',
            service: 'tickeye-api',
            version: '2.0.0.dev0',
            database: { status: 'ok' },
          }),
          { status: 200 },
        ),
      )

    renderApp()

    expect(await screen.findByText('本地服务暂时不可用')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '重新连接' }))
    expect(await screen.findByText('系统已就绪')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
