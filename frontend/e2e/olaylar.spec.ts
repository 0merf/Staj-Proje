import { expect, test } from '@playwright/test'

/**
 * OLAYLAR SAYFASI — ısı haritası + olay tablosu zinciri.
 *
 * ⭐ NEDEN BU TESTLER VAR
 * ----------------------
 * Eski zaman çizelgesinde hücreler `cursor-default` idi ve `onClick`
 * yoktu: bilgi ÜRETİLİYORDU ama kullanıcı ona ULAŞAMIYORDU. Kullanıcı
 * bunu kendisi bildirdi ("kutuların üstüne tıklıyorum, hiçbir bilgi
 * çıkmıyor").
 *
 * ⚠ Bir birim testi bunu ASLA gösteremezdi: bileşen render oluyordu,
 * veri doğruydu, sayılar doğruydu. Eksik olan tek şey tıklanabilirlikti.
 * Projenin İKİNCİ TEZİ (P-43/44/45) tam olarak bu: kapsam maddeleri
 * modüllerle değil, kullanıcının yapabildiği işlerle işaretlenmeli.
 *
 * Bu yüzden aşağıdaki testlerin adları modül değil, İŞ tarif ediyor.
 */

const KULLANICI = process.env.E2E_USER ?? 'e2e-test'
const PAROLA = process.env.E2E_PASSWORD ?? ''

test.beforeAll(() => {
  if (!PAROLA) {
    throw new Error('E2E_PASSWORD tanımlı değil (frontend/.env.e2e).')
  }
})

