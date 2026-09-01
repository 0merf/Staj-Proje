# ADR-0004 · Video ve üst katman ayrı yollardan gider

**Durum:** kabul edildi
**Tarih:** 12.08.2026

## Bağlam

Operatör 20 kamerayı canlı izleyecek ve üzerinde tespit kutuları,
iskeletler görecek. Kutular sunucuda mı çizilecek, tarayıcıda mı?

## Değerlendirilen seçenekler

**A · Sunucu çizsin** — kutuları kareye bas, kodla, yayınla
Basit istemci. Ama her kamera için **yeniden kodlama** gerekir:
- NVENC oturum limiti (tüketici GPU'larda 3-5 eşzamanlı oturum)
- Kodlama GPU'yu YZ ile paylaşır
- Kutu değişince tüm kare yeniden kodlanır

**B · Video ayrı, üst katman ayrı**
Video MediaMTX'ten WHEP/WebRTC ile **yeniden kodlanmadan** geçiyor
(yalnızca kapsayıcı değişiyor). Kutular WebSocket'ten JSON olarak
gidiyor, tarayıcı canvas'a çiziyor.

## Karar

**B.** Mimari kural 2: *"Sunucu videoya kutu çizmez."*

## Sonuçlar

**Kazanılan:** GPU tamamen YZ'ye kalıyor. NVENC hiç kullanılmıyor.
Kutu güncellemesi kare başına birkaç yüz bayt.

**Kaybedilen — ve çözülmesi günler aldı:** İki yol **farklı
gecikmelere** sahip. Video ~13 ms'de geliyor, analiz ~200-465 ms'de.
Kutular videodan geride kalıyor ve operatör bunu "kutular kaymış"
diye görüyor.

Denenen ve **reddedilen** çözüm: kutuları ileri **tahmin** etmek
(ekstrapolasyon). Oyun ağı literatürü (LITERATUR §T) bunun yedek plan
olduğunu söylüyor — doğru yöntem **videoyu geciktirip ara değerleme**
yapmak. `jitterBufferTarget` ile video bilerek geciktiriliyor ve
kutular iki gerçek tespit arasında ara değerleniyor.

**Kaybedilen 2 (güvenlik):** Video API'den geçmediği için API'ye
kimlik doğrulama eklendiğinde **görüntü korumasız kaldı** — fark
edilmesi güvenlik gözden geçirmesinin sonuna kaldı (P-37).

## Ölçüm

| | |
|---|---|
| Video gecikmesi | ~13 ms (WHEP, yeniden kodlama yok) |
| Analiz gecikmesi | 468 ms (K3 sınırı 1500) |
| Kutu verisi | ~200-600 bayt/kare/kamera |
| NVENC oturumu | 0 |
