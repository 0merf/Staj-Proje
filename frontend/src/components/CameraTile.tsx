/** Tek kamera kutucuğu: video + üstüne çizilen analiz katmanı.
 *
 * MİMARİ KURAL 2 BURADA UYGULANIYOR
 * ---------------------------------
 * Sunucu videoya kutu ÇİZMEZ. Video WHEP ile dokunulmadan gelir,
 * kutular WebSocket'ten ~500 baytlık JSON olarak gelir, birleştirmeyi
 * tarayıcı yapar. Sunucu tarafında çizim yapsaydık her kamera için
 * yeniden kodlama gerekirdi ve NVENC oturum limitine takılırdık.
 *
 * ÇİZİM DÖNGÜSÜ REACT'TEN BAĞIMSIZ
 * --------------------------------
 * Sonuçlar saniyede ~3-4 kez geliyor ama çizim requestAnimationFrame
 * ile ekran tazeleme hızında (60 Hz) çalışıyor. Aradaki karelerde kutu
 * ara değerleniyor, yani hareket akıcı görünüyor. Her sonuç mesajında
 * React render etseydik 20 kutucukta arayüz kilitlenirdi.
 */
import { useEffect, useRef } from 'react'
import { analysisFps, buffers, useStore } from '../store'
import { frameAt } from '../lib/sync'
import { recordTrace } from '../lib/trace'
import { BONES, KP_CONF_MIN } from '../lib/skeleton'
import {
  connectWhep,
  measureVideoLatencyMs,
  setVideoBuffer,
  type WhepSession,
} from '../lib/whep'
import { EXPR_MIN_CONF, EXPR_MIN_QUALITY, type Camera } from '../types'

/** Bu süre sonuç gelmezse "analiz durdu" uyarısı. */
const STALE_MS = 4000

interface Props {
  camera: Camera
  webrtcBase: string
}

