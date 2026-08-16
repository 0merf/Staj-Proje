/** Sunucuyla paylaşılan mesaj sözleşmesi.
 *
 * Kaynak: backend `inference/worker.py::_serialize`.
 * ⚠ Alan adları kasten kısa: 20 kamera × ~4 sonuç/sn × ~5 kişi
 * durumunda uzun anahtarlar mesaj boyutunu ikiye katlardı.
 */

/** Tek bir kişi tespiti. Koordinatlar KAYNAK karenin piksel uzayında. */
export interface Detection {
  /** [x1, y1, x2, y2] */
  bbox: [number, number, number, number]
  conf: number
  cls: number
  /** İz kimliği. YOKSA takipçi henüz onaylamamış demektir (P-13). */
  id?: number
  /** Hız vektörü [vx, vy], piksel/saniye. Ara değerleme için. */
  v?: [number, number]
  /** Kaç karedir görülüyor. */
  age?: number
  /** COCO-17 iskelet: 17 × [x, y, güven]. Poz kademesi kapalıysa yok. */
  kp?: [number, number, number][]
}

export interface FrameResult {
  type: 'frame'
  cam: string
  /** Sunucunun MONOTONİK saati — Date.now() ile karşılaştırılamaz. */
  ts: number
  seq: number
  /** Kaynak kare boyutu. Kameralar farklı çözünürlükte olabilir. */
  w: number
  h: number
  count: number
  motion: number
  gate: string
  detections: Detection[]
}

/** İstemci tarafında eklenen alanlar. */
export interface TimedResult extends FrameResult {
  /** Tarayıcının kendi saatiyle varış anı (performance.now). */
  rx: number
}

export interface Camera {
  name: string
  kind: string
  ready: boolean
  readers?: number
}

/** Panelde ne çizilsin — kullanıcı 3 kademeli düğmeyle seçiyor. */
export type ViewMode = 'off' | 'boxes' | 'full'
