import { readFileSync } from 'node:fs'
import { defineConfig, devices } from '@playwright/test'

/**
 * ⚠ Test kullanıcısının bilgileri `.env.e2e`'den okunuyor — o dosya
 * `.gitignore`'da. Parolayı yapılandırmaya gömmek, onu git geçmişine
 * kalıcı olarak yazmak olurdu.
 *
 * Dosya yoksa testler açık bir hata mesajıyla duruyor (bkz. panel.spec.ts).
 */
try {
  const ham = readFileSync(new URL('.env.e2e', import.meta.url), 'utf8')
  for (const satir of ham.split(/\r?\n/)) {
    const kirp = satir.trim()
    if (!kirp || kirp.startsWith('#')) continue
    const esit = kirp.indexOf('=')
    if (esit < 0) continue
    const ad = kirp.slice(0, esit).trim()
    if (!process.env[ad]) process.env[ad] = kirp.slice(esit + 1).trim()
  }
} catch {
  // Dosya yok — ortam değişkenleriyle koşulacağı varsayılıyor.
}

/**
 * Playwright E2E — PLAN §14.1'de vardı, hiç kurulmamıştı.
 *
 * ⭐ NEDEN E2E GEREKLİ — projenin İKİNCİ TEZİ
 * -------------------------------------------
 * CLAUDE.md: *"Her parçası tek tek çalışan bir sistem uçtan uca
 * çalışmayabilir, ve parça testleri bunu asla göstermez."*
 *
 * P-43 (ifade karara girmiyordu), P-44 (`buda()` çağrılmıyordu),
 * P-45 (klipler erişilemiyordu) — üçü de birim testlerinden GEÇERDİ.
 * Bu dosyanın varlık sebebi o üç kayıt.
 *
 * ⚠ SUNUCUYU BU YAPILANDIRMA BAŞLATMIYOR
 * `webServer` bilinçli olarak tanımlanmadı. Sebep: sistem 20 kamera +
 * GPU worker'ı + Valkey + TimescaleDB demek; Playwright'ın onu ayağa
 * kaldırması dakikalar sürer ve ölçüm ortamını kirletir (P-36: koşarken
 * sisteme dokunma). Testler ZATEN AYAKTA olan sisteme bağlanıyor.
 *
 * Önce: pwsh backend/scripts/start_all.ps1
 * Sonra: npm run e2e
 */
export default defineConfig({
  testDir: './e2e',
  // ⚠ Tam sıralı: testler CANLI sisteme bağlanıyor ve paralel oturumlar
  // WS bağlantı limitini (G14) tetikleyebilir.
  fullyParallel: false,
  workers: 1,
  // Canlı sistemde ilk kare gelmesi zaman alıyor (ısınma ~90 sn, P-28).
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8001',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
    // ⚠ Kendi imzalı sertifika yok (G18 Caddy kurulmadı) — HTTP.
    ignoreHTTPSErrors: true,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})