export function CameraTile({ camera, webrtcBase }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const badgeRef = useRef<HTMLSpanElement>(null)
  const sessionRef = useRef<WhepSession | null>(null)

  const playing = useStore((s) => s.playing.has(camera.name))
  const toggle = useStore((s) => s.togglePlaying)
  const setVideoLatency = useStore((s) => s.setVideoLatency)
  const videoBufferMs = useStore((s) => s.videoBufferMs)

  // ─── Video bağlantısı ────────────────────────────────────
  useEffect(() => {
    if (!playing || !videoRef.current) return
    let cancelled = false

    connectWhep(webrtcBase, camera.name, videoRef.current)
      .then((session) => {
        if (cancelled) {
          session.close()
          return
        }
        sessionRef.current = session
        // ⚠ Kutu hizalamasının ÇÖZÜMÜ burada: videoyu bilerek
        // geciktiriyoruz ki analiz sonuçları yetişsin ve kutular
        // tahmin edilmek yerine ARA DEĞERLENSİN (LITERATUR.md §T).
        setVideoBuffer(session.pc, useStore.getState().videoBufferMs)
      })
      .catch((error) => console.warn('WHEP başarısız', camera.name, error))

    // Video gecikmesini periyodik ölç. Bu sayede hizalama kaydırıcısı
    // tahmin değil ÖLÇÜM önerebiliyor (bkz. SyncControl).
    const probe = window.setInterval(async () => {
      const pc = sessionRef.current?.pc
      if (!pc) return
      const ms = await measureVideoLatencyMs(pc)
      if (ms !== null && ms > 0) setVideoLatency(ms)
    }, 3000)

    return () => {
      cancelled = true
      clearInterval(probe)
      sessionRef.current?.close()
      sessionRef.current = null
    }
  }, [playing, camera.name, webrtcBase, setVideoLatency])

  // Kullanıcı tamponu değiştirdiğinde açık oturuma anında uygula —
  // yeniden bağlanmaya gerek yok.
  useEffect(() => {
    const pc = sessionRef.current?.pc
    if (pc) setVideoBuffer(pc, videoBufferMs)
  }, [videoBufferMs])

  // ─── Çizim döngüsü ───────────────────────────────────────
  useEffect(() => {
    if (!playing) return
    let handle = 0
    let usingVideoCallback = false

    // Video kare hızı: rVFC her gerçek video karesinde tetiklendiği
    // için çağrıları saymak doğrudan videonun FPS'ini veriyor.
    const videoTicks: number[] = []

    const draw = () => {
      // ⚠ requestVideoFrameCallback — requestAnimationFrame DEĞİL.
      // rAF ekranın tazeleme hızına bağlıdır (60 Hz) ve videodan
      // bağımsız çalışır; kutu ile videonun güncellendiği anlar
      // birbirini tutmaz. rVFC video karesi ekrana basıldığında
      // tetiklenir, yani çizim video hızına senkron olur
      // (LITERATUR.md §T). Desteklenmiyorsa rAF'a düşüyoruz.
      const video = videoRef.current as
        | (HTMLVideoElement & { requestVideoFrameCallback?: (cb: () => void) => number })
        | null
      if (video && typeof video.requestVideoFrameCallback === 'function') {
        usingVideoCallback = true
        handle = video.requestVideoFrameCallback(draw)
      } else {
        handle = requestAnimationFrame(draw)
      }

      const canvas = canvasRef.current
      if (!canvas) return

      const tick = performance.now()
      videoTicks.push(tick)
      while (videoTicks.length && tick - videoTicks[0] > 1000) videoTicks.shift()

      const rect = canvas.getBoundingClientRect()
      if (canvas.width !== rect.width || canvas.height !== rect.height) {
        canvas.width = Math.max(1, Math.round(rect.width))
        canvas.height = Math.max(1, Math.round(rect.height))
      }
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Ayarları store'dan HER KAREDE okuyoruz. getState() abonelik
      // kurmaz, yani ayar değişimi render tetiklemiyor.
      const { viewMode, videoLatencyMs, videoBufferMs } = useStore.getState()
      const buffer = buffers.get(camera.name)
      const now = performance.now()
      // Ekranda görünen sahnenin yaşı. Ölçüm geldiyse onu kullan;
      // gelmediyse istediğimiz tampon iyi bir yaklaşıktır.
      const shownAgeMs = videoLatencyMs ?? videoBufferMs
      const frame = buffer ? frameAt(buffer, now, shownAgeMs) : null

      if (badgeRef.current) {
        if (!frame || frame.ageMs > STALE_MS) {
          badgeRef.current.textContent = frame ? 'analiz durdu' : 'bekleniyor'
          badgeRef.current.className = 'rounded bg-warn/25 px-2 py-0.5 text-warn'
        } else {
          // Kişi sayısı + iki ayrı kare hızı: video kaç FPS geliyor,
          // analiz kaç FPS yapılıyor. İkisi arasındaki fark kutuların
          // neden ara değerlenmesi gerektiğini gözle gösteriyor.
          const vf = videoTicks.length
          const af = analysisFps(camera.name)
          badgeRef.current.textContent = `${frame.count} kişi · ${vf} vid · ${af} yz`
          badgeRef.current.className = `rounded px-2 py-0.5 font-mono ${
            frame.count > 0 ? 'bg-ok/25 text-ok' : 'bg-panel text-muted'
          }`
        }
      }

      if (viewMode === 'off' || !frame || frame.ageMs > STALE_MS) return

      // Kaynak kare pikselinden görüntü alanına ölçekle. Kameralar
      // farklı çözünürlükte (1280×720, 960×720, 900×720) — sabit bir
      // varsayım yanlış çizime yol açar.
      const sx = canvas.width / (frame.w || 1280)
      const sy = canvas.height / (frame.h || 720)

      ctx.lineWidth = 2
      ctx.font = '600 11px ui-monospace, Consolas, monospace'

      for (const det of frame.detections) {
        const [x1, y1, x2, y2] = det.bbox
        const x = x1 * sx
        const y = y1 * sy
        const w = (x2 - x1) * sx
        const h = (y2 - y1) * sy

        // Kimliksiz kutu = takipçi henüz onaylamadı (P-13). Kesikli
        // çizgiyle gösteriyoruz: tespit var, kimlik bir sonraki karede
        // gelecek. Gizlemek yanlış olurdu — kişi orada.
        const confirmed = det.id !== undefined
        const moving = det.v ? Math.abs(det.v[0]) + Math.abs(det.v[1]) > 15 : false
        ctx.setLineDash(confirmed ? [] : [5, 4])
        ctx.strokeStyle = !confirmed ? '#8b98ad' : moving ? '#3fb950' : '#4d8f5c'
        ctx.fillStyle = ctx.strokeStyle
        ctx.strokeRect(x, y, w, h)
        ctx.setLineDash([])

        const label = confirmed
          ? `#${det.id} ${(det.conf * 100).toFixed(0)}%`
          : `${(det.conf * 100).toFixed(0)}%`
        const tw = ctx.measureText(label).width + 8
        ctx.fillRect(x, Math.max(0, y - 15), tw, 15)
        ctx.fillStyle = '#06111f'
        ctx.fillText(label, x + 4, Math.max(11, y - 4))

        // KADEME 2b — yüz ifadesi, kutunun ALTINDA.
        //
        // ⚠ Yalnızca KALİTE VE GÜVEN eşiği geçilirse yazılıyor. Sunucu
        // her sınıflandırmayı gönderiyor (kalite skoruyla birlikte) ama
        // düşük kaliteli olanı ekrana basmak operatöre bilgi değil
        // gürültü sunmak olurdu — 15 piksellik bulanık bir yüze "öfke"
        // demek teknik olarak bir çıktıdır, bilgi değildir (PLAN §6.3).
        //
        // Eşikler sunucudaki `ExpressionResult.usable` ile aynı.
        const expr = det.expr
        if (expr && expr.q >= EXPR_MIN_QUALITY && expr.conf >= EXPR_MIN_CONF) {
          const text = `${expr.tr} ${(expr.conf * 100).toFixed(0)}%`
          const ew = ctx.measureText(text).width + 8
          ctx.fillStyle = '#1f6feb'
          ctx.fillRect(x, y + h, ew, 15)
          ctx.fillStyle = '#f0f6fc'
          ctx.fillText(text, x + 4, y + h + 11)
          ctx.fillStyle = ctx.strokeStyle
        }

        if (viewMode === 'full' && det.kp) drawSkeleton(ctx, det.kp, sx, sy)
      }

      // Teşhis izi: kayıt açıksa çizilen kutunun konumu saklanıyor.
      // "Takılıyor" şikâyetini gözle değil SAYIYLA incelemek için.
      recordTrace(camera.name, now, frame)
    }

    handle = requestAnimationFrame(draw)
    return () => {
      if (usingVideoCallback) {
        const video = videoRef.current as
          | (HTMLVideoElement & { cancelVideoFrameCallback?: (h: number) => void })
          | null
        video?.cancelVideoFrameCallback?.(handle)
      } else {
        cancelAnimationFrame(handle)
      }
    }
  }, [playing, camera.name])

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-panel">
      <div className="flex items-center gap-2 px-3 py-2 text-sm">
        <span
          className={`h-2 w-2 rounded-full ${camera.ready ? 'bg-ok' : 'bg-bad'}`}
        />
        <span className="font-medium">{camera.name}</span>
        <span className="text-[10px] uppercase tracking-wide text-muted">
          {camera.kind}
        </span>
        <button
          onClick={() => toggle(camera.name)}
          className="ml-auto rounded-md border border-line px-2 py-0.5 text-xs text-muted hover:text-ink"
        >
          {playing ? 'kapat' : 'izle'}
        </button>
      </div>

      <div className="relative aspect-video bg-black">
        {playing ? (
          <>
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="h-full w-full object-contain"
            />
            <canvas
              ref={canvasRef}
              className="pointer-events-none absolute inset-0 h-full w-full"
            />
            <span
              ref={badgeRef}
              className="absolute left-2 top-2 rounded bg-panel px-2 py-0.5 text-xs text-muted"
            />
          </>
        ) : (
          <button
            onClick={() => toggle(camera.name)}
            className="flex h-full w-full items-center justify-center text-xs text-muted hover:text-ink"
          >
            izlemek için tıkla
          </button>
        )}
      </div>
    </div>
  )
}

