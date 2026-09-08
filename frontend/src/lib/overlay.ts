/**
 * Overlay geometrisi — kutu/iskelet çiziminin SAF matematiği.
 *
 * ⚠⚠ NEDEN AYRI BİR MODÜL
 * Bu hesaplar `CameraTile.tsx` içine gömülüydü ve test edilemiyordu.
 * Hakem denetimi (docs/report/denetim-hakem.md §4.1) bunu işaretledi:
 *
 *   > 215 arka uç testine karşı 1 ön yüz test dosyası. Canvas/overlay
 *   > çizimi test edilmiyor — oysa P-14 ve P-26 tam oradan çıkmıştı.
 *
 * P-14 ve P-26'nın ikisi de KOORDİNAT hatasıydı:
 *   P-14 — poz kırpıntısı kareye sıkıştırılıyordu, iskelet kayıyordu
 *   P-26 — kutular kaynak çözünürlükle görüntü alanı arasında ölçeksizdi
 *
 * ⭐ Aynı hata sınıfı arka uçta da tekrarlandı (P-39: tespitler 640×640
 * letterbox uzayında, ızgara 640×360 kaynak uzayında — konumlar 140 px
 * kaymıştı ve AUC 0.483 göstermişti). Koordinat uzayı karışıklığı bu
 * projenin en pahalı hata türü; saf fonksiyona çıkarılıp kilitleniyor.
 */

/** Kaynak kare piksel uzayından görüntü alanına ölçek çarpanları. */
export interface Olcek {
  sx: number
  sy: number
}

/** Görüntü alanına ölçeklenmiş kutu (canvas piksel). */
export interface OlcekliKutu {
  x: number
  y: number
  w: number
  h: number
}

/** Varsayılan kaynak çözünürlük — kare boyutu bildirilmediğinde. */
export const VARSAYILAN_KAYNAK = { w: 1280, h: 720 } as const

/** Hareketli sayılma eşiği (piksel/sn, x+y mutlak toplamı). */
export const HAREKET_ESIGI = 15

/**
 * Kaynak kare boyutundan canvas boyutuna ölçek.
 *
 * ⚠ Kameralar farklı çözünürlükte (1280×720, 960×720, 900×720). Sabit
 * bir varsayım yanlış çizime yol açar — P-26 tam olarak buydu.
 *
 * ⚠ Sıfır/negatif/NaN girdide varsayılana düşülüyor: bozuk bir kare
 * meta verisi yüzünden `Infinity` ölçek üretip tüm overlay'i ekrandan
 * atmaktansa, kutuları biraz yanlış yerde çizmek yeğdir.
 */
export function olcek(
  canvasW: number,
  canvasH: number,
  kareW?: number,
  kareH?: number,
): Olcek {
  const w = Number.isFinite(kareW) && (kareW ?? 0) > 0 ? (kareW as number) : VARSAYILAN_KAYNAK.w
  const h = Number.isFinite(kareH) && (kareH ?? 0) > 0 ? (kareH as number) : VARSAYILAN_KAYNAK.h
  return { sx: canvasW / w, sy: canvasH / h }
}

/**
 * `[x1, y1, x2, y2]` kutusunu görüntü alanına ölçekler.
 *
 * ⚠ Ters kutu (x2 < x1) gelirse genişlik NEGATİF olurdu ve
 * `strokeRect` sessizce ters çizerdi. Normalleştiriliyor.
 */
export function kutuyuOlcekle(
  bbox: readonly [number, number, number, number],
  o: Olcek,
): OlcekliKutu {
  const [x1, y1, x2, y2] = bbox
  const solX = Math.min(x1, x2)
  const ustY = Math.min(y1, y2)
  return {
    x: solX * o.sx,
    y: ustY * o.sy,
    w: Math.abs(x2 - x1) * o.sx,
    h: Math.abs(y2 - y1) * o.sy,
  }
}

/**
 * Hız vektöründen "hareketli mi" kararı.
 *
 * ⚠ Hız YOKSA `false` — "bilinmiyor" ile "duruyor" ayrımı burada
 * bilinçli olarak kayboluyor: renk seçimi ikili bir karar ve üçüncü
 * bir renk operatöre bilgi değil gürültü olurdu.
 */
export function hareketli(v?: readonly number[] | null): boolean {
  if (!v || v.length < 2) return false
  const toplam = Math.abs(v[0]) + Math.abs(v[1])
  return Number.isFinite(toplam) && toplam > HAREKET_ESIGI
}

/**
 * Kutu etiketi.
 *
 * ⚠ Kimliksiz kutu = takipçi henüz onaylamadı (P-13). Etikette kimlik
 * YOK ama kutu çiziliyor — gizlemek yanlış olurdu, kişi orada.
 */
export function kutuEtiketi(id: number | undefined, conf: number): string {
  const yuzde = `${(conf * 100).toFixed(0)}%`
  return id === undefined ? yuzde : `#${id} ${yuzde}`
}

/**
 * Kutu rengi: onaysız gri, hareketli parlak yeşil, duran koyu yeşil.
 */
export function kutuRengi(onayli: boolean, hareket: boolean): string {
  if (!onayli) return '#8b98ad'
  return hareket ? '#3fb950' : '#4d8f5c'
}

/** Onaysız kutu kesikli çizilir — "tespit var, kimlik gelecek". */
export function cizgiDeseni(onayli: boolean): number[] {
  return onayli ? [] : [5, 4]
}
