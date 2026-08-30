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

---
---

# İkinci bölüm — 30 Ağustos: sistemi TAMAMLAMA

Buraya kadarki kısım ölçüm ve düzeltmeydi. Bu bölüm farklı: **eksik
olan parçaları takmak.** Üçü de "Gün 1'den beri boş klasör" durumundaydı.

---

## 5 · ⭐ Alarmlar artık kaybolmuyor — KT4'ün çekirdeği

### Sorun tek cümlede

Bir alarm üretiliyordu, panel açıksa gösteriliyordu, **panel kapanınca
yok oluyordu.**

`db/`, `alerting/`, `storage/` klasörleri **Gün 1'den beri boş
iskeletti.** Veritabanında tek tablo yoktu.

Gözetim sisteminde operatörün asıl sorusu *"şu an ne oluyor"* değil:

> **"Dün gece 03:00'te ne oldu?"**

### Kurulan zincir

```
analytics worker → Valkey → alarm worker → PostgreSQL/TimescaleDB
                      │
                      └→ WebSocket → panel (canlı)
```

⚠ **Alarm worker'ı neden AYRI bir süreç?**

Veritabanına yazmak ağ turu + disk fsync demek. Bunu analiz döngüsünün
içine koymak iki şeyi birden bozardı: gecikme doğrudan artar, ve daha
kötüsü **veritabanı yavaşlarsa ANALİZ yavaşlar.**

Ayrı süreç bu bağı koparıyor: veritabanı tümden çökse bile tespit,
takip, anomali ve panel çalışmaya devam ediyor. Kaybedilen şey alarm
*geçmişi*, alarmın kendisi değil.

**Videoda söylenecek cümle:** *"Yardımcı bir bileşenin arızası ana boru
hattını durduramaz. Bu, sistemin her yerinde tekrarlanan bir ilke."*

### Neden TimescaleDB, neden düz PostgreSQL değil

Bu tablonun üç özelliği var ve üçü de zaman serisi: sadece ekleme
yapılıyor, sorgular hep zaman aralıklı, ve eski veri değerini yitiriyor
ama **özetini** yitirmiyor.

```
hypertable            → zaman dilimlerine otomatik bölme
sürekli toplulaştırma → saatlik özet arka planda güncelleniyor
saklama politikası    → 30 gün sonra ham satırlar siliniyor, özet kalıyor
```

### ⭐ Ve K7 artık sistemin sürekli çıktısı

Bugüne kadar her K7 ölçümü için elle betik yazıp Valkey akışını
dinledim. Artık:

```
GET /api/v1/events/ozet
→ {"alarm_kamera_saat": 1.5, "k7_hedef": 3.0}
```

**Kriter, bir ölçüm koşusunun değil sistemin normal çıktısının
parçası.**

### Bu sırada üç hata yaptım — üçü de öğretici

1. **`SEMA.format()` patladı.** SQL metni `'{}'::jsonb` içeriyordu ve
   `format` onu yer tutucu sandı.
2. **`split(";")` ifadeyi ortasından kesti.** SQL **yorumunun içinde**
   noktalı virgül vardı. *Ayırıcıya bakarak SQL bölmek, dizeleri ve
   yorumları tanımayan bir ayrıştırıcı yazmaktır.*
3. **⚠ En tehlikelisi:** `/ozet?saat=1` boş dönüyordu. Sürekli
   toplulaştırma son saati kasten özetlemiyor (doğru bir karar) ama
   materyalize edilmemiş bölge sorguya hiç girmiyordu.

   **Operatör "son 1 saatte hiçbir şey olmadı" cevabı alıyordu — oysa
   alarmlar tabloya yazılmıştı.**

   *Gözetim sisteminde en tehlikeli cevap budur: "hiçbir şey yok" ile
   "bakmadım" aynı görünüyorsa sistem sessizce yanıltıyor demektir.*

---

## 6 · Olay klibi — alarmı kanıta çeviren şey

Bir alarm satırı "cam-16'da 11:57'de düşme" diyor. Operatörün bir
sonraki sorusu her zaman aynı: **"göster."**

⚠ **Yeniden kodlama YOK — remux.** Klip, MediaMTX'in kaydettiği
segmentlerden kesilip **kopyalanıyor**:

```
yeniden kodlama : ~1-3 sn/klip CPU, kalite kaybı, GPU'ya rakip
remux           : ~32 ms/klip, bit birebir aynı
```

Bu fark 20 kamerada belirleyici: alarm patlamasında (bir olayda birden
çok kamera alarm verir) yeniden kodlama, tam da sistemin en meşgul
olduğu anda CPU'yu tüketirdi.

⚠ **Pencere asimetrik: önce 10 sn, sonra 5 sn.** Operatörün asıl merak
ettiği *"ne oldu da bu duruma gelindi"*, olayın kendisi değil.
Tırmanma skorunun anlamı da orada.

⚠ **Kaçınılmaz kısıt:** remux akışı çözmediği için kesim ancak bir
anahtar karede başlayabilir — 1-2 saniyeye kadar sapma olabilir.
Düzeltmenin tek yolu yeniden kodlamak ve o bedel karşılığını vermiyor.

---

## 7 · Güvenlik: Öncelik-1 ilan edilmişti, tek satır kod yoktu

`PLAN.md` güvenliği Öncelik-1 diyordu ve `config.py` JWT ayarlarını Gün
1'den beri taşıyordu. **API tamamen açıktı:** kamera listesi, olay
geçmişi, **webcam açma/kapatma** — hepsi kimlik doğrulamasız.

