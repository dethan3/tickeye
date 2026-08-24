import { defineConfig } from '@hey-api/openapi-ts'

export default defineConfig({
  input: 'src/api/openapi.json',
  output: {
    path: 'src/api/generated',
  },
  plugins: ['@hey-api/typescript'],
})
