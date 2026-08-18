/** Kutu/video hizalaması — zaman ekseni testleri.
 *
 * ⚠ NEDEN BU DOSYA ÖNCELİKLİ
 * --------------------------
 * Burada üç ayrı AN var ve karıştırmak doğrudan hataya götürüyor:
 *
 *     yakalanma : karenin kameradan alındığı an   ← GERÇEK zaman ekseni
 *     varış     : sonucun tarayıcıya ulaştığı an  (yakalanma + gecikme)
 *     şimdi     : ekrana çizdiğimiz an
 *
 * P-26'da bu üçü karıştırıldı ve İKİ ayrı hata çıktı: kaydırıcı ters
 * yöne çalışıyordu, tampon varış anına göre indeksleniyordu. Kullanıcı
 * "bazen yetişiyor bazen yetişemiyor" diye bildirdi; sebebi gözle
 * görülemezdi çünkü kutular DOĞRU görünüyordu, sadece yanlış andaydı.
 *
 * Bu testler o iki hatanın gerilemesini ve kod incelemesinde bulunan
 * üçüncü hatayı (negatif oran) kilitliyor.
 */

import { describe, expect, it } from 'vitest'
import { BUFFER_SIZE, captureTime, frameAt } from './sync'
import type { Detection, TimedResult } from '../types'

// ─── Yardımcılar ──────────────────────────────────────────────

function det(
  id: number,
  x: number,
  y: number,
  v?: [number, number],
  kp?: [number, number, number][],
): Detection {
  return { bbox: [x, y, x + 50, y + 100], conf: 0.9, cls: 0, id, v, kp }
}

/** Belirli bir YAKALANMA anına ait sonuç üretir.
 *
 * `rx` (varış) = yakalanma + gecikme. Testler yakalanma anını
 * doğrudan verebilsin diye ters hesaplanıyor.
 */
function sonuc(captureMs: number, latMs: number, detections: Detection[]): TimedResult {
  return {
    type: 'frame',
    cam: 'cam-01',
    ts: captureMs / 1000,
    seq: Math.round(captureMs),
    w: 1280,
    h: 720,
    count: detections.length,
    motion: 0.05,
    gate: 'motion',
    lat: latMs,
    detections,
    rx: captureMs + latMs,
  }
}

// ══════════════════════════════════════════════════════════════
//  Yakalanma anı hesabı
// ══════════════════════════════════════════════════════════════

describe('captureTime', () => {
  it('varış anından gecikmeyi çıkarıyor', () => {
    expect(captureTime(sonuc(1000, 200, []))).toBe(1000)
  })

  it('gecikme yoksa varış anına düşüyor (eski sürüm mesajları)', () => {
    const s = sonuc(1000, 200, [])
    delete (s as { lat?: number }).lat
    expect(captureTime(s)).toBe(1200) // rx olduğu gibi
  })

  it('⚠ P-26: DALGALANAN gecikme kareler arası GERÇEK mesafeyi bozmuyor', () => {
    // İkisi de 250 ms arayla yakalandı ama gecikmeleri çok farklı.
    // Varış anına göre hesaplayan kod bunları 50 ms arayla sanıyordu
    // ve kişiyi 5 kat hızlı görüp kutuyu fırlatıyordu.
    const a = sonuc(1000, 400, []) // varış 1400
    const b = sonuc(1250, 200, []) // varış 1450

    expect(b.rx - a.rx).toBe(50) // varış farkı YANILTICI
    expect(captureTime(b) - captureTime(a)).toBe(250) // gerçek fark
  })
})

// ══════════════════════════════════════════════════════════════
//  Boş tampon
// ══════════════════════════════════════════════════════════════

describe('frameAt — veri yokken', () => {
  it('boş tamponda null dönüyor, patlamıyor', () => {
    expect(frameAt([], 1000, 100)).toBeNull()
  })
})

// ══════════════════════════════════════════════════════════════
//  İleri tahmin (video tamponlanmamış)
// ══════════════════════════════════════════════════════════════

