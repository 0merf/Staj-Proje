# ADR-0002 · Kademeli işleme — 20 kamerayı mümkün kılan mimari

**Durum:** kabul edildi
**Tarih:** 12.08.2026

## Bağlam

20 kamera × 25 FPS = **saniyede 500 kare.** Tek orta seviye GPU
(RTX 3070 Laptop, ~7 GB efektif VRAM) üzerinde her kareye tam boru
hattını (tespit + poz + yüz + ifade) uygulamak imkânsız.

Projenin gerçek zorluğu model seçimi değil, **bu aritmetik.**

## Değerlendirilen seçenekler

**A · Kare hızını düşür** — 20 kamerayı 1 FPS'te işle
Basit. Ama 1 FPS'te düşme tespit edilemez: düşme 0.5 saniye sürüyor.

**B · Daha küçük model** — YOLO-nano
Kazanç doğrusal değil; ayrıca ölçüldü ki darboğaz modelde değil (P-18).

**C · Kademeli işleme** — her kareye her şeyi uygulama
Ucuz filtreler pahalı olanları besler; pahalı olan yalnızca aday
karelere/bölgelere uygulanır.

## Karar

**C.** Dört kademe:

```
KADEME 0  hareket filtresi (MOG2, 320×180, CPU)     1.5 ms/kare
KADEME 1  YOLO26 tespit + BoT-SORT takip            6.3 ms/kare
KADEME 2a poz — yalnızca tespit KUTULARINA          9.1 ms/kare
KADEME 2b yüz + ifade — yalnızca yeterince büyük
          kutulara, 3 kademeli kapı                 0.01 ms/kare
```

⚠ **Kademe 0 opsiyonel değil.** Onsuz 20 kamera dönmüyor.

## Sonuçlar

**Kazanılan:** 20 kamera tek GPU'da işleniyor, gecikme 468 ms
(K3 sınırı 1500).

**Kaybedilen:** Hareket filtresinin elediği karede hiçbir şey
görülmüyor. Hareketsiz duran bir kişi (bayılmış olabilir) Kademe 0'ı
geçmez. Bu yüzden filtre **periyodik yoklama** yapıyor: hareket
olmasa da belirli aralıklarla bir kare geçiriliyor (`gate="refresh"`).

**Kaybedilen 2:** Kademeler arasında bilgi kaybı var. Poz yalnızca
tespit edilen kutulara uygulandığı için, tespit kaçırdığı bir kişiye
poz da bakmıyor. Ölçüldü: poz modeli tek başına dedektör olarak
kullanılsa tespitlerin yalnızca **%43'ünü** buluyordu — yani ayrı
kademe olmaları doğru karardı (P-07 döneminin bulgusu).

## Ölçüm

| | |
|---|---|
| Kademe 0 filtre maliyeti | 1.5 ms/kare (4.8'den optimize, P-06) |
| Kademe 0 geçiş oranı | kameraya göre %15-60 |
| KADEME 2b kapı maliyeti | 0.01 ms/kare — 2700 aday, 0 sınıflandırma |
| 20 kamerada toplam | 55 kare/sn analiz, GPU %0-5 kullanım |

⚠ Son satır ilginç ve bir kez yanlış okundu: GPU'nun boş görünmesi
ileri geçişin ucuz olduğu anlamına gelmiyordu (bkz. ADR-0006).
