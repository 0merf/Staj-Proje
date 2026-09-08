/** Olay zaman çizelgesi — PLAN §10.1'in eksik sayfası.
 *
 * ⚠ NEDEN ALARM PANELİ YETMİYOR
 * Alarm paneli bir LİSTE: "şu oldu, şu oldu, şu oldu." Liste iki
 * soruyu cevaplayamıyor:
 *
 *   · **Ne zaman yoğunlaştı?** Gece 03:00'te bir küme mi var, yoksa
 *     alarmlar güne eşit mi yayılmış?
 *   · **Hangi kamera?** Aynı saatte üç kamera birden alarm verdiyse
 *     bu ortak bir sebeptir (ışık değişimi, gölge) — listede yan yana
 *     görünmezler, çünkü liste zamana göre sıralı, kameraya göre değil.
 *
 * Zaman çizelgesi her iki ekseni birden gösteriyor: satırlar kamera,
 * sütunlar saat. Bir bakışta "nerede ve ne zaman" görülüyor.
 *
 * ⚠ VERİ KAYNAĞI SÜREKLİ TOPLULAŞTIRMA
 * `/api/v1/events/ozet` TimescaleDB'nin `olay_saatlik` görünümünden
 * geliyor — saatlik özet arka planda hazır tutuluyor, her açılışta
 * yüz binlerce satır taranmıyor (ADR-0010).
 *
 * ⚠ RENK CİDDİYETE GÖRE, YOĞUNLUĞA GÖRE DEĞİL
 * Bir hücredeki 20 "oyalanma" ile 1 "düşme" aynı renkte olsaydı,
 * operatör yoğunluğu ciddiyet sanırdı. Renk en yüksek ciddiyeti,
 * sayı ise adedi gösteriyor.
 */
import { useEffect, useMemo, useState } from 'react'
import { useStore } from '../store'
import { ANOMALI_TR } from '../types'

interface OzetSatir {
  saat: number
  camera: string
  tur: string
  ciddiyet: string
  adet: number
  ort_skor: number
  azami_skor: number
}

/** Ciddiyet sırası — hücre rengini en yükseği belirliyor. */
const CIDDIYET_SIRA: Record<string, number> = { attention: 0, warning: 1, alarm: 2 }
const CIDDIYET_RENK = ['bg-panel border-line', 'bg-warn/25 border-warn/50', 'bg-bad/30 border-bad/60']

