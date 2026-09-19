/** Canlı alarm akışı — analitik katmanının çıktısı.
 *
 * Neden ayrı bir panel, kutucuk üstünde rozet değil
 * ---------------------------------------------------
 * Alarm, kutucuk kapalı kameralardan da gelir (backend:
 * api/ws/manager.py · _dispatch_alert). Gözetim sisteminin varlık
 * sebebi kimsenin bakmadığı kamerada olanı bildirmek. Uyarıyı yalnızca
 * kutucuğun üstüne çizseydik, tam da görülmesi gereken alarmlar
 * (kapalı kutucuktakiler) görünmez olurdu.
 *
 * Kanıt gösteriliyor — "anomali var" demek yetmez
 * -------------------------------------------------
 * Her satır hangi ölçümün eşiği neden aştığını taşıyor:
 * "en_boy 1.3 · eğim 78° · değişim 95°/sn". Operatör sebebi
 * göremezse sisteme güvenmez ve alarmları kapatır — K7'nin asıl riski
 * yanlış alarm sayısı değil, operatörün sistemi umursamamaya
 * başlamasıdır (`contributing_signals`).
 */
import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { kanitDegeri, kanitEtiketi } from '../lib/kanit'
import { ANOMALI_TR } from '../types'

/** Ciddiyete göre renk. Proje planındaki seviyelerle aynı sözlük. */
const RENK: Record<string, string> = {
  alarm: 'border-bad/60 bg-bad/15 text-bad',
  warning: 'border-warn/60 bg-warn/15 text-warn',
  attention: 'border-line bg-panel text-ink',
}

function saat(rx: number): string {
  // `rx` performance.now() tabanlı; duvar saatine çevirmek için
  // sayfa açılış anını referans alıyoruz.
  const d = new Date(performance.timeOrigin + rx)
  return d.toLocaleTimeString('tr-TR', { hour12: false })
}

/** Olay klibi oynatıcısı — "göster" sorusunun cevabı.
 *
 * Neden gömülü oynatıcı, indirme bağlantısı değil
 * Operatörün sorusu "bu dosyayı bilgisayarıma al" değil, "ne olduğunu
 * göster". İndirme, klibi sistemin denetiminden kalıcı olarak
 * çıkarıyor; izlemek çıkarmıyor. Sunucu da bunu destekliyor
 * (`Content-Disposition: inline`) ve her erişimi denetim izine
 * yazıyor (G19).
 *
 * Tembel yükleme (`preload="none"` + açılınca kur)
 * 50 alarmlık bir listede her satır kendi videosunu önden yüklerse
 * tarayıcı 50 eşzamanlı istek açar. Klip ancak operatör açtığında
 * isteniyor.
 */
export function KlipOynatici({ anahtar }: { anahtar: string }) {
  const [acik, setAcik] = useState(false)
  const [hata, setHata] = useState(false)

  if (!acik) {
    return (
      <button
        type="button"
        onClick={() => setAcik(true)}
        className="mt-1.5 w-full rounded border border-line bg-panel px-2 py-1 text-[10px] text-muted hover:text-ink"
        title="Olay anının ±10 sn'lik kaydı. Her görüntüleme denetim izine yazılır."
      >
        ▶ kanıt klibini göster
      </button>
    )
  }

  if (hata) {
    return (
      <p className="mt-1.5 text-[10px] text-warn">
        Klip bulunamadı.
        {/* En olası sebep bir arıza değil: sürekli kayıt varsayılan
            olarak kapalı (~14 GB/saat) ve kayıt yokken kesilecek bir
            şey de yok. Bunu söylemek, operatörün olmayan bir hatayı
            aramasını engelliyor. */}
        <br />
        <span className="text-muted">
          Sürekli kayıt kapalıysa (varsayılan) klip üretilmez.
        </span>
      </p>
    )
  }

  return (
    <video
      // Anahtar `a/b/c.mp4` biçiminde; her parça ayrı ayrı kodlanmalı,
      // aksi hâlde `encodeURIComponent` bölü işaretlerini de kaçırır
      // ve sunucudaki yol eşleşmez.
      src={`/api/v1/events/klip/${anahtar.split('/').map(encodeURIComponent).join('/')}`}
      controls
      autoPlay
      preload="none"
      onError={() => setHata(true)}
      className="mt-1.5 w-full rounded border border-line"
    />
  )
}

