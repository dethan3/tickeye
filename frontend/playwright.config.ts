import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from '@playwright/test'

const frontendDirectory = fileURLToPath(new URL('.', import.meta.url))
const repositoryDirectory = resolve(frontendDirectory, '..')
const runDirectory = mkdtempSync(join(tmpdir(), 'tickeye-e2e-'))

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  reporter: 'line',
  use: {
    baseURL: 'http://127.0.0.1:4174',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: '.venv/bin/uvicorn tests.e2e_app:app --host 127.0.0.1 --port 8010',
      cwd: repositoryDirectory,
      env: {
        ...process.env,
        TICKEYE_E2E_DATABASE_PATH: join(runDirectory, 'tickeye.db'),
      },
      url: 'http://127.0.0.1:8010/api/v1/health',
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: 'pnpm dev --host 127.0.0.1 --port 4174',
      cwd: frontendDirectory,
      env: {
        ...process.env,
        TICKEYE_API_TARGET: 'http://127.0.0.1:8010',
      },
      url: 'http://127.0.0.1:4174',
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
})
