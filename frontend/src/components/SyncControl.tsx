/** Video tamponu kontrolü — kutu hizalamasının kalbi.
 *
 * NEDEN VİDEOYU GECİKTİRİYORUZ
 * ----------------------------
 * Analiz sonucu ~200-450 ms eski; video canlı. Kutuyu nereye çizeceğiz?
 *
 * İlk yaklaşımımız kişinin ŞU AN nerede olduğunu hız vektöründen
 * tahmin etmekti (ekstrapolasyon). İnsan yavaşlar/döner/durur, tahmin
 * tutmaz, ve bir sonraki gerçek sonuç kutuyu SIÇRATARAK doğru yere
 * çeker — kullanıcının bildirdiği "takılma" buydu.
 *
 * Çok oyunculu oyun ağ literatürünün yerleşik çözümü tersini söylüyor
 * (LITERATUR.md §T): **tahmin etme, görüntüyü geciktir.** Video analiz
 * kadar geriden gelirse, ekranda gösterilen an için elimizde İKİ gerçek
 * ölçüm olur ve aradaki konum hesaplanır — tahmin edilmez.
 *
 * Tarayıcının bunun için hazır bir düğmesi var: `jitterBufferTarget`
 * (Chrome'da `playoutDelayHint`). "Bu videoyu N ms tamponla" diyoruz.
 *
 * Bedeli tazelik. Gözetimde kabul edilebilir: operatör için kutunun
 * DOĞRU YERDE olması, yarım saniye daha taze olmasından önemli —
 * üstelik alarm ayrı kanaldan gecikmesiz geliyor.
 */
import { useStore } from '../store'

export function SyncControl() {
  const buffer = useStore((s) => s.videoBufferMs)
  const setBuffer = useStore((s) => s.setVideoBufferMs)
  const video = useStore((s) => s.videoLatencyMs)
  const ai = useStore((s) => s.aiLatencyMs)

  // Tampon, analiz gecikmesini aşmalı ki ara değerleme mümkün olsun.
  // Pay bırakıyoruz: gecikme dalgalanıyor, sınırda kalırsak yarı yarıya
  // tahmine düşeriz.
  const suggestion = ai !== null ? Math.min(2000, Math.round((ai * 1.3 + 100) / 50) * 50) : null
  const interpolating = video !== null && ai !== null && video > ai

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <span
          className="text-xs text-muted"
          title="Video kaç ms tamponlansın — analizin yetişmesi için"
        >
          Video tamponu
        </span>
        <input
          type="range"
          min={0}
          max={1500}
          step={50}
          value={buffer}
          onChange={(e) => setBuffer(Number(e.target.value))}
          className="w-28 accent-[oklch(0.72_0.17_145)]"
        />
        <span className="w-16 font-mono text-xs text-ink">{buffer} ms</span>
      </div>

      {/* ⚠⚠ SABİT GENİŞLİKLER — süs değil, kullanılabilirlik düzeltmesi
          (10.09).

          Buradaki üç değer de sürekli değişiyor: `video —` → `video
          512ms`, `tahmin` → `ara değerleme`, ve öneri düğmesi gelip
          gidiyor. Genişlikleri içeriğe bağlı olduğu için üst şeridin
          TAMAMI her saniye sağa sola kayıyordu; kullanıcının bildirdiği
          şikâyet buydu ("o yazı dönüşünce soldaki butonlar sağa
          kayıyor").

          Çözüm bir yerleşim düzeltmesi: her değişken alana EN UZUN
          içeriğine yetecek sabit bir yer ayrılıyor. Düğme yokken de
          yeri korunuyor (`invisible`, `hidden` değil — `hidden`
          yerleşimden çıkarır ve kaymayı geri getirirdi). */}
      <div className="flex items-center gap-2 font-mono text-[10px] text-muted">
        <span className="w-[74px]" title="Videonun ölçülen gecikmesi">
          video {video === null ? '—' : `${Math.round(video)}ms`}
        </span>
        <span className="text-line">·</span>
        <span
          className="w-[80px]"
          title="Analiz yolunun ölçülen gecikmesi (sunucu raporluyor)"
        >
          analiz {ai === null ? '—' : `${Math.round(ai)}ms`}
        </span>
        <span
          className={`w-[78px] ${interpolating ? 'text-ok' : 'text-warn'}`}
          title={
            interpolating
              ? 'Video analizden geride — kutular iki gerçek ölçüm arasında ARA DEĞERLENİYOR'
              : 'Video analizden ileride — kutular TAHMİN ediliyor, sıçrama olabilir'
          }
        >
          {interpolating ? 'ara değerleme' : 'tahmin'}
        </span>
      </div>

      <div className="w-[92px]">
        <button
          onClick={() => suggestion !== null && setBuffer(suggestion)}
          title="Analiz gecikmesini aşacak tampon — ara değerlemeyi devreye sokar"
          className={`w-full rounded-md border border-ok/40 px-2 py-0.5 text-[10px] text-ok hover:bg-ok/10 ${
            suggestion !== null && suggestion !== buffer ? '' : 'invisible'
          }`}
        >
          öner: {suggestion ?? 0} ms
        </button>
      </div>
    </div>
  )
}
