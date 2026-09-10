import { test, expect } from '@playwright/test'
import { readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * DİYAGRAMLARI PNG'YE ÇEVİR — ve çevirirken DOĞRULA.
 *
 * ⭐ NEDEN BİR TEST DOSYASI
 * ------------------------
 * İki iş birden yapıyor:
 *   1. Makale/rapor için 2× ölçekli PNG üretiyor (SVG'yi her dergi
 *      kabul etmiyor).
 *   2. ⚠ ASIL SEBEP: SVG'de metin taşması KODDA GÖRÜNMEZ. Bir <text>
 *      kutusundan taşarsa dosya yine geçerli SVG'dir. Burada gerçek
 *      tarayıcıda ölçülüp taşma varsa test DÜŞÜYOR.
 *
 * Bu, P-77'nin dersinin uygulanması: bir çıktının VAR OLMASI,
 * kullanılabilir olması demek değil. Kontrol, dosyanın yapacağı işi
 * yapmalı — burada "tarayıcıda düzgün görünmek".
 */

// ⚠ ESM: `__dirname` yok. Playwright'ı proje kökünden koşturuyoruz,
// bu yüzden yol `frontend/` göreli veriliyor.
const KAYNAK = resolve(process.cwd(), '../docs/report/diagrams')

test.use({ deviceScaleFactor: 2 })

const dosyalar = readdirSync(KAYNAK).filter((d) => d.endsWith('.svg'))

for (const dosya of dosyalar) {
  test(`diyagram render + tasma kontrolu: ${dosya}`, async ({ page }) => {
    const svg = readFileSync(resolve(KAYNAK, dosya), 'utf-8')

    // viewBox'tan gerçek boyutu al — sayfayı ona göre kur.
    const vb = svg.match(/viewBox="0 0 (\d+) (\d+)"/)
    expect(vb, 'viewBox okunamadi').not.toBeNull()
    const g = Number(vb![1])
    const y = Number(vb![2])

    await page.setViewportSize({ width: g, height: y })
    await page.setContent(
      `<body style="margin:0;background:#fff">${svg}</body>`,
      { waitUntil: 'load' },
    )

    // ─── İKİ AYRI KONTROL ───
    //
    // ⚠ İlk sürüm yalnızca (1)'i yapıyordu ve GERÇEK bir hatayı
    // kaçırdı: 02-kademeli-isleme'de bir etiket sağ panelin ALTINDA
    // kalıyordu. viewBox'ın içindeydi, yani (1) temiz diyordu — ama
    // görüntüde metin yarıda kesiliyordu.
    //
    // Test geçiyordu ve hiçbir şey doğrulamıyordu. P-61'in aynısı:
    // "testin kendisi, test etmediği şeyi test ettiğini söylüyordu."
    // Hatayı ancak PNG'ye gözle bakınca gördüm — bir testin varlığı
    // gözle bakmanın yerini tutmadı.
    const tasanlar = await page.evaluate((genislik) => {
      const kotu: string[] = []
      const metinler = Array.from(document.querySelectorAll('svg text'))
      const kutular = Array.from(document.querySelectorAll('svg rect'))
      const hepsi = Array.from(document.querySelectorAll('svg *'))
      const sira = new Map(hepsi.map((el, i) => [el, i]))

      const kesisiyor = (a: DOMRect | SVGRect, b: DOMRect | SVGRect) =>
        a.x < b.x + b.width &&
        a.x + a.width > b.x &&
        a.y < b.y + b.height &&
        a.y + a.height > b.y

      for (const t of metinler) {
        const kutu = (t as SVGGraphicsElement).getBBox()
        const metin = (t.textContent ?? '').slice(0, 55)

        // (1) viewBox dışına taşma
        if (kutu.x + kutu.width > genislik - 8) {
          kotu.push(`sağa taştı (${Math.round(kutu.x + kutu.width)}px): "${metin}"`)
          continue
        }

        // (2) SONRADAN çizilen dolu bir dikdörtgen metni örtüyor mu?
        //     SVG'de boyama sırası belge sırasıdır: metinden SONRA
        //     gelen opak bir <rect> onu gizler. (Metinden ÖNCE gelen
        //     kutu normaldir — kutunun içine yazıyoruz.)
        const benimSiram = sira.get(t) ?? 0
        for (const r of kutular) {
          if ((sira.get(r) ?? 0) < benimSiram) continue
          const dolgu = getComputedStyle(r).fill
          if (dolgu === 'none' || dolgu === 'transparent') continue
          if (kesisiyor(kutu, (r as SVGGraphicsElement).getBBox())) {
            kotu.push(`üstü örtüldü: "${metin}"`)
            break
          }
        }
      }
      return kotu
    }, g)

    if (tasanlar.length) {
      console.log(`\n⚠ ${dosya} — SAGA TASAN METINLER:\n  ${tasanlar.join('\n  ')}`)
    }

    await page.locator('svg').screenshot({
      path: resolve(KAYNAK, dosya.replace('.svg', '.png')),
    })

    expect(tasanlar, `${dosya}: metin viewBox disina tasiyor`).toEqual([])
  })
}