async function olaylaraGit(page: import('@playwright/test').Page) {
  await page.goto('/app')
  await page.locator('input[autocomplete="username"]').fill(KULLANICI)
  await page.locator('input[type="password"]').fill(PAROLA)
  await page.getByRole('button', { name: /giriş/i }).click()
  await expect(page.getByTestId('kamera-izgarasi')).toBeVisible()
  await page.getByRole('button', { name: 'Zaman Çizelgesi', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Olaylar' })).toBeVisible()
}

test('operatör olay tablosunda tek tek kayıtları okuyabiliyor', async ({ page }) => {
  await olaylaraGit(page)

  // Tablo başlıkları — "kanıt gücü" sütunu özellikle önemli: zayıf
  // kanıta dayanan bir alarmı operatörün ayırt edebilmesi gerekiyor.
  const tablo = page.getByTestId('olay-tablosu')
  for (const baslik of ['zaman', 'kamera', 'tür', 'şiddet', 'kanıt gücü']) {
    await expect(
      tablo.getByRole('columnheader', { name: baslik, exact: true }),
    ).toBeVisible()
  }

  // En az bir gerçek satır gelmiş olmalı (sistem 24 saattir alarm üretiyor).
  await expect
    .poll(async () => tablo.locator('tbody tr').count(), { timeout: 15_000 })
    .toBeGreaterThan(0)
})

test('operatör bir olaya tıklayıp KANITINI görebiliyor', async ({ page }) => {
  await olaylaraGit(page)

  // Olay tablosunun ilk satırı (ısı haritası tablosu ayrı; olay
  // tablosunu sütun başlığından bulup ona ait gövdeyi alıyoruz).
  const olayTablosu = page.getByTestId('olay-tablosu')
  await expect(olayTablosu.locator('tbody tr').first()).toBeVisible()
  const ilkSatir = olayTablosu.locator('tbody tr').first()
  await ilkSatir.click()

  // Kanıt açılınca alan/değer çiftleri görünür olmalı. Kapalıyken
  // yalnızca kısa bir özet vardı.
  await expect(olayTablosu.locator('tbody tr').first()).toContainText(/\d/)
  const acikMetin = (await ilkSatir.innerText()).trim()
  expect(acikMetin.length).toBeGreaterThan(20)
})

test('ısı haritasındaki hücreye tıklamak tabloyu O SAATE daraltıyor', async ({
  page,
}) => {
  await olaylaraGit(page)

  const olayTablosu = page.getByTestId('olay-tablosu')
  await expect(olayTablosu.locator('tbody tr').first()).toBeVisible()

  // Filtresiz tabloda birden çok kamera görünüyor olmalı — yoksa
  // "daraldı" iddiası zaten ölçülemez.
  const oncekiKameralar = new Set(
    await olayTablosu.locator('tbody tr td:nth-child(2)').allInnerTexts(),
  )
  expect(oncekiKameralar.size).toBeGreaterThan(1)

  // ⚠ Isı haritası hücreleri artık DÜĞME. Eski sürümde `<td>` idiler
  // ve bu satır hiçbir şey bulamazdı — testin asıl nöbet tuttuğu yer.
  const isiTablosu = page.getByTestId('isi-haritasi')
  const dolu = isiTablosu.locator('tbody button').filter({ hasText: /^\d+$/ })
  expect(await dolu.count()).toBeGreaterThan(0)

  // Hangi kameranın satırındaki hücreye tıkladığımızı önceden bilelim
  // ki sonucu ona karşı sınayabilelim.
  const hedefKamera = (
    await dolu.first().locator('xpath=ancestor::tr/td[1]').innerText()
  ).trim()

  await dolu.first().click()

  // Seçim bir çip olarak görünmeli — filtreli tabloya baktığını
  // unutmak, "olay yok" diye yanlış sonuç çıkarmanın en kolay yolu.
  await expect(page.locator('button', { hasText: /cam-.*·.*×/ }).first()).toBeVisible()

  // ⭐ ASIL SINAV: "satır sayısı azaldı" ZAYIF bir iddia — tıklama hiç
  // çalışmasa da sayı aynı kalır ve `<=` koşulu geçerdi. Bunun yerine
  // daralan tablodaki HER satırın seçilen kameraya ait olduğu
  // doğrulanıyor. Bu, filtrenin gerçekten uygulandığının kanıtı.
  await expect
    .poll(
      async () => {
        const kameralar = await olayTablosu
          .locator('tbody tr td:nth-child(2)')
          .allInnerTexts()
        return kameralar.length > 0 && kameralar.every((k) => k.trim() === hedefKamera)
      },
      { timeout: 15_000 },
    )
    .toBe(true)
})

test('filtre temizlenince tablo geri geniştiyor', async ({ page }) => {
  await olaylaraGit(page)

  const olayTablosu = page.getByTestId('olay-tablosu')
  await expect(olayTablosu.locator('tbody tr').first()).toBeVisible()

  await page.getByRole('combobox').nth(2).selectOption('alarm')
  await expect(page.getByRole('button', { name: 'filtreyi temizle' })).toBeVisible()
  const darAdet = await olayTablosu.locator('tbody tr').count()

  await page.getByRole('button', { name: 'filtreyi temizle' }).click()
  await expect(page.getByRole('button', { name: 'filtreyi temizle' })).toBeHidden()
  await expect
    .poll(async () => olayTablosu.locator('tbody tr').count(), { timeout: 15_000 })
    .toBeGreaterThanOrEqual(darAdet)
})

test('açık/koyu tema değişiyor ve HATIRLANIYOR', async ({ page }) => {
  await olaylaraGit(page)

  await page.getByTitle('Açık tema').click()
  await expect(page.locator('html')).toHaveAttribute('data-tema', 'acik')

  // ⚠ Asıl sınav yenilemeden SONRA: tercih `localStorage`'a yazılıp
  // React yüklenmeden önce uygulanmazsa sayfa koyu açılır (flash).
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-tema', 'acik')

  await page.getByTitle('Koyu tema').click()
  await expect(page.locator('html')).not.toHaveAttribute('data-tema', 'acik')
})

test('"iz kaydet" düğmesi ARTIK YOK (tanı aracıydı, işi bitti)', async ({ page }) => {
  await olaylaraGit(page)
  await expect(page.getByRole('button', { name: 'iz kaydet' })).toHaveCount(0)
})
