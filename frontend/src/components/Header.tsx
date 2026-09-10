import { useStore } from '../store'
import { ViewModeToggle } from './ViewModeToggle'
import { SyncControl } from './SyncControl'
import { TemaSecici } from './TemaSecici'

interface HeaderProps {
  kullanici: { kullanici_adi: string; rol: string }
}

export function Header({ kullanici }: HeaderProps) {
  const connection = useStore((s) => s.connection)
  const cameras = useStore((s) => s.cameras)
  const playing = useStore((s) => s.playing.size)
  const toggle = useStore((s) => s.togglePlaying)
  const sayfa = useStore((s) => s.sayfa)
  const setSayfa = useStore((s) => s.setSayfa)

  const ready = cameras.filter((c) => c.ready).length
  const dot =
    connection === 'bağlı' ? 'bg-ok' : connection === 'kopuk' ? 'bg-bad' : 'bg-warn'

  return (
    <header className="sticky top-0 z-10 border-b border-line bg-bg/95 backdrop-blur">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-base font-semibold tracking-tight">SENTINEL</span>
          <span className={`h-2 w-2 rounded-full ${dot}`} />
          <span className="text-xs text-muted">{connection}</span>
        </div>

        {/* ⚠ `tabular-nums` + sabit genişlik: sayaç saniyede bir
            değişiyor ve orantılı rakamlarla her değişimde metnin
            genişliği oynuyordu — yanındaki gezinme düğmelerini
            kaydırarak. */}
        <span className="w-[190px] shrink-0 text-xs tabular-nums text-muted">
          {ready}/{cameras.length} kamera yayında · {playing} açık
        </span>

        {/* ─── Sayfa gezinmesi (PLAN §10.1) ───
            ⚠ Router yok, durum değişkeni var. Gerekçe types.ts · Sayfa:
            üç görünüm için deep-link gereksinimi olmayan bir panelde
            router bir bağımlılık ve bir URL sözleşmesi getiriyordu. */}
        <nav className="flex gap-1">
          {(
            [
              ['izgara', 'Izgara'],
              ['zaman-cizelgesi', 'Zaman Çizelgesi'],
              ['kamera', 'Kamera Detayı'],
            ] as const
          ).map(([id, etiket]) => (
            <button
              key={id}
              onClick={() => setSayfa(id)}
              className={`rounded px-2 py-1 text-xs transition-colors ${
                sayfa === id
                  ? 'bg-panel text-ink'
                  : 'text-muted hover:text-ink'
              }`}
            >
              {etiket}
            </button>
          ))}
        </nav>

        <div className="ml-auto flex flex-wrap items-center gap-5">
          <ViewModeToggle />
          <SyncControl />
          <button
            onClick={() => {
              const all = useStore.getState().playing.size === cameras.length
              cameras.forEach((c) => {
                const on = useStore.getState().playing.has(c.name)
                if (all === on) toggle(c.name)
              })
            }}
            className="w-[104px] shrink-0 rounded-md border border-line px-3 py-1 text-xs text-muted hover:text-ink"
          >
            {playing === cameras.length ? 'hepsini kapat' : 'hepsini aç'}
          </button>

          <TemaSecici />

          {/* ⚠ ROL GÖSTERİLİYOR — süs değil.
              Operatör hangi yetkiyle bağlı olduğunu bilmeli: `viewer`
              iken webcam düğmesinin neden 403 döndüğü, rol görünmüyorsa
              anlaşılmaz bir hataya dönüşür. */}
          <span className="flex items-center gap-1.5 border-l border-line pl-4 text-xs text-muted">
            <span className="text-ink">{kullanici.kullanici_adi}</span>
            <span className="rounded bg-panel px-1.5 py-0.5 text-[10px] uppercase">
              {kullanici.rol}
            </span>
          </span>
          <button
            onClick={() => {
              // ⚠ Çıkış sunucu çerezini siliyor; sayfa yenilenerek
              // tüm istemci durumu (kamera listesi, alarmlar, açık
              // WebSocket) da temizleniyor. Elle sıfırlamak, ileride
              // eklenecek her yeni durum alanını unutma riski taşırdı.
              void fetch('/api/v1/auth/logout', { method: 'POST' }).finally(() =>
                window.location.reload(),
              )
            }}
            className="rounded-md border border-line px-2 py-1 text-xs text-muted hover:text-ink"
          >
            çıkış
          </button>
        </div>
      </div>
    </header>
  )
}
