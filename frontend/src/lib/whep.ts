/** WHEP istemcisi — videoyu KENDİ kontrolümüzde oynatmak için.
 *
 * Neden kendi istemcimiz, neden `<iframe>` değil
 * ----------------------------------------------
 * Eski panel videoyu MediaMTX'in kendi oynatıcısıyla bir `<iframe>`
 * içinde gösteriyordu. O iframe'e hiçbir müdahalemiz yoktu:
 *
 *   · oynatma zamanını okuyamıyorduk
 *   · duraklatamıyorduk (kullanıcı videoyu durdurunca kutular
 *     hareket etmeye devam ediyordu — sorunun en net kanıtı)
 *   · gecikme tamponu ekleyemiyorduk
 *
 * Video ve kutular tarayıcıya iki AYRI kanaldan geliyor (WebRTC ve
 * WebSocket) ve aralarında doğal bir zaman hizası yok. Literatür bu
 * durumda kare seviyesinde senkronizasyonun zorunlu olduğunu söylüyor
 * (LITERATUR.md §R). Hizalayabilmek için önce videonun kontrolünü
 * ele almak gerekiyordu — bu dosya onu yapıyor.
 *
 * WHEP nedir
 * ----------
 * WebRTC-HTTP Egress Protocol. WebRTC oturumunu tek bir HTTP POST ile
 * başlatan standart: SDP teklifini gönderirsin, SDP cevabını alırsın.
 * MediaMTX bunu `http://host:8889/<yol>/whep` adresinde sunuyor.
 */

export interface WhepSession {
  pc: RTCPeerConnection
  close: () => void
}

/**
 * Videonun tarayıcıya ulaşma gecikmesini WebRTC istatistiklerinden ölçer.
 *
 * Neden bu mümkün: alıcı, gelen kareleri oynatmadan önce bir **jitter
 * tamponunda** bekletir (ağdaki düzensizliği yutmak için). WebRTC bu
 * bekleme süresinin toplamını ve kaç kareye uygulandığını raporlar;
 * bölünce kare başına ortalama bekleme çıkıyor.
 *
 * Her şey aynı makinede olduğu için ağ gecikmesi ~0; geriye kalan
 * baskın bileşen jitter tamponudur. Yani bu ölçüm "video kaç ms
 * geriden geliyor" sorusunun iyi bir yaklaşığı.
 *
 * ⚠ Tam bir uçtan uca ölçüm DEĞİL: kameranın kendi kodlama gecikmesini
 * ve MediaMTX'in paketleme süresini içermez. Ama bizim ihtiyacımız
 * mutlak değer değil, analiz yoluyla ARASINDAKİ FARK.
 */
export async function measureVideoLatencyMs(pc: RTCPeerConnection): Promise<number | null> {
  try {
    const stats = await pc.getStats()
    let delay = 0
    let count = 0
    stats.forEach((report) => {
      if (report.type === 'inbound-rtp' && report.kind === 'video') {
        if (typeof report.jitterBufferDelay === 'number') delay = report.jitterBufferDelay
        if (typeof report.jitterBufferEmittedCount === 'number') {
          count = report.jitterBufferEmittedCount
        }
      }
    })
    if (!count) return null
    return (delay / count) * 1000
  } catch {
    return null
  }
}

/** ICE adaylarının toplanmasını bekler.
 *
 * Trickle ICE kullanmıyoruz: WHEP tek atımlık bir alışveriş, teklifi
 * göndermeden önce adayların hazır olması gerekiyor. Yerel ağda bu
 * birkaç milisaniye sürer; yine de takılmaması için zaman aşımı var.
 */
function waitForIce(pc: RTCPeerConnection, timeoutMs = 3000): Promise<void> {
  if (pc.iceGatheringState === 'complete') return Promise.resolve()
  return new Promise((resolve) => {
    const done = () => {
      pc.removeEventListener('icegatheringstatechange', check)
      clearTimeout(timer)
      resolve()
    }
    const check = () => {
      if (pc.iceGatheringState === 'complete') done()
    }
    const timer = setTimeout(done, timeoutMs)
    pc.addEventListener('icegatheringstatechange', check)
  })
}

/**
 * Bir kameraya WHEP ile bağlanır ve akışı verilen `<video>` elementine bağlar.
 *
 * @param baseUrl MediaMTX WebRTC adresi (örn. http://127.0.0.1:8889)
 * @param camera  Kamera yolu (örn. cam-09)
 * @param video   Akışın bağlanacağı video elementi
 */