function drawSkeleton(
  ctx: CanvasRenderingContext2D,
  kp: [number, number, number][],
  sx: number,
  sy: number,
) {
  const stroke = ctx.strokeStyle
  const fill = ctx.fillStyle
  const ok = (i: number) => kp[i] && kp[i][2] >= KP_CONF_MIN

  ctx.lineWidth = 2
  for (const [a, b, color] of BONES) {
    // Eksik keypoint ARA DEĞERLENMEZ (PLAN.md §6.2): görünmeyen uzvu
    // tahmin etmek, olmayan bir duruşu varmış gibi göstermektir.
    if (!ok(a) || !ok(b)) continue
    ctx.strokeStyle = color
    ctx.beginPath()
    ctx.moveTo(kp[a][0] * sx, kp[a][1] * sy)
    ctx.lineTo(kp[b][0] * sx, kp[b][1] * sy)
    ctx.stroke()
  }

  ctx.fillStyle = '#f0f6fc'
  for (let i = 0; i < kp.length; i++) {
    if (!ok(i)) continue
    ctx.beginPath()
    ctx.arc(kp[i][0] * sx, kp[i][1] * sy, 2, 0, Math.PI * 2)
    ctx.fill()
  }

  ctx.strokeStyle = stroke
  ctx.fillStyle = fill
}
