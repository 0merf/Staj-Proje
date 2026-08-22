/** Canlı alarm akışı — analitik katmanının çıktısı.
 *
 * ⚠ NEDEN AYRI BİR PANEL, KUTUCUK ÜSTÜNDE ROZET DEĞİL
 * ---------------------------------------------------
 * Alarm, kutucuk KAPALI kameralardan da gelir (backend:
 * api/ws/manager.py · _dispatch_alert). Gözetim sisteminin varlık
 * sebebi kimsenin bakmadığı kamerada olanı bildirmek. Uyarıyı yalnızca
 * kutucuğun üstüne çizseydik, tam da görülmesi gereken alarmlar
 * (kapalı kutucuktakiler) görünmez olurdu.
 *
 * ⚠ KANIT GÖSTERİLİYOR — "anomali var" demek yetmez
 * -------------------------------------------------
 * Her satır hangi ölçümün eşiği neden aştığını taşıyor:
 * "en_boy 1.3 · eğim 78° · değişim 95°/sn". Operatör sebebi
 * göremezse sisteme güvenmez ve alarmları kapatır — K7'nin asıl riski
 * yanlış alarm sayısı değil, operatörün sistemi umursamamaya
 * başlamasıdır (PLAN §8.1 `contributing_signals`).
 */
import { useStore } from '../store'
import { ANOMALI_TR } from '../types'

/** Ciddiyete göre renk. PLAN §6.5.3 seviyeleriyle aynı sözlük. */
const RENK: Record<string, string> = {
  alarm: 'border-bad/60 bg-bad/15 text-bad',
  warning: 'border-warn/60 bg-warn/15 text-warn',
  attention: 'border-line bg-panel text-ink',
}

/** Kanıt alanlarının okunabilir adları ve BİRİMLERİ.
 *
 * ⚠ BİRİM ZORUNLU — ilk sürümde yoktu ve kafa karıştırdı.
 * "kişi 7 normal 2.1 eşik 5.24" satırı, kullanıcı tarafından
 * "kişilerin numarası mı?" diye okundu. Birimsiz bir sayı, okuyanın
 * onu ne sandığına bağlı olarak anlam kazanıyor.
 *
 * Ham anahtarları (`govde_egimi_derece`) ekrana basmak da bir şey
 * anlatmaz; panel ve rapor aynı dili konuşmalı. */
const KANIT_TR: Record<string, [etiket: string, birim: string]> = {
  en_boy_orani: ['en/boy oranı', ''],
  govde_egimi_derece: ['gövde eğimi', '°'],
  egim_degisim_hizi: ['eğim değişimi', '°/sn'],
  govde_hizi_govde_sn: ['hız', ' gövde/sn'],
  olculen_p99: ['ölçülen p99', ' gövde/sn'],
  oyalanma_saniye: ['aynı yerde', ' sn'],
  kisi: ['kişi sayısı', ''],
  taban: ['bu kameranın normali', ' kişi'],
  esik: ['eşik', ''],

  // ─── KATMAN A kanıtları (anomaly/normalcy.py) ───
  // Bunlar kuraldan değil ÖĞRENİLEN profilden geliyor; etiketleri de
  // "eşik aşıldı" değil "bu kameranın normaline uymuyor" dilinde.
  nadir_bolge: ['buraya nadiren gidilir', ''],
  bolge_ziyaret: ['bu bölgede toplam gözlem', ' kez'],
  hiz_sapmasi_sigma: ['bölge normalinden sapma', 'σ'],
  bolge_normal_hiz: ['bu bölgenin normal hızı', ' gövde/sn'],
  yon_orani: ['bu yöne gidenlerin oranı', ''],
  kisi_sapmasi_sigma: ['kişi sayısı sapması', 'σ'],
  kamera_normal_kisi: ['bu kameranın normali', ' kişi'],
}

function saat(rx: number): string {
  // `rx` performance.now() tabanlı; duvar saatine çevirmek için
  // sayfa açılış anını referans alıyoruz.
  const d = new Date(performance.timeOrigin + rx)
  return d.toLocaleTimeString('tr-TR', { hour12: false })
}

export function AlertPanel() {
  const alerts = useStore((s) => s.alerts)

  return (
    <aside className="flex w-80 shrink-0 flex-col border-l border-line bg-panel/40">
      <header className="flex items-center gap-2 border-b border-line px-3 py-2">
        <span className="text-sm font-medium">Alarmlar</span>
        <span className="rounded bg-panel px-1.5 py-0.5 text-xs text-muted">
          {alerts.length}
        </span>
        <span className="ml-auto text-[10px] uppercase tracking-wide text-muted">
          kapalı kameralar dâhil
        </span>
      </header>

      <div className="flex-1 overflow-y-auto">
        {alerts.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted">
            Henüz alarm yok.
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
                    {saat(a.rx)}
                  </span>
                </div>

                {/* ⚠ KANIT — alarmın neden üretildiği */}
                {/* Her kanıt kendi satırında: yan yana dizilince
                    hangi sayının hangi etikete ait olduğu
                    karışıyordu. */}
                <div className="mt-1 space-y-0.5 text-[10px] text-muted">
                  {Object.entries(a.evidence).map(([k, v]) => {
                    const [etiket, birim] = KANIT_TR[k] ?? [k, '']
                    return (
                      <div key={k} className="flex justify-between gap-2">
                        <span>{etiket}</span>
                        <span className="font-mono text-ink">
                          {v}
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
                  {/* ⚠ Tamlık: özellik vektörü kaç örnekten hesaplandı.
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
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  )
}
