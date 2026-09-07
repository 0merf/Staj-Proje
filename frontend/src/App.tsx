import { useCallback, useEffect, useState } from 'react'
import { Giris } from './components/Giris'
import { Header } from './components/Header'
import { CameraTile } from './components/CameraTile'
import { AlertPanel } from './components/AlertPanel'
import { ZamanCizelgesi } from './components/ZamanCizelgesi'
import { KameraDetay } from './components/KameraDetay'
import { useLiveResults } from './hooks/useLiveResults'
import { useStore } from './store'
import type { Camera } from './types'

/** Oturum durumu.
 *
 * ⚠ `null` = HENÜZ BİLİNMİYOR, `false` = giriş yapılmamış.
 * İkisini tek bir boolean'a sıkıştırmak, sayfa açılırken bir an için
 * giriş ekranını göstermek demekti — kullanıcı zaten girişliyse bu
 * "atıldım mı?" izlenimi verirdi.
 */
type Oturum = { kullanici_adi: string; rol: string } | false | null

export default function App() {
  const [oturum, setOturum] = useState<Oturum>(null)

  // ⚠ "Girişli miyim" sorusu SUNUCUYA soruluyor, tokena bakılarak
  // değil. Token `httponly` çerezde ve JavaScript onu okuyamıyor
  // (components/Giris.tsx). Bu, tokenı localStorage'da tutmanın
  // XSS riskinden kaçınmanın bedeli — ve ucuz bir bedel.
  const oturumKontrol = useCallback(() => {
    fetch('/api/v1/auth/ben')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('yetkisiz'))))
      .then((d: { kullanici_adi: string; rol: string }) => setOturum(d))
      .catch(() => setOturum(false))
  }, [])

  useEffect(oturumKontrol, [oturumKontrol])

  if (oturum === null) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-muted">
        Oturum kontrol ediliyor…
      </div>
    )
  }
  if (oturum === false) return <Giris onSuccess={oturumKontrol} />

  return <Panel kullanici={oturum} />
}

function Panel({ kullanici }: { kullanici: { kullanici_adi: string; rol: string } }) {
  useLiveResults()
  const cameras = useStore((s) => s.cameras)
  const setCameras = useStore((s) => s.setCameras)
  const sayfa = useStore((s) => s.sayfa)
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
    <div className="flex h-screen flex-col">
      <Header kullanici={kullanici} />
      {/* ⚠ Alarm paneli SABİT, içerik kayar.
          Alarm kaçırılmaması gereken tek şey; onu kaydırma alanının
          içine koysaydık operatör aşağı indiğinde görünmez olurdu.

          ⚠ Alarm paneli HER SAYFADA duruyor — zaman çizelgesine
          bakarken canlı bir alarm gelirse operatör onu kaçırmamalı.
          Gözetim sisteminde "başka sayfadaydım" bir mazeret değil. */}
      <div className="flex min-h-0 flex-1">
        {sayfa === 'izgara' && (
          <main className="grid flex-1 auto-rows-min gap-3 overflow-y-auto p-4 sm:grid-cols-2 lg:grid-cols-3">
            {cameras.map((camera) => (
              <CameraTile key={camera.name} camera={camera} webrtcBase={webrtcBase} />
            ))}
            {cameras.length === 0 && (
              <p className="text-sm text-muted">Kamera listesi bekleniyor…</p>
            )}
          </main>
        )}
        {sayfa === 'zaman-cizelgesi' && <ZamanCizelgesi />}
        {sayfa === 'kamera' && <KameraDetay webrtcBase={webrtcBase} />}
        <AlertPanel />
      </div>
    </div>
  )
}
