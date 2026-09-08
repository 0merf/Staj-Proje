/** Kamera detay sayfası — PLAN §10.1'in ikinci eksik sayfası.
 *
 * ⚠ NEDEN IZGARADAKİ KUTUCUK YETMİYOR
 * Izgarada bir kutucuk ~320 piksel genişliğinde. Bu boyutta:
 *   · iskelet eklemleri üst üste biniyor
 *   · yüz ifadesi etiketi okunmuyor
 *   · birden çok kişi varsa kutular ayırt edilemiyor
 *
 * Operatör bir alarmı DOĞRULAMAK istediğinde ("gerçekten düşmüş mü?")
 * ızgara görüntüsü karar vermeye yetmiyor. Bu sayfa tek kamerayı tam
 * genişlikte gösteriyor ve yanına o kameranın olay geçmişini koyuyor.
 *
 * ⚠ KUTUCUK BİLEŞENİ YENİDEN KULLANILIYOR, KOPYALANMIYOR
 * `CameraTile` zaten WHEP bağlantısı, kutu ara değerleme, iskelet
 * çizimi ve senkronizasyonu yapıyor. Detay için ikinci bir çizici
 * yazmak, P-14 ve P-26'da düzeltilen hataların ikinci bir kopyasını
 * üretmek olurdu — o hatalar tam olarak çizim kodunda çıkmıştı.
 */
import { useEffect, useState } from 'react'
import { CameraTile } from './CameraTile'
import { useStore } from '../store'
import { ANOMALI_TR, type HistoryEvent } from '../types'

interface Props {
  webrtcBase: string
}

const CIDDIYET_RENK: Record<string, string> = {
  alarm: 'border-bad/60 bg-bad/15 text-bad',
  warning: 'border-warn/60 bg-warn/15 text-warn',
  attention: 'border-line bg-panel text-ink',
}