export function ZamanCizelgesi() {
  const cameras = useStore((s) => s.cameras)
  const kameraAc = useStore((s) => s.kameraAc)
  const [saat, setSaat] = useState(24)
  // ⚠⚠ 08.09.2026 — YAPI DEĞİŞTİ, ÜÇ HATA BİRDEN DÜZELDİ (ESLint bulgusu)
  //
  // Eski hâli üç ayrı `useState` + efektin BAŞINDA `setSatirlar(null)`
  // idi. ESLint ilk kurulduğu koşuda bunu işaretledi ve arkasından üç
  // gerçek kusur çıktı:
  //
  // 1. `Date.now()` `useMemo` içinde çağrılıyordu. useMemo yalnızca
  //    `[satirlar, saat]` değişince yeniden hesaplanıyor — yani SAAT
  //    KOVALARI son veri çekiminde DONUYORDU. Panel bir saat açık
  //    kalırsa zaman ekseni geride kalıyor ve kimse fark etmiyor.
  //    Artık `simdi` veriyle birlikte state'e yazılıyor; useMemo saf.
  //
  // 2. İstek yarışı: `saat` hızlı değiştirilirse ESKİ ve yavaş yanıt,
  //    YENİ yanıtın üstüne yazabiliyordu. `iptal` bayrağı kapattı.
  //
  // 3. Efektin başında setState → basamaklı yeniden render. Artık
  //    "yükleniyor" durumu TÜRETİLİYOR: gelen verinin anahtarı
  //    istenen `saat`ten farklıysa yükleniyoruz.
  const [veri, setVeri] = useState<{
    anahtar: number
    satirlar: OzetSatir[] | null
    hata: string | null
    simdi: number
  }>({ anahtar: -1, satirlar: null, hata: null, simdi: 0 })

  useEffect(() => {
    // ⚠ `AbortController`, mutable bayraktan iyi: isteğin kendisini
    // iptal eder, yalnızca yanıtı yok saymakla kalmaz.
    const kontrol = new AbortController()
    const istekAni = Date.now() / 1000
    fetch(`/api/v1/events/ozet?saat=${saat}`, { signal: kontrol.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d: { satirlar: OzetSatir[] }) => {
        setVeri({
          anahtar: saat,
          satirlar: d.satirlar ?? [],
          hata: null,
          simdi: istekAni,
        })
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === 'AbortError') return
        setVeri({
          anahtar: saat,
          satirlar: null,
          hata: 'Olay özeti alınamadı — alarm worker çalışıyor mu?',
          simdi: istekAni,
        })
      })
    return () => {
      kontrol.abort()
    }
  }, [saat])

  // Yükleniyor durumu TÜRETİLİYOR, ayrı bir state değil.
  const yukleniyor = veri.anahtar !== saat
  const satirlar = yukleniyor ? null : veri.satirlar
  const hata = yukleniyor ? null : veri.hata

  /** Saat kovaları (en eskiden yeniye) ve kamera → kova → olaylar. */
  const { kovalar, izgara, kameraListesi, toplam } = useMemo(() => {
    const bosluk = {
      kovalar: [] as number[],
      izgara: new Map<string, Map<number, OzetSatir[]>>(),
      kameraListesi: [] as string[],
      toplam: 0,
    }
    if (!satirlar) return bosluk

    // ⚠ Kovalar VERİDEN değil ZAMANDAN üretiliyor. Yalnızca olay olan
    // saatleri göstermek, "sessiz saatler"i görünmez yapardı — oysa
    // bir gözetim panelinde sessizlik de bilgidir.
    // ⚠ `Date.now()` BURADA ÇAĞRILMIYOR — useMemo saf olmak zorunda.
    // Zaman, veriyle birlikte state'e yazıldı (bkz. yukarıdaki not).
    const suAnkiKova = Math.floor(veri.simdi / 3600) * 3600
    const kovalar: number[] = []
    for (let i = saat - 1; i >= 0; i--) kovalar.push(suAnkiKova - i * 3600)

    const izgara = new Map<string, Map<number, OzetSatir[]>>()
    let toplam = 0
    for (const s of satirlar) {
      const kova = Math.floor(s.saat / 3600) * 3600
      let satirHarita = izgara.get(s.camera)
      if (!satirHarita) {
        satirHarita = new Map()
        izgara.set(s.camera, satirHarita)
      }
      const mevcut = satirHarita.get(kova) ?? []
      mevcut.push(s)
      satirHarita.set(kova, mevcut)
      toplam += s.adet
    }

    // ⚠ TÜM kameralar listeleniyor, yalnızca alarm verenler değil.
    // "cam-18'de hiç alarm yok" bir bulgudur (kontrol kamerası) ve
    // ancak satır görünürse fark edilir.
    const bilinen = cameras.map((c) => c.name)
    const ekstra = [...izgara.keys()].filter((k) => !bilinen.includes(k))
    return { kovalar, izgara, kameraListesi: [...bilinen, ...ekstra], toplam }
  }, [satirlar, saat, cameras, veri.simdi])

  return (
    <div className="flex-1 overflow-auto p-4">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h2 className="text-sm font-semibold">Olay Zaman Çizelgesi</h2>
        <div className="flex gap-1">
          {[6, 24, 72].map((s) => (
            <button
              key={s}
              onClick={() => setSaat(s)}
              className={`rounded px-2 py-0.5 text-xs ${
                saat === s ? 'bg-panel text-ink' : 'text-muted hover:text-ink'
              }`}
            >
              {s} saat
            </button>
          ))}
        </div>
        {satirlar && (
          <span className="text-xs text-muted">
            {toplam} olay · {izgara.size} kamerada
          </span>
        )}
        <span className="ml-auto flex items-center gap-3 text-[10px] text-muted">
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-sm border border-line bg-panel" /> dikkat
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-sm border border-warn/50 bg-warn/25" /> uyarı
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-sm border border-bad/60 bg-bad/30" /> alarm
          </span>
        </span>
      </div>

      {hata && <p className="text-xs text-warn">{hata}</p>}
      {!satirlar && !hata && <p className="text-xs text-muted">Yükleniyor…</p>}

      {satirlar && (
        <div className="overflow-x-auto">
          <table className="border-separate border-spacing-0.5 text-[10px]">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-bg pr-2 text-left font-normal text-muted">
                  kamera
                </th>
                {kovalar.map((k) => {
                  const d = new Date(k * 1000)
                  // ⚠ Yalnızca 0, 6, 12, 18 saatlerinde etiket: 72
                  // saatlik görünümde her sütuna etiket koymak okunmaz
                  // bir şerit üretiyordu.
                  const goster = d.getHours() % 6 === 0
                  return (
                    <th
                      key={k}
                      className="w-5 pb-1 font-normal text-muted"
                      title={d.toLocaleString('tr-TR')}
                    >
                      {goster ? String(d.getHours()).padStart(2, '0') : ''}
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {kameraListesi.map((kam) => {
                const satirHarita = izgara.get(kam)
                return (
                  <tr key={kam}>
                    <td className="sticky left-0 z-10 bg-bg pr-2 font-mono text-muted">
                      <button
                        onClick={() => kameraAc(kam)}
                        className="hover:text-ink hover:underline"
                        title="Kamera detayını aç"
                      >
                        {kam}
                      </button>
                    </td>
                    {kovalar.map((k) => {
                      const olaylar = satirHarita?.get(k)
                      if (!olaylar) {
                        return (
                          <td
                            key={k}
                            className="h-5 w-5 rounded-sm border border-line/30"
                          />
                        )
                      }
                      const adet = olaylar.reduce((t, o) => t + o.adet, 0)
                      const enCiddi = Math.max(
                        ...olaylar.map((o) => CIDDIYET_SIRA[o.ciddiyet] ?? 0),
                      )
                      const ozet = olaylar
                        .map((o) => `${ANOMALI_TR[o.tur] ?? o.tur} ×${o.adet}`)
                        .join(' · ')
                      return (
                        <td
                          key={k}
                          title={`${kam} · ${new Date(k * 1000).toLocaleString('tr-TR')}\n${ozet}`}
                          className={`h-5 w-5 cursor-default rounded-sm border text-center ${CIDDIYET_RENK[enCiddi]}`}
                        >
                          {adet > 0 ? adet : ''}
                        </td>
                      )
                    })}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {satirlar && satirlar.length === 0 && (
        <p className="mt-4 text-xs text-muted">
          Bu aralıkta hiç olay yok.
          <br />
          {/* ⚠ "Hiçbir şey yok" ile "bakamadım" ayrımı — ADR-0010'daki
              en öğretici hata tam buydu. Kullanıcıya hangisi olduğu
              söylenmeli. */}
          <span className="text-[10px]">
            Sorgu çalıştı ve boş döndü — bu bir arıza değil, sessizlik.
          </span>
        </p>
      )}
    </div>
  )
}
