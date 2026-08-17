# Karşılaşılan Problemler ve Çözümleri

> **Bu dosya staj raporunun en değerli bölümüdür.**
> Sonradan hatırlanmaz — her problemi **yaşadığın gün** yaz.
> Rapor bölümü: 4.6 "Karşılaşılan problemler ve çözümleri"

**Yazım formatı:** Her kayıt aşağıdaki şablonu kullanır. Kısa tutmaktan çekinme,
ama **belirti / sebep / çözüm** üçlüsü mutlaka olsun.

---

## Şablon

```markdown
### P-XX · [Kısa başlık]

**Tarih:** GG.AA.YYYY · **Faz:** X · **Kaybedilen süre:** ~X saat

**Belirti:** Ne oldu, hata mesajı neydi, nasıl fark ettim?

**Araştırma:** Neyi denedim, hangi kaynaklara baktım, hangi hipotezler yanlış çıktı?

**Kök sebep:** Asıl sebep neydi?

**Çözüm:** Ne yaptım? (kod parçası / komut / konfigürasyon)

**Öğrenilen ders:** Bir dahaki sefere neyi farklı yaparım?
```

---

## Kayıtlar

<!-- Yeni kayıtlar buraya, en yenisi en üstte -->

### P-23 · React arayüzü beyaz açıldı — `base` yolu ayarlanmamıştı

**Tarih:** 17.08.2026 · **Faz:** 1 / Gün 11 · **Kaybedilen süre:** ~10 dk

**Belirti:** `http://127.0.0.1:8001/app/` tamamen **beyaz** açılıyordu.
Sunucu 200 döndürüyordu, HTML geliyordu, `<div id="root">` yerindeydi.
Hiçbir hata mesajı yoktu.

**Kök sebep:** Vite derlerken varlıkları **kökten** referanslıyordu:

```html
<script src="/assets/index-DB3ZTPzo.js">     ← 404
```

Uygulama `/app` altında servis edildiği için doğru yol
`/app/assets/...` olmalıydı. Tarayıcı script'i bulamayınca React hiç
başlamıyor, `<div id="root">` boş kalıyor ve sayfa beyaz görünüyor.

**Çözüm:** `vite.config.ts` içinde `base` ayarı — ama yalnızca
derlemede, geliştirme sunucusunda kök zaten doğru:

```ts
base: command === 'build' ? '/app/' : '/',
```

**Öğrenilen ders:** Bu hatanın tehlikesi **sessiz** olması. Sunucu
200 veriyor, HTML doğru, konsola bakmazsan hiçbir ipucu yok. Bir SPA
beyaz açılıyorsa ilk bakılacak yer **ağ sekmesinde varlıkların
yüklenip yüklenmediği** — sayfanın kendisi değil. Ayrıca: bir uygulamayı
kök dışında bir yola monte ediyorsan, derleyicinin bunu bilmesi gerekir.

---

### P-24 · Paneli açmak boru hattının verimini yarıya düşürüyor

**Tarih:** 17.08.2026 · **Faz:** 1 / Gün 11 · **Durum:** ölçüldü, karar kullanıcıya

**Belirti:** Arayüz devreye girdikten sonra verim 57.7 → 29 kare/sn'ye
düştü, gecikme 426 → 1304 ms'e çıktı.

**İlk (yanlış) refleks:** "React sistemi yavaşlattı." Bu yanlış olurdu —
React arka uçta hiçbir şey çalıştırmıyor, ayrı bir süreç.

**Ölçüm ne diyor:**

```
MediaMTX okuyucu sayısı : 40
  · 20 → alım worker'ı (analiz için, her zaman var)
  · 20 → TARAYICI (WebRTC, panel açık)

CPU yükü         : %35
GPU              : %25
GPU dekoder      : %0     ← tarayıcı videoları CPU'da çözüyor
```

**Kök sebep:** Panelde 20 kamerayı birden açmak, tarayıcının aynı
laptopta 20 adet H.264 akışını çözmesi demek — ve bu iş **CPU'da**
yapılıyor (GPU dekoder %0). Sistem Gün 8'den beri **CPU sınırlı**
(P-18), dolayısıyla tarayıcının aldığı her çekirdek doğrudan analiz
boru hattından çalınıyor.

**Bu React'e özgü DEĞİL.** Eski tek dosyalık panel de 20 `<iframe>`
içinde aynı 20 akışı çözüyordu. Yeni olan tek şey, artık ölçebiliyor
olmamız.

**Sonuç ve karar:**
- Gerçek kullanımda operatör 20 kamerayı birden izlemez; 4-6 kutucuk açar.
- **Ölçüm yaparken panel kapalı olmalı** — aksi hâlde ölçtüğümüz şey
  sistemin kapasitesi değil, "panel açıkken kalan kapasite" olur.
- Panelde açık kamera sayısı bir **ölçüm koşulu** olarak raporlanmalı.

**Öğrenilen ders:** Gözlem aracının kendisi ölçtüğü sistemi etkiliyor.
Bu, P-07 ve P-17 ile aynı aile: *ölçüm düzeneği sonucu bozmamalı.*
Üçüncü kez aynı ders — ama bu sefer düzeneğin kendisi değil,
**operatörün davranışı** ölçümü bozuyor.

---

### P-22 · Yeniden başlatma sonrası Docker bind mount ve port yönlendirmeleri bozuldu

**Tarih:** 17.08.2026 · **Faz:** 1 / Gün 11 · **Kaybedilen süre:** ~25 dk

**Belirti:** Bilgisayar yeniden başlatıldıktan sonra Docker servisleri
`docker compose ps` çıktısında **"Up ... (healthy)"** görünüyordu ama
sistem hiçbir kare üretmiyordu. Alım worker'ı ayaktaydı, 20 kamera
başta bağlanmış gibiydi, sonra hepsi düştü (`sentinel_camera_up` = 0/20).

**Yanlış yola sapma:** İlk baktığım yer modeldi — çıkarım worker'ı
kare başına 169 ms gösteriyordu (normalde 6.5 ms). "GPU bozuldu"
sandım. Oysa o sayı **kümülatif ortalamaydı** ve yalnızca 51 batch
vardı; çoğu soğuk başlangıçtı. Kendi öğrettiğim dersi (ortalama değil
p50, kümülatif değil aralık) neredeyse tekrar unutuyordum.

**Kök sebep — iki ayrı bozulma, ikisi de Docker Desktop kaynaklı:**

1. **Bind mount koptu.** MediaMTX video dosyalarını açamıyordu:
   ```
   Error opening input file /videos/cam-16.mp4.  I/O error
   ```
   Konteyner içinden `ls /videos` → `I/O error`. Host'ta dosyalar
   sapasağlam duruyordu. Konteyneri yeniden yaratmayı deneyince asıl
   hata çıktı:
   ```
   mkdir /run/desktop/mnt/host/d: file exists
   ```
   Yani Docker'ın WSL2 sanal makinesinde D: sürücüsünün bağlanma
   noktası bozuk bir durumda kalmış.

2. **Port yönlendirmeleri bayatladı.** Sanal makineyi yeniden
   başlattıktan sonra Valkey konteyneri "healthy" olmasına rağmen
   host'tan `ping` bile `Connection closed by server` veriyordu.
   Konteyner içinde sağlıklı, dışarıdan erişilemez.

**Çözüm:**
```powershell
wsl --terminate docker-desktop   # sanal makineyi yeniden başlat
docker compose down              # konteynerleri kaldır (veri kaybolmaz)
docker compose up -d             # yeniden kur — port yönlendirmeleri tazelenir
```

**Öğrenilen ders — "healthy" ile "erişilebilir" aynı şey değil.**
Bu, P-02'nin daha derin bir versiyonu. Docker'ın sağlık kontrolü
konteynerin **içinden** çalışır; mount'un okunabildiğini ya da port
yönlendirmesinin ayakta olduğunu söylemez. Sağlık kontrolümüz
(`/api/v1/system/health`) de aynı tuzağa düşüyordu: MediaMTX'in API'si
cevap verdiği için "sağlıklı" diyordu, ama yolların hiçbiri `ready`
değildi.

**Yapılacak (Gün 11 kapsamına alındı):** Sağlık kontrolü "kaç yol
ready" bilgisini zaten topluyor; **0 ise sağlıksız saymalı.** Aksi
hâlde panel yeşil görünürken sistem boş çalışıyor — sessiz hata.

---

