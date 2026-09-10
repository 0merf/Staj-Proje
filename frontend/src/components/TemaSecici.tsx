/** Açık / koyu tema anahtarı.
 *
 * ⚠ TEMA `<html>` ÜZERİNDE, REACT DURUMUNDA DEĞİL
 * Renkler CSS değişkeni (`index.css`). React'e bir "tema" prop'u
 * geçirip her bileşende dallanmak, her yeni bileşende unutulabilecek
 * bir adım eklerdi. `data-tema` niteliği tek noktada değişiyor ve
 * tüm ağaç CSS üzerinden takip ediyor.
 *
 * ⚠ İLK DEĞER `index.html` İÇİNDE OKUNUYOR, BURADA DEĞİL
 * Burada `useEffect` ile uygulasaydık sayfa bir kare KOYU açılır,
 * sonra açığa atlardı (flash). Seçim `localStorage`'dan React
 * yüklenmeden önce, `index.html` içindeki küçük betikle uygulanıyor.
 * Bu bileşen yalnızca sonradan DEĞİŞTİRİYOR.
 *
 * ⚠ VARSAYILAN: işletim sisteminin tercihi
 * "Koyu" varsayılan seçmek bir tasarım tercihini kullanıcıya dayatmak
 * olurdu. `prefers-color-scheme` zaten kullanıcının cevabı.
 */
import { useState } from 'react'

export type Tema = 'acik' | 'koyu'

/** Yürürlükteki tema — `index.html`'in yazdığı nitelikten okunuyor. */
function mevcutTema(): Tema {
  return document.documentElement.dataset.tema === 'acik' ? 'acik' : 'koyu'
}

/** ⚠ Dışa AÇILMIYOR: yalnızca bu bileşen çağırıyor ve bir bileşen
 *  dosyasından işlev ihraç etmek React'in hızlı yenilemesini bozuyor. */
function temaUygula(tema: Tema): void {
  // Koyu varsayılan olduğu için nitelik yalnızca açık temada yazılıyor.
  if (tema === 'acik') document.documentElement.dataset.tema = 'acik'
  else delete document.documentElement.dataset.tema
  try {
    localStorage.setItem('sentinel-tema', tema)
  } catch {
    // Gizli sekmede / depolama kapalıyken yazma patlar. Tema yine
    // çalışsın, yalnızca hatırlanmasın — bir tercih kaydı için
    // sayfayı çökertmek orantısız olurdu.
  }
}

export function TemaSecici() {
  const [tema, setTema] = useState<Tema>(mevcutTema)

  const degistir = (yeni: Tema) => {
    temaUygula(yeni)
    setTema(yeni)
  }

  return (
    <div
      className="flex overflow-hidden rounded-md border border-line"
      title="Panel teması"
    >
      {(
        [
          ['koyu', '🌙', 'Koyu tema'],
          ['acik', '☀', 'Açık tema'],
        ] as const
      ).map(([id, ikon, baslik]) => (
        <button
          key={id}
          onClick={() => degistir(id)}
          title={baslik}
          aria-pressed={tema === id}
          className={`px-2 py-1 text-xs transition-colors ${
            tema === id ? 'bg-panel text-ink' : 'text-muted hover:text-ink'
          }`}
        >
          {ikon}
        </button>
      ))}
    </div>
  )
}
