/** 3 kademeli görünüm düğmesi: kapalı → kutular → kutular+iskelet.
 *
 * Neden kapatılabilir olsun
 * -------------------------
 * Ölçüm: iskelet WebSocket mesajının %74'ü (1907 vs 500 bayt). Mutlak
 * değer küçük (7 KB/sn), yani bant genişliği sorun değil. Asıl kazanç
 * tarayıcı tarafında: 20 kutucukta canvas'a çizilen her çizgi ve JSON
 * ayrıştırma maliyeti birikiyor.
 *
 * Ama iskeleti tamamen kaldırmıyoruz çünkü demo değeri yüksek —
 * "model kişinin kolunu görüyor" görsel kanıtı sunumda çok işe yarıyor
 * ve hata ayıklamada iskeletin yanlış olduğunu anında gösteriyor.
 * Karar kullanıcıya bırakıldı.
 */
import type { ViewMode } from '../types'
import { useStore } from '../store'

const OPTIONS: { value: ViewMode; label: string; hint: string }[] = [
  { value: 'off', label: 'Kapalı', hint: 'Yalnızca video — en hafif' },
  { value: 'boxes', label: 'Kutular', hint: 'Kutu + kimlik + güven' },
  { value: 'full', label: 'İskelet', hint: 'Kutular + COCO-17 iskelet' },
]

export function ViewModeToggle() {
  const mode = useStore((s) => s.viewMode)
  const setMode = useStore((s) => s.setViewMode)

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted">Görünüm</span>
      <div className="flex rounded-lg border border-line bg-panel p-0.5">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            title={option.hint}
            onClick={() => setMode(option.value)}
            className={`rounded-md px-3 py-1 text-xs font-medium transition ${
              mode === option.value
                ? 'bg-ok/20 text-ok'
                : 'text-muted hover:text-ink'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}
