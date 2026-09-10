import { expect, test } from '@playwright/test'

/**
 * G18 — TLS + TEK GİRİŞ NOKTASI · güvenlik nöbetçisi
 *
 * ⭐ NE KORUYOR: P-37'nin tam çözümü
 * ----------------------------------
 * 30.08.2026'da bulunan açık: API kimlik doğrulamalıydı ama **video
 * değildi**. O gün uygulanan çözüm bir ağ kısıtıydı (port 127.0.0.1'e
 * bağlandı) — erişimi sınırlar, açığı KAPATMAZ.
 *
 * Caddy videoyu API ile aynı kökene alıp `forward_auth` ile her WHEP
 * isteğini önce FastAPI'ye sorduruyor. Bu dosya o iddiayı sınıyor.
 *
 * ⚠ ÖN KOŞUL: `docker compose --profile tls up -d caddy`
 * Caddy kapalıysa testler ATLANIYOR (başarısız sayılmıyor) — çünkü
 * varsayılan kurulumda kapalı olması bilinçli bir karar.
 */

const TLS_TABAN = process.env.E2E_TLS_URL ?? 'https://localhost:8443'
const KULLANICI = process.env.E2E_USER ?? 'e2e-test'
const PAROLA = process.env.E2E_PASSWORD ?? ''

test.describe('G18 — TLS ve video kimlik doğrulaması', () => {
  test.use({ ignoreHTTPSErrors: true, baseURL: TLS_TABAN })

  test.beforeEach(async ({ request }) => {
    try {
      await request.get(`${TLS_TABAN}/app`, { timeout: 5000 })
    } catch {
      test.skip(true, 'Caddy ayakta değil (docker compose --profile tls up -d caddy)')
    }
  })

  test('⭐ KİMLİKSİZ video isteği ENGELLENİYOR (P-37)', async ({ request }) => {
    const cevap = await request.post(`${TLS_TABAN}/cam-01/whep`, {
      headers: { 'Content-Type': 'application/sdp' },
      data: 'v=0',
    })
    // 401/403 = forward_auth reddetti, MediaMTX'e HİÇ ulaşmadı.
    // ⚠ 400 gelirse Caddy isteği GEÇİRMİŞ demektir — açık geri gelmiş.
    expect(
      [401, 403],
      `kimliksiz WHEP ${cevap.status()} döndü — video korumasız olabilir`,
    ).toContain(cevap.status())
  })

  test('⭐ GİRİŞ YAPMIŞ istemci videoya ERİŞEBİLİYOR', async ({ request }) => {
    const giris = await request.post(`${TLS_TABAN}/api/v1/auth/login`, {
      data: { kullanici_adi: KULLANICI, parola: PAROLA },
    })
    expect(giris.status(), 'giriş başarısız').toBe(200)

    const cevap = await request.post(`${TLS_TABAN}/cam-01/whep`, {
      headers: { 'Content-Type': 'application/sdp' },
      data: 'v=0',
    })
    // ⚠ 400 BEKLENEN VE DOĞRU: Caddy isteği geçirdi, MediaMTX geçerli
    // bir SDP teklifi bekliyordu. Yani yetki kapısı açıldı.
    // 401 gelseydi güvenlik sistemi meşru kullanıcıyı da kesiyordu —
    // "güvenli ama çalışmıyor" da bir arıza.
    expect(
      [200, 201, 400],
      `giriş yapmış istemci videoya erişemedi (${cevap.status()})`,
    ).toContain(cevap.status())
  })

  test('güvenlik başlıkları uygulanıyor', async ({ request }) => {
    const cevap = await request.get(`${TLS_TABAN}/app`)
    const b = cevap.headers()
    expect(b['strict-transport-security'], 'HSTS yok').toBeTruthy()
    expect(b['x-content-type-options']).toBe('nosniff')
    expect(b['x-frame-options']).toBe('DENY')
    // Sunucu sürümü sızmamalı
    expect(b['server'] ?? '').not.toContain('Caddy')
  })

  test('panel HTTPS üzerinden açılıyor ve giriş çalışıyor', async ({ page }) => {
    await page.goto(`${TLS_TABAN}/app`)
    await page.locator('input[autocomplete="username"]').fill(KULLANICI)
    await page.locator('input[type="password"]').fill(PAROLA)
    await page.getByRole('button', { name: /giriş/i }).click()
    await expect(page.getByTestId('kamera-izgarasi')).toBeVisible()
  })
})
