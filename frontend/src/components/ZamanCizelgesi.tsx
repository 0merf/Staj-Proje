/** Olaylar sayfası — ısı haritası + GERÇEK OLAY TABLOSU.
 *
 * ⚠⚠ 10.09.2026 — YENİDEN TASARLANDI, ÇÜNKÜ OKUNMUYORDU
 * ------------------------------------------------------
 * Kullanıcının tespiti: *"Bu zaman çizelgesinin olayı ne, burası ne
 * anlatıyor? Ben hiçbir şey anlamadım. Kutuların üstüne tıklıyorum
 * herhangi bir bilgi de çıkmıyor."*
 *
 * Haklıydı ve sebebi koddaydı: hücreler `cursor-default` idi ve
 * `onClick` yoktu. Tek bilgi kanalı `title` tooltip'iydi — yani
 * bilgi vardı ama **ulaşılamıyordu**.
 *
 * ⭐ Bu, projenin P-45'iyle aynı sınıf hata: *"klipler kesiliyordu,
 * kimse göremiyordu."* Bir şeyin ÜRETİLMİŞ olması, kullanılabilir
 * olması demek değil. Kapsam maddeleri modüllerle değil, kullanıcının
 * yapabildiği işlerle işaretlenmeli — "ısı haritası çiziliyor" bir
 * modül ifadesi; "operatör bir hücreye tıklayıp o saatteki olayları
 * okuyabiliyor" bir kapsam ifadesi.
 *
 * ⚠ ISI HARİTASI NEDEN SİLİNMEDİ
 * Kullanıcı "gerekirse değiştir" dedi, "sil" demedi — ve harita iki
 * soruyu tablodan daha iyi cevaplıyor: *ne zaman yoğunlaştı* ve
 * *hangi kameralar birlikte alarm verdi*. 2102 satırlık bir tabloda
 * "cam-15 ve cam-17 aynı saatte patlamış" görünmez. Harita artık
 * tablonun FİLTRESİ: bir hücreye tıkla, tablo o kameraya ve o saate
 * daralsın.
 *
 * ⚠ VERİ KAYNAĞI İKİ AYRI UÇ
 *   · harita  → `/api/v1/events/ozet`  (saatlik toplulaştırma, ucuz)
 *   · tablo   → `/api/v1/events`       (tek tek olaylar, filtreli)
 * Haritayı ham olaylardan çizmek her açılışta yüz binlerce satır
 * taramak olurdu (ADR-0010).
 *
 * ⚠ RENK CİDDİYETE GÖRE, YOĞUNLUĞA GÖRE DEĞİL
 * Bir hücredeki 20 "oyalanma" ile 1 "düşme" aynı renkte olsaydı,
 * operatör yoğunluğu ciddiyet sanırdı. Renk en yüksek ciddiyeti,
 * sayı ise adedi gösteriyor.
 */
import { useEffect, useMemo, useState } from 'react'
import { useStore } from '../store'
import { ANOMALI_TR, type HistoryEvent } from '../types'
import { KlipOynatici } from './AlertPanel'

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
const CIDDIYET_RENK = [
  'bg-panel border-line',
  'bg-warn/25 border-warn/50',
  'bg-bad/30 border-bad/60',
]
const CIDDIYET_TR: Record<string, string> = {
  attention: 'dikkat',
  warning: 'uyarı',
  alarm: 'alarm',
}
const SATIR_RENK: Record<string, string> = {
  alarm: 'border-bad/60 text-bad',
  warning: 'border-warn/60 text-warn',
  attention: 'border-line text-ink',
}

/** Seçili hücre: hangi kamera, hangi saat kovası. */
interface Secim {
  camera: string
  kova: number
}

function saatMetni(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('tr-TR', { hour12: false })
}

