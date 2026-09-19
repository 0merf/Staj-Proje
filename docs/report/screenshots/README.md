# Ekran Görüntüleri

Panelin ekran görüntüleri. 01-06 arası `frontend/e2e/ekran-goruntusu.spec.ts`
ile Playwright'tan üretiliyor; arayüz değişirse aynı testle yeniden
üretilebilir.

| Dosya | İçerik |
|---|---|
| `01-giris.png` | Giriş ekranı |
| `02-izgara-20-kamera.png` | 20 kameralık ızgara |
| `03-canli-kutular.png` | Canlı video üzerinde tespit kutuları ve iskeletler |
| `04-kutucuk-yakin.png` | Tek kutucuğun yakın görünümü |
| `05-zaman-cizelgesi.png` | Kamera × saat ısı haritası ve olay tablosu |
| `06-kamera-detayi.png` | Kamera detay sayfası |
| `07-klip-zinciri-dogrulama.png` | Alarm klibinin panelde oynatılması (P-83) |

## Mahremiyet kuralı

Sistem gerçek insanları içeren görüntüler işliyor. İki veri setinde
tanımlanabilir kişiler var ve `SOURCE.md` dosyalarında bunun kuralını
yazdım:

| Set | Kamera | Kural |
|---|---|---|
| Oxford TownCentre | cam-09 | Rapora görüntü konmuyor |
| UR Fall | cam-16 | Yüzü açık araştırma gönüllüsü, görüntü konmuyor |

Bu kameralar için yalnızca iskelet ve kutu çizimleri, altındaki görüntü
olmadan gösterilebilir. Panelin görünüm modu düğmesi (kapalı / kutular /
iskelet) bunu destekliyor. Bir gözetim sistemi raporunda mahremiyet ihlali
yapmak raporun kendi tezini çürütür.

Ekran görüntülerinde parola, token ya da `.env` içeriği görünmemeli.
