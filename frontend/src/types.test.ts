import { describe, expect, it } from 'vitest'
import { ANOMALI_TR, OLAY_TURLERI } from './types'

/**
 * ⚠ NEDEN BU TEST VAR — 10.09.2026
 *
 * Panelde bir olay türü "AGGRESSİON" diye görünüyordu: Türkçe bir
 * arayüzün ortasında ham İngilizce bir alan adı. Sebep basitti —
 * `ANOMALI_TR` sözlüğünde o anahtar yoktu ve kod sessizce ham türe
 * düşüyordu (`ANOMALI_TR[o.tur] ?? o.tur`).
 *
 * ⭐ Asıl mesele o tek eksik satır değil, ONU HİÇBİR ŞEYİN
 * YAKALAMAMASI. Yedek değer (`?? o.tur`) doğru bir savunma — panel
 * çökmüyor — ama aynı zamanda hatayı GÖRÜNMEZ kılıyor: eksik çeviri
 * bir arıza gibi değil, tuhaf bir etiket gibi görünüyor.
 *
 * Bu, projenin tekrar eden dersinin ön yüz hâli: *"bulgu tekil,
 * düzeltme çoğuldur."* Tek bir çeviriyi eklemek bu türü düzeltir;
 * bu test, GELECEKTEKİ türleri de düzeltir.
 */
describe('olay türü sözlüğü', () => {
  it('arka ucun ürettiği HER tür için Türkçe karşılık var', () => {
    const eksik = OLAY_TURLERI.filter((t) => !(t in ANOMALI_TR))
    expect(
      eksik,
      `Bu türler panelde ham İngilizce görünecek: ${eksik.join(', ')}. ` +
        'src/types.ts · ANOMALI_TR içine ekleyin.',
    ).toEqual([])
  })

  it('sözlükte arka ucun üretmediği ÖLÜ anahtar yok', () => {
    // ⚠ Ters yön de önemli: kaldırılmış bir tür sözlükte kalırsa,
    // okuyan kişi sistemin hâlâ o alarmı ürettiğini sanır. Belge/kod
    // sapması (mimari kural 0) burada da geçerli.
    const fazla = Object.keys(ANOMALI_TR).filter(
      (k) => !(OLAY_TURLERI as readonly string[]).includes(k),
    )
    expect(fazla, `Arka uçta olmayan türler: ${fazla.join(', ')}`).toEqual([])
  })
})