export async function connectWhep(
  baseUrl: string,
  camera: string,
  video: HTMLVideoElement,
): Promise<WhepSession> {
  const pc = new RTCPeerConnection({
    // Tümü yerel ağda; STUN/TURN gereksiz. Sunucu listesi boş bırakmak
    // aday toplamayı da hızlandırıyor.
    iceServers: [],
  })

  pc.addTransceiver('video', { direction: 'recvonly' })
  pc.ontrack = (event) => {
    if (event.streams[0]) video.srcObject = event.streams[0]
  }

  const offer = await pc.createOffer()
  await pc.setLocalDescription(offer)
  await waitForIce(pc)

  const response = await fetch(`${baseUrl}/${camera}/whep`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/sdp' },
    body: pc.localDescription?.sdp ?? '',
  })
  if (!response.ok) {
    pc.close()
    throw new Error(`WHEP ${response.status}: ${camera}`)
  }

  const answer = await response.text()
  await pc.setRemoteDescription({ type: 'answer', sdp: answer })

  // WHEP oturumu Location başlığında bir kaynak adresi döndürür;
  // kapatırken DELETE göndermek sunucudaki oturumu hemen serbest
  // bırakır. Göndermezsek zaman aşımına kadar kaynak tutulur —
  // 20 kamerada bu birikir.
  const location = response.headers.get('Location')
  const sessionUrl = location
    ? new URL(location, `${baseUrl}/${camera}/whep`).toString()
    : null

  return {
    pc,
    close: () => {
      pc.close()
      video.srcObject = null
      if (sessionUrl) {
        // Kapatma sırasında hata önemsiz — sayfa zaten kapanıyor olabilir.
        fetch(sessionUrl, { method: 'DELETE' }).catch(() => {})
      }
    },
  }
}


/**
 * Tarayıcıya "bu videoyu N milisaniye tamponla" der.
 *
 * ⚠ PROJENİN KUTU HİZALAMA SORUNUNUN ÇÖZÜMÜ BU SATIR.
 *
 * Problem: analiz sonucu ~450 ms eski, video canlı. Kutuyu nereye
 * çizeceğiz? Şimdiye kadar kişinin nerede OLACAĞINI hız vektöründen
 * tahmin ediyorduk (ekstrapolasyon). İnsan yavaşlar/döner/durur, tahmin
 * tutmaz, ve bir sonraki gerçek sonuç kutuyu SIÇRATARAK doğru yere
 * çeker — kullanıcının gördüğü "takılma" buydu.
 *
 * Oyun ağ literatürünün (LITERATUR.md §T) yerleşik çözümü tersini
 * söylüyor: **tahmin etme, görüntüyü geciktir.** Video 450 ms geriden
 * gelirse, ekranda gösterilen an için elimizde İKİ gerçek ölçüm olur
 * (öncesi ve sonrası) ve aradaki konum hesaplanır — tahmin edilmez.
 *
 * Film dublajı mantığı: çevirmenin ne diyeceğini tahmin etmezsin,
 * görüntüyü çeviri hazır olana kadar bekletirsin.
 *
 * Bedeli 450 ms tazelik. Gözetimde bu takas rahatlıkla kabul edilir:
 * operatör için kutunun DOĞRU YERDE olması, yarım saniye daha taze
 * olmasından önemli. (Alarm zaten ayrı kanaldan, gecikmesiz geliyor.)
 *
 * Tarayıcı uyumluluğu: standart ad `jitterBufferTarget`, Chrome hâlâ
 * eski ad `playoutDelayHint` ile sunuyor. İkisini de deniyoruz;
 * hiçbiri yoksa sessizce ekstrapolasyona düşüyoruz.
 */
export function setVideoBuffer(pc: RTCPeerConnection, ms: number): boolean {
  const clamped = Math.max(0, Math.min(ms, 4000))
  let applied = false
  for (const receiver of pc.getReceivers()) {
    if (receiver.track?.kind !== 'video') continue
    // Tip iddiası: iki özellik de TypeScript'in DOM tanımlarında yok
    // (biri çok yeni, biri Chrome'a özgü). Varlıklarını çalışma anında
    // yokluyoruz.
    const r = receiver as unknown as Record<string, unknown>
    try {
      if ('jitterBufferTarget' in r) {
        r.jitterBufferTarget = clamped        // standart ad: MİLİSANİYE
        applied = true
      } else if ('playoutDelayHint' in r) {
        r.playoutDelayHint = clamped / 1000   // Chrome eski adı: SANİYE
        applied = true
      }
    } catch {
      /* aralık dışı değer — yok say */
    }
  }
  return applied
}
