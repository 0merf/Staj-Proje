# 3. Sunum Notları — Gün 15 ve sonrası

> **Bu dosya birikerek yazılıyor.** Video çekilirken hazır olsun diye
> her iş bittiği anda buraya not düşülüyor.
> Önceki video: `sunum-notlari-2.md` (Gün 5 → Gün 15)

---

## Anlatının omurgası

Bu dönemin hikâyesi tek cümlede: **"ölçmeden değiştirmedik, ölçünce üç
kez yanıldığımızı gördük."**

Üç yanılgı da farklı türden ve üçü de öğretici:

| # | Yanılgı | Nasıl anlaşıldı |
|---|---|---|
| 1 | Düşme kuralı çalışıyor "olmalı" | Gerçek düşme görüntüsü bulunana kadar hiç denenmemişti |
| 2 | Saldırganlık eşikleri makul "görünüyordu" | Girdinin dağılımı ölçülünce sıfır noktası olmadığı çıktı |
| 3 | "GPU boşta, hızlandırmaya değmez" | Boşta olmak ucuz olmak değilmiş |

---

## 1 · Düşme kuralı ilk kez GERÇEK bir düşmede sınandı

### Sorun

Düşme, kural tabanlı anomali katmanının en kritik kuralı. Ama bugüne
kadar yalnızca **elle kurulmuş sentetik iskeletlerle** test edilmişti.

Aradaki fark önemli: sentetik test kuralın *mantığını* sınar
("en-boy oranı 1.2 ise ve eğim 80° ise alarm ver"). Kuralın gerçek
dünyada ürettiği *değerlerin* eşiklere uyup uymadığını sınamaz.

Elimizdeki hiçbir veri setinde düşme yoktu:

| Set | İçerdiği | Düşme? |
|---|---|---|
| CUHK Avenue | koşma, nesne fırlatma, oyalanma | ❌ |
| RWF-2000 | kavga | ❌ |
| VIRAT / PETS / Oxford | etiketsiz normal | ❌ |

### Yapılan

UR Fall Detection Dataset'ten bir düşme dizisi (160 kare, ofis ortamı)
cam-16'ya kondu — o slot PETS'in 7 kopya açısından biriydi, çiftlikteki
en az bilgi taşıyan kamera.

### Sonuç

```
10 dakikada cam-16 düşme alarmı :  5
Azami mümkün (60 sn soğuma)     : 10
Yakalama                        : %50
```

⚠ **Kaçırma değil, bastırma.** Sınırlayan şey soğuma penceresi.

Beş alarmın beşinde de kanıt zinciri eksiksiz:

| Kanıt | Düşen kişi | Ayakta duran |
|---|---|---|
| en-boy oranı | 1.10 – 1.79 | ~0.4 |
| gövde eğimi | 78° – 101° | 0-15° |
| devrilme hızı | 42 – 165 °/sn | 0-10 °/sn |

**Videoda söylenecek cümle:** *"Üç bağımsız kanıtın aynı anda tutması
gerekiyor. Eğilip bir şey almak da gövdeyi yatırır — ama yavaş yatırır.
Düşmeyi ayıran şey hız."*

### Bonus: gerçek görüntü bir hatayı da ortaya çıkardı

Kural, **175° gövde eğimiyle** skor 1.00 üretmişti — poz modelinin baş
ile ayağı karıştırdığı ters dönmüş bir iskelette. Üst sınır eklendi
(`DUSME_EGIM_AZAMI = 150°`). Sentetik testte bu hata asla çıkmazdı.

---

## 2 · Yanlış alarm yağmuru: 26.4/kamera-saat → sebebi bulundu

### Ölçüm

10 dakikalık canlı koşuda **88 alarm** = 26.4 alarm/kamera-saat.
Hedef (K7): **≤3**.

```
saldırganlık 30   ← Oxford caddesinde tek başına 12
unusual      19
kalabalık    17
oyalanma     11
düşme         7
```

Oxford'da 10 dakikada 12 kavga yok. Orada sadece yaya trafiği var.

### Yapmadığım şey

Eşikleri yükseltmek. Eşik yükseltmek yanlış alarmı **her zaman**
düşürür — bu bir keşif değil, aritmetik. Sebebi öğrenmeden yapılan ayar
bir sonraki sahnede yine patlar.

### Yaptığım şey: girdiyi ölçmek

20 kamera, 200 saniye, 40 bin özellik vektörü:

```
ÖZELLİK              p50     p90     p99   o günkü doyum
bilek_hizi_azami    0.87    1.80    4.01     3.0
bilek_sarsintisi    0.54    1.39    3.24     2.0
hareket_enerjisi    0.45    0.85    1.39     1.5
```

**Normal davranışın p90'ı doyumun %56-69'unu dolduruyor.**

Yani skorun **sıfır noktası yoktu.** Hiçbir şey yapmayan bir insan bile
puan alıyordu — çünkü yürüyen insanın bileği de hareket eder.

Kalem kalem, sıradan bir yaya (yanından biri geçerken):