export function KameraDetay({ webrtcBase }: Props) {
  const cameras = useStore((s) => s.cameras)
  const secili = useStore((s) => s.seciliKamera)
  const kameraAc = useStore((s) => s.kameraAc)
  const setSayfa = useStore((s) => s.setSayfa)
  const playing = useStore((s) => s.playing)
  const toggle = useStore((s) => s.togglePlaying)

  // ⚠ Yapı ZamanCizelgesi ile aynı gerekçeyle değişti (ESLint bulgusu):
  // efektin başında `setOlaylar(null)` basamaklı render tetikliyordu ve
  // istek yarışı vardı — kamera hızlı değiştirilirse ESKİ kameranın
  // yavaş yanıtı YENİ kameranın listesinin üstüne yazabiliyordu.
  // "Yükleniyor" artık türetiliyor: gelen verinin anahtarı (kamera adı)
  // istenen kameradan farklıysa yükleniyoruz.
  const [veri, setVeri] = useState<{
    anahtar: string | null
    olaylar: HistoryEvent[] | null
  }>({ anahtar: null, olaylar: null })

  const camera = cameras.find((c) => c.name === secili) ?? cameras[0]

  // ⚠ Detay sayfasına gelindiğinde video OTOMATİK açılıyor.
  // Izgarada bu davranış yanlış olurdu (20 akış birden = P-24), ama
  // burada tek kamera var ve kullanıcı zaten onu görmeye geldi.
  const kameraAdi = camera?.name ?? null

  useEffect(() => {
    if (kameraAdi && !playing.has(kameraAdi)) toggle(kameraAdi)
    // ⚠ `playing` bağımlılığa KONULMUYOR: konulsaydı kullanıcı videoyu
    // elle kapattığı anda efekt yeniden çalışıp geri açardı.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kameraAdi])

  useEffect(() => {
    if (!kameraAdi) return undefined
    // ⚠ `AbortController`, mutable bir "iptal" bayrağından İYİ:
    // bayrak yalnızca yanıtı yok sayar, controller isteğin KENDİSİNİ
    // iptal eder. Kamera hızlı değiştirilirse ağ da boşa çalışmaz.
    const kontrol = new AbortController()
    fetch(
      `/api/v1/events?camera=${encodeURIComponent(kameraAdi)}&limit=40&saat=24`,
      { signal: kontrol.signal },
    )
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d: { olaylar: HistoryEvent[] }) => {
        setVeri({ anahtar: kameraAdi, olaylar: d.olaylar ?? [] })
      })
      .catch((e: unknown) => {
        // İptal bir hata değil — kullanıcı kamerayı değiştirdi.
        if (e instanceof DOMException && e.name === 'AbortError') return
        setVeri({ anahtar: kameraAdi, olaylar: [] })
      })
    return () => {
      kontrol.abort()
    }
  }, [kameraAdi])

  const olaylar = veri.anahtar === kameraAdi ? veri.olaylar : null

  if (!camera) {
    return <p className="p-4 text-sm text-muted">Kamera listesi bekleniyor…</p>
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-2">
        <button
          onClick={() => setSayfa('izgara')}
          className="rounded border border-line px-2 py-0.5 text-xs text-muted hover:text-ink"
        >
          ← ızgaraya dön
        </button>
        <select
          value={camera.name}
          onChange={(e) => kameraAc(e.target.value)}
          className="rounded border border-line bg-panel px-2 py-0.5 font-mono text-xs"
        >
          {cameras.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name}
              {c.ready ? '' : ' (yayın yok)'}
            </option>
          ))}
        </select>
        <span className="text-xs text-muted">
          {camera.kind}
          {camera.readers !== undefined && ` · ${camera.readers} izleyici`}
        </span>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4 lg:flex-row">
        {/* ⚠ Kutucuk BÜYÜK: ızgaradakiyle aynı bileşen, farklı genişlik.
            Canvas kendi ölçeğini video boyutundan alıyor, yani çizim
            büyütmede bozulmuyor. */}
        <div className="min-w-0 flex-1">
          <CameraTile camera={camera} webrtcBase={webrtcBase} />
        </div>

        {/* ─── O kameranın olay geçmişi ─── */}
        <aside className="w-full shrink-0 lg:w-96">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
            Son 24 saat · {camera.name}
          </h3>
          {olaylar === null && <p className="text-xs text-muted">Yükleniyor…</p>}
          {olaylar?.length === 0 && (
            <p className="text-xs text-muted">
              Bu kamerada son 24 saatte olay yok.
              <br />
              <span className="text-[10px]">
                Sorgu çalıştı ve boş döndü — arıza değil, sessizlik.
              </span>
            </p>
          )}
          <ul className="space-y-1">
            {olaylar?.map((o, i) => (
              <li
                key={`${o.ts}-${i}`}
                className={`rounded border-l-2 px-2 py-1.5 text-[11px] ${
                  CIDDIYET_RENK[o.ciddiyet] ?? CIDDIYET_RENK.attention
                }`}
              >
                <div className="flex items-baseline gap-2">
                  <span className="font-semibold uppercase">
                    {ANOMALI_TR[o.tur] ?? o.tur}
                  </span>
                  {o.track !== null && (
                    <span className="text-[10px] text-muted">kişi #{o.track}</span>
                  )}
                  <span className="ml-auto font-mono text-[10px] text-muted">
                    {new Date(o.ts * 1000).toLocaleTimeString('tr-TR', {
                      hour12: false,
                    })}
                  </span>
                </div>
                {/* Kanıt — açıklanabilirlik ızgaradakiyle aynı ilkede */}
                {o.kanit && Object.keys(o.kanit).length > 0 && (
                  <div className="mt-1 space-y-0.5 text-[10px] text-muted">
                    {Object.entries(o.kanit)
                      .slice(0, 4)
                      .map(([k, v]) => (
                        <div key={k} className="flex justify-between gap-2">
                          <span>{k}</span>
                          <span className="font-mono text-ink">
                            {typeof v === 'number' ? v.toFixed(2) : String(v)}
                          </span>
                        </div>
                      ))}
                  </div>
                )}
                <div className="mt-1 flex gap-3 text-[10px] text-muted">
                  <span>şiddet {(o.skor * 100).toFixed(0)}%</span>
                  {o.tamlik !== null && (
                    <span>kanıt gücü {(o.tamlik * 100).toFixed(0)}%</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  )
}
