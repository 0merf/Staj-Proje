/** Çizim izi kaydedici — "kutular takılıyor" şikâyetini SAYIYLA incelemek için.
 *
 * Neden var
 * ---------
 * Gözle bakınca "sıçradı" denebiliyor ama "kaç piksel, ne zaman, hangi
 * hızda, sonuç varışlarıyla örtüşüyor mu" denemiyor. Video kaydı da
 * yardımcı olmuyor — göz ölçemez.
 *
 * Bu modül, çizilen her karede kutunun konumunu kaydediyor. Sonra
 * sunucuya gönderilip sayısal inceleniyor: ardışık kareler arası
 * sıçrama dağılımı, ara değerleme mi tahmin mi kullanıldığı, hangi
 * anlarda bozulduğu.
 *
 * Kapalıyken maliyeti tek bir karşılaştırma.
 */
import type { RenderFrame } from './sync'

interface Sample {
  /** Kayıt başlangıcından beri geçen süre (ms) */
  t: number
  /** İzlenen izin kutu sol-üst köşesi */
  x: number
  y: number
  /** interpolated | predicted | exact */
  mode: string
  /** En yeni sonucun yaşı (ms) */
  age: number
}

let active: string | null = null
let trackId: number | null = null
let samples: Sample[] = []
let startedAt = 0

/** Kaydı başlatır. Kimlik verilmezse en geniş kutu seçilir. */
export function startTrace(camera: string, id?: number): void {
  active = camera
  trackId = id ?? null
  samples = []
  startedAt = performance.now()
  console.info(`[iz] kayıt başladı: ${camera}`)
}

export function isTracing(): boolean {
  return active !== null
}

export function recordTrace(camera: string, now: number, frame: RenderFrame | null): void {
  if (active !== camera || !frame) return

  // İlk çağrıda takip edilecek kimliği seç: en geniş kutu — en yakın
  // kişi, hareketi en görünür olan.
  if (trackId === null) {
    let best = -1
    let bestWidth = 0
    for (const d of frame.detections) {
      if (d.id === undefined) continue
      const width = d.bbox[2] - d.bbox[0]
      if (width > bestWidth) {
        bestWidth = width
        best = d.id
      }
    }
    if (best < 0) return
    trackId = best
  }

  const det = frame.detections.find((d) => d.id === trackId)
  if (!det) return

  samples.push({
    t: Math.round(now - startedAt),
    x: Math.round(det.bbox[0] * 10) / 10,
    y: Math.round(det.bbox[1] * 10) / 10,
    mode: frame.mode,
    age: Math.round(frame.ageMs),
  })
}

/** Kaydı bitirir ve sunucuya gönderir. */
export async function stopTrace(extra: Record<string, unknown> = {}): Promise<unknown> {
  if (!active) return null
  const camera = active
  const payload = {
    camera,
    trackId,
    durationMs: Math.round(performance.now() - startedAt),
    sampleCount: samples.length,
    samples,
    ...extra,
  }
  active = null
  try {
    const response = await fetch('/api/v1/debug/trace', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const result = await response.json()
    console.info(`[iz] ${camera}: ${samples.length} örnek kaydedildi`, result)
    return result
  } catch (error) {
    console.warn('[iz] gönderilemedi', error)
    return null
  }
}