describe('frameAt — ileri tahmin', () => {
  it('hedef tam sonucun üstündeyse tahmin yapılmıyor', () => {
    const buffer = [sonuc(1000, 0, [det(1, 100, 100, [40, 0])])]
    const f = frameAt(buffer, 1000, 0)!

    expect(f.mode).toBe('exact')
    expect(f.detections[0].bbox[0]).toBe(100)
  })

  it('hız vektörüyle İLERİ taşıyor', () => {
    // 500 ms sonrası, 40 px/sn yatay hız → +20 px
    const buffer = [sonuc(1000, 0, [det(1, 100, 100, [40, 0])])]
    const f = frameAt(buffer, 1500, 0)!

    expect(f.mode).toBe('predicted')
    expect(f.detections[0].bbox[0]).toBeCloseTo(120, 5)
    expect(f.detections[0].bbox[2]).toBeCloseTo(170, 5) // kutu genişliği korunuyor
  })

  it('hızı olmayan tespit yerinde kalıyor', () => {
    const buffer = [sonuc(1000, 0, [det(1, 100, 100)])]
    const f = frameAt(buffer, 1600, 0)!
    expect(f.detections[0].bbox[0]).toBe(100)
  })

  it('⚠ tahmin ÜST SINIRDA kesiliyor — uzun mesafede donuk göstermek daha dürüst', () => {
    // Hız vektörü DOĞRUSAL bir tahmin. Kişi dönerse, durursa ya da
    // hızlanırsa tahmin bozulur; 700 ms'ten sonra kutu yanlış yerde olur.
    const buffer = [sonuc(1000, 0, [det(1, 100, 100, [100, 0])])]

    const sinirda = frameAt(buffer, 1700, 0)! // tam 700 ms
    const cokIleri = frameAt(buffer, 5000, 0)! // 4 saniye

    expect(sinirda.detections[0].bbox[0]).toBeCloseTo(170, 5)
    // Üst sınır aşıldığında kutu 700 ms'lik konumda DONUYOR
    expect(cokIleri.detections[0].bbox[0]).toBeCloseTo(170, 5)
  })

  it('iskelet de hız vektörüyle taşınıyor', () => {
    const kp: [number, number, number][] = [[110, 120, 0.9], [130, 140, 0.8]]
    const buffer = [sonuc(1000, 0, [det(1, 100, 100, [40, 20], kp)])]
    const f = frameAt(buffer, 1500, 0)!

    expect(f.detections[0].kp![0][0]).toBeCloseTo(130, 5) // 110 + 20
    expect(f.detections[0].kp![0][1]).toBeCloseTo(130, 5) // 120 + 10
    expect(f.detections[0].kp![0][2]).toBe(0.9) // güven DEĞİŞMEZ
  })
})

// ══════════════════════════════════════════════════════════════
//  Ara değerleme (video tamponlanmış)
// ══════════════════════════════════════════════════════════════

