/** Video/kutu hizalama kaydırıcısı.
 *
 * Neden kaydırıcı, neden otomatik değil
 * -------------------------------------
 * Kutuların videoyla hizalanması için videonun gecikmesini bilmek
 * gerekiyor. Ama tarayıcı bunu güvenilir şekilde ölçemiyor: WebRTC'nin
 * sunum zaman damgaları alıcıda yeniden üretiliyor ve MediaMTX gibi
 * ara sunucular kendi zaman referanslarını koyuyor (LITERATUR.md §R).
 *
 * En dürüst çözüm: operatörün gözüne göre ayarlanabilir bir kaydırma.
 * 0 = eski davranış (kutular ileri tahmin edilir).
 * Pozitif = kutular geriden çizilir, ARA DEĞERLEME devreye girer.
 */
import { useStore } from '../store'

export function SyncControl() {
  const offset = useStore((s) => s.syncOffsetMs)
  const setOffset = useStore((s) => s.setSyncOffset)

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted" title="Kutular videodan kaç ms geriden çizilsin">
        Hizalama
      </span>
      <input
        type="range"
        min={0}
        max={800}
        step={25}
        value={offset}
        onChange={(e) => setOffset(Number(e.target.value))}
        className="w-32 accent-[oklch(0.72_0.17_145)]"
      />
      <span className="w-16 font-mono text-xs text-ink">{offset} ms</span>
      <span className="text-[10px] text-muted">
        {offset === 0 ? 'ileri tahmin' : 'ara değerleme'}
      </span>
    </div>
  )
}
