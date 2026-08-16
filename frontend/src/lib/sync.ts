/** Kutuları videoyla hizalama ve ara değerleme.
 *
 * PROBLEM
 * -------
 * Video ve analiz sonuçları tarayıcıya iki ayrı yoldan geliyor:
 *
 *   video    : MediaMTX ──WebRTC──► <video>        ~200-500 ms
 *   kutular  : alım → GPU → Valkey → WS → canvas   ~273 ms (ölçüldü)
 *
 * İkisini hizalayan doğal bir mekanizma yok. Kutular videodan önce
 * ya da sonra gelir; fark sabit de değildir.
 *
 * ÇÖZÜM: GERİYE BAKARAK ÇİZ
 * -------------------------
 * Sonuçları tamponda tutuyoruz ve ekrana ŞU ANI değil, `now - offset`
 * anını çiziyoruz. Bunun iki faydası var:
 *
 * 1. **Hizalama.** Offset'i videonun gecikmesine ayarlayınca kutular
 *    videoyla aynı ana ait olur.
 *
 * 2. **Ara değerleme (asıl kazanç).** Geçmişe baktığımız için o an
 *    için İKİ gerçek tespit de elimizde olur — öncesi ve sonrası.
 *    Kutuyu körlemesine ileri tahmin etmek (ekstrapolasyon) yerine
 *    iki bilinen nokta arasında ara değerliyoruz (interpolasyon).
 *
 *    Fark önemli: tespit kamera başına 4 FPS yapılıyor, yani kareler
 *    arası 250 ms. Ekstrapolasyonda kişi hızlanır/yavaşlar/dönerse
 *    kutu boşluğu gösterir. İnterpolasyonda kutu iki gerçek konum
 *    arasında ilerler — kişi ne yaptıysa onu takip eder.
 *
 * Offset 0 iken davranış eskisi gibidir (ileri tahmin), yani
 * kullanıcı isterse kapatabilir.
 */

import type { Detection, TimedResult } from '../types'

/** Ekstrapolasyonun güvenli sayıldığı en uzun süre.
 * Bunun ötesinde hız bilgisi eskir; yanlış yerde kutu göstermektense
 * kutuyu olduğu yerde dondurmak yeğdir. */
const MAX_EXTRAPOLATE_MS = 500

/** Tampon derinliği. 4 FPS'te 12 sonuç ≈ 3 saniyelik geçmiş —
 * en büyük offset'in çok üstünde, ama bellekte hiçbir şey değil. */
export const BUFFER_SIZE = 12

const lerp = (a: number, b: number, t: number) => a + (b - a) * t

/** İki tespitin kutusunu ve iskeletini oranla harmanlar. */
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
      // Güveni DÜŞÜK olan noktayı ara değerlemiyoruz: eksik bir
      // keypoint'i "yolda" göstermek olmayan bir duruş uydurmaktır
      // (PLAN.md §6.2 — eksik keypoint enterpole edilmez).
      if (prev[2] < 0.3 || point[2] < 0.3) return point
      return [lerp(prev[0], point[0], t), lerp(prev[1], point[1], t), point[2]] as
        [number, number, number]
    })
  }

  return { ...to, bbox, kp }
}

/** Bir tespiti hız vektörüyle ileri taşır (iki gerçek nokta yoksa). */
function extrapolate(det: Detection, seconds: number): Detection {
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
  /** Kaynak kare boyutu — kutuları görüntü alanına ölçeklemek için. */
  w: number
  h: number
  count: number
  /** Çizilen sonucun yaşı (ms). Bayatsa kullanıcıya söylüyoruz. */
  ageMs: number
  /** Ara değerlendi mi, yoksa ileri mi tahmin edildi? Panelde gösteriliyor. */
  mode: 'interpolated' | 'extrapolated' | 'exact'
}

/**
 * Tampondan, `now - offsetMs` anına ait çizilecek kareyi üretir.
 *
 * @param buffer  Eskiden yeniye sıralı sonuçlar
 * @param now     performance.now()
 * @param offsetMs Kaç ms geriye bakılacak (0 = ara değerleme yok)
 */
export function frameAt(
  buffer: TimedResult[],
  now: number,
  offsetMs: number,
): RenderFrame | null {
  if (buffer.length === 0) return null

  const target = now - offsetMs
  const newest = buffer[buffer.length - 1]

  // Hedef an en yeni sonuçtan sonraysa geçmişte veri yok → ileri tahmin.
  if (target >= newest.rx) {
    const ahead = Math.min(target - newest.rx, MAX_EXTRAPOLATE_MS) / 1000
    return {
      detections: ahead > 0 ? newest.detections.map((d) => extrapolate(d, ahead)) : newest.detections,
      w: newest.w,
      h: newest.h,
      count: newest.count,
      ageMs: now - newest.rx,
      mode: ahead > 0 ? 'extrapolated' : 'exact',
    }
  }

  // Hedefi kuşatan iki sonucu bul.
  let before = buffer[0]
  let after = newest
  for (let i = 0; i < buffer.length - 1; i++) {
    if (buffer[i].rx <= target && target <= buffer[i + 1].rx) {
      before = buffer[i]
      after = buffer[i + 1]
      break
    }
  }

  const span = after.rx - before.rx
  const t = span > 0 ? (target - before.rx) / span : 1

  // Kimliği olan izleri eşleştirip ara değerliyoruz. Kimliksiz
  // tespitler (takipçi henüz onaylamadı — P-13) eşleştirilemez;
  // onları olduğu gibi geçiriyoruz, kaybetmiyoruz.
  const previous = new Map<number, Detection>()
  for (const d of before.detections) {
    if (d.id !== undefined) previous.set(d.id, d)
  }

  const detections = after.detections.map((d) => {
    if (d.id === undefined) return d
    const prev = previous.get(d.id)
    return prev ? blend(prev, d, t) : d
  })

  return {
    detections,
    w: after.w,
    h: after.h,
    count: after.count,
    ageMs: now - after.rx,
    mode: 'interpolated',
  }
}
