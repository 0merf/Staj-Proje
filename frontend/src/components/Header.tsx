import { useStore } from '../store'
import { ViewModeToggle } from './ViewModeToggle'
import { SyncControl } from './SyncControl'

export function Header() {
  const connection = useStore((s) => s.connection)
  const cameras = useStore((s) => s.cameras)
  const playing = useStore((s) => s.playing.size)
  const toggle = useStore((s) => s.togglePlaying)

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

        <span className="text-xs text-muted">
          {ready}/{cameras.length} kamera yayında · {playing} açık
        </span>

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
            className="rounded-md border border-line px-3 py-1 text-xs text-muted hover:text-ink"
          >
            {playing === cameras.length ? 'hepsini kapat' : 'hepsini aç'}
          </button>
        </div>
      </div>
    </header>
  )
}
