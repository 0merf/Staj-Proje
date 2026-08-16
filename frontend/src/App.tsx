import { useEffect, useState } from 'react'
import { Header } from './components/Header'
import { CameraTile } from './components/CameraTile'
import { useLiveResults } from './hooks/useLiveResults'
import { useStore } from './store'
import type { Camera } from './types'

export default function App() {
  useLiveResults()
  const cameras = useStore((s) => s.cameras)
  const setCameras = useStore((s) => s.setCameras)
  const [webrtcBase, setWebrtcBase] = useState('http://127.0.0.1:8889')

  useEffect(() => {
    // Kamera envanteri ve MediaMTX adresi sunucudan geliyor —
    // adresi koda gömmek farklı kurulumda sessizce kırılırdı.
    fetch('/api/v1/cameras')
      .then((r) => r.json())
      .then((data: { cameras?: Camera[] }) => setCameras(data.cameras ?? []))
      .catch((e) => console.warn('kamera listesi alınamadı', e))

    fetch('/api/v1/system/config')
      .then((r) => r.json())
      .then((data: { urls?: { webrtc?: string } }) => {
        if (data.urls?.webrtc) setWebrtcBase(data.urls.webrtc)
      })
      .catch(() => {
        /* varsayılan adres kullanılır */
      })
  }, [setCameras])

  return (
    <div className="min-h-full">
      <Header />
      <main className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        {cameras.map((camera) => (
          <CameraTile key={camera.name} camera={camera} webrtcBase={webrtcBase} />
        ))}
      </main>
      {cameras.length === 0 && (
        <p className="px-4 text-sm text-muted">Kamera listesi bekleniyor…</p>
      )}
    </div>
  )
}
