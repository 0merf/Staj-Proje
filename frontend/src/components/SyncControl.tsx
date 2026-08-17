/** Video tamponu kontrolü — kutu hizalamasının kalbi.
 *
 * NEDEN VİDEOYU GECİKTİRİYORUZ
 * ----------------------------
 * Analiz sonucu ~200-450 ms eski; video canlı. Kutuyu nereye çizeceğiz?
 *
 * İlk yaklaşımımız kişinin ŞU AN nerede olduğunu hız vektöründen
 * tahmin etmekti (ekstrapolasyon). İnsan yavaşlar/döner/durur, tahmin
 * tutmaz, ve bir sonraki gerçek sonuç kutuyu SIÇRATARAK doğru yere
 * çeker — kullanıcının bildirdiği "takılma" buydu.
 *
 * Çok oyunculu oyun ağ literatürünün yerleşik çözümü tersini söylüyor
 * (LITERATUR.md §T): **tahmin etme, görüntüyü geciktir.** Video analiz
 * kadar geriden gelirse, ekranda gösterilen an için elimizde İKİ gerçek
 * ölçüm olur ve aradaki konum hesaplanır — tahmin edilmez.
 *
 * Tarayıcının bunun için hazır bir düğmesi var: `jitterBufferTarget`
 * (Chrome'da `playoutDelayHint`). "Bu videoyu N ms tamponla" diyoruz.
 *
 * Bedeli tazelik. Gözetimde kabul edilebilir: operatör için kutunun
 * DOĞRU YERDE olması, yarım saniye daha taze olmasından önemli —
 * üstelik alarm ayrı kanaldan gecikmesiz geliyor.
 */
import { buffers, useStore } from '../store'
import { startTrace, stopTrace, isTracing } from '../lib/trace'
import { useState } from 'react'

export function SyncControl() {
  const buffer = useStore((s) => s.videoBufferMs)
  const setBuffer = useStore((s) => s.setVideoBufferMs)
  const video = useStore((s) => s.videoLatencyMs)
  const ai = useStore((s) => s.aiLatencyMs)
  const playing = useStore((s) => s.playing)
  const [tracing, setTracing] = useState(isTracing())

  // Tampon, analiz gecikmesini aşmalı ki ara değerleme mümkün olsun.
  // Pay bırakıyoruz: gecikme dalgalanıyor, sınırda kalırsak yarı yarıya
  // tahmine düşeriz.
  const suggestion = ai !== null ? Math.min(2000, Math.round((ai * 1.3 + 100) / 50) * 50) : null
  const interpolating = video !== null && ai !== null && video > ai

  const toggleTrace = async () => {
    if (tracing) {
      await stopTrace({ videoBufferMs: buffer, videoLatencyMs: video, aiLatencyMs: ai })
      setTracing(false)
    } else {
      // ⚠ İlk açık kamerayı almak yetmiyor: boş bir otopark seçilirse
      // takip edilecek kimse olmaz ve kayıt boş çıkar (ilk denemede
      // tam olarak bu oldu). En çok kişi görülen kamerayı seçiyoruz.
      let best: string | null = null
      let bestCount = 0
      for (const cam of playing) {
        const buffer = buffers.get(cam)
        const last = buffer?.[buffer.length - 1]
        const count = last?.detections.filter((d) => d.id !== undefined).length ?? 0
        if (count > bestCount) {
          bestCount = count
          best = cam
        }
      }
      if (!best) {
        console.warn('[iz] kimlikli tespit olan açık kamera yok')
        return
      }
      startTrace(best)
      setTracing(true)
    }
  }

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <span
          className="text-xs text-muted"
          title="Video kaç ms tamponlansın — analizin yetişmesi için"
        >
          Video tamponu
        </span>
        <input
          type="range"
          min={0}
          max={1500}
          step={50}
          value={buffer}
          onChange={(e) => setBuffer(Number(e.target.value))}
          className="w-28 accent-[oklch(0.72_0.17_145)]"
        />
        <span className="w-16 font-mono text-xs text-ink">{buffer} ms</span>
      </div>

      <div className="flex items-center gap-2 font-mono text-[10px] text-muted">
        <span title="Videonun ölçülen gecikmesi">
          video {video === null ? '—' : `${Math.round(video)}ms`}
        </span>
        <span className="text-line">·</span>
        <span title="Analiz yolunun ölçülen gecikmesi (sunucu raporluyor)">
          analiz {ai === null ? '—' : `${Math.round(ai)}ms`}
        </span>
        <span
          className={interpolating ? 'text-ok' : 'text-warn'}
          title={
            interpolating
              ? 'Video analizden geride — kutular iki gerçek ölçüm arasında ARA DEĞERLENİYOR'
              : 'Video analizden ileride — kutular TAHMİN ediliyor, sıçrama olabilir'
          }
        >
          {interpolating ? 'ara değerleme' : 'tahmin'}
        </span>
      </div>

      {suggestion !== null && suggestion !== buffer && (
        <button
          onClick={() => setBuffer(suggestion)}
          title="Analiz gecikmesini aşacak tampon — ara değerlemeyi devreye sokar"
          className="rounded-md border border-ok/40 px-2 py-0.5 text-[10px] text-ok hover:bg-ok/10"
        >
          öner: {suggestion} ms
        </button>
      )}

      <button
        onClick={toggleTrace}
        title="Çizilen kutunun konumunu kaydeder; takılmayı sayısal incelemek için"
        className={`rounded-md border px-2 py-0.5 text-[10px] ${
          tracing ? 'border-bad/50 text-bad' : 'border-line text-muted hover:text-ink'
        }`}
      >
        {tracing ? '● kaydı bitir' : 'iz kaydet'}
      </button>
    </div>
  )
}
