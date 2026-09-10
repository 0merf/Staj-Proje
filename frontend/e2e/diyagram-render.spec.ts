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

    // ─── Taşma kontrolü: her <text> viewBox içinde mi ───
    const tasanlar = await page.evaluate((genislik) => {
      const kotu: string[] = []
      document.querySelectorAll('svg text').forEach((t) => {
        const kutu = (t as SVGGraphicsElement).getBBox()
        if (kutu.x + kutu.width > genislik - 8) {
          kotu.push(
            `${Math.round(kutu.x + kutu.width)}px: "${(t.textContent ?? '').slice(0, 60)}"`,
          )
        }
      })
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
