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
import type {
  Camera,
  HistoryEvent,
  TimedAlert,
  TimedResult,
  Sayfa,
  ViewMode,
} from './types'
import { BUFFER_SIZE } from './lib/sync'

/** Kamera adı → son N sonuç (eskiden yeniye). React dışında. */
export const buffers = new Map<string, TimedResult[]>()

/** Kamera başına analiz sonucu varış zamanları — FPS hesabı için.
 * React dışında tutuluyor; saniyede ~60 mesaj render tetiklemesin. */
export const resultTimes = new Map<string, number[]>()

/** Son bir saniyede kaç analiz sonucu geldi (kamera başına). */
/** Analiz penceresi. ⚠ Video penceresinden UZUN olmak ZORUNDA.
 *
 * İlk sürüm 1 saniye kullanıyordu ve `length < 2` ise 0 dönüyordu.
 * Video için doğruydu (25 FPS → saniyede 26 örnek), analiz için
 * TAMAMEN yanlış: analiz kamera başına ~0.5-2 FPS koşuyor, yani çoğu
 * saniyede 0 veya 1 sonuç düşüyor. Sonuç: panelde kutular çizilirken
 * rozet "0 yz" yazıyordu — ölçüm aracı bozuktu, boru hattı değil.
 *
 * 5 saniye, 0.2 FPS'i bile görünür kılıyor. */
const ANALIZ_PENCERE_MS = 5000

export function analysisFps(camera: string): number {
  const times = resultTimes.get(camera)
  if (!times || times.length === 0) return 0
  const now = performance.now()
  while (times.length && now - times[0] > ANALIZ_PENCERE_MS) times.shift()
  if (times.length === 0) return 0
  // Sabit pencereye değil GERÇEKLEŞEN aralığa bölüyoruz: kamera yeni
  // açıldıysa elimizde 5 saniyelik geçmiş yok ve sabit bölme hızı
  // olduğundan düşük gösterirdi.
  const span = Math.max(500, now - times[0])
  return times.length / (span / 1000)
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
  sayfa: Sayfa
  /** Kamera detay sayfasında hangi kamera açık. */
  seciliKamera: string | null
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
  /** Son alarmlar — en yenisi başta.
   *
   * ⚠ 30.08.2026: artık YALNIZCA canlı akış değil. Panel açılışta
   * `/api/v1/events` ile geçmişi de yüklüyor. Öncesinde panel
   * kapalıyken olan hiçbir şey görülemiyordu ve panel her açıldığında
   * sistem "hiç alarm üretmemiş" gibi görünüyordu. */
  alerts: TimedAlert[]
  /** Geçmiş yüklendi mi (bir kez yükleniyor). */
  historyLoaded: boolean

  setCameras: (c: Camera[]) => void
  setConnection: (c: State['connection']) => void
  setViewMode: (m: ViewMode) => void
  setSayfa: (s: Sayfa) => void
  kameraAc: (ad: string) => void
  setSyncOffset: (ms: number) => void
  togglePlaying: (name: string) => void
  bumpMessages: () => void
  setVideoBufferMs: (ms: number) => void
  setVideoLatency: (ms: number) => void
  setAiLatency: (ms: number) => void
  pushAlert: (a: TimedAlert) => void
  loadHistory: () => Promise<void>
}

export const useStore = create<State>((set) => ({
  cameras: [],
  connection: 'bağlanıyor',
  viewMode: 'full',
  sayfa: 'izgara',
  seciliKamera: null,
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
  alerts: [],
  historyLoaded: false,

  setCameras: (cameras) => set({ cameras }),
  setConnection: (connection) => set({ connection }),
  setViewMode: (viewMode) => set({ viewMode }),
  setSayfa: (sayfa) => set({ sayfa }),
  // Kamera detayına geçiş: hem sayfayı hem seçili kamerayı tek
  // güncellemede değiştiriyor — ikisini ayrı set() ile yapmak arada
  // bir kare "kamera seçilmemiş detay sayfası" gösterirdi.
  kameraAc: (ad) => set({ sayfa: 'kamera', seciliKamera: ad }),
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
  pushAlert: (a) =>
    set((s) => ({
      // En yenisi BAŞTA, en fazla 50 kayıt.
      // ⚠ Panelde tutulan sayı bir GÖRÜNTÜLEME sınırı, saklama sınırı
      // değil. Kalıcı kayıt TimescaleDB'de (30 gün) ve `/api/v1/events`
      // ile sorgulanabiliyor. Sınırsız biriktirmek belleği şişirir ve
      // operatörün dikkatini eskiye dağıtır.
      alerts: [a, ...s.alerts].slice(0, 50),
    })),

  /** Açılışta son 24 saatin alarmlarını yükler.
   *
   * ⚠ CANLI AKIŞLA ÇAKIŞMA: WebSocket bağlanmadan önce çağrılıyor ama
   * yine de aynı olay iki kez gelebilir (geçmiş sorgusu ile ilk canlı
   * mesaj arasındaki pencerede üretilenler). Tekilleştirme
   * (kamera, ts, iz) üçlüsüne göre yapılıyor — olay kimliği yok.
   *
   * ⚠ HATA SESSİZ GEÇİLİYOR. Geçmiş yüklenemezse panel canlı akışla
   * çalışmaya devam etmeli; yardımcı bir isteğin başarısızlığı asıl
   * işlevi durdurmamalı. */
  loadHistory: async () => {
    try {
      const r = await fetch('/api/v1/events?limit=50&saat=24')
      if (!r.ok) return
      const d = (await r.json()) as { olaylar: HistoryEvent[] }
      set((s) => {
        const gorulen = new Set(
          s.alerts.map((a) => `${a.cam}|${a.ts.toFixed(3)}|${a.track}`),
        )
        const gecmis: TimedAlert[] = []
        for (const o of d.olaylar) {
          const anahtar = `${o.camera}|${o.ts.toFixed(3)}|${o.track}`
          if (gorulen.has(anahtar)) continue
          gorulen.add(anahtar)
          gecmis.push({
            type: 'alert',
            cam: o.camera,
            ts: o.ts,
            anomaly: o.tur,
            severity: o.ciddiyet,
            track: o.track,
            score: o.skor,
            evidence: o.kanit ?? {},
            completeness: o.tamlik ?? 0,
            // ⚠ `rx` normalde varış anı (performance.now tabanlı).
            // Geçmiş kayıtlarda "varış" diye bir şey yok; olayın kendi
            // zamanını tarayıcı zaman tabanına çeviriyoruz ki liste
            // doğru sıralansın ve saat doğru görünsün.
            rx: o.ts * 1000 - performance.timeOrigin,
            gecmis: true,
            // Kanıt klibi — `AlertPanel` bunu bir oynatıcıya çeviriyor.
            klip: o.klip,
          })
        }
        return {
          historyLoaded: true,
          alerts: [...s.alerts, ...gecmis]
            .sort((a, b) => b.ts - a.ts)
            .slice(0, 50),
        }
      })
    } catch {
      // Geçmiş yoksa canlı akışla devam — panel çalışmaya devam etmeli.
      set({ historyLoaded: true })
    }
  },
  setAiLatency: (ms) =>
    set((s) => ({
      aiLatencyMs: s.aiLatencyMs === null ? ms : s.aiLatencyMs * 0.9 + ms * 0.1,
    })),
}))
