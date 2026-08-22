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
  /** KADEME 2b — yüz ifadesi. Seyrek gelir (iz başına ~2 sn'de bir). */
  expr?: Expression
}

/** Yüz ifadesi sınıflandırması.
 *
 * ⚠ Bu bir DUYGU İDDİASI DEĞİL. Model "üzgün" dediğinde kanıtladığı tek
 * şey, görüntünün eğitim setindeki "üzgün" etiketli yüzlere benzediği.
 * Bu yüzden panelde `q` (kalite) eşiğin altındaysa etiket HİÇ
 * gösterilmiyor — gürültüyü bilgi gibi sunmamak için (PLAN.md §6.3).
 */
export interface Expression {
  /** AffectNet etiketi (İngilizce, modelden geldiği gibi). */
  label: string
  /** Türkçe karşılığı — panelde bu gösteriliyor. */
  tr: string
  conf: number
  /** Kalite 0-1: yüz boyutu × netlik. 0.5 altı gösterilmez. */
  q: number
}

/** Etiketin operatöre gösterilebilecek kadar güvenilir olduğu eşikler.
 * Sunucudaki `ExpressionResult.usable` ile AYNI değerler olmalı
 * (backend `inference/emotion/base.py`). */
export const EXPR_MIN_QUALITY = 0.5
export const EXPR_MIN_CONF = 0.4

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
  /** Bu karenin ANALIZ yolunda harcadigi sure (ms) — sunucu olcuyor. */
  lat?: number
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

/** Analitik katmanının ürettiği anomali (KATMAN B).
 *
 * ⚠ Alarm ABONELİK FİLTRESİNE TAKILMAZ — kutucuk kapalı olsa bile
 * gelir. Gözetim sisteminin varlık sebebi kimsenin bakmadığı kamerada
 * olanı bildirmek (backend: api/ws/manager.py · _dispatch_alert).
 */
export interface Alert {
  type: 'alert'
  cam: string
  ts: number
  /** fall | running | loitering | crowd */
  anomaly: string
  severity: string
  track: number | null
  score: number
  /** Hangi ölçümün eşiği neden aştığı — açıklanabilirlik zorunlu. */
  evidence: Record<string, number>
  completeness: number
}

/** Panelde gösterilen alarm — varış anı eklenmiş. */
export interface TimedAlert extends Alert {
  rx: number
}

/** Anomali türlerinin Türkçe karşılıkları ve renkleri. */
export const ANOMALI_TR: Record<string, string> = {
  fall: 'DÜŞME',
  running: 'koşma',
  loitering: 'oyalanma',
  crowd: 'kalabalık',
  // KATMAN A — kural değil, öğrenilmiş profile göre üretilen alarm.
  // Diğerleri "şu fiziksel olay oldu" der; bu "bu kameranın normali
  // böyle değil" der. Adlandırma bu farkı taşımalı.
  unusual: 'olağandışı',
}
