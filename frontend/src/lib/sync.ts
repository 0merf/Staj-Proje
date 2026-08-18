/** Kutuları videoyla hizalama.
 *
 * ZAMAN ÇİZELGESİ — önce bunu netleştirelim
 * -----------------------------------------
 * Üç farklı an var ve karıştırmak doğrudan hataya götürüyor:
 *
 *   yakalanma anı : karenin kameradan alındığı an   ← GERÇEK zaman ekseni
 *   varış anı     : sonucun tarayıcıya ulaştığı an  (yakalanma + gecikme)
 *   şimdi         : ekrana çizdiğimiz an
 *
 * ⚠ İLK SÜRÜMÜN HATASI: tamponu **varış anına** göre indeksliyordu.
 * Boru hattı gecikmesi sabit olmadığı için (181-465 ms arası
 * dalgalanıyor) düzenli aralıklarla yakalanan kareler DÜZENSİZ
 * aralıklarla varıyor. Zaman ekseni çarpılınca kutular hızlanıp
 * yavaşlıyordu — "bazen yetişiyor, bazen yetişemiyor" tam olarak buydu.
 *
 * Sunucu artık her sonuca kendi ölçtüğü gecikmeyi ekliyor (`lat`),
 * yani yakalanma anını hesaplayabiliyoruz:
 *
 *     yakalanma ≈ varış − gecikme
 *
 * Tampon bu eksene göre sıralanınca kareler arası mesafe gerçekten
 * eşit oluyor ve hareket düzgünleşiyor.
 *
 * NEDEN İLERİ TAHMİN ZORUNLU
 * --------------------------
 * Video sahneyi `now − 13 ms` anında gösteriyor (WebRTC çok hızlı).
 * Analiz ise `now − 465 ms` anına ait. Yani ekranda gördüğümüz ana
 * ait bir analiz sonucu HENÜZ YOK — o kare daha yeni işleniyor.
 *
 * Dolayısıyla kutuları hizalamanın tek yolu, kişinin ŞU AN nerede
 * olduğunu hız vektöründen tahmin etmek. Ara değerleme (iki gerçek
 * nokta arasını doldurmak) ancak videoyu geciktirirsek mümkün olur —
 * o da ayrı bir iş (CALISMA.md §11.1, seçenek A1).
 *
 * ⚠ İLK SÜRÜMÜN İKİNCİ HATASI: kaydırıcı "geriye bak" diye
 * uygulanıyordu. Analiz zaten geride olduğu için bu, kutuları daha da
 * geriye atıyordu — kullanıcı kaydırıcıyı artırdıkça sorun büyüyordu.
 * Şimdi kaydırıcı "ne kadar İLERİ tahmin et" anlamına geliyor.
 */

import type { Detection, TimedResult } from '../types'

/** İleri tahminin güvenli sayıldığı en uzun süre.
 *
 * Hız vektörü doğrusal bir tahmindir: kişi dönerse, durursa ya da
 * hızlanırsa tahmin bozulur. Uzun mesafede kutu yanlış yerde olur —
 * o zaman donuk göstermek daha dürüst. */
const MAX_LEAD_MS = 700

/** Tampon derinliği. 4 FPS'te 12 sonuç ≈ 3 saniyelik geçmiş. */
export const BUFFER_SIZE = 12

const lerp = (a: number, b: number, t: number) => a + (b - a) * t

/**
 * Bir sonucun YAKALANMA anını tarayıcı saatinde verir.
 *
 * `lat` sunucunun ölçtüğü boru hattı gecikmesi. Yoksa (eski sürüm)
 * varış anına düşüyoruz — bozulmaz, sadece daha az düzgün olur.
 */
export function captureTime(result: TimedResult): number {
  return result.rx - (result.lat ?? 0)
}

/** İki tespiti oranla harmanlar (iki gerçek nokta arasında). */
function blend(from: Detection, to: Detection, t: number): Detection {
  const bbox: [number, number, number, number] = [
    lerp(from.bbox[0], to.bbox[0], t),
    lerp(from.bbox[1], to.bbox[1], t),
    lerp(from.bbox[2], to.bbox[2], t),
    lerp(from.bbox[3], to.bbox[3], t),
  ]

  let kp = to.kp
  if (from.kp && to.kp && from.kp.length === to.kp.length) {
    kp = to.kp.map((point, i) => {
      const prev = from.kp![i]
      // Güveni düşük keypoint ARA DEĞERLENMEZ: görünmeyen uzvu
      // "yolda" göstermek olmayan bir duruş uydurmaktır (PLAN §6.2).
      if (prev[2] < 0.3 || point[2] < 0.3) return point
      return [lerp(prev[0], point[0], t), lerp(prev[1], point[1], t), point[2]] as
        [number, number, number]
    })
  }
  return { ...to, bbox, kp }
}