Tek hafifletici koşul her şeyin `127.0.0.1`'e bağlı olması. Bu bir
savunma değil bir **tesadüf**.

### Kurulanlar

| | |
|---|---|
| Parola | **Argon2id** — MD5/SHA değil |
| Token | JWT · erişim 15 dk + yenileme 7 gün |
| Roller | admin > operator > viewer (hiyerarşik) |
| Hız sınırı | Valkey'de, kullanıcı+IP başına |
| Denetim izi | **veritabanında**, günlükte değil |

⚠ **Neden Argon2id:** MD5/SHA **hızlı olmak için** tasarlandı ve parola
hash'inde hız saldırganın işine yarar. Argon2id hem CPU hem **bellek**
maliyeti dayatıyor — GPU'yla paralel kırma avantajını da siliyor.

⚠ **Salt okunur ile yazan uçlar ayrıldı.** Olay geçmişi `viewer`'a
açık; **webcam açmak `operator` istiyor.** Mahremiyet açısından fark
büyük: biri geçmişe bakmak, diğeri **yeni bir kamera açmak.**

⚠ **Token `localStorage`'da değil, `httponly` çerezde.** JavaScript
okuyamıyor, yani XSS ile çalınamıyor. Bedeli: "girişli miyim" sorusu
tokena bakarak değil **sunucuya sorularak** cevaplanıyor.

⚠ **Zamanlama saldırısı kapatıldı:** kullanıcı yoksa da sahte bir
hash'e karşı parola doğrulanıyor. Hemen dönmek, cevap süresinden "bu
kullanıcı adı var mı" bilgisini sızdırırdı.

⚠ **Varsayılan hesap YOK.** Birçok sistem ilk açılışta `admin/admin`
yaratıyor ve bu sahada en sık sömürülen açıklardan biri.

### Denetim izi neden veritabanında

Bir gözetim sistemi insanları izliyor. *"Kim, ne zaman, hangi kamerayı
izledi"* sorusunun cevabı olmadan **sistemin kendisi denetlenemez** hâle
gelir — ve denetlenemeyen bir gözetim sistemi, izlediği kişilerden çok
onu işletenlere ayrıcalık tanır.

Günlük dosyası döner, silinir, biçimi değişir; tablo sorgulanabilir.

### ⚠ Bilinen kısıt, dürüstçe

**JWT iptal edilemez.** "Çıkış yap" gerçek bir iptal değil — çerezi
siliyor, ama elde tutulan bir Bearer tokenı 15 dakika daha geçerli.
Gerçek iptal `jti` kara listesi ister ve erişim tokenının kısa ömrü
karşılığında **bilinçli olarak** yapılmadı. Yenileme tokenları için
iptal *var* (`token_surumu` sayacı).

---

## 8 · Güvenlik gözden geçirmesinin kendi hatası

Uçları tek tek korurken fark ettim: **video API'den geçmiyor.**

Mimari kural 2 zaten bunu söylüyordu ve bilinçliydi — tarayıcı doğrudan
MediaMTX'e bağlanıyor. Ben API'yi korurken **görüntünün kendisini** hiç
düşünmemişim. `read` izni herkese açıktı.

**Videoda söylenecek cümle:** *"Güvenlik çalışmasını 'hangi uçları
yazdım' listesi üzerinden yürüttüm, 'hangi veri değerli' listesi
üzerinden değil. Sistemin en mahrem çıktısı, benim yazmadığım bir
sürecin içinden akıyordu. Koruma, kolay korunan yere değil değerli
olana konur."*

Yerel ağa kısıtlandı — ama bu **tam çözüm değil** ve raporda öyle
yazılıyor: IP kısıtı kimlik doğrulaması değildir. Doğru cevap Caddy'yi
tek giriş noktası yapmak.

---

## 9 · Bir ölçüm aracının en önemli özelliği: ölçemediğini söylemesi

Parti doldurma (`--batch-fill-ms`) özelliğini ölçtüm. Dönüşümlü A/B —
P-17'nin dersi zaten uygulanmıştı. Özet **"-%15.2 verim"** dedi.

Blok blok bakınca:

```
[tur 1] fill=0    36.0 kare/sn · dolu %46
[tur 1] fill=60   51.7 kare/sn · dolu %78
[tur 2] fill=0    49.0 kare/sn · dolu %20
[tur 2] fill=60   20.4 kare/sn · dolu  %0   ⬅ ?
```

Son blok koşarken **MediaMTX'i yeniden başlatmıştım** (güvenlik
düzeltmesi için). 20 kamera birden yeniden bağlandı; o blokta ölçülen
şey parti doldurma değil, yeniden bağlanmaydı.

Ama asıl sorun bu değil. Asıl sorun: **betik ortalama raporluyordu** ve
bir bozuk örnek özeti tersine çevirdi.

Üstelik geçerli bloklara bakınca bile sonuç çıkmıyor: fill=0 blokları
36.0 ve 49.0 vermiş — aradaki fark, fill=60'ın farkı kadar büyük.

**Videoda söylenecek cümle:** *"İki örneğin ortalamasını, aralarında
%40 fark varken tek bir sayı gibi raporlamak, ölçülmemiş bir şeyi
ölçülmüş göstermektir. Dönüşümlü koşuya geçmiştim ama o sistematik
sürüklenmeyi çözüyor, tek seferlik bir bozulmayı çözmüyor."*

Betik artık medyan kullanıyor, yayılımı basıyor, ve etki gürültüden
küçükse açıkça **"SONUÇSUZ"** yazıyor.