export function AlertPanel() {
  const alerts = useStore((s) => s.alerts)
  const loadHistory = useStore((s) => s.loadHistory)
  const historyLoaded = useStore((s) => s.historyLoaded)

  // Açılışta geçmişi yükle
  // Panel kapalıyken üretilen alarmlar 30.08.2026'ya kadar
  // görülemiyordu: panel her açıldığında liste boştu ve sistem hiç
  // alarm üretmemiş gibi görünüyordu. Artık son 24 saat
  // TimescaleDB'den geliyor.
  //
  // Bir kez çalışıyor (`historyLoaded`): canlı akış zaten yeni
  // olayları getiriyor, tekrar tekrar sorgulamak hem gereksiz hem de
  // canlı kayıtları geçmiş kopyalarıyla karıştırma riski.
  useEffect(() => {
    if (!historyLoaded) void loadHistory()
  }, [historyLoaded, loadHistory])

  const canli = alerts.filter((a) => !a.gecmis).length

  return (
    <aside className="flex w-80 shrink-0 flex-col border-l border-line bg-panel/40">
      <header className="flex items-center gap-2 border-b border-line px-3 py-2">
        <span className="text-sm font-medium">Alarmlar</span>
        <span className="rounded bg-panel px-1.5 py-0.5 text-xs text-muted">
          {alerts.length}
        </span>
        {/* Canlı ile geçmiş ayrı sayılıyor: "12 alarm var" cümlesi,
            hepsi bu oturumda mı oldu yoksa dün geceden mi kaldı,
            bilinmeden okunamaz. */}
        {canli < alerts.length && (
          <span
            className="text-[10px] text-muted"
            title="Bu oturumda canlı gelen / son 24 saatin geçmişinden yüklenen"
          >
            {canli} canlı · {alerts.length - canli} geçmiş
          </span>
        )}
        <span className="ml-auto text-[10px] uppercase tracking-wide text-muted">
          kapalı kameralar dâhil
        </span>
      </header>

      <div className="flex-1 overflow-y-auto">
        {alerts.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted">
            {historyLoaded ? 'Son 24 saatte alarm yok.' : 'Geçmiş yükleniyor…'}
            <br />
            <span className="text-[10px]">
              Kural motoru düşme, koşma, oyalanma ve kalabalık arıyor.
            </span>
          </p>
        ) : (
          <ul className="divide-y divide-line">
            {alerts.map((a, i) => (
              <li
                key={`${a.cam}-${a.rx}-${i}`}
                className={`border-l-2 px-3 py-2 ${RENK[a.severity] ?? RENK.attention}`}
              >
                <div className="flex items-baseline gap-2">
                  <span className="text-xs font-semibold uppercase">
                    {ANOMALI_TR[a.anomaly] ?? a.anomaly}
                  </span>
                  <span className="font-mono text-xs">{a.cam}</span>
                  {a.track !== null && (
                    <span
                      className="text-[10px] text-muted"
                      title="Takip kimliği — bu kişiye sistemin verdiği numara"
                    >
                      kişi #{a.track}
                    </span>
                  )}
                  <span className="ml-auto font-mono text-[10px] text-muted">
                    {/* Geçmiş kayıtlarda nokta: operatör "şu an oluyor"
                        ile "olmuştu"yu ayırt edebilmeli. */}
                    {a.gecmis && (
                      <span title="geçmişten yüklendi" className="mr-1">
                        ·
                      </span>
                    )}
                    {saat(a.rx)}
                  </span>
                </div>

                {/* kanıt — alarmın neden üretildiği */}
                {/* Her kanıt kendi satırında: yan yana dizilince
                    hangi sayının hangi etikete ait olduğu
                    karışıyordu. */}
                <div className="mt-1 space-y-0.5 text-[10px] text-muted">
                  {Object.entries(a.evidence).map(([k, v]) => {
                    const [etiket, birim] = kanitEtiketi(k)
                    return (
                      <div key={k} className="flex justify-between gap-2">
                        <span>{etiket}</span>
                        <span className="font-mono text-ink">
                          {kanitDegeri(v)}
                          {birim}
                        </span>
                      </div>
                    )
                  })}
                </div>

                <div className="mt-1.5 flex items-center gap-3 border-t border-line/50 pt-1 text-[10px] text-muted">
                  <span title="Eşiğin ne kadar aşıldığı">
                    şiddet {(a.score * 100).toFixed(0)}%
                  </span>
                  {/* Tamlık: özellik vektörü kaç örnekten hesaplandı.
                      Düşükse alarm daha az güvenilir — ölçüm izlerin
                      medyan ömrünün ~4 kare olduğunu gösterdi, yani
                      bu değer sık sık 1.0'ın altında olacak. */}
                  <span
                    className={a.completeness < 0.5 ? 'text-warn' : undefined}
                    title="Özellik vektörünün tamlığı — düşükse az örnekten hesaplandı"
                  >
                    kanıt gücü {(a.completeness * 100).toFixed(0)}%
                  </span>
                </div>

                {/* kanıt klibi — "alarm bir iddia, klip bir kanıt"
                    (alerting/klip.py). Klip yalnızca ciddi olaylarda
                    ve yalnızca sürekli kayıt açıkken üretiliyor, bu
                    yüzden satırların çoğunda görünmeyecek. */}
                {a.klip && <KlipOynatici anahtar={a.klip} />}
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  )
}
