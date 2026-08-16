import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Vite 7 — Vite 8 DEĞİL. Gerekçe: Vite 8 + Tailwind v4 + React 19
// birleşiminde bilinen kurulum sorunları raporlanmış (PLAN.md §3.5).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // ⚠ IPv4'e SABİTLENDİ. Varsayılan `localhost` Windows'ta yalnızca
    // ::1 (IPv6) dinlemeye yol açıyor; 127.0.0.1'den erişilemiyor ve
    // araçlar sessizce bağlanamıyor. Aynı tuzak altyapı adreslerinde de
    // yaşanmıştı (docs/report/problems.md · P-03).
    host: '127.0.0.1',
    port: 5173,
    // Geliştirme sunucusu 5173'te, API 8001'de. Vekil (proxy) olmadan
    // tarayıcı çapraz köken (CORS) engeline takılırdı. Vekille aynı
    // köken gibi görünüyor — WebSocket'in Origin doğrulaması da
    // sorunsuz geçiyor (bkz. problems.md · P-11).
    proxy: {
      '/api': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8001', ws: true, changeOrigin: true },
    },
  },
  build: {
    // Üretimde FastAPI'nin servis ettiği dizine derleniyor.
    outDir: '../backend/src/sentinel/api/static/app',
    emptyOutDir: true,
  },
})