### P-21 · `localhost` ile `127.0.0.1` ayrı kökenlerdir — P-11 ikinci kez

**Tarih:** 16.08.2026 · **Faz:** 1 / Gün 10 · **Kaybedilen süre:** ~0 (önceden test edildi)

**Belirti:** React geliştirme sunucusu kurulduktan sonra WebSocket
bağlantısı `http://127.0.0.1:5173` adresinden **403** alıyordu,
`http://localhost:5173` adresinden ise çalışıyordu.

**Kök sebep:** Tarayıcı `Origin` başlığını adres çubuğuna ne yazıldıysa
ona göre gönderir ve **`localhost` ile `127.0.0.1` farklı kökenlerdir**
— aynı makineyi göstermeleri fark etmez. Beyaz listede yalnızca
`http://localhost:5173` vardı. Aynı-köken (same-origin) kontrolü de
kurtarmıyordu: Vite vekili arkasında Host `127.0.0.1:8001`, Origin ise
`127.0.0.1:5173` — portlar farklı olduğu için eşleşmiyor.

**Çözüm:** Her iki yazım da beyaz listeye eklendi.

**Bu P-11'in tekrarı — ama bu sefer bedeli olmadı.** P-11'de aynı hata
panelin sessizce boş kalmasına yol açmış ve teşhis zaman almıştı. Bu
sefer arayüzü kurar kurmaz *önce* üç senaryoyu birden test ettim:

```
OK  http://127.0.0.1:5173     kabul edildi, 3 kare
OK  http://localhost:5173     kabul edildi, 3 kare
OK  http://evil.example.com   reddedildi
```

**Öğrenilen ders:** P-11'in dersi ("güvenlik kontrolü eklerken meşru
istemcileri de test et") burada **işe yaradı** — aynı sınıf hata
tekrar üretildi ama bu kez teşhis değil, rutin bir doğrulama oldu.
Problem günlüğü tutmanın somut faydası tam olarak bu: aynı tuzağa
ikinci kez düşerken maliyeti sıfıra iniyor.

Ek not: Vite de varsayılan olarak yalnızca `::1` (IPv6) dinliyordu ve
`127.0.0.1`'den erişilemiyordu — P-03'ün aynısı. `host: '127.0.0.1'`
ile sabitlendi.

---

### P-20 · Alım worker'ını yeniden başlatmak çıkarım worker'ını öldürüyordu

**Tarih:** 16.08.2026 · **Faz:** 1 / Gün 9 · **Tür:** hata izolasyonu

**Belirti:** Gün 9 değişikliklerini denemek için alım worker'ını yeniden
başlattım. Çıkarım worker'ı birkaç saniye sonra çöktü:

```
redis.exceptions.ResponseError: NOGROUP No such key 'frames.ready'
or consumer group 'inference' in XREADGROUP with GROUP option
```

**Kök sebep — iki doğru kararın çarpışması:**

