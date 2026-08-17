/** Canlı durum — Zustand.
 *
 * Neden Zustand, neden React state değil
 * --------------------------------------
 * Saniyede ~60 sonuç mesajı geliyor (20 kamera × ~3 FPS). Bunları
 * React state'ine yazmak her mesajda tüm ağacın yeniden render
 * edilmesi demek olurdu. Zustand ile abone olan bileşen kendi
 * kesitini seçiyor.
 *
 * ⚠ DAHA ÖNEMLİSİ: sonuç tamponu React'in DIŞINDA tutuluyor
 * (`buffers` bir Map ve mutasyona uğruyor). Çizim döngüsü
 * requestAnimationFrame ile ekran tazeleme hızında çalışıyor ve
 * tampondan okuyor — yani gelen her mesaj bir render tetiklemiyor.
 * React yalnızca kamera listesi, bağlantı durumu ve kullanıcı
 * ayarları gibi SEYREK değişen şeyleri yönetiyor.
 */
import { create } from 'zustand'
import type { Camera, TimedResult, ViewMode } from './types'
import { BUFFER_SIZE } from './lib/sync'

/** Kamera adı → son N sonuç (eskiden yeniye). React dışında. */
export const buffers = new Map<string, TimedResult[]>()

/** Kamera başına analiz sonucu varış zamanları — FPS hesabı için.
 * React dışında tutuluyor; saniyede ~60 mesaj render tetiklemesin. */
export const resultTimes = new Map<string, number[]>()

/** Son bir saniyede kaç analiz sonucu geldi (kamera başına). */
export function analysisFps(camera: string): number {
  const times = resultTimes.get(camera)
  if (!times || times.length < 2) return 0
  const now = performance.now()
  while (times.length && now - times[0] > 1000) times.shift()
  return times.length
}

export function pushResult(result: TimedResult) {
  let list = buffers.get(result.cam)
  if (!list) {
    list = []
    buffers.set(result.cam, list)
  }
  list.push(result)
  if (list.length > BUFFER_SIZE) list.shift()

  let times = resultTimes.get(result.cam)
  if (!times) {
    times = []
    resultTimes.set(result.cam, times)
  }
  times.push(result.rx)
  if (times.length > 60) times.shift()
}

interface State {
  cameras: Camera[]
  connection: 'bağlanıyor' | 'bağlı' | 'kopuk'
  /** Panelde ne çizilsin (kullanıcı düğmesi). */
  viewMode: ViewMode
  /** Kutular kaç ms geriden çizilsin — video/kutu hizalaması. */
  syncOffsetMs: number
  /** Açık olan kameralar (video oynatılıyor). */
  playing: Set<string>
  messageCount: number
  /** Tarayıcıya "videoyu bu kadar tamponla" dediğimiz değer (ms).
   *  Analiz gecikmesini aşarsa kutular TAHMİN yerine ARA DEĞERLEME ile
   *  çiziliyor — literatürün önerdiği yöntem (LITERATUR.md §T). */
  videoBufferMs: number
  /** Ölçülen video yolu gecikmesi (WebRTC jitter tamponu). */
  videoLatencyMs: number | null
  /** Ölçülen analiz yolu gecikmesi (sunucu raporluyor). */
  aiLatencyMs: number | null

  setCameras: (c: Camera[]) => void
  setConnection: (c: State['connection']) => void
  setViewMode: (m: ViewMode) => void
  setSyncOffset: (ms: number) => void
  togglePlaying: (name: string) => void
  bumpMessages: () => void
  setVideoBufferMs: (ms: number) => void
  setVideoLatency: (ms: number) => void
  setAiLatency: (ms: number) => void
}

export const useStore = create<State>((set) => ({
  cameras: [],
  connection: 'bağlanıyor',
  viewMode: 'full',
  // İLERİ TAHMİN payı (ms). Video ~13 ms'de geliyor, analiz ~200-465 ms.
  // Aradaki fark kadar ileri tahmin gerekiyor; panel bunu ölçüp
  // "öner" düğmesiyle sunuyor. 0 = tahmin yok (kutular analizin
  // olduğu anı gösterir, yani videodan geride kalır).
  syncOffsetMs: 400,
  playing: new Set<string>(),
  messageCount: 0,
  videoBufferMs: 500,
  videoLatencyMs: null,
  aiLatencyMs: null,

  setCameras: (cameras) => set({ cameras }),
  setConnection: (connection) => set({ connection }),
  setViewMode: (viewMode) => set({ viewMode }),
  setSyncOffset: (syncOffsetMs) => set({ syncOffsetMs }),
  togglePlaying: (name) =>
    set((s) => {
      const next = new Set(s.playing)
      if (next.has(name)) {
        next.delete(name)
        buffers.delete(name)
      } else {
        next.add(name)
      }
      return { playing: next }
    }),
  bumpMessages: () => set((s) => ({ messageCount: s.messageCount + 1 })),
  // Üstel yumuşatma: tek bir sıçrama öneriyi zıplatmasın.
  setVideoBufferMs: (videoBufferMs) => set({ videoBufferMs }),
  setVideoLatency: (ms) =>
    set((s) => ({
      videoLatencyMs: s.videoLatencyMs === null ? ms : s.videoLatencyMs * 0.7 + ms * 0.3,
    })),
  setAiLatency: (ms) =>
    set((s) => ({
      aiLatencyMs: s.aiLatencyMs === null ? ms : s.aiLatencyMs * 0.9 + ms * 0.1,
    })),
}))
