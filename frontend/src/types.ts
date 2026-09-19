/** Sunucuyla paylaşılan mesaj sözleşmesi.
 *
 * Kaynak: backend `inference/worker.py::_serialize`.
 * Alan adları kasten kısa: 20 kamera × ~4 sonuç/sn × ~5 kişi
 * durumunda uzun anahtarlar mesaj boyutunu ikiye katlardı.
 */

/** Tek bir kişi tespiti. Koordinatlar kaynak karenin piksel uzayında. */
export interface Detection {
  /** [x1, y1, x2, y2] */
  bbox: [number, number, number, number]
  conf: number
  cls: number
  /** İz kimliği. Yoksa takipçi henüz onaylamamış demektir (P-13). */
  id?: number
  /** Hız vektörü [vx, vy], piksel/saniye. Ara değerleme için. */
  v?: [number, number]
  /** Kaç karedir görülüyor. */
  age?: number
  /** COCO-17 iskelet: 17 × [x, y, güven]. Poz kademesi kapalıysa yok. */
  kp?: [number, number, number][]
  /** kademe 2b — yüz ifadesi. Seyrek gelir (iz başına ~2 sn'de bir). */
  expr?: Expression
}

/** Yüz ifadesi sınıflandırması.
 *
 * Bu bir duygu iddiası değil. Model "üzgün" dediğinde kanıtladığı tek
 * şey, görüntünün eğitim setindeki "üzgün" etiketli yüzlere benzediği.
 * Bu yüzden panelde `q` (kalite) eşiğin altındaysa etiket hiç
 * gösterilmiyor — gürültüyü bilgi gibi sunmamak için.
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
 * Sunucudaki `ExpressionResult.usable` ile aynı değerler olmalı
 * (backend `inference/emotion/base.py`). */
export const EXPR_MIN_QUALITY = 0.5
// 10.09.2026 — 0.40 -> 0.55 (P-73). Sunucudaki `usable` ile aynı
// olmak zorunda; ayrışırlarsa panel sunucunun güvenilmez saydığı bir
// etiketi gösterir (ya da tersi) ve iki taraf farklı şey iddia eder.
//
// Gerekçe: 12 yüzlük elle değerlendirmede 0.55 üstü etiketlerin hepsi
// doğru, 0.50 altındakiler yanlıştı. Eski eşik tam hatalı bandı
// geçiriyordu — kullanıcı panelde gülümseyen bir yüzde "şaşkınlık"
// görüp sordu.
export const EXPR_MIN_CONF = 0.55

export interface FrameResult {
  type: 'frame'
  cam: string
  /** Sunucunun monotonik saati — Date.now() ile karşılaştırılamaz. */
  ts: number
  seq: number
  /** Kaynak kare boyutu. Kameralar farklı çözünürlükte olabilir. */
  w: number
  h: number
  count: number
  motion: number
  gate: string
  /** Bu karenin analiz yolunda harcadigi sure (ms) — sunucu olcuyor. */
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

/** Panelin hangi sayfada olduğu.
 *
 * Neden router değil, durum değişkeni
 * `react-router` üç görünüm için bir bağımlılık, bir sağlayıcı
 * sarmalayıcısı ve bir URL sözleşmesi getiriyordu. Bu panelde derin
 * bağlantı (deep link) gereksinimi yok: operatör panele girip
 * görünüm değiştiriyor, URL paylaşmıyor.
 *
 * Bedeli açıkça yazılıyor: tarayıcının geri düğmesi görünümler
 * arasında çalışmıyor ve bir görünüme doğrudan bağlantı verilemiyor.
 * Gerçek bir üründe router doğru seçim olurdu; bu takas kapsam
 * gerekçesiyle yapıldı. */
export type Sayfa = 'izgara' | 'zaman-cizelgesi' | 'kamera'

/** Analitik katmanının ürettiği anomali (katman B).
 *
 * Alarm abonelik filtresine takılmaz — kutucuk kapalı olsa bile
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
  /** Canlı akıştan değil, veritabanı geçmişinden geldiyse `true`.
   *  Operatör "şu an oluyor" ile "olmuştu"yu ayırt edebilmeli. */
  gecmis?: boolean
  /** Olay klibinin anahtarı — varsa `/api/v1/events/klip/<anahtar>`.
   *
   * 03.09.2026'ya kadar bu alan maplenmiyordu: `/api/v1/events`
   * yanıtı `klip` alanını döndürüyordu (`HistoryEvent.klip`), ama
   * `loadHistory` onu `TimedAlert`'e taşımıyordu ve panelde kullanan
   * hiçbir şey yoktu. Yani klip kesiliyor, veritabanına yazılıyor ve
   * arayüze hiç ulaşmıyordu.
   *
   * Canlı alarmlarda boş ve bu normaldir: klibi alarm worker'ı
   * veritabanına yazarken kesiyor, canlı WebSocket mesajı ondan önce
   * gidiyor. Klip ancak geçmiş yüklendiğinde görünür — yani "canlı
   * alarmda klip yok" bir arıza değil, sıralamanın sonucu. */
  klip?: string | null
}

