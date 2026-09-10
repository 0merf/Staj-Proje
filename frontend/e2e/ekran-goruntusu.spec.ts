import { test } from '@playwright/test'
import { mkdirSync } from 'node:fs'

/**
 * RAPOR EKRAN GÖRÜNTÜLERİ — elle değil, OTOMATİK.
 *
 * ⭐ NEDEN PLAYWRIGHT İLE
 * ----------------------
 * Elle alınan ekran görüntüsü bir kez alınır ve rapor güncellenirken
 * bayatlar — arayüz değişir, görüntü eski kalır ve okuyucuya artık var
 * olmayan bir sistem gösterilir. Bu proje bunun bir örneğini zaten
 * yaşadı: CLAUDE.md "zaman çizelgesi ve kamera detayı sayfaları YOK"
 * diyordu, oysa panelde ikisi de VARDI (belge bayattı).
 *
 * Bu betik her koşuda yeniden üretiyor: rapor ile sistem arasındaki
 * sapma imkânsız hale geliyor (mimari kural 0).
 *
 * ⚠ ÖN KOŞUL: sistem ayakta (`start_all.ps1`) ve `.env.e2e` dolu.
 *
 * Kullanım:
 *   npx playwright test e2e/ekran-goruntusu.spec.ts
 *   → docs/report/screenshots/*.png
 */

const KULLANICI = process.env.E2E_USER ?? 'e2e-test'
const PAROLA = process.env.E2E_PASSWORD ?? ''
const DIZIN = '../docs/report/screenshots'

// ⚠ VARSAYILAN OLARAK KOŞMUYOR (10.09).
//
// Kullanıcının isteği: *"her koşuda yeni bir görsel çıkarmaya gerek
// yok, kapat o özelliği. 1 kere çıkarırız, eğer değiştirirsek yeniden
// çıkartırız — ama NİHAİ MODELDEN çıkarttırırız."*
//
// Haklı ve gerekçesi teknik: her koşu 7.6 MB'lık yeni PNG üretiyordu
// ve hepsi git geçmişine kalıcı olarak giriyordu. Dahası rapora
// girecek görüntülerin TEK bir sürümden gelmesi gerekiyor; her koşuda
// yenilemek, raporun farklı bölümlerinde farklı sistem sürümlerinin
// görüntülerini kullanma riski taşıyor.
//
// Elle üretmek için:
//   $env:EKRAN_GORUNTUSU="1"; npx playwright test e2e/ekran-goruntusu.spec.ts
test.skip(
  !process.env.EKRAN_GORUNTUSU,
  'Rapor görüntüleri elle üretiliyor — EKRAN_GORUNTUSU=1 ile çalıştırın.',
)

// ⚠ Baskı için 2× ölçek: makale PDF'inde 1× görüntüler bulanık çıkıyor.
test.use({ viewport: { width: 1600, height: 950 }, deviceScaleFactor: 2 })

test('rapor ekran görüntülerini üret', async ({ page }) => {
  test.setTimeout(240_000)
  mkdirSync(DIZIN, { recursive: true })

  // ─── 1. Giriş ekranı (kimlik doğrulama var, G01) ───
  await page.goto('/app')
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${DIZIN}/01-giris.png` })

  await page.locator('input[autocomplete="username"]').fill(KULLANICI)
  await page.locator('input[type="password"]').fill(PAROLA)
  await page.getByRole('button', { name: /giriş/i }).click()
  await page.getByTestId('kamera-izgarasi').waitFor()

  // Kameraların HAZIR bilgisi WebSocket'ten sonra geliyor.
  const hazirlar = page.locator('[data-testid="kamera-kutucugu"][data-hazir="1"]')
  for (let i = 0; i < 30 && (await hazirlar.count()) < 20; i++) {
    await page.waitForTimeout(1000)
  }

  // ─── 2. 20 kameralı ızgara — kapalı (K1: eşzamanlı kamera) ───
  await page.screenshot({ path: `${DIZIN}/02-izgara-20-kamera.png` })

  // ─── 3. Birkaç kamera açık: canlı video + kutular ───
  const sayi = Math.min(await hazirlar.count(), 6)
  for (let i = 0; i < sayi; i++) {
    await hazirlar.nth(i).getByRole('button', { name: 'izle', exact: true }).click()
    await page.waitForTimeout(400)
  }
  // İlk karelerin gelmesi + kutuların çizilmesi için bekle.
  await page.waitForTimeout(12_000)
  await page.screenshot({ path: `${DIZIN}/03-canli-kutular.png` })

  // ─── 4. Tek kamera yakın plan — ⚠ İÇİNDE KİŞİ OLAN kutucuk ───
  //
  // İlk sürüm `hazirlar.first()` alıyordu ve boş bir otoparkı
  // yakaladı: rapora "kutu çizimi" örneği diye konacak görüntüde
  // hiç kutu yoktu. Kutucuk metnindeki "N kişi" sayacına bakıp
  // gerçekten tespit olan biri seçiliyor.
  const acik = page.locator('[data-testid="kamera-kutucugu"]:has(video)')
  let hedefKutu = acik.first()
  const adet = await acik.count()
  for (let i = 0; i < adet; i++) {
    const metin = (await acik.nth(i).innerText()) ?? ''
    const m = metin.match(/(\d+)\s+kişi/)
    if (m && Number(m[1]) > 0) {
      hedefKutu = acik.nth(i)
      break
    }
  }
  await hedefKutu.scrollIntoViewIfNeeded()
  await page.waitForTimeout(1500)
  await hedefKutu.screenshot({ path: `${DIZIN}/04-kutucuk-yakin.png` })

  // ─── 5. Zaman çizelgesi sayfası ───
  await page.getByRole('button', { name: 'Zaman Çizelgesi', exact: true }).click()
  await page.waitForTimeout(3000)
  await page.screenshot({ path: `${DIZIN}/05-zaman-cizelgesi.png` })

  // ─── 6. Kamera detayı sayfası ───
  await page.getByRole('button', { name: 'Kamera Detayı', exact: true }).click()
  await page.waitForTimeout(3000)
  await page.screenshot({ path: `${DIZIN}/06-kamera-detayi.png` })

  console.log(`\n⭐ Ekran görüntüleri yazıldı → docs/report/screenshots/`)
})
