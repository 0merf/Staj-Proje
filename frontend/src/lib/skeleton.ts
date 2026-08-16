/** COCO-17 iskelet tanımı.
 *
 * Keypoint sırası backend'deki KEYPOINT_NAMES ile AYNI olmak zorunda
 * (backend: inference/detector/base.py). Sıra kayarsa iskelet sessizce
 * saçmalar — kollar bacağa bağlanır.
 *
 * Kemikler renk gruplarına ayrıldı ki operatör bir bakışta hangi uzvun
 * nerede olduğunu görsün. Kollar turuncu: saldırganlık modülünün
 * baktığı yer orası (bilek hızı, kol açısı — PLAN.md §6.5.2).
 */
export const KP_CONF_MIN = 0.3

export const BONES: [number, number, string][] = [
  // gövde
  [5, 6, '#58a6ff'], [5, 11, '#58a6ff'], [6, 12, '#58a6ff'], [11, 12, '#58a6ff'],
  // kollar — saldırganlık sinyali buradan geliyor
  [5, 7, '#f0883e'], [7, 9, '#f0883e'],
  [6, 8, '#f0883e'], [8, 10, '#f0883e'],
  // bacaklar
  [11, 13, '#3fb950'], [13, 15, '#3fb950'],
  [12, 14, '#3fb950'], [14, 16, '#3fb950'],
  // baş
  [0, 1, '#a371f7'], [0, 2, '#a371f7'], [1, 3, '#a371f7'], [2, 4, '#a371f7'],
]