```
bilek    0.66 × 0.25 = 0.164
enerji   0.41 × 0.15 = 0.061
duruş    0.25 × 0.10 = 0.025
yakınlık 0.38 × 0.30 = 0.113
yaklaşma 1.00 × 0.20 = 0.200
                       ─────
                       0.563   >  0.55 = UYARI
```

**Videoda söylenecek cümle:** *"Sistem 'iki yabancı yan yana geçti'
durumunu 'kavga çıkıyor' diye okuyordu. Eşik yanlış değildi — ölçek
yanlıştı."*

### Üç düzeltme

**a) Ölü bölge.** Her bileşen artık ölçülen normal p90'ın altında
**sıfır** üretiyor: `(değer − taban) / (doyum − taban)`.
İlke: *normal davranış kanıt değildir.*

**b) `DOYUM_YAKLASMA` yanlıştı ve yorumu ölçümle çelişiyordu.** Kodda
*"bu hızda yaklaşmak koşarak gelmektir"* yazıyordu; ölçüm gövde hızı
p99'unun 0.94 olduğunu söylüyor — iki kişi normal yürüyüşle karşılıklı
gelince kapanma hızı zaten o eşiği aşıyor. Bileşen sürekli doygundu.

**c) Etkileşim kapısı.** Modül kendi başlığında *"saldırganlık tanımı
gereği etkileşimlidir"* diyordu ama **toplamsal** skor bunu
uygulamıyordu: yalnız koşan biri bilek + enerji + duruştan puan
toplayabiliyordu. Skor artık `× max(yakınlık, yaklaşma)` ile çarpılıyor.

⚠ Kapı salt yakınlığa bağlanmadı — birbirine **koşan** iki kişi henüz
yakın değildir ve projenin özgün katkısı tam olarak o anı yakalamak.

### Doğrulama: dört ayar, tek veri, aynı anda

Ayarları arka arkaya denemek yanıltıcı olurdu — aradaki farkın ayardan
mı yoksa o sırada kameralarda olan biten farklı sahneden mi geldiği
bilinmez. (Bu hata Gün 8'de bir kez yapılmıştı: kazanç önce %-34
ölçülüp sonra %+43 çıkmıştı.)

Yazılan araç tek canlı akıştan **dört ayarı aynı anda** skorluyor:

```
6932 değerlendirme · 300 sn · 9 "normal olduğu bilinen" kamera
AYAR    dikkat  uyarı    p50     p99
ESKI       610     43   0.193   0.464
BANT       173      0   0.117   0.394
KAPI        23      0   0.088   0.278
IKISI        0      0   0.053   0.189
```

---

## 3 · ⚠ En dürüst bölüm: K5 tutmuyor

Yanlış alarmı sıfıra indirmenin en kolay yolu modülü **sağır etmektir.**
O yüzden ikinci ölçüm şart: *kavgayı hâlâ yakalıyor muyuz?*

RWF-2000'in `val` bölümünden 60 kavga + 60 normal klip, canlı boru
hattının aynısından geçirildi.

⚠ `val` seçildi çünkü `train` bölümü sahte kamera cam-17'yi besliyor.
Eşiği aynı kliplerle hem ayarlayıp hem değerlendirmek, ezberi başarı
sanmaktır.

```
AYAR    kavga p50  normal p50    AUC      F1
ESKI        0.368       0.219  0.665   0.704
BANT        0.175       0.131  0.652   0.717
KAPI        0.199       0.117  0.638   0.708
IKISI       0.089       0.063  0.629   0.712
```

**İki sonuç:**

1. ✅ Düzeltmeler ayırt etme gücünü **bozmadı** — AUC farkları n=120'de
   gürültü içinde. Ama canlı yanlış alarmı 610 → 0 yaptı. Aynı ayrım,
   çok daha az gürültü.

2. ❌ **K5 tutmuyor.** En iyi F1 = 0.712, hedef ≥0.85.

Sebep ayar değil, skorun kendi sınırı (AUC ≈ 0.63):

```
eşik 0.05 → kavganın %78'i,  normalin %53'ü
eşik 0.15 → kavganın %20'si, normalin %20'si   ⬅ şans seviyesi
eşik 0.19 → kavganın  %8'i,  normalin  %3'ü
```

**Videoda söylenecek cümle:** *"Bu bir başarısızlık değil, planın
kendisi. PLAN'da bu modül baştan 'eğitilmiş modelin geçmesi gereken
taban çizgisi' diye tanımlanmıştı. Artık o sayı elimizde: 0.712.
Model bunu geçemezse model kullanmanın anlamı yok."*

### Eşikler yeniden ölçeklendi

Ölü bölge skorun ölçeğini değiştirdi. Eski eşikleri (0.35/0.55/0.75)
bırakmak modülü tümden susturmak olurdu — kavga klip medyanı 0.089.

⚠ **Ölçek değişince eşik de değişmeli.** Yoksa "yanlış alarmı
düşürdüm" diye rapor edilen şey aslında sağırlıktır.

```
dikkat 0.12   ← YAYINLANMIYOR; skor geçmişi ve K8 ölçümü için
uyarı  0.20   ← canlı normalin p99'unun (0.189) hemen üstü
alarm  0.32
```

