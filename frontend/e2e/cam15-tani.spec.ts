import { test } from '@playwright/test'

/**
 * cam-15 SİYAH EKRAN — tek kamera odaklı tanı.
 *
 * Bilinenler: MediaMTX'te hazır, H264, okuyucu var; alım worker'ı
 * 4.15 FPS okuyor. Yani sorun WHEP/WebRTC el sıkışmasında ya da
 * tarayıcının çözücüsünde.
 *
 * ⚠ Bu bir TEST değil, TANI: hiçbir şey iddia etmiyor, kanıt topluyor.
 */

const KULLANICI = process.env.E2E_USER ?? 'e2e-test'
const PAROLA = process.env.E2E_PASSWORD ?? ''

test('cam-15 WHEP tanısı — kanıt topla', async ({ page }) => {
  test.setTimeout(120_000)
  const kayit: string[] = []

  page.on('console', (m) => kayit.push(`[konsol:${m.type()}] ${m.text()}`))
  page.on('pageerror', (e) => kayit.push(`[pageerror] ${e.message}`))
  page.on('request', (r) => {
    if (r.url().includes('whep') || r.url().includes('cam-15')) {
      kayit.push(`[istek] ${r.method()} ${r.url()}`)
    }
  })
  page.on('response', async (r) => {
    if (r.url().includes('whep') || r.url().includes('cam-15')) {
      kayit.push(`[yanıt] ${r.status()} ${r.url()}`)
    }
  })

  await page.goto('/app')
  await page.locator('input[autocomplete="username"]').fill(KULLANICI)
  await page.locator('input[type="password"]').fill(PAROLA)
  await page.getByRole('button', { name: /giriş/i }).click()
  await page.getByTestId('kamera-izgarasi').waitFor()

  const kutu = page.locator('[data-testid="kamera-kutucugu"][data-kamera="cam-15"]')
  await kutu.waitFor()
  await kutu.getByRole('button', { name: 'izle', exact: true }).click()

  // 25 saniye boyunca video ve WebRTC durumunu izle.
  for (let i = 0; i < 25; i++) {
    await page.waitForTimeout(1000)
    const durum = await kutu.locator('video').evaluate((v: HTMLVideoElement) => ({
      w: v.videoWidth,
      h: v.videoHeight,
      hazir: v.readyState,
      ag: v.networkState,
      hata: v.error ? `${v.error.code}: ${v.error.message}` : null,
      src: v.srcObject ? 'MediaStream' : (v.src || 'YOK'),
      iz: v.srcObject
        ? (v.srcObject as MediaStream).getTracks().map(
            (t) => `${t.kind}/${t.readyState}/${t.muted ? 'muted' : 'live'}`,
          )
        : [],
    }))
    if (i % 5 === 0 || durum.w > 0) {
      kayit.push(`[${i}sn] ${JSON.stringify(durum)}`)
    }
    if (durum.w > 0) break
  }

  console.log('\n════ cam-15 TANI KAYDI ════')
  for (const s of kayit) console.log(s)
})