describe('frameAt — ara değerleme', () => {
  const buffer = [
    sonuc(1000, 100, [det(1, 100, 100)]),
    sonuc(1250, 100, [det(1, 200, 200)]),
  ]

  it('iki gerçek sonuç arasını harmanlıyor', () => {
    // Video 250 ms tamponlanmış, şimdi 1375 → hedef 1125 = tam ortası
    const f = frameAt(buffer, 1375, 250)!

    expect(f.mode).toBe('interpolated')
    expect(f.detections[0].bbox[0]).toBeCloseTo(150, 5)
    expect(f.detections[0].bbox[1]).toBeCloseTo(150, 5)
  })

  it('kimliği eşleşmeyen tespit KAYBOLMUYOR', () => {
    // Kimliksiz tespit = takipçi henüz onaylamadı (P-13). Gizlemek
    // yanlış olurdu: kişi orada, sadece kimliği bir sonraki karede
    // gelecek.
    const kimliksiz: Detection = { bbox: [10, 10, 60, 110], conf: 0.5, cls: 0 }
    const b = [
      sonuc(1000, 100, [det(1, 100, 100)]),
      sonuc(1250, 100, [det(1, 200, 200), kimliksiz]),
    ]
    const f = frameAt(b, 1375, 250)!

    expect(f.detections).toHaveLength(2)
    expect(f.detections.some((d) => d.id === undefined)).toBe(true)
  })

  it('⚠ güveni DÜŞÜK keypoint ara değerlenmiyor', () => {
    // Görünmeyen bir uzvu "yolda" göstermek, olmayan bir duruşu varmış
    // gibi göstermektir (PLAN.md §6.2).
    const oncekiKp: [number, number, number][] = [[100, 100, 0.1]]
    const sonrakiKp: [number, number, number][] = [[200, 200, 0.9]]
    const b = [
      sonuc(1000, 100, [det(1, 100, 100, undefined, oncekiKp)]),
      sonuc(1250, 100, [det(1, 200, 200, undefined, sonrakiKp)]),
    ]
    const f = frameAt(b, 1375, 250)!

    // Harmanlansaydı 150 olurdu; güven düşük olduğu için SON değer alınıyor
    expect(f.detections[0].kp![0][0]).toBe(200)
  })

  it('⚠ B3 GERİLEMESİ: hedef tamponun tamamından eskiyse kutu GERİYE FIRLAMIYOR', () => {
    // Kod incelemesinde bulunan hata: hedef en eski sonuçtan da eskiyse
    // döngü hiçbir aralık bulamıyor, `before = buffer[0]` kalıyor ve
    // oran NEGATİF çıkıyordu. `blend` kutuyu iki gerçek nokta arasında
    // değil, hareketin TERS yönünde fırlatıyordu.
    //
    // Ulaşılabilir: analiz durur/yavaşlarsa ve video tamponu yüksekse.
    const f = frameAt(buffer, 1100, 5000)! // hedef 1100-5000 = çok geçmiş

    const x = f.detections[0].bbox[0]
    // Kutu iki gerçek konum ARASINDA kalmalı (100 ile 200)
    expect(x).toBeGreaterThanOrEqual(100)
    expect(x).toBeLessThanOrEqual(200)
  })

  it('hedef geleceğe taşarsa oran 1i geçmiyor', () => {
    // Simetrik koruma: en yeni sonuçtan sonrası ara değerleme değil,
    // tahmin dalına düşmeli.
    const f = frameAt(buffer, 2000, 0)!
    expect(f.mode).toBe('predicted')
  })

  it('kaynak kare boyutu SON sonuçtan alınıyor', () => {
    // Kameralar farklı çözünürlükte olabilir; tarayıcı ölçekleme için
    // buna muhtaç.
    const f = frameAt(buffer, 1375, 250)!
    expect(f.w).toBe(1280)
    expect(f.h).toBe(720)
  })
})

// ══════════════════════════════════════════════════════════════
//  Bayatlama
// ══════════════════════════════════════════════════════════════

describe('frameAt — bayatlama', () => {
  it('en yeni sonucun yaşını bildiriyor', () => {
    // Panel bu değerle "analiz durdu" uyarısı gösteriyor.
    const buffer = [sonuc(1000, 100, [det(1, 100, 100)])] // varış 1100
    const f = frameAt(buffer, 6100, 0)!
    expect(f.ageMs).toBeCloseTo(5000, 5)
  })
})

describe('sabitler', () => {
  it('tampon derinliği 4 FPSte ~3 saniyelik geçmiş veriyor', () => {
    // Ara değerleme için en az iki gerçek nokta gerekiyor; 3 saniyelik
    // pencere video tamponu yükseltildiğinde de yetiyor.
    expect(BUFFER_SIZE).toBeGreaterThanOrEqual(8)
    expect(BUFFER_SIZE / 4).toBeGreaterThanOrEqual(2)
  })
})