Seçim bilinçli olarak **sessizlik tarafında**: çiftlikte kavga içeriği
neredeyse yok, duyarlı eşik pratikte sadece yanlış alarm üretir.
*Alarmı kapatan operatör, hiç alarmı olmayan operatörden kötüdür.*

---

## 4 · "GPU boşta, hızlandırmaya değmez" — on gündür yanlışmış

Gün 8'den beri proje hafızasında şu yazıyordu:

> *"TensorRT planlandı ama kullanılmıyor: GPU %0-5'te boş oturuyor,
> yani modeli hızlandırmak kazanç getirmezdi."*

Cümle mantıklı görünüyor. **Yanlış.**

İki farklı büyüklük karıştırılmış:

| Ölçülen | Sanılan |
|---|---|
| **Görev döngüsü** — GPU zamanın yüzde kaçında meşgul | **Çağrı maliyeti** — bir ileri geçiş kaç ms |

GPU'nun %5 kullanımda görünmesi, ileri geçişin ucuz olduğunu değil,
**partiler arasında beklediğini** söyler.

### Ölçüm (CUDA olayıyla, boru hattı kapalı)

⚠ Duvar saatiyle ölçmek de yanlış sonuç verirdi: CUDA çağrıları
eşzamansızdır, `time.perf_counter()` işin bitişini değil **kuyruğa
atılışını** ölçer.

```
AŞAMA      kare ms    pay
TENSOR       0.960    15%
FORWARD      3.372    53%   ⬅ TensorRT'nin dokunabildiği tek yer
ARTIK        1.970    31%   NMS + Results nesnesi kurma
CONVERT      0.004     0%
TOPLAM       6.305
```

İleri geçiş bütçenin **yarısından fazlası.** Amdahl yasasına göre 3×
hızlanma → toplam %35.6 kazanç.

**Videoda söylenecek cümle:** *"Bir metriğin adı ile anlamı aynı şey
değil. 'GPU kullanımı %5' cümlesi doğruydu; ondan çıkardığım sonuç
yanlıştı. Ve bir kez belgeye girdikten sonra o çıkarım veri gibi
davranmaya başladı — on gün boyunca bulgu diye alıntılandı."*

*(TensorRT ölçümünün sonucu — devam ediyor)*

---

## Yan bulgu: diskte yalan söyleyen 5 dosya

UR Fall eklenirken fark edildi: `data/annotations/` içinde beş kamera
için **bayat yer gerçeği** duruyordu — dosyada RWF kavga zaman
damgaları, ekranda PETS kalabalık meydanı.

O slotlar bir zamanlar RWF kameralarıydı; video üzerine yazıldı, etiket
dosyası yerinde kaldı.

**Neden kimse fark etmedi:** hiçbir betik o dosyaları okumuyordu. Yani
hata görünmez biçimde bekliyordu — okuyan ilk ölçüm sessizce yanlış
sonuç verecekti.

⚠ **Testi olmayan veri, testi olmayan koddan tehlikelidir.** Kod
yanlışsa patlar; veri yanlışsa patlamaz, sadece yanlış sayı üretir.

Her etiket dosyası artık hangi kaynaktan üretildiğini yazıyor ve üretim
betiği uyuşmazlığı bildiriyor. **Silmiyor, uyarıyor** — elle yazılmış
bir dosyayı bir betiğin silmesi, çözdüğü sorundan büyük bir sorundur.

---

## Yan bulgu: yeşil kalan boş bir test

Yeni yazdığım regresyon testi ("yan yana geçen iki yaya dikkat bile
vermemeli") **ilk hâlinde hatayı yakalamıyordu** — eski ayarla bile
yeşil geçiyordu.

Sebep: test sahneyi yükleyip skorlayıcıyı **bir kez** çağırıyordu. Skor
üstel hareketli ortalamayla yumuşatıldığı için tek çağrıda ham değerin
ancak %40'ı görünüyordu: 0.178 ölçülüyordu, oturmuş değer 0.395.

Düzeltilince: **ESKI 0.395 (dikkat) · YENI 0.074 (sakin).**

**Videoda söylenecek cümle:** *"Zamansal yumuşatması olan bir sistemi
tek adımda test etmek, sistemi test etmemektir. Test yeşildi ama
hiçbir şey sınamıyordu."*

---

## Sayılarla özet

| | Önce | Sonra |
|---|---|---|
| Düşme kuralı doğrulaması | yalnızca sentetik | **gerçek düşme, %50 yakalama (soğuma sınırlı)** |
| Canlı yanlış alarm (normal kameralar, 300 sn) | 610 dikkat + 43 uyarı | **0 + 0** |
| Saldırganlık AUC (RWF val, 120 klip) | 0.665 | 0.629 (fark gürültü içinde) |
| K5 (F1) | ölçülmemişti | **0.712** — hedef 0.85, tutmuyor |
| `detect` ileri geçiş payı | "önemsiz" varsayılıyordu | **%53 (3.37 ms/kare)** |
| Test sayısı | 118 | 118 (2 yeni, 1 anlamlı hâle getirildi) |