1. Havuz sahibi (alım worker'ı) açılışta akışı **silmek zorunda**.
   Bu P-10'da öğrenilmişti: önceki çalışmadan kalan mesajlar geçersiz
   slot referansları taşır, tüketici onları "işledim" diye slotları
   geri verirse havuz bozulur ve iki kamera aynı slota yazar.
2. Çıkarım worker'ı akıştan tüketici grubu ile okuyor.

Valkey'de bir akışı silmek **tüketici gruplarını da siler.** Yani (1)
her yapıldığında (2) ayaklarının altındaki zemini kaybediyor.

Tek başına her iki karar da doğru; **etkileşimleri** yanlış.

**Neden önemli:** Bir bileşenin *normal* yeniden başlaması başka bir
bileşeni düşürmemeli (PLAN.md §4.2 hata izolasyonu). Üstelik bu sessiz
değil gürültülü bir çökmeydi ama yine de fark edilmesi zaman aldı,
çünkü çıkarım worker'ı arka planda çalışıyordu.

**Çözüm:** `FrameStream.consume()` artık `NOGROUP` hatasını yakalayıp
grubu sessizce yeniden kuruyor ve bir sonraki turda devam ediyor.

**Doğrulama (birim testi):**
```
1) grup kuruldu
2) okuma calisti
3) akis silindi (grup da gitti)
4) okuma COKMEDI, 0 mesaj dondu
5) ikinci okuma da calisiyor -> grup yeniden kurulmus
```

**Öğrenilen ders:** Dağıtık sistemlerde hatalar tek tek bileşenlerde
değil, **bileşenler arası varsayımlarda** yaşıyor. Burada üretici
"akışı ben yönetiyorum" varsayıyordu, tüketici "grubum kalıcıdır"
varsayıyordu. İkisi de kendi içinde makul. Bir bileşenin yeniden
başlatılmasının diğerlerinde ne yarattığını **düzenli olarak test
etmek** gerekiyor — bu yüzden Gün 9'un planında "hata izolasyonu
testi" vardı ve tam da onu bulduk.

---

### P-19 · Hedef 4 FPS, gerçekleşen 3.57 — örnekleme takvimi kayıyordu

**Tarih:** 16.08.2026 · **Faz:** 1 / Gün 9 · **Kazanç:** kamera başına %12 daha fazla kare

**Belirti:** `TARGET_FPS=4` ayarlıyken her kamera tam **3.57 FPS**
örneklüyordu. Sapma küçük ama şüpheliydi: 20 kamerada tutarlı olarak
aynı sayı çıkıyordu, yani rastgele bir gecikme değil **sistematik**
bir şeydi.

**Kök sebep:** Örnekleme kodu şöyleydi:

```python
if pts_s < next_emit:
    continue
next_emit = pts_s + self._interval    # ← hata burada
```

Takvim her seferinde **gerçekleşen** karenin zamanına sıfırlanıyordu.
Kaynak ayrık olduğu için (25 FPS = kareler 0.04 sn aralıklı) gerçekleşen
kare hedeften hep biraz sonradır ve bu aşma **her turda birikiyordu**:

```
hedef aralık 0.25 sn
6 kare = 0.24 sn  <  0.25  → yetmiyor, atla
7 kare = 0.28 sn  ≥  0.25  → yayınla, takvimi 0.28'e sıfırla
sonuç: 25 / 7 = 3.57 FPS
```

**Çözüm:** Sabit takvim — `next_emit += interval`. Aralıklar
0.28/0.24/0.24/0.24 diye değişiyor ama **ortalaması tam 0.25 sn**.
Çok geri kalınırsa (kare atlandı, yeniden bağlanıldı) takvim tazeleniyor,
yoksa yetişmek için ardı ardına kare yayınlamaya çalışırdı.

**Sonuç:** Örnekleme 3.57 → **4.00 FPS**. Bu, K2 kriterinin
tutturulmasındaki son adım oldu: hareketli kameralar artık tam 4.00
FPS'te analiz ediliyor.

**Öğrenilen ders:** Zamanlanmış tekrarlarda **"bir sonraki sefer"i
gerçekleşen zamana göre değil, planlanan takvime göre hesapla.**
Gerçekleşen zamana dayanmak her turda küçük bir gecikme ekler ve bu
gecikme birikir (kayma / drift). Klasik bir zamanlayıcı hatası; sapma
küçük olduğu için de kolayca gözden kaçıyor. Fark etmemi sağlayan şey,
sayının **20 kamerada da birebir aynı** çıkmasıydı — tesadüf öyle
davranmaz.

---

### P-18 · Darboğaz GPU sanılıyordu, CPU çıktı — GPU %0-5'te boş oturuyormuş

**Tarih:** 16.08.2026 · **Faz:** 1 / Gün 8 · **Kazanç:** gecikme 4× azaldı

**Belirti:** Poz eklendikten sonra sistem 20-37 FPS'te takılı kaldı
(gereken 80). Kare başına maliyet 16 ms ölçülmüştü — bu 62 FPS'e
denk gelmeliydi. Aradaki açık açıklanamıyordu.

**Araştırma:** Önce worker'a aşama bazlı süre ölçümü eklendi. Bekleme
süresi yalnızca %0.5 çıktı, yani worker kare beklemiyordu — gerçekten
çalışıyordu. Sonra koşu sırasında GPU izlendi:

```
GPU kullanımı : %0-5
Güç çekişi    : 17-32 W   (kartın bütçesi 80-125 W)
Sıcaklık      : 49°C
Kısıtlama sebebi: 0x01 = GpuIdle
```

**GPU boş oturuyordu.** Termal kısıtlama da yoktu (49°C).

Kesin ölçüm — `predict()` içinde süre nereye gidiyor:

| | toplam | saf GPU | CPU tarafı |
|---|---|---|---|
| Tespit (batch 8) | 47.7 ms | 22.5 ms (%47) | **25.3 ms (%53)** |
| Poz (64 kırpıntı) | 52.1 ms | 22.5 ms (%43) | **29.6 ms (%57)** |

**Kök sebep:** Ultralytics'e numpy dizisi verildiğinde ön işlemeyi
(1280×720 → 640 yeniden boyutlandırma, BGR→RGB, eksen değiştirme,
normalizasyon, GPU'ya kopyalama) **CPU'da** yapıyor. Boru hattımız seri
çalıştığı için GPU, bir sonraki batch'in CPU hazırlığı bitene kadar
bekliyordu.

Bu bilinen bir problem: Ultralytics kendi dokümanında *"üretimde ön
işleme çoğu zaman darboğaz olur"* ve *"seri boru hattında GPU çoğu
zaman boş oturur, çözüm eşzamanlılıktır"* diyor (LITERATUR §P).

**Çözüm:** Ön işleme **alım katmanına** taşındı. Kareler paylaşımlı
belleğe ham değil, model uzayında (640×640 letterbox) yazılıyor.
Çıkarım worker'ı hazır diziyi doğrudan GPU tensörüne çevirip veriyor;
Ultralytics kendi ön işlemesini atlıyor.

Neden alım tarafı: orası 20 kamera iş parçacığına dağılıyor ve
`cv2.resize` GIL'i bıraktığı için gerçekten paralel koşuyor. Çıkarım
worker'ı ise **tek süreç** — aynı işi orada yapmak seri kalırdı.
Ölçüm bunu doğruladı: hazırlık çıkarım tarafında yapılınca net kazanç
sıfır (3.87 + 3.43 ≈ 6.8 ≈ eski 6.78 ms).

**Sonuç (20 kamera, 210 sn):**

| | Gün 7 | Gün 8 | |
|---|---|---|---|
| Uçtan uca gecikme | ~600 ms | **144 ms** | 4.2× |
| Akış | 20-37 FPS | 34.6 FPS | kararlı |
| Tespit | 7.6 ms | 6.5 ms | |
| Boş slot | 0-8 / 48 | **44 / 48** | kuyruk artık dolmuyor |
| Kamera başına FPS | 1.5-1.9 | 2.2-2.4 | |
| Parçalanma | %46.6 | **%37.3** | kimlik daha kararlı |
| shm slot boyutu | 2.76 MB | 1.23 MB | 2.2× küçük |

**En önemli değişim boş slot sayısı.** Tüketici artık üreticiden hızlı;
sistem "kuyruk sınırlı" olmaktan çıktı. Gecikmedeki 4 katlık düşüş
doğrudan bunun sonucu — P-16'da teşhis edilen mekanizma kapandı.

**Doğrulama:** Kutular artık model uzayında (640×640) üretilip kaynak
piksel uzayına geri taşınıyor. Bu eşleme hatalı olsaydı sessizce yanlış
yere çizerdi, o yüzden ayrıca ölçüldü: 2240 tespitte **0** kare dışı/bozuk
kutu, 28 342 keypoint'in **%100'ü** kendi kutusuyla uyumlu, üç farklı
kaynak çözünürlük (900/960/1280 × 720) doğru raporlanıyor.

**Öğrenilen ders:** Bütçe hesabı yaparken **hangi kaynağın** sınır
olduğunu varsaymak yerine ölçmek gerekiyor. PLAN.md §2.3'te GPU bütçesi
titizlikle hesaplanmış, **CPU bütçesi hiç hesaplanmamıştı.** Sistemin
darboğazı hesaplanan yerde değil, hiç bakılmayan yerdeydi. Ayrıca
"GPU kullanımı" metriği baştan izlenseydi bu 3 gün önce görülürdü —
`nvidia-smi`'nin tek satırı, tüm süre bütçesi tablosundan daha
açıklayıcıydı.

---

### P-17 · Ölçümü sırayla koşturmak sonucu tersine çevirdi

**Tarih:** 16.08.2026 · **Faz:** 1 / Gün 8 · **Kaybedilen süre:** ~20 dk

**Belirti:** Ön işlemenin nereye taşınacağına karar vermek için üç
senaryo ölçüldü. Sonuç hipotezin tam tersi çıktı:

```
A) numpy 1280x720 (mevcut)   6.78 ms/kare
B) numpy 640x640             (A'dan %9 YAVAŞ)
C) hazır GPU tensörü         (A'dan %34 YAVAŞ)
```

C'nin daha yavaş çıkması Ultralytics'in kendi dokümanıyla çelişiyordu.
Neredeyse "hazır tensör işe yaramıyor" diye kaydedip başka yol
arayacaktım.

**Kök sebep:** Senaryolar **sırayla** koşturulmuştu — önce A'nın 25
turu, sonra B'nin, sonra C'nin. Arka planda 20 kameralık alım katmanı
çalışıyor ve makinedeki yük dalgalanıyor. Ölçüm ilerledikçe yük arttığı
için **sonra koşan senaryo cezalandırılıyordu.** Ölçtüğüm şey senaryolar
arasındaki fark değil, zamanın kendisiydi.

**Çözüm:** A/B/C **dönüşümlü** (interleaved) koşturuldu — her turda
sırayla biri, 25 tur, sonra medyan. Böylece yük dalgalanması üç
senaryoyu da eşit etkiliyor.

**Düzeltilmiş sonuç:**

| Senaryo | ms/kare | Kazanç |
|---|---|---|
| A) numpy 1280×720 | 6.78 | — |
| B) numpy 640×640 | 6.31 | %7 |
| **C) hazır GPU tensörü** | **3.87** | **%43** |

Tam tersi. Üçü de aynı tespitleri veriyor (69), yani kazanç doğruluk
bedeli olmadan geliyor.

**Öğrenilen ders:** Bu, P-07'nin aynısı — *ölçüm düzeneğinin kendisi
sonucu bozmamalı.* P-07'de RTSP'nin hız sınırını kapasite sanmıştım;
burada zamanla değişen sistem yükünü senaryo farkı sandım. Ortak kural:
**A/B karşılaştırmasında A ve B eşit koşullarda koşmalı.** Değişen bir
ortamda bunun tek güvenli yolu dönüşümlü ölçüm ve medyandır. Sıralı
ölçüm ancak ortam sabitse geçerlidir — ve bizim ortamımız asla sabit
değil, çünkü sistemin kendisi arka planda çalışıyor.

---

### P-16 · Poz açılınca gecikme 68 ms'ten 600 ms'e çıktı — P-12'nin geri dönüşü

**Tarih:** 15.08.2026 · **Faz:** 1 / Gün 7 · **Durum:** teşhis kondu, karar Gün 8'e

**Belirti:** Kademe 2a (poz) devreye alındıktan sonra uçtan uca gecikme
**68 ms → ~600 ms** çıktı. Poz modelinin kendisi hızlıydı (7.3 ms/kare),
yani 530 ms'lik fark modelin çalışma süresinden gelmiyordu.

**Kök sebep — üretim/tüketim dengesizliği:**

```
Alım katmanı üretiyor : ~52 kare/sn   (değişmedi)
Çıkarım tüketiyor     :  37 kare/sn   (poz eklendi, 52'den düştü)
                        ─────────────
Fark                  :  15 kare/sn   → havuz sürekli dolu
```

48 slotluk havuz, 37 FPS tüketimle **48 / 37 ≈ 1.3 saniyelik** azami
kuyruk beklemesi demek. Ölçülen p50 600 ms tam da bu aralıkta.

**Bu tam olarak P-12'de teşhis edilen mekanizma.** Orada tamponu
küçülterek çözmüştük (128→48, gecikme 770→68 ms). Şimdi aynı tampon,
tüketim hızı düştüğü için yeniden dolu kalıyor. Yani P-12'nin çözümü
yanlış değildi — **belirli bir tüketim hızına göre boyutlanmıştı** ve o
varsayım değişti.

**Öğrenilen ders:** Bir tampon boyutu mutlak bir sayı değil, **tüketici
hızının fonksiyonudur**. `48 slot` kararını verirken "48 iyi bir sayı"
diye not almıştım; doğrusu "52 FPS tüketimde 0.9 sn'lik tampon" olmalıydı.
Böyle yazsaydım, tüketim 37'ye düştüğünde tamponun da küçülmesi gerektiği
kendiliğinden görünürdü. **Türetilmiş sabitleri, türetildikleri formülle
birlikte yaz.**

