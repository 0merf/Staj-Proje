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
  cizgiDeseni,
  hareketli,
  kutuEtiketi,
  kutuRengi,
  kutuyuOlcekle,
  olcek,
} from '../lib/overlay'
import {
  connectWhep,
  measureVideoLatencyMs,
  setVideoBuffer,
  type WhepSession,
} from '../lib/whep'
import { EXPR_MIN_CONF, EXPR_MIN_QUALITY, type Camera } from '../types'

/** ⚠ İKİ EŞİK — çünkü "sakin" ile "bozuk" aynı şey değil
 *
 * Eski sürümde tek eşik vardı (4 sn) ve aşıldığında "analiz durdu"
 * yazıyordu. Bu YANILTICIYDI: bir otopark kamerasında saatlerce hiçbir
 * şey olmaz, Kademe 0 hareket filtresi kareleri haklı olarak eler ve
 * sonuç üretilmez. Sistem tam olarak tasarlandığı gibi çalışırken panel
 * "analiz durdu" diye alarm veriyordu.
 *
 * Üstüne uyarlanabilir FPS var: 30 sn hareketsizlikte kamera 1 FPS'e
 * düşüyor ve yalnızca 5 saniyelik zorunlu yenileme karesi geçiyor.
 * Yani SAĞLIKLI bir sakin kamerada sonuçlar 5-10 sn arayla gelir —
 * 4 sn eşiği bunu daima "arıza" sayıyordu.
 *
 * Şimdi: SAKIN_MS'i aşan ama son karesi `refresh` olan kamera "sakin"
 * diye gösteriliyor (bilgi, alarm değil). Gerçekten uzun süre hiçbir
 * şey gelmezse DURDU_MS'te "analiz durdu" yazıyor. */
const SAKIN_MS = 6000
const DURDU_MS = 20000

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
        if (!frame) {
          badgeRef.current.textContent = 'bekleniyor'
          badgeRef.current.className = 'rounded bg-warn/25 px-2 py-0.5 text-warn'
        } else if (frame.ageMs > DURDU_MS) {
          // Bu kadar uzun sessizlik gerçekten anormal: zorunlu yenileme
          // karesi 5 saniyede bir geçtiği için sağlıklı bir kamera
          // 20 saniye susmaz.
          badgeRef.current.textContent = `analiz durdu · ${(frame.ageMs / 1000).toFixed(0)} sn`
          badgeRef.current.className = 'rounded bg-bad/25 px-2 py-0.5 text-bad'
        } else if (frame.ageMs > SAKIN_MS && frame.gate === 'refresh') {
          // Kademe 0 kareleri eliyor çünkü sahnede hareket YOK.
          // Bu bir arıza değil, filtrenin doğru çalıştığının kanıtı —
          // 20 kamerayı tek GPU'da döndürebilmemizin sebebi tam da bu.
          badgeRef.current.textContent = 'sakin · hareket yok'
          badgeRef.current.className = 'rounded bg-panel px-2 py-0.5 text-muted'
        } else if (frame.ageMs > SAKIN_MS) {
          // Son kare hareketliydi ama yenisi gelmiyor — kamera meşgul
          // ama analiz yetişemiyor. Kullanıcı yaşı görsün, tahmin etmesin.
          badgeRef.current.textContent = `gecikiyor · ${(frame.ageMs / 1000).toFixed(1)} sn`
          badgeRef.current.className = 'rounded bg-warn/25 px-2 py-0.5 text-warn'
        } else {
          // Kişi sayısı + iki ayrı kare hızı: video kaç FPS geliyor,
          // analiz kaç FPS yapılıyor. İkisi arasındaki fark kutuların
          // neden ara değerlenmesi gerektiğini gözle gösteriyor.
          const vf = videoTicks.length
          const af = analysisFps(camera.name)
          // ⚠ ONDALIK: analiz kamera başına 1 FPS'in ALTINDA koşuyor.
          // Tam sayıya yuvarlamak 0.6 FPS'i "0" gösterir ve sistem
          // çalışmıyor sanılır — tam olarak yaşanan buydu.
          badgeRef.current.textContent =
            `${frame.count} kişi · ${vf} vid · ${af.toFixed(1)} yz`
          badgeRef.current.className = `rounded px-2 py-0.5 font-mono ${
            frame.count > 0 ? 'bg-ok/25 text-ok' : 'bg-panel text-muted'
          }`
        }
      }

      // Kutuları çizmeyi bırakma eşiği: bayat kutu yanlış yerde durur.
      if (viewMode === 'off' || !frame || frame.ageMs > DURDU_MS) return

      // ⚠ Ölçek matematiği `lib/overlay.ts`e taşındı ve orada test
      // ediliyor (25 test). Burada kopyasını tutmak, "test edilen kod
      // ile koşan kod" ayrışması demekti — bu projenin en pahalı hata
      // türü (P-39, P-56).
      const o = olcek(canvas.width, canvas.height, frame.w, frame.h)
      const { sx, sy } = o

      ctx.lineWidth = 2
      ctx.font = '600 11px ui-monospace, Consolas, monospace'

      for (const det of frame.detections) {
        const { x, y, w, h } = kutuyuOlcekle(det.bbox, o)

        // Kimliksiz kutu = takipçi henüz onaylamadı (P-13). Kesikli
        // çizgiyle gösteriyoruz: tespit var, kimlik bir sonraki karede
        // gelecek. Gizlemek yanlış olurdu — kişi orada.
        const confirmed = det.id !== undefined
        const moving = hareketli(det.v)
        ctx.setLineDash(cizgiDeseni(confirmed))
        ctx.strokeStyle = kutuRengi(confirmed, moving)
        ctx.fillStyle = ctx.strokeStyle
        ctx.strokeRect(x, y, w, h)
        ctx.setLineDash([])

        const label = kutuEtiketi(det.id, det.conf)
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
    // ⚠ REF DEĞERİ TEMİZLİKTEN ÖNCE KOPYALANIYOR (ESLint bulgusu).
    // `videoRef.current` temizlik çalıştığında BAŞKA bir düğümü
    // gösteriyor olabilir — React o ana kadar DOM'u değiştirmiş olur.
    // O durumda `cancelVideoFrameCallback` YANLIŞ videoda çağrılır ve
    // eski geri çağrı iptal edilmeden kalır: sessiz bir sızıntı.
    const videoDugumu = videoRef.current as
      | (HTMLVideoElement & { cancelVideoFrameCallback?: (h: number) => void })
      | null
    return () => {
      if (usingVideoCallback) {
        videoDugumu?.cancelVideoFrameCallback?.(handle)
      } else {
        cancelAnimationFrame(handle)
      }
    }
  }, [playing, camera.name])

  return (
    <div
      data-testid="kamera-kutucugu"
      data-kamera={camera.name}
      data-hazir={camera.ready ? '1' : '0'}
      className="overflow-hidden rounded-xl border border-line bg-panel"
    >
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
