/** Video/kutu hizalama kaydırıcısı — artık ÖLÇÜME dayalı.
 *
 * PROBLEM
 * -------
 * Video ve kutular tarayıcıya iki ayrı yoldan geliyor ve gecikmeleri
 * farklı. Kutuların doğru yerde görünmesi için aradaki FARK kadar
 * geriden çizilmeleri gerekiyor.
 *
 * İlk sürümde bu farkı kullanıcı gözüyle ayarlıyordu. Artık iki yolu
 * da ölçüyoruz:
 *
 *   analiz yolu : sunucu her sonuçta kendi ölçtüğü gecikmeyi
 *                 gönderiyor (`lat` alanı) — kare yakalanmasından
 *                 sonucun yazılmasına kadar geçen süre
 *   video yolu  : WebRTC'nin jitter tamponu istatistiğinden
 *                 (`jitterBufferDelay / jitterBufferEmittedCount`)
 *
 *   önerilen kaydırma = analiz − video
 *
 * Fark negatifse (video analizden yavaş) kaydırma 0'dır: kutuları
 * geriye almak yerine olduğu gibi çizmek doğru olur.
 *
 * Kaydırıcı yine elle ayarlanabilir — ölçüm bir öneri, emir değil.
 * Jitter tamponu kameranın kodlama gecikmesini içermiyor, o yüzden
 * gözle ince ayar hâlâ anlamlı.
 */
import { useStore } from '../store'

export function SyncControl() {
  const offset = useStore((s) => s.syncOffsetMs)
  const setOffset = useStore((s) => s.setSyncOffset)
  const video = useStore((s) => s.videoLatencyMs)
  const ai = useStore((s) => s.aiLatencyMs)

  const suggestion =
    video !== null && ai !== null ? Math.max(0, Math.round((ai - video) / 25) * 25) : null

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <span
          className="text-xs text-muted"
          title="Kutular ne kadar İLERİ tahmin edilsin — analiz ile video arasındaki fark"
        >
          İleri tahmin
        </span>
        <input
          type="range"
          min={0}
          max={800}
          step={25}
          value={offset}
          onChange={(e) => setOffset(Number(e.target.value))}
          className="w-28 accent-[oklch(0.72_0.17_145)]"
        />
        <span className="w-14 font-mono text-xs text-ink">{offset} ms</span>
      </div>

      {/* Ölçülen gecikmeler — "hangi yol ne kadar sürüyor" sorusunun cevabı */}
      <div className="flex items-center gap-2 font-mono text-[10px] text-muted">
        <span title="Videonun tarayıcıya ulaşma gecikmesi (WebRTC jitter tamponu)">
          video {video === null ? '—' : `${Math.round(video)}ms`}
        </span>
        <span className="text-line">·</span>
        <span title="Kare yakalanmasından analiz sonucunun yazılmasına kadar (sunucu ölçüyor)">
          analiz {ai === null ? '—' : `${Math.round(ai)}ms`}
        </span>
      </div>

      {suggestion !== null && suggestion !== offset && (
        <button
          onClick={() => setOffset(suggestion)}
          title="Ölçülen iki gecikmenin farkını uygula"
          className="rounded-md border border-ok/40 px-2 py-0.5 text-[10px] text-ok hover:bg-ok/10"
        >
          öner: {suggestion} ms
        </button>
      )}
    </div>
  )
}
