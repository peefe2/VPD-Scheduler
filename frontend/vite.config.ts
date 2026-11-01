import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // 프론트는 /api/... 로 부르고, 개발 중엔 백엔드(8000, app.serve — API가 /api 아래)로 넘긴다.
    // 배포 때는 같은 서버가 화면과 /api를 함께 준다.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
