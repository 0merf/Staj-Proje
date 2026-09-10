import { expect, test } from '@playwright/test'

/**
 * Uçtan uca panel testleri — CANLI sisteme karşı koşar.
 *
 * ⚠ ÖN KOŞUL: sistem ayakta olmalı (`start_all.ps1`) ve `.env.e2e`
 * içinde test kullanıcısının bilgileri bulunmalı.
 *
 * ⭐ Bu testlerin hedefi ZİNCİR, parça değil. Her biri "kullanıcının
 * yapabildiği bir iş"i doğruluyor — CLAUDE.md'nin kapsam kuralı:
 * *"'klip kesiliyor' bir modül ifadesi; 'operatör alarmın videosunu
 * izleyebiliyor' bir kapsam ifadesi."*
 */

const KULLANICI = process.env.E2E_USER ?? 'e2e-test'
const PAROLA = process.env.E2E_PASSWORD ?? ''

test.beforeAll(() => {
  if (!PAROLA) {
    throw new Error(
      'E2E_PASSWORD tanımlı değil. `frontend/.env.e2e` dosyasını oluşturun ' +
        '(bkz. e2e/BENIOKU.md) ya da ortam değişkeni verin.',
    )
  }
})

async function girisYap(page: import('@playwright/test').Page) {
  await page.goto('/app')
  await page.locator('input[autocomplete="username"]').fill(KULLANICI)
  await page.locator('input[type="password"]').fill(PAROLA)
  await page.getByRole('button', { name: /giriş/i }).click()
  // Giriş başarılıysa kamera ızgarası geliyor.
  await expect(page.getByTestId('kamera-izgarasi')).toBeVisible()
}

test('API kimlik doğrulaması OLMADAN veri sızdırmıyor (G01)', async ({
  request,
}) => {
  // ⚠ Bu test P-37'nin nöbetçisi: 30.08'de API korunurken VİDEO
  // herkese açık kalmıştı. Kimliksiz istek 401/403 dönmeli — 200
  // dönerse bir uç nokta korumasız demektir.
  for (const yol of [
    '/api/v1/system/health',
    '/api/v1/cameras',
    '/api/v1/events/ozet',
  ]) {
    const cevap = await request.get(yol)
    expect(
      [401, 403],
      `${yol} kimliksiz erişime ${cevap.status()} döndü`,
    ).toContain(cevap.status())
  }
})

test('yanlış parola reddediliyor ve hata GÖSTERİLİYOR', async ({ page }) => {
  await page.goto('/app')
  await page.locator('input[autocomplete="username"]').fill(KULLANICI)
  await page.locator('input[type="password"]').fill('kesinlikle-yanlis-parola')
  await page.getByRole('button', { name: /giriş/i }).click()

  // ⚠ Yalnızca "girilemedi" yetmez — kullanıcıya SEBEP gösterilmeli.
  // Sessiz başarısızlık, operatörün sistemi çökmüş sanmasına yol açar.
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.getByTestId('kamera-izgarasi')).toBeHidden()
})

test('giriş yapılınca 20 kamera kutucuğu geliyor (K1)', async ({ page }) => {
  await girisYap(page)
  const kutucuklar = page.getByTestId('kamera-kutucugu')
  // K1 kriteri ≥20 eşzamanlı kamera. Webcam (cam-21) ortamda olmayabilir,
  // o yüzden alt sınır kontrolü.
  await expect
    .poll(() => kutucuklar.count(), { timeout: 20_000 })
    .toBeGreaterThanOrEqual(20)
})

test('kameralar HAZIR durumda — akış gerçekten bağlı', async ({ page }) => {
  await girisYap(page)
  const kutucuklar = page.getByTestId('kamera-kutucugu')
  await expect.poll(() => kutucuklar.count()).toBeGreaterThanOrEqual(20)

  // ⚠ Kutucuğun ÇİZİLMESİ akışın çalıştığını göstermez — P-45'in dersi
  // (klipler kesiliyordu, erişilemiyordu). `data-hazir` alım katmanının
  // o kamerayı gerçekten okuyabildiğini söylüyor.
  await expect
    .poll(
      async () => page.locator('[data-testid="kamera-kutucugu"][data-hazir="1"]').count(),
      { timeout: 30_000 },
    )
    .toBeGreaterThanOrEqual(18)
})

test('bir kamera açılınca video + kutu tuvali geliyor', async ({ page }) => {
  await girisYap(page)
  // ⚠ Izgaranın çizilmesi kameraların HAZIR olduğu anlamına gelmiyor:
  // hazır bilgisi WebSocket'ten sonradan geliyor. Beklemeden tıklamak
  // testi zamanlamaya bağımlı (flaky) yapardı — ilk koşuda tam da bu
  // yüzden düştü.
  const hazirlar = page.locator('[data-testid="kamera-kutucugu"][data-hazir="1"]')
  await expect.poll(() => hazirlar.count(), { timeout: 30_000 }).toBeGreaterThan(0)

  // ⚠ `exact: true` şart: kutucukta iki düğme "izle" içeriyor —
  // başlıktaki "izle" ve yer tutucudaki "izlemek için tıkla".
  const ilk = hazirlar.first()
  await ilk.getByRole('button', { name: 'izle', exact: true }).click()

  // Mimari kural 2: video WHEP ile ayrı gelir, kutular ayrı kanaldan
  // gelip TARAYICI canvas'ına çizilir. İkisinin de var olması gerekiyor.
  await expect(ilk.locator('video')).toBeVisible()
  await expect(ilk.locator('canvas')).toBeAttached()
})