**Seçenekler (Gün 8'de karara bağlanacak):**

| Seçenek | Etkisi | Bedeli |
|---|---|---|
| Havuzu küçült (48 → ~24) | gecikme ~600 → ~300 ms | daha çok kare atılır |
| Pozu seyrelt (iz başına her N karede bir) | tüketim 37 → ~48 FPS | bilek hızı çözünürlüğü düşer |
| Alım hızını tüketime bağla (geri basınç) | kuyruk hiç dolmaz | uyarlanabilir FPS mantığı gerekir (PLAN.md §5.2) |
| Kabul et, raporla | iş yok | K2 hedefinden uzaklaşılır |

⚠ Karar verilirken şu unutulmamalı: **poz, saldırganlık modülünün tek
girdisidir** (PLAN.md §6.5.2 — bilek hızı, kol açısı, gövde eğimi).
Pozu kısmak doğrudan projenin ana yeteneğini kısar.

---

### P-15 · Doğru batch boyutu modelin değil, ÜRETİLEN İŞİN fonksiyonuymuş

**Tarih:** 15.08.2026 · **Faz:** 1 / Gün 7 · **Kazanç:** poz maliyeti %27 düştü

**Belirti:** İzole ölçüm (`benchmark_pose.py`) kırpıntı başına poz
maliyetini **1.30 ms** buldu ve kare başına 5.80 ms öngördü. Boru hattına
bağlayınca gerçekleşen **12.5 ms/kare** oldu — 2 kattan fazla sapma.

**Araştırma:** Önce GPU çekişmesinden şüphelendim (aynı anda tespit de
koşuyor). Ama tespit de aynı oranda yavaşlamıştı, yani sistematik bir
şey vardı. Sayıları yazınca görüldü:

```
8 kare × ~4.4 kişi/kare  ≈  35 kırpıntı
kırpıntı batch sınırı    =  32
                            ────────────────
sonuç                    :  32 + 3  →  İKİ GPU çağrısı
```

**Kök sebep:** 3 kırpıntılık kuyruk çağrısı, 32'lik çağrıyla neredeyse
**aynı sabit maliyeti** ödüyor (çekirdek başlatma, Python tarafı ön/son
işleme, sonuç nesnelerinin kurulması). Yani her batch'te bir çağrının
maliyetini boşuna ödüyorduk.

Batch sınırı 32 seçilmişti çünkü izole ölçümde kırpıntı başına maliyet
32'de en düşüktü (8 → 2.84 ms, 16 → 1.80 ms, 32 → 1.30 ms). Ölçüm
doğruydu; **soru yanlıştı.** "Hangi batch boyutu en verimli?" diye
sormuştum. Doğru soru: "Sistemim tipik olarak kaç kırpıntı üretiyor ve
bunu kaç çağrıya bölüyorum?"

**Çözüm:** Sınır 64'e çıkarıldı — tipik yük tek çağrıya sığıyor.

| | batch 32 | batch 64 |
|---|---|---|
| Poz maliyeti (p50) | 12.5 ms/kare | **9.1 ms/kare** |
| GPU çağrısı / batch | 2 | 1 |

**Öğrenilen ders:** İzole kıyaslama, bileşenin **kendi** eğrisini verir;
sistemdeki davranışını vermez. Kritik olan parametre "eğrinin en iyi
noktası" değil, **iş miktarının o parametreye bölünme biçimiydi.** Bir
sonraki sefer: bir batch sınırı seçerken önce "gerçek yük bunun neresine
düşüyor" diye bakmalı — özellikle sınırın hemen üstüne düşen yükler en
kötü durumdur (33 kırpıntı = 2 çağrı, biri 1 elemanlı).

---

### P-14 · İskeletlerin yarısı çıkmıyordu — suçlu çözünürlük değil, en-boy oranıydı

**Tarih:** 15.08.2026 · **Faz:** 1 / Gün 7 · **Kazanç:** iskelet başarısı %47 → %88

**Bağlam:** Gün 7 ölçümü, poz modelinin tek başına kullanılamayacağını
gösterdi (tespitlerin yalnızca %43'ünü buluyor — aşağıya bakınız). Bu
yüzden tasarım "tespit + kişi kırpıntısına poz" oldu. İlk uygulamada
kırpıntılar modele `cv2.resize(crop, (192, 192))` ile veriliyordu.

**Belirti:** Kırpıntıların yalnızca **%47.4'ünden** iskelet çıkıyordu.
Dahası başarısızlık kutu boyutuyla güçlü şekilde ilişkiliydi:

| Kutu alanı | Başarı |
|---|---|
| < 3 000 px² | %18.1 |
| 3–6 000 px² | %28.3 |
| 6–12 000 px² | %59.4 |
| 12–25 000 px² | %78.5 |

**Yanlış hipotez:** "Küçük kutular çözünürlük sınırı. 50×50 pikseli
192'ye büyütmek bulanık bir leke veriyor, model eklem göremiyor."
Bu tamamen makul görünüyordu ve veriye de uyuyordu — kabul edip
"küçük kutulara poz çalıştırma" filtresi eklemeye hazırdım.

**Gerçek kök sebep:** Kareye sıkıştırma. Uzaktaki bir kişi **ince ve
uzun** bir kutu verir (örn. 40×130 px, oran 1:3.25). Bunu 192×192'ye
sıkıştırmak kişiyi yatay olarak **3 kat şişirir** — model artık insan
şekli görmez. Kutu ne kadar uzunsa bozulma o kadar büyük, ve en uzun
kutular tam da en uzak (en küçük alanlı) kişilerdir. **Alanla korelasyon
sahteydi; asıl değişken en-boy oranıydı.**

**Çözüm:** En-boy oranını koruyarak dolgulama (letterbox) — kırpıntı
oranı bozulmadan büyütülür, kalan yer nötr griyle (114) doldurulur.

| | Kare sıkıştırma | Letterbox |
|---|---|---|
| Genel başarı | %47.4 | **%88.1** |
| < 3 000 px² kutular | %18.1 | **%94.4** |

En küçük kutular en çok kazanan grup oldu — hipotezin tam tersi.

**Öğrenilen ders:** İki değişken birlikte hareket ettiğinde (burada
"küçük alan" ve "uzun oran"), veriye uyan ilk açıklama doğru olmayabilir.
Hipotezi kabul etmeden önce **ayırt edici bir deney** yapmak gerekiyordu:
"oranı düzeltirsem küçük kutular düzelir mi?" Bu deney 10 dakika sürdü ve
bir filtreyi (dolayısıyla uzaktaki kişilerin iskeletini tamamen) kurtardı.

Gözetim açısından bu kritik: uzaktaki kişi tam da izlenmesi gerekendir.
"Küçük kutulara poz çalıştırma" filtresini eklemiş olsaydım, koridorun
ucundaki kavgayı hiç göremezdik ve sebebini de bilemezdik.

---

### P-13 · Takip eklendi, tespitlerin %21'i kayboldu

**Tarih:** 15.08.2026 · **Faz:** 1 / Gün 6 · **Tür:** gerileme (regression)

**Belirti:** BoT-SORT takibi devreye alındıktan sonra panelde **bariz
görünen kişiler kutuya alınmıyordu** ve kutular eskisinden daha geç
beliriyordu. Takipten önce çalışan bir şey, takipten sonra bozuldu.

**Kök sebep:** ByteTrack ailesindeki takipçiler yeni bir izi **hemen
çıktı vermez.** Bir iz "onaylanmış" (`is_activated`) sayılması için
**ikinci bir karede tekrar eşleşmesi** gerekir. Mantık şu: tek karelik
yanlış pozitiflerden kalıcı iz üretmemek.

Normal video hızında (25-30 FPS) bu gecikme ~35 ms, fark edilmez.
Ama bizde tespit **kamera başına ~3 FPS** yapılıyor (kademeli işleme
gereği), dolayısıyla:

- Yeni beliren her kişi **~330 ms geç** görünüyor
- Kadrajdan hızla geçen kişiler **hiç görünmüyor** (iki tespit süresi
  boyunca kalmıyorlar)

Ölçüm: tespitlerin **%21'i** bu şekilde düşüyordu.

**Tasarım hatası neydi:** Takip katmanını dedektörün *arkasına* değil
*önüne* koymuşum gibi davranmışım — takipçinin çıktısını tek gerçek
kaynak saymışım. Oysa takip, tespiti **zenginleştiren** bir katman
olmalı, **filtreleyen** değil.

**Çözüm:** Takipçiyle eşleşmemiş tespitler artık **kimliksiz olarak**
geçiriliyor (`track_id = -1`, mesajda `id` alanı hiç yok). Kutu anında
görünüyor, kimlik bir sonraki karede geliyor.

Panelde kimliksiz kutular **kesikli çizgiyle** gösteriliyor — operatör
"bu tespit henüz doğrulanmadı" bilgisini görüyor ama kişi ekrandan
kaybolmuyor.

**Sonuç:**

| | Takipten önce | Takip (hatalı) | Düzeltme sonrası |
|---|---|---|---|
| Kare başına tespit | 4.24 | ~3.5 | **4.88** |
| Kayıp tespit | — | %21 | **%0** |

**Öğrenilen ders:** Bir katman eklerken *"eskiden çalışan ne bozuldu?"*
diye sormak gerekiyor. Yeni özelliğin doğru çalışması yetmez; mevcut
davranışı bozmaması da gerekir. Kullanıcının "eskiden herkesi çiziyordu,
şimdi çizmiyor" geri bildirimi olmasa bu, saldırganlık modülü yanlış
sonuç verene kadar fark edilmeyebilirdi.

Ayrıca: bir kütüphanenin varsayılan davranışı (iz onayı) kendi
bağlamında doğru, bizim bağlamımızda (düşük kare hızı) yanlış. Kütüphane
varsayımlarını kendi çalışma koşullarınla karşılaştırmak gerekiyor.

---

### P-12 · Kutular geriden geliyordu — derin kuyruk gerçek zamanlılığın düşmanı

**Tarih:** 14.08.2026 · **Faz:** 1 / Gün 5 · **Kazanç:** gecikme 11× azaldı

**Belirti:** Kutular ekranda görünüyordu ama **kişinin arkasından**
geliyorlardı; yürüyen biri kutunun dışına çıkıyor, kutu boşluğu
gösteriyordu.

**İki ayrı sebep vardı — karıştırmamak önemli:**

#### Sebep 1 — Boru hattı gecikmesi (çözüldü)

Ölçüm: `frames.ready` kuyruğu **sürekli doluydu** (206/200) ve paylaşımlı
bellek havuzunun 128 slotu da kullanımdaydı.

Hesap basit: 128 kare kuyrukta bekliyor, sistem saniyede ~70 kare
işliyor → kuyruğun sonundaki kare işlendiğinde **1.8 saniye eskimiş**
oluyor. Model doğru çalışıyor ama *geçmişe* bakıyor.

**Kök sebep bir tasarım hatası:** tamponu büyük tutmak "kare kaybetmeyelim"
diye iyi bir fikir gibi görünüyor. Gerçek zamanlı bir sistemde tam tersi:
**kuyrukta bekleyen kare değersizleşir.** 2 saniye önceki kareyi mükemmel
analiz etmenin operasyonel değeri yoktur.

**Çözüm:** Tamponlar küçültüldü.
```
SHM_SLOT_COUNT        128 -> 48
STREAM_FRAMES_MAXLEN  200 -> 64
```
Fazla kare artık kuyrukta beklemek yerine **atılıyor**. Bu bilinçli bir
takas: bütünlük yerine tazelik (PLAN.md §4.3).

**Sonuç:**

| | Önce | Sonra |
|---|---|---|
| Uçtan uca gecikme (p50) | ~770 ms | **68 ms** |
| Boş slot | 0/128 (tıkalı) | 47/48 (rahat) |
| İşlem hızı | 52 FPS | 52 FPS (değişmedi) |

**11 kat iyileşme, üretim hızından hiçbir şey kaybetmeden.**

#### Sebep 2 — Tespitler arası donma (Gün 6'da çözülecek)

Kalan sorun: video **25 FPS** akıyor, tespit ise kamera başına
**~3 FPS** yapılıyor (kademeli işleme gereği — her kareye YOLO
çalıştırmak 20 kamerada imkânsız).

Ölçüm: iki tespit arasında ortalama **334 ms** (p50 279, p95 863) geçiyor.
Yürüyen bir insan bu sürede 30-50 piksel yol alıyor. Kutu son bilinen
konumda **donuk** kalıyor, kişi ondan çıkıyor.

**Çözüm (Gün 6):** Nesne takibi (BoT-SORT) her kişiye kalıcı bir kimlik
ve **hız vektörü** verecek. Tarayıcı iki tespit arasında kutuyu bu hızla
**ara değerleyecek** (interpolasyon). Gerçek güvenlik yazılımları da
tam olarak böyle çalışır — 25 FPS tespit yapmazlar, 3 FPS tespit yapıp
aradaki kareleri tahmin ederler.

**Öğrenilen ders:** "Kutular geç geliyor" tek bir belirti gibi görünüyordu
ama arkasında iki bağımsız sebep vardı: biri **kuyruk tasarımı**, diğeri
**örnekleme hızı**. Ölçmeden tek bir çözüme koşsaydık yanlış olanı
düzeltmiş olabilirdik.

---

### P-11 · Kendi güvenlik kontrolüm kendi panelimi engelledi

**Tarih:** 14.08.2026 · **Faz:** 1 / Gün 5 · **Kaybedilen süre:** ~15 dk

**Belirti:** Panelde tüm kameralarda "analiz bekleniyor" yazıyordu, hiç
kutu çizilmiyordu. Oysa:
- Alım ve çıkarım worker'ları çalışıyor, GPU aktif
- `inference.results` akışına saniyede ~70 sonuç yazılıyor
- **Test betiği `scripts/test_websocket.py` sorunsuz 57 FPS alıyordu**

Son madde kritikti: WebSocket sunucusu çalışıyordu ama tarayıcı veri
alamıyordu. İkisi arasındaki fark neydi?

**Kök sebep:** `Origin` başlığı.

| İstemci | Gönderdiği Origin | Sonuç |
|---|---|---|
| Test betiği | `http://localhost:5173` | ✅ beyaz listede |
| **Tarayıcı (panel)** | `http://127.0.0.1:8001` | ❌ **listede yok** |

Panel, API ile **aynı sunucudan** servis ediliyor. Dolayısıyla tarayıcı
`Origin: http://127.0.0.1:8001` gönderiyor. Beyaz listede ise yalnızca
React geliştirme sunucusunun adresleri vardı (`:5173`, `:3000`).

Yani G06 güvenlik kontrolü **doğru çalışıyordu** — sadece izin verilmesi
gereken bir istemciyi de reddediyordu. Kendi panelimi kendi güvenlik
duvarıma çarptırmışım.

**Çözüm:** Beyaz listeye elle adres eklemek yerine **aynı köken (same
origin) kontrolü** eklendi: `Origin` başlığı `Host` başlığıyla eşleşiyorsa
bağlantı kabul edilir. Bu tanımı gereği güvenlidir — aynı köken
politikasının koruduğu şey zaten tam olarak budur.

Neden beyaz listeye elle eklemedim: adres değişince (farklı port, farklı
makine, ters proxy arkası) sessizce kırılırdı. Same-origin kontrolü
adresten bağımsız çalışır.

**Doğrulama — birim testi yazıldı:**

```
[OK] ayni kaynak - PANEL           -> True
[OK] ayni kaynak - localhost       -> True
[OK] beyaz liste - React dev       -> True
[OK] kotu niyetli site             -> False
[OK] farkli port                   -> False
[OK] Origin yok                    -> False
```

Tarayıcının gönderdiği başlıkla yapılan testte: **8 saniyede 498 kare,
1790 tespit, 20 kamera.**

**Öğrenilen ders:** Güvenlik kontrolü eklerken **meşru istemcileri de
test et.** "Kötü niyetli istek reddediliyor mu?" sorusunun yanına
"iyi niyetli istek geçiyor mu?" sorusu da konmalı. İlk yazdığım testte
yalnızca reddedilme senaryolarını kontrol etmiştim; kabul senaryosunu
gerçek tarayıcı başlığıyla değil, kendi seçtiğim Origin ile test etmiştim.

Bu ayrıca "sessiz başarısızlık" örneği: sistem hata vermedi, log'a
`ws_origin_reddedildi` yazdı ama panelde yalnızca "bekleniyor" göründü.
Bu yüzden panele artık **sebep gösteren** bir uyarı eklendi (P-10 ile
birlikte).

---

### P-10 · Slot havuzu bozulması ve ardından tüketici kilitlenmesi

**Tarih:** 13.08.2026 · **Faz:** 0 / Gün 3 · **Kaybedilen süre:** ~25 dk

İki ayrı hata, biri diğerinin düzeltmesinden doğdu. İkisi de dağıtık
sistemlerin klasik tuzakları.

#### Hata A — Slot çift serbest bırakma

**Belirti:** Boru hattı çalışıyordu ama istatistikte imkânsız bir sayı
vardı: `boş slot 230/128`. Havuzda 128 slot var, boş listede 230 giriş.

**Kök sebep:** Havuz sahibi worker açılışta boş slot listesini sıfırlıyor
(`0..127`), ama **Valkey Stream'i temizlemiyordu.** Önceki çalışmadan
kalan ~205 mesaj akışta duruyordu. Yeni tüketici bu eski mesajları okuyup
"işledim" diyerek slotlarını havuza geri veriyordu — oysa o slotlar zaten
listedeydi.

**Neden tehlikeli:** Liste bozulunca iki farklı kamera **aynı slotu**
alabilir. İkisi de aynı belleğe yazar, biri diğerinin karesini ezer.
Sonuç: kamera 5'in ekranında kamera 12'nin görüntüsü — ve bunu hata
ayıklamak kâbustur, çünkü kod doğru görünür.

**Çözüm:** Havuz sahibi açılışta **önce akışı siler, sonra slotları
dağıtır.** Sıra önemli.

#### Hata B — Tüketici grubu kilitlenmesi

**Belirti:** A'yı düzelttikten sonra tüketici **0 kare** aldı. Worker ise
128 kare yayınlayıp tıkandı: `boş slot 0/128`.

**Kök sebep:** Tüketici grubu `id="$"` ile oluşturuluyordu — Valkey'de bu
"yalnızca bundan sonraki mesajlar" demek. Olaylar şöyle sıralandı:

1. Worker akışı sildi, 128 kare yayınladı, boş slot kalmadı → durdu
2. Tüketici 8 saniye sonra başladı, grubu `"$"` ile açtı → *"şu andan
   sonrası"*, yani mevcut 128 mesaj kapsam dışı
3. Tüketici okuyacak mesaj bulamadı → slot serbest bırakmadı
4. Worker slot bulamadı → yeni mesaj üretemedi
5. **Karşılıklı bekleme.** Klasik kilitlenme.

**Çözüm:** Grup `id="0"` ile oluşturuluyor — akışın başından. Mantık
basit: *akışta duran her mesaj işlenmemiş iştir.* `"$"` yalnızca canlı
telemetri gibi "geçmiş önemsiz" senaryolarda doğrudur; iş kuyruğunda değil.

**Doğrulama (20 kamera, 40 saniye):**
```
20/20 kamera · 65.5 FPS alınıyor · 2062 yayınlanıyor
Tüketici     : 2202 kare · 55.0 FPS
Veri kontrolü: 2202/2202 karede gerçek piksel
Boş slot     : 128/128  ← havuz bütünlüğü korunuyor
```

**Öğrenilen ders:** Kaynak havuzlarında **sahiplik ve temizlik sırası**
kritiktir; yeniden başlatma senaryosu ilk günden düşünülmeli. Ayrıca bir
hatayı düzeltirken ikincisini yaratmak, iki bileşenin varsayımlarının
uyuşmadığını gösterir — burada üretici "akışı sildim" varsayıyordu,
tüketici "akışta ne varsa yenidir" varsayıyordu.

---

### P-09 · NVDEC, CPU'dan YAVAŞ çıktı — ve decode zaten darboğaz değilmiş

**Tarih:** 13.08.2026 · **Faz:** 0 / Gün 3 · **Sonuç:** Mimari karar değişti

**Bağlam:** P-07'de "CPU çözme yetmiyor, NVDEC'e geçmeliyiz" sonucuna
varmıştım. `PLAN.md` §2.4 de bunu varsayıyordu. Gün 3'ün ana işi buydu.

**Ölçüm (RTX 3070 Laptop + i7-12700H, 720p H.264 yerel dosya):**

| Yöntem | Sadece çözme | Çözme + BGR dizi |
|---|---|---|
| CPU tek iş parçacığı | 1044 FPS | **240.6 FPS** |
| CPU çoklu iş parçacığı | 2943 FPS | — |
| **NVDEC (cuda hwaccel)** | 1246 FPS | **175.1 FPS** ⬅ daha yavaş |

**İki sürpriz:**

**1. NVDEC daha yavaş.** Sebepleri:
- Her kare için GPU→CPU bellek transferi gerekiyor (biz kareyi CPU'da
  işleyeceğiz — hareket filtresi OpenCV'de).
- NVDEC `nv12` formatında verir; `bgr24`'e dönüşüm yine CPU'da yapılıyor.
- 720p küçük bir çözünürlük; çekirdek başlatma gecikmesi baskın hâle geliyor.
- Laptop GPU'sunda tek NVDEC birimi var; yüksek çözünürlükte parlar,
  720p'de değil.

**2. Decode zaten darboğaz değilmiş.**

```
Gereken : 20 kamera × 25 FPS            = 500 FPS
Mevcut  : 240.6 FPS/çekirdek × 14 çekirdek ≈ 3368 FPS
Kullanım: ~2.1 çekirdek  (14 çekirdeğin %15'i)
```

**Asıl maliyet renk dönüşümüymüş:** çözme tek başına 1037 FPS, `bgr24`
dizisine çevirince 240 FPS. Yani sürenin **%77'si** H.264 çözmede değil,
YUV→BGR dönüşümünde geçiyor. Denenen alternatif (küçültmeyi swscale'e
yaptırmak, `frame.reformat(320,180)`) 0.92× ile **daha yavaş** çıktı —
maliyet hedef çözünürlükten değil kaynak çözünürlüğünden geliyor.

**Karar:** **NVDEC KULLANILMAYACAK.** CPU çözme hem daha hızlı hem daha
basit. Ek fayda: GPU tamamen YZ modellerine kalıyor, VRAM'de decode
tamponu tutulmuyor.

**Öğrenilen ders:** "GPU her zaman daha hızlıdır" bir efsanedir. Donanım
hızlandırma, veri GPU'da kalıyorsa kazandırır; her kareyi geri indireceksen
transfer maliyeti kazancı yer. Ayrıca *sezgiye dayalı optimizasyon planı*
(NVDEC'e geçmek) ölçümle çürütüldü ve **bir günlük iş iptal edildi** —
ölçmeseydik boşa harcanacaktı.

**Rapora:** Bu iki kayıt (P-07 hatalı teşhis + P-09 düzeltme) birlikte,
"ölç, varsayma" ilkesinin en somut örneği olarak sunulacak.

---

### P-08 · Kameralar tarayıcıda oynamadı — WebRTC B-frame kabul etmiyor

**Tarih:** 13.08.2026 · **Faz:** 0 · **Kaybedilen süre:** ~10 dk + 9 dk yeniden kodlama

**Belirti:** 20 kameranın tamamı MediaMTX'te `ready=True` görünüyor,
`ffprobe` ile RTSP'den kare alınabiliyor, ama tarayıcıda hiçbiri oynamıyor:
*"Error: stream not found, retrying in some seconds"* ya da sonsuz dönen
yükleme animasyonu. Sentetik test kameraları (`cam-test-*`) ise sorunsuz
çalışıyor.

**Araştırma:** "Sentetikler çalışıyor, dosyadan gelenler çalışmıyor" ayrımı
kritik ipucuydu — sorun MediaMTX'te değil, **videoların kendisinde** olmalıydı.
MediaMTX logları tek satırda cevabı verdi:

```
[WebRTC] [session ab21e276] closed:
    WebRTC doesn't support H264 streams with B-frames
```

**Kök sebep:** `libx264` varsayılan olarak **B-frame** (bidirectional
predicted frame — hem önceki hem sonraki kareye bakarak tahmin yapan kare)
üretir. Sıkıştırmayı iyileştirir ama **WebRTC'nin H.264 profili B-frame
desteklemez.**

Sentetik kameraların çalışmasının sebebi tesadüftü: onları üretirken
`-tune zerolatency` kullanmıştım ve bu ayar yan etki olarak B-frame'i
kapatıyor. Kamera çiftliği betiğinde ise `-tune` yoktu.

**Çözüm:** Kodlama parametrelerine `-bf 0` eklendi ve 20 kamera yeniden
üretildi. Ayrıca ffmpeg'in MediaMTX'e yayınlarken kullandığı komuta
`-rtsp_transport tcp` eklendi — loglardaki *"27 RTP packets lost"* ve
*"invalid FU-A packet"* uyarıları, 20 eşzamanlı UDP oturumundaki paket
kaybından geliyordu.

**Öğrenilen ders:** Bir kodlayıcının varsayılanları hedef protokolün
kısıtlarını bilmez. WebRTC için H.264 üretirken en az üç kısıt var:
B-frame yok, kısa GOP, `yuv420p`. Ayrıca "bir grup çalışıyor, diğeri
çalışmıyor" durumu en değerli hata ayıklama ipucudur — aradaki **tek**
farkı bulmak yeterlidir.

---

### P-07 · ⛔ HATALI TEŞHİS — "decode darboğazı" diye bir şey yokmuş

> **DÜZELTME (13.08.2026, Gün 3):** Aşağıdaki teşhis **yanlıştı.** Doğru
> ölçüm P-09'da. Kaydı silmiyorum çünkü *nasıl yanlış teşhis konduğu*
> raporun en öğretici parçalarından biri.
>
> **Hata neydi:** RTSP akışından ölçüm aldım. MediaMTX akışı **gerçek
> zamanlı 25 FPS** hızında yayınlıyor — daha hızlı okumak fiziksel olarak
> mümkün değil. Ben bu **hız sınırını (rate limit)** decode kapasitesinin
> tavanı **(throughput limit)** sandım.
>
> Doğru ölçüm yerel dosyadan yapılmalıydı: orada decode 1037 FPS çıkıyor,
> 23 FPS değil. Gerçek ihtiyaç 20 kamera için ~2.1 çekirdek; elimizde 14 var.
> **Darboğaz yok.**
>
> **Ders:** Bir bileşenin kapasitesini ölçerken, ölçüm düzeneğinin kendisi
> sınırlayıcı olmamalı. Gerçek zamanlı bir kaynaktan "en fazla ne kadar
> hızlı işleyebiliriz" sorusu cevaplanamaz.

**Tarih:** 13.08.2026 · **Faz:** 0 · **Durum:** ❌ Geçersiz — bkz. P-09

**Belirti:** Kademe 0 ölçümünde beklenmedik bir sayı görüldü:
`decode_amplification = 6.94`. Yani 100 kare *işlemek* için 694 kare
*çözülüyor*. Ayrıca hedef 4 FPS iken gerçekleşen 3.2 FPS'te kalıyordu.

**Kök sebep:** H.264 kareler arası kodlamalıdır — 7. kareyi çözmek için
önceki 6 kareyi de çözmek gerekir. "25 FPS'ten 4 FPS'e örnekleme yapıyoruz"
demek, **decode maliyetinden kaçtığımız anlamına gelmez.** Örnekleme yalnızca
pahalı YZ modellerine giden kare sayısını azaltır.

**Ölçülen gerçek:** Tek 720p akış, tek iş parçacığında **~23 FPS** hızla
çözülüyor. Akışın kendisi 25 FPS. Yani **bir kamera ≈ bir CPU çekirdeği**,
üstelik %8 geride kalarak.

**Etkisi:** Donanım i7-12700H (14 fiziksel / 20 mantıksal çekirdek).
CPU çözme ile 20 kamera **matematiksel olarak sığmıyor** — çözme için
20×25 = 500 FPS gerekiyor, elimizde ~14×23 ≈ 320 FPS var. Üstelik
YZ modelleri, analitik ve API için hiç çekirdek kalmıyor.

**Planlanan çözüm (Gün 3):**
1. **NVDEC** — GPU donanımsal çözücü. RTX 3070'in NVDEC birimi CPU'dan
   bağımsız çalışır ve oturum sınırı yoktur. PyAV üzerinden
   `hwaccel="cuda"` ile denenecek.
2. Başarısız olursa: kaynak videoların GOP'unu kısaltıp anahtar-kare
   atlama (`skip_frame`), ya da kamera başına çözünürlüğü düşürme.
3. Her iki durumda da **gerçek sayı ölçülüp raporlanacak** — hedef
   tutmazsa "X kamerada Y FPS" olarak dürüstçe yazılacak (PLAN.md §16 / R2).

**Öğrenilen ders:** Planlama aşamasında GPU bütçesini titizlikle hesaplamış
(PLAN.md §2.3) ama **decode bütçesini varsaymıştım.** Sistemin darboğazı
tahmin ettiğim yerde değildi. Bu tam olarak "önce ölç" ilkesinin neden
var olduğunun kanıtı — ve raporun en güçlü bölümlerinden biri olacak.

---

### P-06 · Hareket filtresi tahminimin 16 katı yavaş çıktı — suçlu MOG2 değildi

**Tarih:** 13.08.2026 · **Faz:** 0 · **Kaybedilen süre:** ~15 dk (kazanç: 3.2× hız)

**Belirti:** PLAN.md §5'te Kademe 0 maliyeti **~0.3 ms/kare** olarak
tahmin edilmişti. İlk ölçümde **4.797 ms** çıktı — 16 kat fazla.
20 kamera × 4 FPS'te bu, saniyede 384 ms CPU demek.

**Araştırma:** "MOG2 yavaşmış" diye kabul etmek yerine adımları tek tek
ölçtüm (720p girdi, i7-12700H, tek iş parçacığı):

| Adım | Süre |
|---|---|
| `resize` **INTER_AREA** → 320×180 | **0.967 ms** ← suçlu |
| `resize` INTER_LINEAR → 320×180 | 0.136 ms |
| `resize` INTER_NEAREST → 320×180 | 0.047 ms |
| `MOG2.apply` (320×180) | 0.702 ms |
| `morphologyEx` OPEN | 0.022 ms |
| `countNonZero` | 0.002 ms |

**Kök sebep:** Suçlu arka plan çıkarma modeli değil, **küçültme
enterpolasyonu**ydu. `INTER_AREA` her çıktı pikseli için kaynak bölgenin
alan ortalamasını alır — görüntü kalitesi için mükemmel, ama biz
hareketin *varlığını* arıyoruz, güzel bir küçük resim değil.

**Çözüm:** `INTER_LINEAR`. `INTER_NEAREST` daha da hızlı ama örtüşme
(aliasing) yapıp sensör gürültüsünü hareket sanabilir; `INTER_LINEAR`
hem 7× hızlı hem yumuşatmayı koruyor.

**Sonuç:** 4.797 ms → **1.495 ms** (3.2× hızlanma), eleme doğruluğu aynı
(`cam-test-static` %95.7 → %96.0).

**Öğrenilen ders:** "Yavaş" bir fonksiyonu optimize etmeden önce **hangi
satırın** yavaş olduğunu ölç. Sezgim MOG2'yi işaret ediyordu; ölçüm
`cv2.resize`'ı gösterdi. Ayrıca bir kütüphane varsayılanı ("en kaliteli
enterpolasyon") her zaman senin kullanım senaryon için doğru varsayılan
değildir.

---

### P-05 · `.gitignore` satır içi yorum desteklemiyor — 5565 JPEG commit'e girdi

**Tarih:** 13.08.2026 · **Faz:** 0 · **Kaybedilen süre:** ~10 dk

**Belirti:** Veri setleri `data/_sources/` altına taşındıktan sonra
`git add -A` çalıştırıldığında 5565 PETS2009 JPEG dosyası stage'e girdi.
`.gitignore`'a kural eklenmişti ama işe yaramıyordu.

**Araştırma:** İlk hipotez "kural yanlış yazılmış" idi. `git check-ignore -v`
ile bakınca kuralın **hiçbir dosyayla eşleşmediği** görüldü.

**Kök sebep:** Kural şöyle yazılmıştı:

```gitignore
data/_sources/*      # ham indirilen veri setleri
```

**`.gitignore` satır içi yorum desteklemez.** `#` yalnızca satırın
**başındayken** yorum başlatır. Ortadaki `#` desenin bir parçası sayılır;
git `data/_sources/*      # ham indirilen veri setleri` diye tuhaf bir
desen arar ve hiçbir şey eşleşmez. Sessizce başarısız olur — hata vermez.

**Çözüm:** Yorumlar kendi satırlarına alındı:

```gitignore
# ham indirilen veri setleri (VIRAT, Oxford, PETS…)
data/_sources/*
```

**Öğrenilen ders:** Yeni bir `.gitignore` kuralı yazınca **her zaman
`git check-ignore -v <dosya>` ile doğrula.** Sessizce çalışmayan kural,
hata veren kuraldan çok daha tehlikelidir — bu vakada 800 MB'lık veri
seti fark edilmeden depoya gidebilirdi. Commit öncesi
`git diff --cached --name-only` kontrolü de rutin hâline getirildi.

---

### P-04 · Ruff, Türkçe harfleri "belirsiz unicode" sayıp 108 yanlış pozitif üretti

**Tarih:** 13.08.2026 · **Faz:** 0 · **Kaybedilen süre:** ~5 dk

**Belirti:** `ruff check src` 110 hata döndürdü. Kod yeni yazılmıştı ve
çalışıyordu.

**Kök sebep:** RUF001/RUF002/RUF003 kuralları, görsel olarak ASCII'ye
benzeyen unicode karakterleri "homoglif saldırısı" riski olarak işaretler.
Türkçe `ı` (noktasız i), `ş`, `ğ`, `İ` harfleri bu kapsama giriyor.
108 hatanın tamamı Türkçe docstring ve yorumlardan kaynaklanıyordu.

**Çözüm:** Bu üç kural `pyproject.toml`'da gerekçesiyle birlikte kapatıldı.
Kalan 2 gerçek hata (`RUF100` kullanılmayan `noqa`, import sıralaması)
`--fix` ile düzeltildi.

**Öğrenilen ders:** Lint kuralları dil-agnostik değildir. Yanlış pozitifleri
tek tek `noqa` ile susturmak yerine kuralın **neden** yanlış olduğunu anlayıp
merkezi olarak, gerekçe yazarak kapatmak doğru yaklaşım. Aksi halde 108 tane
`# noqa` satırı kodu okunamaz hale getirirdi.

---

### P-03 · Sağlık kontrolü, sağlıklı servisleri "ölü" raporladı (Windows IPv6 tuzağı)

**Tarih:** 13.08.2026 · **Faz:** 0 · **Kaybedilen süre:** ~20 dk

**Belirti:** `/api/v1/system/health` uç noktası 503 döndürüyor; Valkey ve
PostgreSQL "erişilemiyor" görünüyordu. Ancak `docker compose ps` her ikisini
de `healthy` gösteriyor, `valkey-cli PING` ve `psql` elle çalışıyordu.

**Araştırma:** Aynı bağlantıları uygulama dışında bir Python betiğiyle
denedim — **çalıştılar**, ama Valkey PING'i **2491 ms** sürdü. Sağlık
kontrolündeki zaman aşımı 3 sn'ydi; yani kontrol kıl payı düşüyordu.
Asıl soru "neden bağlanamıyor" değil, "neden 2.5 saniye sürüyor" oldu.

**Kök sebep:** İki karar birleşince ortaya çıkan bir etkileşim:
1. `docker-compose.yml` portları güvenlik gereği **yalnızca IPv4**'e
   bağlıyor (`127.0.0.1:6379:6379`).
2. `.env` dosyasında adres `localhost` yazıyordu.

Windows'ta `localhost` **önce `::1` (IPv6)** olarak çözülür. Servis IPv6
dinlemediği için bağlantı zaman aşımına uğrar, ardından IPv4'e düşülür.
Bu geri düşüş ~2 saniye sürüyor — her istekte.

**Çözüm:** İki yönlü:
- `.env` ve `config.py` içindeki tüm **servis adresleri** `localhost` yerine
  `127.0.0.1` yapıldı. (`ALLOWED_ORIGINS` bilerek `localhost` kaldı —
  tarayıcı Origin başlığını öyle gönderiyor.)
- Sağlık kontrolü zaman aşımı 3 sn → 5 sn (soğuk başlangıç payı).

**Sonuç:** Valkey gecikmesi **2491 ms → 525 ms**. Tüm servisler sağlıklı.

**Öğrenilen ders:** "Bağlanamıyor" ile "yavaş bağlanıyor" farklı problemlerdir
ve zaman aşımı ikisini aynı hataya dönüştürür. Zaman aşımını büyütmek
semptomu gizlerdi; asıl kazanç kök sebebi bulmaktı. Ayrıca bu, güvenlik
kararının (portları IPv4-localhost'a kısıtlamak) beklenmedik bir performans
yan etkisi yaratmasının güzel bir örneği — **rapora bu şekilde yazılacak.**

---

### P-02 · MediaMTX yönetim API'si 401 döndürüyor

**Tarih:** 13.08.2026 · **Faz:** 0 · **Kaybedilen süre:** ~10 dk

**Belirti:** Konteynerler sağlıklı (`healthy`) görünmesine rağmen host'tan
`http://127.0.0.1:9997/v3/config/paths/list` çağrısı
`{"status":"error","error":"authentication error"}` döndürüyordu.

**Araştırma:** İlk hipotez "port yanlış" idi — değildi. İkinci hipotez
"konteyner içinden çalışıyor, dışarıdan çalışmıyor" — doğru çıktı.
Docker sağlık kontrolü konteyner *içinden* `localhost` ile bağlandığı için
geçiyordu; host'tan gelen istek ise Docker köprü ağının IP'sinden (172.x)
geliyordu.

**Kök sebep:** MediaMTX v1.x, varsayılan iç kullanıcı tanımında yalnızca
`publish` / `read` / `playback` izinlerini veriyor. `api` ve `metrics`
eylemleri **varsayılan olarak kapalı** — bu aslında iyi bir güvenlik
varsayılanı, hata değil.

**Çözüm:** `infra/mediamtx/mediamtx.yml` içine `authInternalUsers` bloğu
eklendi. Yayın/izleme iç ağdan serbest bırakıldı; `api` ve `metrics`
izinleri **yalnızca localhost ve özel ağ aralıklarıyla** sınırlandı
(`127.0.0.1/32`, `::1/128`, `10/8`, `172.16/12`, `192.168/16`).

**Öğrenilen ders:** "Konteyner healthy" ile "host'tan erişilebilir" aynı şey
değil. Ayrıca güvenli varsayılanlar ilk denemede hata gibi görünür — konfigürasyonu
gevşetmeden önce *neden* kapalı olduğunu anlamak gerekir. Burada izinleri
tamamen açmak yerine IP kısıtlı açtık (PLAN.md §11 ilkesi).

---

### P-01 · Aynı makinede çalışan başka bir projeyle port çakışması

**Tarih:** 13.08.2026 · **Faz:** 0 · **Kaybedilen süre:** ~15 dk

**Belirti:** `docker compose up` çalıştırılmadan önce yapılan kontrolde,
makinede halihazırda çalışan başka bir Docker Compose projesi (`deploy`)
olduğu görüldü. Konteynerleri: `teknofest_postgres` (5432),
`teknofest_api` (8000), `teknofest_dashboard` (5000).

**Araştırma:** `docker ps -a`, `docker compose ls -a` ve `docker volume ls`
ile mevcut durum çıkarıldı. İki gerçek çakışma tespit edildi: PostgreSQL
(5432) ve planlanan FastAPI portu (8000).

**Kök sebep:** Standart varsayılan portlar kullanılmıştı. Aynı host üzerinde
iki proje aynı portu dinleyemez.

**Çözüm:** SENTINEL'in portları kaydırıldı — **PostgreSQL 5433**, **API 8001**.
Diğer servisler (Valkey 6379, MediaMTX 8554/8889, Prometheus 9090,
Grafana 3000) boştu, standart bırakıldı. Ayrıca `prometheus.yml` içindeki
`sentinel-api` hedefi de 8001'e çekildi — aksi halde Prometheus yanlışlıkla
**diğer projenin** API'sini kazıyacaktı (sessiz ve fark edilmesi zor bir hata).

**Öğrenilen ders:** Altyapıyı ayağa kaldırmadan **önce** `docker ps` ile
mevcut durumu incele. Ayrıca Docker'ın port çakışmasında yeni konteyneri
başlatmayı reddettiğini, çalışan konteynere zarar vermediğini bilmek
gereksiz endişeyi önler. İzolasyon garantileri: proje adı (`name: sentinel`),
açık konteyner adları (`sentinel-*`), ayrı ağ (`sentinel-net`) ve
ad-alanlı volume'lar (`sentinel_*`).

---