/** Bir tespiti hız vektörüyle ileri taşır. */
function lead(det: Detection, seconds: number): Detection {
  if (!det.v || (det.v[0] === 0 && det.v[1] === 0)) return det
  const dx = det.v[0] * seconds
  const dy = det.v[1] * seconds
  return {
    ...det,
    bbox: [det.bbox[0] + dx, det.bbox[1] + dy, det.bbox[2] + dx, det.bbox[3] + dy],
    kp: det.kp?.map((p) => [p[0] + dx, p[1] + dy, p[2]] as [number, number, number]),
  }
}

export interface RenderFrame {
  detections: Detection[]
  w: number
  h: number
  count: number
  /** En yeni sonucun yaşı (ms) — bayatsa kullanıcıya söylüyoruz. */
  ageMs: number
  mode: 'interpolated' | 'predicted' | 'exact'
}

/**
 * `now` anında ekrana çizilecek kareyi üretir.
 *
 * @param buffer   Sonuçlar (varış sırasına göre)
 * @param now      performance.now()
 * @param leadMs   Videonun ÖLÇÜLEN gecikmesi (ms). Ekranda görünen
 *                 sahnenin ne kadar geride olduğu. Büyükse ara
 *                 değerleme, küçükse ileri tahmin devreye girer.
 */
export function frameAt(
  buffer: TimedResult[],
  now: number,
  leadMs: number,
): RenderFrame | null {
  if (buffer.length === 0) return null

  const newest = buffer[buffer.length - 1]
  const newestCapture = captureTime(newest)

  // Hedef: ŞU AN EKRANDA GÖRÜNEN karenin yakalanma anı.
  //
  // Video `videoLatencyMs` kadar geriden geliyor, yani ekranda
  // gördüğümüz sahne `now - videoLatencyMs` anına ait. Analiz sonucunu
  // da o ana getirmemiz gerekiyor.
  //
  // Video TAMPONLANMIŞSA (setVideoBuffer) videoLatency analiz
  // gecikmesini aşar ve hedef, elimizdeki en yeni sonucun GERİSİNDE
  // kalır → iki gerçek ölçüm arasında ARA DEĞERLEME yapabiliriz.
  // Tamponlanmamışsa hedef ileride kalır → tahmine düşeriz.
  const target = now - leadMs

  if (target >= newestCapture) {
    const ahead = Math.min(target - newestCapture, MAX_LEAD_MS) / 1000
    return {
      detections: ahead > 0 ? newest.detections.map((d) => lead(d, ahead)) : newest.detections,
      w: newest.w,
      h: newest.h,
      count: newest.count,
      ageMs: now - newest.rx,
      mode: ahead > 0 ? 'predicted' : 'exact',
    }
  }

  // Hedef geçmişte kalıyorsa (kullanıcı payı negatifse ya da video
  // geciktirilmişse) iki gerçek sonuç arasında ara değerleyebiliriz.
  let before = buffer[0]
  let after = newest
  for (let i = 0; i < buffer.length - 1; i++) {
    if (captureTime(buffer[i]) <= target && target <= captureTime(buffer[i + 1])) {
      before = buffer[i]
      after = buffer[i + 1]
      break
    }
  }

  // ⚠ t [0,1] ARALIĞINA KISILIYOR
  // Hedef, tamponun EN ESKİSİNDEN de eskiyse yukarıdaki döngü hiçbir
  // aralık bulamaz ve `before = buffer[0]` olarak kalır. O durumda
  // `target - captureTime(before)` NEGATİF çıkar; kısılmazsa `blend`
  // kutuyu iki gerçek nokta arasında değil, hareketin TERS yönünde
  // 3 saniyelik tampon boyu kadar uzağa fırlatır.
  //
  // Ne zaman olur: analiz durur/yavaşlarsa (sonuç gelmiyor) ve video
  // tamponu yüksekse. `STALE_MS` kontrolü bunu kısmen yakalıyor ama
  // tam örtmüyor — kısma ucuz ve kesin.
  const span = captureTime(after) - captureTime(before)
  const raw = span > 0 ? (target - captureTime(before)) / span : 1
  const t = Math.max(0, Math.min(1, raw))

  // Kimliği olan izleri eşleştirip ara değerliyoruz. Kimliksiz
  // tespitler (takipçi henüz onaylamadı — P-13) eşleştirilemez ama
  // KAYBOLMAZ.
  const previous = new Map<number, Detection>()
  for (const d of before.detections) {
    if (d.id !== undefined) previous.set(d.id, d)
  }

  return {
    detections: after.detections.map((d) => {
      if (d.id === undefined) return d
      const prev = previous.get(d.id)
      return prev ? blend(prev, d, t) : d
    }),
    w: after.w,
    h: after.h,
    count: after.count,
    ageMs: now - after.rx,
    mode: 'interpolated',
  }
}
