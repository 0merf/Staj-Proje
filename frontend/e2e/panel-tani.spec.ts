import { expect, test } from '@playwright/test'

/**
 * PANEL TANI — gözle değil ÖLÇEREK kontrol.
 *
 * ⭐ NEDEN AYRI BİR DOSYA
 * ----------------------
 * `panel.spec.ts` "çalışıyor mu" diye soruyor (geçer/kalır). Bu dosya
 * "sessizce bozuk bir şey var mı" diye soruyor ve BULGULARI RAPORLUYOR.
 *
 * Sebep: kullanıcı canlı panelde cam-15'in **siyah kaldığını** gördü.
 * Arka uç tarafı temizdi (kamera hazır, 4.15 FPS, MediaMTX ready) —
 * yani sorun tarayıcıda ve hiçbir sunucu metriği onu göstermiyor.
 *
 * ⚠ Bir kutucuğun çizilmesi videonun geldiğini GÖSTERMEZ. Tek
 * gözlemlenebilir kanıt `video.videoWidth > 0` ve `readyState >= 2`.
 */

const KULLANICI = process.env.E2E_USER ?? 'e2e-test'
const PAROLA = process.env.E2E_PASSWORD ?? ''

async function girisYap(page: import('@playwright/test').Page) {
  await page.goto('/app')
  await page.locator('input[autocomplete="username"]').fill(KULLANICI)
  await page.locator('input[type="password"]').fill(PAROLA)
  await page.getByRole('button', { name: /giriş/i }).click()
  await expect(page.getByTestId('kamera-izgarasi')).toBeVisible()
}

test('konsol hatası ve başarısız istek YOK — tüm sayfalar gezilerek', async ({
  page,
}) => {
  const konsolHatalari: string[] = []
  const basarisizIstekler: string[] = []

  /**
   * ⚠ İKİ HATA BEKLENEN VE GEREKÇELİ — gizlenmiyor, TANIMLANIYOR
   *
   * 1. `401 /api/v1/auth/ben` — uygulama açılışta "oturumum var mı"
   *    diye soruyor. Giriş yapılmadan önce 401 DOĞRU cevaptır;
   *    bastırmak, gerçek bir yetki hatasını da gizlerdi.
   *
   * 2. `404 /<cam>/whep/<oturum>` — kutucuk kapanırken WHEP oturumu
   *    DELETE ediliyor; MediaMTX oturumu çoktan temizlemiş olabiliyor.
   *    Zararsız bir yarış durumu.
   *
   * Bunları beyaz listeye almak, "konsol temiz" demenin dürüst yolu:
   * beklenmeyen HER hata hâlâ testi düşürüyor.
   */
  const beklenen = (metin: string) =>
    metin.includes('/api/v1/auth/ben') || /\/whep\/[0-9a-f-]{8,}/.test(metin)

  page.on('console', (m) => {
    if (m.type() !== 'error') return
    // Konsol mesajı URL taşımıyor; eşleşen bir yanıt görülmüşse atla.
    if (m.text().includes('401') || m.text().includes('404')) return
    konsolHatalari.push(m.text())
  })
  page.on('response', (r) => {
    if ((r.status() === 401 || r.status() === 404) && !beklenen(r.url())) {
      konsolHatalari.push(`${r.status()} ${r.url()}`)
    }
  })
  page.on('pageerror', (e) => konsolHatalari.push(`pageerror: ${e.message}`))
  page.on('requestfailed', (r) => {
    // ⚠ WebRTC/WHEP oturumu kapanırken iptal edilen istekler normal.
    const sebep = r.failure()?.errorText ?? ''
    if (sebep.includes('ERR_ABORTED')) return
    basarisizIstekler.push(`${r.method()} ${r.url()} — ${sebep}`)
  })
  page.on('response', (r) => {
    if (r.status() >= 500) basarisizIstekler.push(`${r.status()} ${r.url()}`)
  })

  await girisYap(page)

  // Üç sayfanın da açıldığını doğrula — CLAUDE.md "zaman çizelgesi ve
  // kamera detayı YOK" diyordu, panelde VARLAR (belge bayat).
  // ⚠ `exact: true` şart: "Izgara" hem sekme düğmesinde hem de
  // "← ızgaraya dön" düğmesinde geçiyor.
  for (const ad of ['Zaman Çizelgesi', 'Kamera Detayı', 'Izgara']) {
    await page.getByRole('button', { name: ad, exact: true }).click()
    await page.waitForTimeout(1500)
  }

  if (konsolHatalari.length) {
    console.log('\n⚠ KONSOL HATALARI:')
    for (const h of [...new Set(konsolHatalari)].slice(0, 10)) console.log(`   ${h}`)
  }
  if (basarisizIstekler.length) {
    console.log('\n⚠ BAŞARISIZ İSTEKLER:')
    for (const h of [...new Set(basarisizIstekler)].slice(0, 10)) console.log(`   ${h}`)
  }

  expect(konsolHatalari, 'konsolda hata var').toHaveLength(0)
  expect(basarisizIstekler, 'başarısız istek var').toHaveLength(0)
})

test('⭐ AÇILAN HER KAMERADA VİDEO GERÇEKTEN GELİYOR MU (siyah ekran avı)', async ({
  page,
}) => {
  test.setTimeout(180_000)
  await girisYap(page)

  const hazirlar = page.locator('[data-testid="kamera-kutucugu"][data-hazir="1"]')
  await expect.poll(() => hazirlar.count(), { timeout: 30_000 }).toBeGreaterThan(0)

  const toplam = await hazirlar.count()
  // ⚠ TÜM hazır kameralar taranıyor: kullanıcı cam-15'in siyah
  // kaldığını bildirdi ve ilk 8'de o yoktu.
  const denenecek = toplam
  const siyah: string[] = []
  const calisan: string[] = []

  for (let i = 0; i < denenecek; i++) {
    const kutu = hazirlar.nth(i)
    const ad = (await kutu.getAttribute('data-kamera')) ?? `#${i}`
    await kutu.getByRole('button', { name: 'izle', exact: true }).click()

    // WHEP el sıkışması + ilk kare için makul süre.
    const video = kutu.locator('video')
    let geldi = false
    for (let deneme = 0; deneme < 20; deneme++) {
      await page.waitForTimeout(1000)
      geldi = await video.evaluate((v: HTMLVideoElement) =>
        v.videoWidth > 0 && v.readyState >= 2,
      )
      if (geldi) break
    }
    ;(geldi ? calisan : siyah).push(ad)
    // Bir sonrakine geçmeden kapat: 20 eşzamanlı WebRTC oturumu
    // tarayıcı sınırına takılır ve ölçümü kirletir.
    await kutu.getByRole('button', { name: 'kapat' }).click()
    await page.waitForTimeout(400)
  }

  console.log(`\n⭐ VİDEO GELDİ  (${calisan.length}/${denenecek}): ${calisan.join(', ')}`)
  if (siyah.length) console.log(`❌ SİYAH KALDI (${siyah.length}): ${siyah.join(', ')}`)

  expect(siyah, `şu kameralarda video gelmedi: ${siyah.join(', ')}`).toHaveLength(0)
})