/** `/api/v1/events` yanıtındaki tek kayıt.
 *
 * Alan adları türkçe çünkü veritabanı şeması Türkçe (`db/schema.py`).
 * Canlı WebSocket mesajı ise İngilizce alan adları kullanıyor — ikisi
 * ayrı sözleşme ve karıştırılmamalı. Dönüşüm tek yerde yapılıyor
 * (`store.ts · loadHistory`). */
export interface HistoryEvent {
  ts: number
  camera: string
  tur: string
  ciddiyet: string
  skor: number
  track: number | null
  kanit: Record<string, number> | null
  tamlik: number | null
  karsi_taraf: number | null
  klip: string | null
}

/** Anomali türlerinin Türkçe karşılıkları ve renkleri. */
export const ANOMALI_TR: Record<string, string> = {
  fall: 'DÜŞME',
  running: 'koşma',
  loitering: 'oyalanma',
  crowd: 'kalabalık',
  // Katman A — kural değil, öğrenilmiş profile göre üretilen alarm.
  // Diğerleri "şu fiziksel olay oldu" der; bu "bu kameranın normali
  // böyle değil" der. Adlandırma bu farkı taşımalı.
  unusual: 'olağandışı',
  // Füzyon — beş sinyalin birleşimi (analytics/fusion.py).
  // Diğerleri "şu olay oldu" der; bu "bu kişi genel olarak riskli"
  // der. Adlandırma farkı taşımalı: operatör tek bir gözleme mi
  // yoksa bir birikime mi baktığını bilmeli.
  risk: 'RİSK (birleşik)',
  // 10.09'da eklendi — üretimde vardı, sözlükte yoktu.
  // Panelde ham anahtar görünüyordu ("aggression"): Türkçe bir
  // arayüzün ortasında İngilizce bir alan adı. Sözlükte olmayan tür
  // sessizce ham hâliyle geçiyordu; artık `types.test.ts` bunu
  // yakalıyor (arka uçtaki tür listesiyle karşılaştırarak).
  aggression: 'SALDIRGANLIK',
}

/** Arka ucun ürettiği tüm olay türleri (`analytics/`, `alerting/`).
 *
 * Bu liste bir kopya ve kopyalar bayatlar. Bayatlamayı sessiz
 * olmaktan çıkarmak için `types.test.ts` her ikisini karşılaştırıyor:
 * arka uçta yeni bir tür eklenirse ve buraya yansımazsa test düşüyor.
 * Kopyanın kendisini yok edemiyoruz (ön yüz Python okumuyor), ama
 * sapmasını yakalayabiliyoruz. */
export const OLAY_TURLERI = [
  'aggression',
  'crowd',
  'fall',
  'loitering',
  'risk',
  'running',
  'unusual',
] as const
