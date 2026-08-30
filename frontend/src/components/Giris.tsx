/** Giriş ekranı — PLAN.md §11.1.
 *
 * ⚠ TOKEN NEREDE SAKLANIYOR: HİÇBİR YERDE
 * ---------------------------------------
 * Erişim tokenı `localStorage`'a ya da bir React state'ine
 * KONULMUYOR. Sunucu onu `httponly` çerez olarak veriyor; JavaScript
 * okuyamıyor, dolayısıyla bir XSS açığı tokenı çalamıyor.
 *
 * Bu, "token'ı localStorage'da tut" yaygın kalıbının tam tersi ve
 * bilinçli: localStorage'daki token, sayfaya sızan herhangi bir
 * betiğin okuyabileceği düz metin bir anahtardır.
 *
 * Bunun bedeli: `fetch` çağrılarının `credentials: 'include'` demesi
 * gerekiyor (aynı kökende varsayılan zaten böyle) ve uygulama "giriş
 * yapılmış mı" sorusunu tokena bakarak değil, **sunucuya sorarak**
 * cevaplıyor (`/api/v1/auth/ben`).
 *
 * ⚠ WEBSOCKET DE ÇEREZLE ÇALIŞIYOR
 * Tarayıcının WebSocket API'si özel başlık eklemeye izin vermiyor;
 * çerez ise el sıkışmada kendiliğinden gidiyor. Token'ı sorgu
 * parametresine koymak alternatifti ve kötü olurdu: sorgu dizeleri
 * sunucu günlüklerine, vekil kayıtlarına ve tarayıcı geçmişine düşer.
 */
import { useState } from 'react'

interface Props {
  onSuccess: () => void
}

export function Giris({ onSuccess }: Props) {
  const [kullaniciAdi, setKullaniciAdi] = useState('')
  const [parola, setParola] = useState('')
  const [hata, setHata] = useState<string | null>(null)
  const [bekliyor, setBekliyor] = useState(false)

  async function gonder(e: React.FormEvent) {
    e.preventDefault()
    setHata(null)
    setBekliyor(true)
    try {
      const r = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kullanici_adi: kullaniciAdi, parola }),
      })
      if (r.ok) {
        onSuccess()
        return
      }
      // ⚠ SUNUCUNUN MESAJI OLDUĞU GİBİ GÖSTERİLİYOR ve o mesaj
      // bilinçli olarak belirsiz ("kullanıcı adı ya da parola hatalı").
      // İstemcide "kullanıcı bulunamadı" gibi bir ayrım uydurmak,
      // sunucunun kullanıcı numaralandırmaya karşı aldığı önlemi
      // boşa çıkarırdı.
      const govde = (await r.json().catch(() => null)) as { detail?: string } | null
      setHata(govde?.detail ?? 'giriş başarısız')
    } catch {
      setHata('sunucuya ulaşılamıyor')
    } finally {
      setBekliyor(false)
    }
  }

  return (
    <div className="flex h-screen items-center justify-center bg-bg">
      <form
        onSubmit={gonder}
        className="w-80 rounded-lg border border-line bg-panel p-6 shadow-lg"
      >
        <h1 className="mb-1 text-lg font-semibold">SENTINEL</h1>
        <p className="mb-5 text-xs text-muted">
          Çok kameralı gözetim sistemi — giriş gerekli
        </p>

        <label className="mb-3 block">
          <span className="mb-1 block text-xs text-muted">Kullanıcı adı</span>
          <input
            value={kullaniciAdi}
            onChange={(e) => setKullaniciAdi(e.target.value)}
            autoComplete="username"
            autoFocus
            required
            className="w-full rounded border border-line bg-bg px-2 py-1.5 text-sm outline-none focus:border-accent"
          />
        </label>

        <label className="mb-4 block">
          <span className="mb-1 block text-xs text-muted">Parola</span>
          <input
            type="password"
            value={parola}
            onChange={(e) => setParola(e.target.value)}
            autoComplete="current-password"
            required
            className="w-full rounded border border-line bg-bg px-2 py-1.5 text-sm outline-none focus:border-accent"
          />
        </label>

        {hata && (
          <p
            role="alert"
            className="mb-3 rounded border border-bad/50 bg-bad/10 px-2 py-1.5 text-xs text-bad"
          >
            {hata}
          </p>
        )}

        <button
          type="submit"
          disabled={bekliyor}
          className="w-full rounded bg-accent px-3 py-1.5 text-sm font-medium text-bg disabled:opacity-50"
        >
          {bekliyor ? 'Giriş yapılıyor…' : 'Giriş yap'}
        </button>

        <p className="mt-4 text-[10px] leading-relaxed text-muted">
          ⚠ Bu sistem kişileri görüntülüyor. Her giriş ve her kamera
          açma işlemi denetim izine kaydedilir.
        </p>
      </form>
    </div>
  )
}