function tarihMetni(ts: number): string {
  return new Date(ts * 1000).toLocaleString('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export function ZamanCizelgesi() {
  const cameras = useStore((s) => s.cameras)
  const kameraAc = useStore((s) => s.kameraAc)
  const [saat, setSaat] = useState(24)
  const [secim, setSecim] = useState<Secim | null>(null)
  const [filtreKamera, setFiltreKamera] = useState('')
  const [filtreTur, setFiltreTur] = useState('')
  const [filtreCiddiyet, setFiltreCiddiyet] = useState('')
  const [acikSatir, setAcikSatir] = useState<string | null>(null)

  // ⚠⚠ 08.09.2026 — YAPI DEĞİŞTİ, ÜÇ HATA BİRDEN DÜZELDİ (ESLint bulgusu)
  //
  // Eski hâli üç ayrı `useState` + efektin BAŞINDA `setSatirlar(null)`
  // idi. ESLint ilk kurulduğu koşuda bunu işaretledi ve arkasından üç
  // gerçek kusur çıktı:
  //
  // 1. `Date.now()` `useMemo` içinde çağrılıyordu. useMemo yalnızca
  //    `[satirlar, saat]` değişince yeniden hesaplanıyor — yani SAAT
  //    KOVALARI son veri çekiminde DONUYORDU.
  // 2. İstek yarışı: `saat` hızlı değiştirilirse ESKİ ve yavaş yanıt,
  //    YENİ yanıtın üstüne yazabiliyordu.
  // 3. Efektin başında setState → basamaklı yeniden render.
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
        setVeri({ anahtar: saat, satirlar: d.satirlar ?? [], hata: null, simdi: istekAni })
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
  const { kovalar, izgara, kameraListesi, toplam, turler } = useMemo(() => {
    const bosluk = {
      kovalar: [] as number[],
      izgara: new Map<string, Map<number, OzetSatir[]>>(),
      kameraListesi: [] as string[],
      toplam: 0,
      turler: [] as string[],
    }
    if (!satirlar) return bosluk

    // ⚠ Kovalar VERİDEN değil ZAMANDAN üretiliyor. Yalnızca olay olan
    // saatleri göstermek, "sessiz saatler"i görünmez yapardı — oysa
    // bir gözetim panelinde sessizlik de bilgidir.
    const suAnkiKova = Math.floor(veri.simdi / 3600) * 3600
    const kovalar: number[] = []
    for (let i = saat - 1; i >= 0; i--) kovalar.push(suAnkiKova - i * 3600)

    const izgara = new Map<string, Map<number, OzetSatir[]>>()
    const turKumesi = new Set<string>()
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
      turKumesi.add(s.tur)
    }

    // ⚠ TÜM kameralar listeleniyor, yalnızca alarm verenler değil.
    // "cam-18'de hiç alarm yok" bir bulgudur (kontrol kamerası) ve
    // ancak satır görünürse fark edilir.
    const bilinen = cameras.map((c) => c.name)
    const ekstra = [...izgara.keys()].filter((k) => !bilinen.includes(k))
    return {
      kovalar,
      izgara,
      kameraListesi: [...bilinen, ...ekstra],
      toplam,
      turler: [...turKumesi].sort(),
    }
  }, [satirlar, saat, cameras, veri.simdi])

  // ─────────────────────────────────────────────────────────────
  // OLAY TABLOSU — tek tek kayıtlar
  // ─────────────────────────────────────────────────────────────
  const [olaylar, setOlaylar] = useState<{
    anahtar: string
    kayitlar: HistoryEvent[] | null
    hata: boolean
  }>({ anahtar: '', kayitlar: null, hata: false })

  // Sorgu anahtarı: filtrelerin tamamı. Efekt buna bağlı, tek tek
  // filtrelere değil — yeni bir filtre eklendiğinde bağımlılık
  // listesini güncellemeyi unutma riski kalmıyor.
  const sorgu = useMemo(() => {
    const p = new URLSearchParams()
    p.set('limit', '200')
    if (secim) {
      // ⚠ Hücre seçiliyse `saat` DEĞİL pencere gönderiliyor: hücre
      // "şu kamera, şu saat" demek ve "son N saat" bunu ifade edemez.
      p.set('camera', secim.camera)
      p.set('bas', String(secim.kova))
      p.set('bit', String(secim.kova + 3600))
    } else {
      p.set('saat', String(saat))
      if (filtreKamera) p.set('camera', filtreKamera)
    }
    if (filtreTur) p.set('tur', filtreTur)
    if (filtreCiddiyet) p.set('ciddiyet', filtreCiddiyet)
    return p.toString()
  }, [secim, saat, filtreKamera, filtreTur, filtreCiddiyet])

  useEffect(() => {
    const kontrol = new AbortController()
    fetch(`/api/v1/events?${sorgu}`, { signal: kontrol.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d: { olaylar: HistoryEvent[] }) => {
        setOlaylar({ anahtar: sorgu, kayitlar: d.olaylar ?? [], hata: false })
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === 'AbortError') return
        setOlaylar({ anahtar: sorgu, kayitlar: null, hata: true })
      })
    return () => {
      kontrol.abort()
    }
  }, [sorgu])

  const tabloYukleniyor = olaylar.anahtar !== sorgu
  const kayitlar = tabloYukleniyor ? null : olaylar.kayitlar

  const filtreVar = secim !== null || filtreKamera || filtreTur || filtreCiddiyet
  const temizle = () => {
    setSecim(null)
    setFiltreKamera('')
    setFiltreTur('')
    setFiltreCiddiyet('')
  }

  return (
    <div className="flex-1 overflow-auto p-4">
      {/* ═══ ISI HARİTASI ═══ */}
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h2 className="text-sm font-semibold">Olay Zaman Çizelgesi</h2>
        <div className="flex gap-1">
          {[6, 24, 72].map((s) => (
            <button
              key={s}
              onClick={() => {
                setSaat(s)
                setSecim(null)
              }}
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

      {/* ⚠ Kullanım ipucu görünür olmalı: eski sürümde hücrelerin bilgi
          taşıdığı YALNIZCA tooltip'ten anlaşılıyordu ve kimse tooltip
          aramıyor. */}
      <p className="mb-2 text-[10px] text-muted">
        Bir hücreye tıklayın — aşağıdaki tablo o kameranın o saatine daralır.
        Satırlar kamera, sütunlar saat.
      </p>

      {hata && <p className="text-xs text-warn">{hata}</p>}
      {!satirlar && !hata && <p className="text-xs text-muted">Yükleniyor…</p>}

      {satirlar && (
        <div className="overflow-x-auto">
          {/* ⚠ `data-testid`: iki tablonun da "kamera" başlığı var ve
              rol tabanlı seçiciler ikisini birden buluyor. Testin
              hangisine baktığı belirsiz kalmamalı. */}
          <table
            data-testid="isi-haritasi"
            className="border-separate border-spacing-0.5 text-[10px]"
          >
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
                      const olaylarKova = satirHarita?.get(k)
                      const secili = secim?.camera === kam && secim.kova === k
                      if (!olaylarKova) {
                        return (
                          <td
                            key={k}
                            className="h-5 w-5 rounded-sm border border-line/30"
                          />
                        )
                      }
                      const adet = olaylarKova.reduce((t, o) => t + o.adet, 0)
                      const enCiddi = Math.max(
                        ...olaylarKova.map((o) => CIDDIYET_SIRA[o.ciddiyet] ?? 0),
                      )
                      const ozet = olaylarKova
                        .map((o) => `${ANOMALI_TR[o.tur] ?? o.tur} ×${o.adet}`)
                        .join(' · ')
                      return (
                        <td key={k} className="p-0">
                          <button
                            onClick={() => {
                              setAcikSatir(null)
                              setSecim(secili ? null : { camera: kam, kova: k })
                            }}
                            title={`${kam} · ${new Date(k * 1000).toLocaleString('tr-TR')}\n${ozet}\n\n(tıkla: tabloyu bu saate daralt)`}
                            className={`h-5 w-5 cursor-pointer rounded-sm border text-center text-[10px] transition-all hover:brightness-150 ${
                              CIDDIYET_RENK[enCiddi]
                            } ${secili ? 'ring-2 ring-ok ring-offset-1 ring-offset-bg' : ''}`}
                          >
                            {adet > 0 ? adet : ''}
                          </button>
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
              en öğretici hata tam buydu. */}
          <span className="text-[10px]">
            Sorgu çalıştı ve boş döndü — bu bir arıza değil, sessizlik.
          </span>
        </p>
      )}

      {/* ═══ OLAY TABLOSU ═══ */}
      <div className="mt-6 border-t border-line pt-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold">Olaylar</h2>

          {secim ? (
            /* ⚠ Seçim bir ÇİP olarak gösteriliyor: filtreli bir tabloya
               bakarken bunu unutmak, "olay yok" diye yanlış sonuç
               çıkarmanın en kolay yolu. */
            <button
              onClick={() => setSecim(null)}
              className="rounded border border-ok/50 bg-ok/10 px-2 py-0.5 font-mono text-[10px] text-ok"
              title="Seçimi kaldır"
            >
              {secim.camera} · {tarihMetni(secim.kova)}–
              {new Date((secim.kova + 3600) * 1000).getHours()}:00 ×
            </button>
          ) : (
            <select
              value={filtreKamera}
              onChange={(e) => setFiltreKamera(e.target.value)}
              className="rounded border border-line bg-panel px-2 py-0.5 font-mono text-[11px]"
            >
              <option value="">tüm kameralar</option>
              {kameraListesi.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          )}

          <select
            value={filtreTur}
            onChange={(e) => setFiltreTur(e.target.value)}
            className="rounded border border-line bg-panel px-2 py-0.5 text-[11px]"
          >
            <option value="">tüm türler</option>
            {turler.map((t) => (
              <option key={t} value={t}>
                {ANOMALI_TR[t] ?? t}
              </option>
            ))}
          </select>

          <select
            value={filtreCiddiyet}
            onChange={(e) => setFiltreCiddiyet(e.target.value)}
            className="rounded border border-line bg-panel px-2 py-0.5 text-[11px]"
          >
            <option value="">her ciddiyet</option>
            <option value="alarm">alarm</option>
            <option value="warning">uyarı</option>
            <option value="attention">dikkat</option>
          </select>

          {filtreVar && (
            <button
              onClick={temizle}
              className="rounded border border-line px-2 py-0.5 text-[11px] text-muted hover:text-ink"
            >
              filtreyi temizle
            </button>
          )}

          {kayitlar && (
            <span className="ml-auto text-[11px] text-muted">
              {kayitlar.length} kayıt
              {kayitlar.length === 200 && ' (üst sınır — daraltın)'}
            </span>
          )}
        </div>

        {olaylar.hata && !tabloYukleniyor && (
          <p className="text-xs text-warn">Olaylar alınamadı.</p>
        )}
        {tabloYukleniyor && <p className="text-xs text-muted">Yükleniyor…</p>}

        {kayitlar && kayitlar.length === 0 && (
          <p className="text-xs text-muted">
            Bu filtrede olay yok.
            <br />
            <span className="text-[10px]">Sorgu çalıştı ve boş döndü — arıza değil.</span>
          </p>
        )}

        {kayitlar && kayitlar.length > 0 && (
          <div className="overflow-x-auto">
            <table data-testid="olay-tablosu" className="w-full text-left text-[11px]">
              <thead className="text-[10px] uppercase tracking-wide text-muted">
                <tr className="border-b border-line">
                  <th className="py-1.5 pr-3 font-normal">zaman</th>
                  <th className="py-1.5 pr-3 font-normal">kamera</th>
                  <th className="py-1.5 pr-3 font-normal">tür</th>
                  <th className="py-1.5 pr-3 font-normal">kişi</th>
                  <th className="py-1.5 pr-3 font-normal">şiddet</th>
                  <th className="py-1.5 pr-3 font-normal">kanıt gücü</th>
                  <th className="py-1.5 pr-3 font-normal">kanıt</th>
                </tr>
              </thead>
              <tbody>
                {kayitlar.map((o, i) => {
                  const kimlik = `${o.ts}-${o.camera}-${i}`
                  const acik = acikSatir === kimlik
                  const kanitlar = o.kanit ? Object.entries(o.kanit) : []
                  return (
                    <tr
                      key={kimlik}
                      onClick={() => setAcikSatir(acik ? null : kimlik)}
                      className={`cursor-pointer border-b border-line/40 align-top hover:bg-panel/60 ${
                        acik ? 'bg-panel/60' : ''
                      }`}
                    >
                      <td className="py-1.5 pr-3 font-mono text-muted">
                        {saatMetni(o.ts)}
                      </td>
                      <td className="py-1.5 pr-3 font-mono">{o.camera}</td>
                      <td
                        className={`border-l-2 py-1.5 pl-2 pr-3 font-semibold ${
                          SATIR_RENK[o.ciddiyet] ?? SATIR_RENK.attention
                        }`}
                      >
                        {ANOMALI_TR[o.tur] ?? o.tur}
                        <span className="ml-1 text-[9px] font-normal text-muted">
                          {CIDDIYET_TR[o.ciddiyet] ?? o.ciddiyet}
                        </span>
                      </td>
                      <td className="py-1.5 pr-3 font-mono text-muted">
                        {o.track === null ? '—' : `#${o.track}`}
                      </td>
                      <td className="py-1.5 pr-3 font-mono">
                        {(o.skor * 100).toFixed(0)}%
                      </td>
                      <td className="py-1.5 pr-3 font-mono text-muted">
                        {/* ⚠ `tamlik` = özellik vektörünün ne kadarı
                            doluydu. Düşükse alarm zayıf kanıta dayanıyor
                            demektir ve operatör bunu görmeli. */}
                        {o.tamlik === null ? '—' : `${(o.tamlik * 100).toFixed(0)}%`}
                      </td>
                      <td className="py-1.5 pr-3 text-muted">
                        {!acik && (
                          <span className="font-mono text-[10px]">
                            {kanitlar
                              .slice(0, 2)
                              .map(
                                ([k, d]) =>
                                  `${k} ${typeof d === 'number' ? d.toFixed(2) : String(d)}`,
                              )
                              .join(' · ') || '—'}
                            {kanitlar.length > 2 && ` +${kanitlar.length - 2}`}
                          </span>
                        )}
                        {acik && (
                          <div className="space-y-0.5 py-1">
                            {kanitlar.length === 0 && <span>kanıt kaydedilmemiş</span>}
                            {kanitlar.map(([k, d]) => (
                              <div key={k} className="flex justify-between gap-4">
                                <span>{k}</span>
                                <span className="font-mono text-ink">
                                  {typeof d === 'number' ? d.toFixed(2) : String(d)}
                                </span>
                              </div>
                            ))}
                            {/* ⚠ KANIT KLİBİ — "alarm bir iddia, klip bir
                                kanıt" (alerting/klip.py). */}
                            {o.klip && <KlipOynatici anahtar={o.klip} />}
                            {!o.klip && (
                              <p className="pt-1 text-[10px]">
                                Klip yok — sürekli kayıt varsayılan olarak kapalı.
                              </p>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
