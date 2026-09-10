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

### P-59 · ⭐⭐⭐ Duygu analizi ÜRETİMDE HİÇ ÇALIŞMIYORDU + eski ölçümler yeniden yapıldı

**Tarih:** 09.09.2026 · **Faz:** 3 · **Kaybedilen süre:** ~2 saat

**Neden bakıldı:** Kullanıcının uyarısı:

> *"Sen en son CPU ölçüm metriğini yanlış yazmışsın ve hep %0.0
> geliyor demişsin. Yani demem o ki bu önceki ölçümlerde yanlış
> olabilir... özellikle ilk 10-15 güne kadar olan günlerdeki ölçüm ve
> bulgulardan çok emin değilim."*

Haklıydı. P-58'de bulunan hata (**duvar saati ≠ CPU zamanı**) tek bir
ölçümün değil, bir **ölçüm sınıfının** hatasıydı ve o sınıftaki hiçbir
eski sayı doğrulanmamıştı.

---

#### 1. 🔴 ÖNCE: duygu analizi üretimde çalışmıyormuş

Ölçüm sırasında ifade sınıflandırıcısı patladı:

```
AttributeError: module 'onnxruntime' has no attribute
                'set_default_logger_severity'
```

Üretim loglarına bakıldı — **aynı hata orada da vardı:**

```
[error] ifade_kademesi_kurulamadi
        error="AttributeError: module 'onnxruntime' has no attribute ..."
```

⭐⭐⭐ **Şartnamedeki üç YZ görevinden biri — "duygu analizi" —
üretimde HİÇ kurulamıyordu.** KADEME 2b sessizce devre dışı kalıyor
ve boru hattı hatasız çalışmaya devam ediyordu.

**Kök sebep:** `site-packages/onnxruntime/__init__.py` **YOKTU.** Tüm
DLL'ler, `.pyd`'ler ve alt paketler yerindeydi ama paket girişi
eksikti; Python `onnxruntime`u **boş bir namespace paketi** olarak
çözüyordu (`__file__` = None, 0 özellik). `emotiefflib` 1.1.1 o modülde
`set_default_logger_severity` arayınca patlıyordu.

Muhtemel sebep: daha önceki disk temizliğinde (P-?? · C: diski dolmuştu)
yarım kalan bir işlem.

**Çözüm:** `uv pip install --force-reinstall --no-deps onnxruntime-gpu==1.28.0`

Doğrulandı:
```
onnxruntime 1.28.0 · set_default_logger_severity: True
sağlayıcılar: TensorRT · CUDA · CPU
ifade sınıflandırıcı → [('Fear', 0.343)]  ✅
```

⚠ **Bu, CLAUDE.md'deki bir iddiayı da düzeltiyor.** Orada
*"03.09 · İfade sinyali füzyona BAĞLANDI — 'duygu analizi' ilk kez
karara katılıyor (P-43)"* yazıyor. Bağlantı doğru kurulmuştu ama
sınıflandırıcının kendisi (muhtemelen sonradan) kırılmıştı. **P-43'ten
sonra hiçbir kriter yeniden ölçülmediği için fark edilmedi** — bu da
denetimde (§5.3) zaten işaretlenmiş bir eksiklikti.

> ⭐ "Bağladık" demek "çalışıyor" demek değil. P-43/P-44/P-45'in
> dersi bir kez daha, bu sefer **kütüphane sürümü** kılığında.

---

#### 2. Eski ölçümler yeniden yapıldı — duvar saati VE CPU zamanıyla

`scripts/yeniden_olc.py` yazıldı. Her aşama için **iki sayı** üretiyor:

```
duvar saati (ms) — "kullanıcı ne kadar bekledi"
CPU zamanı  (ms) — "kaç çekirdek-milisaniye harcandı"
paralellik       — CPU / duvar
```

**Sonuç (cam-20, yakın çekim, 80 tekrar):**

```
aşama       duvar ms   CPU ms   paralellik   eski iddia   kayıt
on_isleme     0.466     0.938      2.01        3.87       P-18
tespit       10.609    10.547      0.99        6.30       P-33
poz          11.796    11.719      0.99         —          —
yuz_tespit    1.465     1.562      1.07        1.46       P-30  ✅
ifade         6.248    86.719     13.88        7.40       P-30  ⬅⬅
decode_cpu    1.858    28.958     15.58         —          —    ⬅⬅
```

⭐⭐⭐ **P-30'un "ifade 7.4 ms/yüz" iddiası: DUVAR SAATİ DOĞRU
(6.25 ms) AMA CPU ZAMANI 86.7 ms — 14 KAT.**

Sayı yanlış değildi; **yanlış büyüklüktü**. P-58'in dersi burada
ikinci kez ve **bağımsız bir ölçümle** doğrulandı.

⭐ `yuz_tespit` (YuNet) ise **birebir doğrulandı**: iddia 1.46 ms,
ölçülen 1.465 ms, paralellik 1.07 (tek iş parçacıklı). Yani P-30'un
yarısı sağlam, yarısı eksik.

**20 kamera × 2.9 FPS bütçesinde:**

```
aşama         CPU ms/sn   çekirdek
ifade              5030      5.03   ⬅ TEK BAŞINA 5 ÇEKİRDEK
decode_cpu         2143      2.14
poz                 680      0.68
tespit              612      0.61
yuz_tespit           91      0.09
on_isleme            54      0.05
TOPLAM                       8.61 çekirdek (20'nin %43'ü)
```

---

#### 3. Thread sınırının zarar vermediği doğrulandı

P-58'de `OMP_NUM_THREADS=1` tüm boru hattına uygulanmıştı. Zarar
verip vermediği A/B ile ölçüldü:

```
aşama       thread=1        thread=20
            duvar   CPU     duvar   CPU
on_isleme   0.340  0.344    0.356  0.375
tespit     10.421 10.312   10.201  9.531
poz        10.896 10.469   11.280 11.406
```

⭐ **Fark yok.** Tespit ve poz GPU'da koşuyor; CPU iş parçacığı
sayısı onları etkilemiyor. Sınır güvenli.

⚠ Ama **ifade ONNX Runtime kullanıyor ve o `OMP_NUM_THREADS`'i
DİNLEMİYOR** — kendi `intra_op_num_threads` ayarı var. 13.88 paralellik
bunu gösteriyor. **Açık iş:** ONNX oturumuna `intra_op_num_threads=1`
vermek 5.03 çekirdeği ciddi biçimde düşürebilir.

---

#### ⚠ Bu ölçümün kendi sınırları — dürüstçe

1. **`decode_cpu` sayısı şüpheli.** Betikte en SON ölçülüyor ve o ana
   kadar ONNX Runtime'ın iş parçacığı havuzları uyanmış oluyor. CPU
   zamanı **süreç geneli** olduğu için o havuzların beklerken dönmesi
   decode'un hanesine yazılıyor. Aynı ölçüm ONNX yüklenmeden önce
   0.94 ms CPU veriyordu, sonra 28.96. **Gerçek decode maliyeti
   ikisinin arasında ve ayrıca ölçülmeli.**

2. **Üretim ölçümü değil.** `cv2.VideoCapture` ile DOSYADAN okuma
   ölçüldü; üretimde PyAV ile RTSP okunuyor. Farklı kod yolu.

3. **Tek kare, tek kişi.** Tespit tek karede 10.6 ms çıkıyor ama
   üretimde partili koşuyor: ölçülen `inference_duration` 12.30 ms /
   5.05 kare = **2.44 ms/kare**. Yani tek kare ölçümü tespiti
   **4 kat pahalı** gösteriyor. Parti etkisi büyük ve bu betik onu
   yakalamıyor.

4. **Karşılaştırma zemini yok.** Kod, mimari ve kütüphaneler o
   günden bu yana değişti. Bu sayılar *"eski sayı yanlıştı"* demez;
   yalnızca **bugünün doğru yöntemle ölçülmüş hâli**dir.

**Öğrenilen ders:** Bir ölçüm hatası bulunduğunda sorulacak soru
*"bu sayıyı düzelttim mi"* değil, **"aynı hatayı hangi başka
ölçümlerde yaptım"**dır. P-58'i tek bir olay sanıp geçseydik, ifadenin
14 kat eksik ölçüldüğü ve duygu analizinin hiç çalışmadığı ortaya
çıkmayacaktı.


---

### P-58 · ⭐⭐⭐ Gecikme 2.2 kat artışının GERÇEK sebebi: NumPy/BLAS iş parçacığı havuzu

**Tarih:** 09.09.2026 · **Faz:** 3 · **Kaybedilen süre:** ~4 saat (iki gün)

**Belirti:** Öğrenilmiş model üretime alındıktan sonra (P-56):

```
ölçüt              model YOKKEN   model VARKEN
gecikme p50 (ms)         205            455
gecikme p95 (ms)         463           1047
analiz FPS/kamera       2.75           1.69
```

P-57'de bunu "doyum noktası" ile açıklamıştım ve kuyruk teorisi
sayıları tutmuştu (beklenen 2.33×, ölçülen 2.22×). **O açıklama
yanlıştı** — doğru bir mekanizma, yanlış bir suçlu.

---

#### Dört hipotez, üçü çürüdü

| # | hipotez | test | sonuç |
|---|---|---|---|
| 1 | Kopya süreçler | iki tam takım worker bulundu ve temizlendi | ❌ RAM %98.7→%61 ama **gecikme aynı** |
| 2 | Modelin kendi işi | üretime histogram konuldu | ❌ kare başına **0.86 ms** — masum |
| 3 | LightGBM OpenMP | `num_threads=1` | ❌ CPU 1427%→1341%, gecikme **aynı** |
| 4 | **NumPy/BLAS havuzu** | `OMP/OPENBLAS/MKL_NUM_THREADS=1` | ✅ **ÇÖZDÜ** |

**Hipotez 1 — kopya süreçler.** Sistemde gerçekten iki tam takım
worker koşuyordu: 40 RTSP akışı, iki kopya YOLO (mimari kural 3
ihlali), iki `--owner` alım worker'ı aynı paylaşımlı bellek havuzu
için yarışıyor. RAM %98.7'den %61'e düştü. **Ama gecikme 454 ms'te
kaldı** — suçlu değillerdi.

⚠ CLAUDE.md bu tuzağı açıkça yazıyordu: *"2 normal, 4 = kopya var
demektir."* Ben yine de düştüm.

**Hipotez 2 — model.** Üretime aşama bazlı histogram kondu:

```
besle    0.041 ms   ·   ozet  0.507 ms   ·   tahmin  0.307 ms
kare başına TOPLAM: 0.864 ms   →  bir çekirdeğin %2.6'sı
```

⭐ Ve bu, sentetik benchmark'ın (0.789 ms) **doğru** olduğunu
gösterdi — 1.1 kat fark. Yani benchmark suçlanamazdı.

---

#### ⭐⭐⭐ Suçlu nasıl bulundu: SÜREÇ BAŞINA CPU

Asıl ilerleme, hiç yapmadığım bir ölçümü yapmakla geldi. `measure_canli.py`
süreç başına CPU'yu **yanlış okuyordu**: `uv run` iki python.exe
üretiyor (sarmalayıcı + asıl) ve betik sarmalayıcıyı yakalıyordu —
her rol için hep `15.5 MB / %0.0` gösteriyordu. Toplam doğruydu,
**kırılım anlamsızdı** ve tam da bu yüzden iki gün boyunca 10
çekirdeğin nerede olduğunu göremedim.

RSS'e göre asıl süreci seçen bir betik yazılınca:

```
rol          CPU %    çekirdek   thread
ALIM         294.0      2.94       440
CIKARIM       91.4      0.91        26
ANALITIK     795.5      7.96        59    ⬅⬅ 8 ÇEKİRDEK
ALARM          0.0      0.00        21
```

**Analitik worker 8 çekirdek yiyordu** — kendi ölçülen işi kare
başına 0.86 ms iken.

---

#### Mekanizma: `np.array()` bir iş parçacığı havuzu uyandırıyor

Modelin tek NumPy çağrısı —

```python
x = np.array([[ozet.get(c, float("nan")) for c in self._sutunlar]])
```

— NumPy'ın BLAS arka ucunu (OpenBLAS) tetikliyor. BLAS havuzu
**çekirdek sayısı kadar** iş parçacığı açıyor (bu makinede 20) ve
işler arasında **meşgul bekliyor** (busy-wait, `OMP_WAIT_POLICY`
varsayılanı). Saniyede ~27 tahminle havuz hiç uykuya geçmiyor —
sürekli dönüyor.

**Ortam değişkenleri sınırlandığında:**

```
ANALITIK CPU     795.5%  →  38.3%    (7.96 → 0.38 çekirdek · 21 KAT)
ANALITIK thread     59   →  3
sistem CPU        %94.1  →  %33.8
```

⭐ Ve bu iş parçacıkları **hiçbir şey kazandırmıyordu**: tahmin
girdimiz **tek satır × 99 özellik**. Böyle bir işlemi 20 çekirdeğe
yaymanın faydası yok, yalnızca zararı var.

---

#### ⚠⚠ ASIL DERS: DUVAR SAATİ ≠ CPU ZAMANI

Modelin içine koyduğum histogram `predict`i **0.307 ms** ölçüyordu ve
bu sayı **doğruydu**. İş 20 iş parçacığına yayıldığı için duvar
saati gerçekten küçüktü. Ama CPU zamanı 20 katıydı ve asıl maliyet
havuzun **beklerken dönmesiydi**.

> ⭐ Bir işlemin maliyetini *"ne kadar sürdü"* diye ölçmek, paralel
> çalışan bir şey için **yanlış sorudur**. Doğru soru: *"kaç
> çekirdek-saniye harcadı"*.

Bu, projedeki ölçüm aracı hatalarının yeni bir türü: araç doğru
çalışıyordu, **yanlış büyüklüğü** ölçüyordu. Önceki hatalar
girdiyi, tasarımı, ölçütün tanımını, yer gerçeğini bozuyordu;
bu sefer **birim** yanlıştı.

---

#### Sonuç

```
                model AÇIK   model KAPALI   DÜZELTME SONRASI   K4 referansı
p50 (ms)          454.15        149.02         172.50            205
p95 (ms)         1047.40        477.11         423.48            463
analiz FPS          1.69          2.74           2.68            2.75
CPU toplam        1427.1%        368.1%         401.6%             —
```

⭐ **Model açık, gecikme K4 referansından DÜŞÜK.** Modelin gerçek
maliyeti: `401.6 − 368.1 = %33.5` = **0.34 çekirdek** (önce 10.6).

**Düzeltme `sentinel/__init__.py`'a kondu, `.env`'e değil.** Sebep:
NumPy'ın BLAS havuzu **import anında** kuruluyor ve boyutunu o anki
ortam değişkenlerinden okuyor; sonradan değiştirmek etkisiz. Paketin
`__init__.py`'ı, hiçbir alt modül `numpy` import etmeden önce
çalışıyor — ayarın konabileceği tek doğru yer orası.

⚠ Başlatma betiğine yazmak da çalışırdı ama kırılgan: worker elle
başlatılırsa (geliştirme, hata ayıklama, test) ayar kaybolur ve sorun
sessizce geri gelir.

⚠ Ayar **tüm** worker'lara uygulanıyor. Zarar verip vermediği ölçüldü:
çıkarım worker'ının iş parçacığı 26 → 7 düştü ama **CPU'su değişmedi**
(%88-90) — çünkü işi GPU'da. Alım ve alarm da etkilenmedi.

---

#### ⚠ Kapanmayan kısım — dürüstçe

Düzeltmeden sonraki iki koşu arasında değişkenlik yüksek:

```
koşu 1: p50 172.50 ms · analiz 2.68 FPS
koşu 2: p50 247.66 ms · analiz 1.41 FPS
```

İkisinde de CPU aynı (%402, sistem %46), GPU %35, çıkarım kapasitesi
410 kare/sn (28 yapıyor). **Hiçbir kaynak dolu değil.** Yani kalan
değişkenliğin sebebi ayrı ve henüz bilinmiyor. Muhtemel aday: sistem
RAM'i %90 (15.7 GB'ın 14.1'i) ve bunun getirdiği sayfalama.

Bu **ayrı bir soru** ve raporda böyle yazılacak: ana darboğaz
çözüldü, artık gecikme referansın altında, ama koşular arası
değişkenlik açıklanmadı.

**Öğrenilen ders:** Bir sürecin kaynak kullanımını ölçerken *toplam*
yetmez — **süreç başına** kırılım gerekir. İki gün boyunca "10
çekirdek nerede" diye sorup bulamamamın tek sebebi, o kırılımı
gösteren aracın sessizce yanlış süreci okumasıydı.


---

### P-57 · ⭐⭐⭐ Model eklenince gecikme 2.2 KAT arttı — sebep model değil, DOYUM NOKTASI

**Tarih:** 08.09.2026 · **Faz:** 3 · **Kaybedilen süre:** ~2 saat

**Belirti:** Öğrenilmiş model üretime alındıktan sonra (P-56) canlı
ölçüm ağır bir gerileme gösterdi:

```
ölçüt              model YOKKEN   model VARKEN     fark
gecikme p50 (ms)         205            455       +250   (2.22×)
gecikme p95 (ms)         463            723       +260   (1.56×)
analiz FPS/kamera       2.75           1.67      −1.08   (−%39)
örnekleme FPS/kam       3.64           2.81      −0.83   (−%23)
```

⚠ İkinci koşuda (sistem ısındıktan sonra) sayılar **aynı** kaldı —
yani soğuk başlangıç değil, kalıcı bir gerileme.

⭐ İlk dikkat çeken tutarsızlık: **örnekleme hızı da düştü.** Örnekleme
alım worker'ında yapılıyor ve orada model YOK. Model bir bileşeni
yavaşlattıysa, dokunmadığı bir bileşen neden yavaşladı?

---

#### 1. Şüpheli #1: modelin maliyeti — ve orada da kendi hatam çıktı

Modeli suçlamadan önce ölçtüm (`benchmark_model_maliyeti.py`).

⚠⚠ **İlk ölçüm 24.84 ms verdi ve YANLIŞTI.** Betik `besle()`yi 800 kez
çağırıyordu ve zaman damgalarını 1 µs aralıklarla ilerletiyordu — yani
`_buda()` hiçbir şey atmıyordu ve pencere 14 kareden **814 kareye**
şişiyordu. Sonraki adım özeti o şişmiş pencerede ölçüyordu.

> ⭐ **Ölçüm aracı, kendi yan etkisiyle ölçtüğü şeyi bozdu.** Bu
> projede beşinci kez aynı hata sınıfı (P-17, P-36, P-41, P-46) ve
> bu kez yine ben yaptım.

Düzeltilmiş ölçüm:

```
aşama                        ms      pay
besle() — pencereye ekle  0.0137     2%
pencere_ozeti() — ÖZET    0.4438    56%
booster.predict()         0.3313    42%
TOPLAM                    0.7888    →  kare bütçesinin %7.1'i
```

⚠ **Ve bu da eski bir iddiamı çürüttü.** Kaskad analizinde şöyle
yazmıştım:

> *"LightGBM çıkarımı kare başına 0.0004 ms; toplam 11.10 ms'nin
> %0.004'ü. Modeli kapılamak yanlış aşamayı kapılamaktır."*

Ölçülen gerçek maliyet **0.7888 ms** — o sayının **1972 katı**. Sayı
yanlış değildi, **eksikti**: yalnızca `predict()` çağrısını ölçüyordu.
Üretimde asıl iş `predict` değil, onu **beslemek** — pencereyi her
karede yeniden özetlemek.

> ⭐ Bir bileşenin maliyetini ölçerken *"hangi çağrı"* değil
> **"hangi İŞ"** sorulmalı.

**Ama %7, −%39 verim düşüşünü açıklamıyor.** Şüpheli #1 elendi.

---

#### 2. Şüpheli #2: kuyruk birikimi — ölçüldü, küçük

```
frames.ready      : 86 kayıt (sınır 200) · lag 20 · pending 8
inference.results : maxlen'de (5000) ama pending yalnızca 4
analytics.events  : 114
shm.free          : 27 slot boşta
```

⚠ `inference.results`in 5000'de olması **birikim değil** — MAXLEN ile
kırpılan bir akışta uzunluk zaten tavanda durur. Gerçek gösterge
`lag` ve `pending`, ikisi de küçük. Tüketiciler geri kalmıyor.

Şüpheli #2 de elendi.

---

#### 3. ⭐⭐⭐ Şüpheli #3: MAKİNE — ve cevap bu

```
mantıksal çekirdek : 20
SİSTEM CPU         : %98.6      ⬅ DOYMUŞ
SİSTEM RAM         : %86.0  (13.5 / 15.7 GB)

en çok CPU kullanan:
  1043.3%  python.exe   ⬅ ALIM worker'ı = 10.4 çekirdek
   303.9%  python.exe   ⬅ çıkarım
   104.4%  vmmemWSL     ⬅ Docker
    91.5%  python.exe   ⬅ analitik
```

⭐ **Alım worker'ı tek başına 20 çekirdeğin 10.4'ünü yiyor** — 20
RTSP akışını CPU'da H.264 çözmek için. Model ise bir çekirdeğin
%4'ünü alıyor.

**Ve doyum noktasında gecikme DOĞRUSAL DEĞİL.** Klasik kuyruk sonucu
(M/M/1): bekleme süresi `W ∝ 1/(1−ρ)`.

```
doluluk ρ    göreli bekleme
  %90.0         10.0×
  %93.0         14.3×
  %95.0         20.0×
  %97.0         33.3×
  %98.6         71.4×
```

K4'te ρ ≈ 0.93, şimdi ρ ≈ 0.97 varsayımıyla:

```
beklenen gecikme artışı : 2.33 kat
ÖLÇÜLEN artış           : 2.22 kat   (205 → 455 ms)
```

⭐⭐⭐ **Teori ölçümle tuttu.** Yani mekanizma şu:

> Sistem zaten doyuma yakın çalışıyordu (ρ≈0.93). Modelin eklediği
> **%7'lik iş**, doluluğu 0.97'ye taşıdı. Doyuma yakın bölgede
> `1/(1−ρ)` patlıyor: **%7 ek iş, %120 ek gecikme** üretti.

**Bu ne mimari hatası ne model hatası — bir KAPASİTE sınırı.**

---

#### Neden örnekleme hızı da düştü — tutarsızlık çözüldü

Alım worker'ı modeli çalıştırmıyor ama **aynı CPU'yu paylaşıyor.**
Makine doyunca 20 decode iş parçacığı daha az zaman dilimi alıyor ve
örnekleme 3.64 → 2.81'e düşüyor. Yani düşüş modelin *doğrudan* değil,
**paylaşılan kaynak üzerinden dolaylı** etkisi.

---

#### Sonuç ve seçenekler

Darboğaz **CPU'da video çözme** (10.4 çekirdek / 20). Seçenekler:

| seçenek | not |
|---|---|
| Kamera sayısını düşür | Şartname ≥20 diyor — feragat |
| NVDEC (GPU'da çöz) | ⚠ P-07/P-09'da denendi ve **daha yavaştı**. Ama o ölçüm 2026-08'de, farklı kod ve daha az yükle yapıldı — yeniden ölçülmeli |
| Çözünürlüğü düşür | Kişi boyu zaten 129 px; düşürmek pozu bozar |
| Modeli seyrelt | Pencere %93 örtüşüyor; her karede değil her N karede çalıştırmak ~N× ucuzlar |
| Daha güçlü makine | Kapsam dışı ama raporda yazılmalı |

⚠ **Hiçbiri henüz ölçülmedi.** Rapor, sorunun **teşhis edildiğini** ama
**çözülmediğini** dürüstçe yazacak.

**Öğrenilen ders:** Bir sistemin doyuma ne kadar yakın çalıştığı, ona
eklenen her şeyin maliyetini belirler. Doyumdan uzakta %7'lik bir ek
iş fark edilmez; doyuma yakın aynı %7 gecikmeyi ikiye katlar.
**Bir bileşenin "maliyeti" mutlak bir sayı değil, sistemin o andaki
dolulukla birlikte okunması gereken bir orandır.**

> ⭐ Ve bu, projenin merkezî tezinin bir başka yüzü: ölçtüğümüz sayı
> (%7) doğruydu, **yorumu** yanlıştı. "Küçük bir maliyet" ancak
> sistemde yer varsa küçüktür.

---

### P-56 · Öğrenilmiş model üretime alındı — ve iki sessiz hata daha çıktı

**Tarih:** 08.09.2026 · **Faz:** 3 · **Kaybedilen süre:** ~2 saat

**Belirti:** Hakem denetimi (`docs/report/denetim-hakem.md` §1.1-§1.2)
iki ölümcül bulgu çıkardı:

```
$ grep -rln "lightgbm|Booster" backend/src/
(çıktı boş)
```

Raporlanan bütün model sonuçları (K5 F1 **0.889**, birleşim 0.937)
yalnızca çevrim dışı betiklerdeydi. Ve füzyonun **en ağır sinyali**
(`A_SALDIRGANLIK = 0.40`), P-52'de ayırt etmediği ölçülen kural
kümesinden geliyordu: K7 koşusundaki 39 alarmın **sıfırı**
saldırganlıktandı.

**Çözüm:** `src/sentinel/analytics/model.py` — LightGBM canlı boru
hattında. Rol bölüşümü:

```
saldirganlik(iz) = model_kamera × pay(iz)
pay(iz)          = kural(iz) / max(kural)   [0.5, 1.0]
```

Model *"ne kadar riskli"* (ölçülmüş F1 0.889), kural *"kim riskli"*.
P-52 kuralın **büyüklüğünün** bilgisiz olduğunu ölçmüştü ama
**sıralaması** hâlâ anlamlı.

**Sonuç — iki bulgu da kapandı:**

```
model canlıda    : 18/20 kamerada skor · medyan 0.070 · azami 0.487
                   en yüksek skor cam-15'te (gerçek kavga videosu) ✓

alarm türleri    ESKİ (model yok)        YENİ (model var)
  crowd                15                     55
  unusual              12                      —
  loitering             6                     17
  fall                  6                     12
  risk                  —                     12
  aggression            0  ⬅               ⭐ 6
  running               —                      2
```

---

#### ⚠ Yol boyunca ÜÇ sessiz hata daha bulundu

**1. İki model dizini vardı.** Üretim `config.resolve_path()` ile
`<kök>/models/` okuyor; ölçüm betikleri `<kök>/backend/models/`
yazıyordu. Yani modeli entegre ettikten **sonra bile** "model yok"
deyip sessizce devre dışı kalıyordu. 16 betik düzeltildi.
⚠ Ayrıca YOLO ağırlıkları iki yerde birden duruyordu (~100 MB kopya).

**2. Ölçüm betiği yanlış worker'ı kazıyordu.** Alarm sayacını
`sentinel_events_written_total` adıyla alarm worker'ından (9130)
arıyordu; o worker yalnızca `sentinel_worker_up` yayınlıyor.
Anomaliler **analitik** worker'da (9120) sayılıyor. Betik
*"alarm yok"* diye raporluyordu — oysa 43 alarm vardı.

> ⭐ *"Sonuç yok"* ile *"yanlış yere baktım"* aynı görünür. P-40'ta
> panel kare yerine kişi sayıyordu; aynı hata sınıfı.

**3. `decode_duration` metriği işi değil BEKLEMEYİ ölçüyor.**

```python
last = time.perf_counter()
for frame in decoder.frames():
    now = time.perf_counter()
    metrics.decode_duration.labels(...).observe(now - last)
```

Çözücü `target_fps`e göre hız sınırlı olduğu için bu aralık, kareler
arası **bekleme** süresidir. Ölçülen 263.84 ms ≈ 1/3.79 FPS — yani
tam olarak alım hızının tersi. "Decode 264 ms sürüyor" diye okumak,
darboğazı yanlış yerde aramaya yol açardı ve ilk teşhisimde tam
olarak buna kapıldım.

⚠ Metrik **yeniden adlandırılmalı** (`frame_interval_seconds`) ya da
gerçek çözme süresini ölçecek şekilde düzeltilmeli. Açık iş.

---

#### ⭐ Kilit test: eğitim ⟷ üretim özellik eşitliği

`model.py · pencere_ozeti()` ile `train_aggression.py ·
_klip_ozellikleri()` **aynı** 99'luk vektörü üretmek zorunda.
Ayrışırlarsa hata **sessiz** olur: skor üretilir, boru hattı çalışır,
yalnızca sonuç yanlıştır.

`tests/unit/test_model_ozellik.py` (10 test) bunu kilitliyor ve
eğitim özetini **kasten bağımsız** yeniden yazıyor — `pencere_ozeti`yi
çağırsaydı test hiçbir şey doğrulamazdı.

**Öğrenilen ders:** Bir modeli "entegre etmek" onu import etmek değil;
**aynı girdiyi üretmek, doğru yerden yüklemek ve gerçekten çağrıldığını
ölçmektir.** Bu üç adımdan her birinde ayrı bir sessiz hata çıktı.


---

### P-55 · ⭐⭐ MOD A / MOD B — 20 kamera kısıtının doğruluk bedeli ÖLÇÜLDÜ (ve benim iddiam yanlıştı)

**Tarih:** 08.09.2026 · **Faz:** 3 · **Kaybedilen süre:** ~1 saat

**Soru kullanıcının:**

> *"Bizim analizimiz yavaş olduğu için, yani 2.5 FPS civarında olduğu
> için bilekler vb. hızlı görünüyor olabilir. Eğer 10-15 FPS civarında
> bir işlem gücü olsa daha detaylı ve derin inceleme şansı olacaktır."*

**⚠⚠ ÖNCE BENİM HATAM — ve nasıl bir hata olduğu önemli**

Kullanıcıya *"burada fizik senin sezginin tersine işliyor"* dedim ve
şu argümanı kurdum:

```
hız = (x₂ − x₁)/Δt   →   gürültü ≈ σ√2/Δt
   2.75 FPS → Δt 0.364 sn →  3.9σ
  15.0  FPS → Δt 0.067 sn → 21.2σ   (5.5 KAT daha fazla gürültü)
```

Formül doğru. Ama **dayanağım yanlıştı**: iddiayı, elimde duran tek
ölçüme yaslamıştım — 4.0 FPS (AUC 0.895) ⟷ 2.75 FPS (0.911).

O karşılaştırmanın iki kusuru vardı:

1. **Kontrollü değildi.** İki koşu farklı klip kümelerinden geliyordu.
2. **Ve zaten NULL bir karşılaştırmaydı** — kontrollü hâlinde
   4.00 ⟷ 2.75 farkı **−0.003, %95 GA [−0.056, +0.045], P(>0)=%46**.
   Yani ortada bir etki hiç yoktu.

⭐ **Bir null sonuçtan, 5 kat daha yüksek bir hız hakkında genelleme
yaptım.** Mekanizmanın varlığını (gürültü ∝ 1/Δt) mekanizmanın
BASKINLIĞI sanmak — bu, ölçmeden konuşmanın ders kitabı biçimi ve
projenin merkezî tezinin bir örneği. Üstelik bu kez hatayı yapan
ölçüm aracı değil, **ben**dim.

---

**⭐⭐ EĞRİ TAMAMLANDI — VE DÖNDÜ (08.09.2026, ikinci güncelleme)**

İlk sürüm yalnızca 2.75 / 4.00 / 8.25 FPS ölçmüştü ve *"yüksek FPS daha
iyi"* diyordu. Kullanıcı haklı olarak itiraz etti: *"neden 8.25 ile
denedin ki, tek bir videoyu 15-25 FPS ile dene dedim ya."*

Denendi. Eğri **döndü**:

```
koşul                     AUC      F1     ΔAUC vs 2.75      P(>0)
2.75 FPS (MOD A·canlı)  0.906   0.885          —              —
4.00 FPS                0.903   0.862       −0.003           %46
8.25 FPS                0.936   0.916       +0.030           %97
16.50 FPS (MOD B)       0.949   0.914       +0.043           %96   ⬅ TEPE
24.75 FPS (MOD B+)      0.918   0.865       +0.013           %70   ⬅ DÜŞÜŞ
```

⭐⭐⭐ **Bu şekil bir tesadüf değil, İKİ TERS ETKİNİN İMZASI** — ve
modül başlığında ölçümden ÖNCE tarif edilmiş olan tam da buydu:

| etki | yönü | mekanizma |
|---|---|---|
| örtüşme (aliasing) | yüksek FPS'i sever | 0.2 sn'lik bir yumruk, örnekler arasına düşüp tamamen kaçabilir |
| sonlu fark gürültüsü | düşük FPS'i sever | `v̂ = Δx/Δt` · gürültü ≈ σ√2/Δt · Δt küçüldükçe BÜYÜR |

**Monoton bir eğri, etkilerden yalnızca birinin gerçek olduğunu
gösterirdi. Tepe noktası İKİSİNİN DE gerçek olduğunu gösteriyor.**

```
Δt = 0.364 sn (2.75 FPS)  → gürültü  3.9σ · olay ıskalanıyor
Δt = 0.061 sn (16.5 FPS)  → gürültü 23.3σ · olay yakalanıyor  ⬅ denge
Δt = 0.040 sn (24.75 FPS) → gürültü 35.0σ · gürültü kazanıyor
```

⚠ **Ve bu, hem kullanıcıyı hem beni kısmen haklı çıkarıyor:**
kullanıcının *"daha fazla FPS daha derin analiz"* sezgisi 16.5'e kadar
doğru; benim *"gürültü 1/Δt ile büyür"* mekanizmam ondan sonra doğru.
Yanlış olan, **mekanizmanın var olmasından baskın olduğunu çıkarmaktı**
— ve o çıkarımı NULL bir karşılaştırmadan (4.00 ⟷ 2.75) yapmıştım.

⚠ Betiğin yorum mantığı da düzeltildi: ilk sürüm yalnızca *"en yüksek
hangisi"* diye soruyordu ve 24.75 ölçülene kadar *"yüksek FPS daha
iyi"* diyordu. **Tek yönlü bir soru, tek yönlü bir cevap üretir.**
Artık iç optimum aranıyor ve bulunamazsa *"eğri henüz dönmemiş
olabilir"* uyarısı basılıyor.

⚠ Dürüstlük: 24.75'in düşüşü (−0.031) ve 16.5'in üstünlüğü, %95 güven
aralıkları hâlâ sıfırı içerdiği için **kesin kanıtlanmış değil**
(96 kliplik doğrulama kümesi). Eğrinin ŞEKLİ tutarlı ve mekanizmayla
uyumlu; tek tek farklar sınırda.

**Ölçüm — tek değişken, aynı klipler**

Yüksek FPS'te daha çok klip özellik üretebiliyor (482/96 → 545/108),
dolayısıyla ham koşuları kıyaslamak iki farklı sınavı kıyaslamak
olurdu. Karşılaştırma **yalnızca ortak kliplerde** yapıldı
(train 479 · val 96):

```
koşul                          AUC      F1  kesinlik  duyarlılık
2.75 FPS (MOD A · canlı)     0.906   0.885     0.902       0.868
4.00 FPS                     0.903   0.862     0.839       0.887
8.25 FPS (MOD B)             0.936   0.916     0.907       0.925
```

İki bağımsız koşuda **birebir aynı** sayılar çıktı (LightGBM
deterministik). Ama determinizm anlamlılık değildir; 96 kliplik bir
kümede 0.030 fark hâlâ örnekleme gürültüsü olabilir. **Eşleştirilmiş
bootstrap** (2000 tekrar, aynı örneklemde iki AUC):

```
karşılaştırma          ΔAUC          %95 GA        P(>0)
4.00 − 2.75          -0.003   [-0.056, +0.045]     %46   ⬅ etki YOK
8.25 − 2.75          +0.030   [-0.001, +0.067]     %97   ⬅ gerçek
```

⚠ **Dürüst okuma:** bootstrap örneklemlerinin %97'si 8.25 FPS lehine,
ama %95 güven aralığı sıfırı **kıl payı** içeriyor (−0.001). Yani etki
büyük olasılıkla gerçek, fakat tek bir 96 kliplik doğrulama kümesinde
**kesin olarak kanıtlanmış değil.** Daha güçlü bir sonuç çapraz
doğrulama ya da daha büyük bir küme ister.

⭐ **Kullanıcı haklıydı, ben yanılmıştım.** Örtüşme (aliasing) kaybı,
sonlu fark gürültüsüne baskın geliyor: daha sık örnekleme kısa süreli
olayları yakalıyor ve bu, hız ölçümündeki ek gürültüden daha değerli.

---

**MOD A / MOD B — kısıtın bedeli**

Boru hattı maliyeti ölçülmüştü: **11.10 ms/kare**.

```
MOD A  20 kamera × 2.75 FPS =  55 kare/sn ×11.10 =  610 ms/sn  (%61)  ✅
       20 kamera × 8.25 FPS = 165 kare/sn ×11.10 = 1832 ms/sn (%183)  ❌
MOD B  8.25 FPS'te azami kamera: 1000/(8.25×11.10) ≈ 10.9 kamera
       (pay bırakılırsa ~6-7 kamera)
```

> ⭐⭐ **Şartnamenin "≥20 kamera" maddesi, ölçülebilir bir doğruluk
> bedeli ödetiyor: ΔAUC ≈ 0.030 (F1 ≈ 0.031).**
>
> Bu bir kusur değil, bir **takas** — ve ilk kez sayısı var. Rapor
> bunu böyle yazacak: 20 kamera hedefi mimari bir kısıt olarak
> seçildi; bedeli tek kamera başına doğrulukta ~3 puan.

**Kapsam kararı:** MOD B üretime alınmadı. Gerekçe kısıtın kendisi —
sistemin şartnamesi 20 kamera. Ama Mod B ölçüldü ve raporlanıyor:
*"aynı model, kamera başına 3× analiz hızıyla, 0.936 AUC veriyor."*

⚠ **Ortak kümeye inmenin yanlılığı:** düşük FPS'te elenen klipler
rastgele değil (kısa ya da az kişili olanlar). Ortak küme bir miktar
"kolay" tarafa kaymış olabilir; her üç koşul da aynı kümede ölçüldüğü
için karşılaştırma geçerli, ama **mutlak** sayılar hafif iyimser.

**Öğrenilen ders:** Bir mekanizmanın var olduğunu göstermek, o
mekanizmanın **baskın** olduğunu göstermez. İki etki ters yönde
çalışıyorsa (burada: gürültü büyümesi ⟷ örtüşme kaybı), hangisinin
kazandığı ancak ölçümle bilinir. Formülü doğru yazıp yanlış sonuca
varmak mümkün.

> ⭐ Ve bu kez düzeltmeyi tetikleyen şey bir ölçüm değil, **kullanıcının
> ısrarıydı**. "Yanlış mıyım" diye sorulan bir soruya "evet" demeden
> önce ölçmek gerekiyordu; ölçünce cevap "hayır, haklısın" çıktı.


---

### P-54 · ⭐⭐⭐ İki bağımsız model birleşince AUC 0.968 — "3 YZ birlikte çalışsın" fikri ÖLÇÜLDÜ ve TUTTU

**Tarih:** 08.09.2026 · **Faz:** 3 · **Kaybedilen süre:** — (kazanç)

**Soru kullanıcının, iki parçalı:**

> *"Bu LightGBM'i neden kullanıyoruz? LightGBM tablosal verilerde iyi
> değil mi? Buradaki veriler görüntü verileri değil mi, tensör hâlinde
> gelmiyor mu?"*

> *"Bu adamların 3 farklı yapay zekâ istemelerinin sebebi üçünün
> birlikte çalışmasını istemeleri; üçü birlikte çalışsa daha iyi sonuç
> vermez mi?"*

İkisinin de cevabı aynı deneyden çıktı.

---

#### 1. LightGBM neden — ve sorunun haklı olan kısmı

Boru hattı görüntüyü LightGBM'e **vermiyor**. Görüntüyü işleyen şey
zaten derin ağlar:

```
kare (H×W×3) → YOLO26-s (CNN)     → kişi kutuları
             → YOLO26-pose (CNN)  → 17 eklem
             → BoT-SORT           → kimlik + zaman serisi
             → özellik çıkarımı   → 99 SKALER
             → LightGBM           → karar
```

Görüntü→tablo dönüşümünü CNN'ler yapıyor; LightGBM tablonun üstünde
karar veriyor. İskelet tabanlı eylem tanımanın standart kurgusu.

⚠ **Ama sorunun asıl kısmı haklıydı:** literatürdeki RWF-2000
çalışmalarının çoğu bu yolu izlemiyor, **ham piksellere 3B evrişim**
uyguluyor. Biz o yolu hiç denemedik, sadece onların yayınlanmış
sayılarını yazdık — kendi ölçmediğimiz bir sayıyla kıyaslanmak bu
projede defalarca yanlış çıkan türden bir kıyas (P-17, P-41, P-51).

**Denendi.** Kinetics-400 ön eğitimli **R3D-18**, RWF train'in tamamıyla
(1600 klip) ince ayarlandı; **aynı doğrulama kümesi, aynı klipler:**

```
yöntem                                 AUC      F1   kesinlik  duyarlılık
kural tabanı (elle)                  0.629   0.712     0.612       0.867
iskelet + LightGBM (bizim)           0.927   0.889     0.957       0.830
R3D-18 ham piksel (literatür yolu)   0.937   0.911     0.864       0.962
```

⚠ **İki dürüstlük notu:**

1. R3D-18'in "en iyi devri" doğrulama AUC'sine bakılarak seçildi —
   **raporlanan kümede seçim**, ve 12 devrin maksimumunu almak tek bir
   eşik seçmekten güçlü bir yanlılık. Seçimsiz **son devir: 0.918 /
   0.874** — LightGBM'in biraz altında. Gerçek başarım ikisinin
   arasında ve betik her iki satırı da basıyor.
2. 482 kliple eğitildiğinde R3D-18 **0.916 / 0.879** veriyordu. Yani
   video yolunun avantajı veri miktarından geliyor; aynı veriyle
   iskelet yolu önde. Bu, kaynak kısıtlı bir kurulum için anlamlı bir
   bilgi.

---

#### 2. ⭐⭐⭐ ASIL BULGU: iki model ZIT hatalar yapıyor

Sıralama değil, **hata profili** önemli:

```
iskelet + LightGBM : kesinlik 0.957 · duyarlılık 0.830   ⬅ TEMKİNLİ
R3D-18             : kesinlik 0.864 · duyarlılık 0.962   ⬅ AÇGÖZLÜ
```

Biri yanlış alarm vermiyor ama kaçırıyor; diğeri neredeyse hiç
kaçırmıyor ama yanlış alarm veriyor. Ve gerçekten **farklı şeye**
bakıyorlar:

| | iskelet yolu | video yolu |
|---|---|---|
| girdi | 17 eklem koordinatı → geometri | ham piksel → doku, hareket bulanıklığı, sahne |
| körlük | poz bulunamazsa **kör** | yeni sahnede genellemesi zayıf |

**Hata bağımsızlığı ölçüldü** (96 klip, ayrı ayrı en iyi eşiklerinde):

```
yalnızca iskelet yanıldı :  10
yalnızca video yanıldı   :   9
İKİSİ birden yanıldı     :   1   ⬅ birleşimin kurtaramayacağı
toplam hata (iskelet)    :  11
toplam hata (video)      :  10

hata örtüşmesi: %10
```

21 hatanın yalnızca **1'i ortak**. Ders kitabı örneği bir tamamlayıcılık.

**Birleşim sonucu:**

```
yöntem                     AUC      F1  kesinlik  duyarlılık
iskelet (LightGBM)       0.927   0.889     0.957       0.830
video (R3D-18)           0.937   0.911     0.864       0.962
⭐ ortalama              0.968   0.937     0.897       0.981
azami (VEYA)             0.964   0.936     0.911       0.962
asgari (VE)              0.938   0.889     0.873       0.906
çarpım                   0.956   0.901     0.862       0.943
```

⭐ **Basit ortalama, iyi olan tek modelin üstüne +0.031 AUC ve
+0.026 F1 koyuyor.** Duyarlılık 0.981'e çıkarken kesinlik 0.897'de
kalıyor — yani kaçırma neredeyse bitiyor, yanlış alarm bedeli küçük.

⚠ **Sızıntı yakalandı ve düzeltildi.** İlk sürüm skorları min-max ile
ölçekliyordu ve ölçek **doğrulama kümesinin kendi min/max'ından**
geliyordu: birleşim val dağılımını görmüş oluyordu. Normalizasyon
tamamen kaldırıldı — iki çıktı da zaten olasılık ([0,1], "kavga olma
olasılığı"), doğrudan ortalanabiliyorlar. Sonuç düzeltmeden sonra
**aynı kaldı** (0.968), yani sızıntı sonucu üretmemişti; ama
düzeltilmeden raporlanamazdı.

---

#### 3. Maliyet — ve 20 kamera kısıtı

```
R3D-18 çıkarım    : 6.5 ms / 16 karelik pencere
20 kamera × 2.75 FPS = 55 pencere/sn gerekir
→ 357 ms/saniye = tek GPU'nun %36'sı
```

Mevcut boru hattı 11.10 ms/kare × 55 = **610 ms/sn (%61)**. Video
modeli eklenince toplam **~967 ms/sn (%97)** — sınırda. Yani
teorik olarak yetişiyor ama **payı yok**; termal kısıtlama (R1) ya da
kamera sayısındaki küçük bir artış bunu kırar.

⚠ Ölçüm tek klip çıkarımıyla yapıldı; üretimde partili çalışır ve
daha iyi olur. Ama YOLO ile aynı GPU'yu paylaşacağı da hesaba
katılmalı. **Üretime alma kararı Mod A/B çalışmasına bırakıldı.**

---

**Öğrenilen ders:** Bir topluluğun kazancı üyelerin *tek tek*
başarımından değil, **hatalarının bağımsızlığından** gelir. Mevcut
füzyon katmanımız beş skoru topluyordu ama beşi de aynı özelliklerden
türüyordu — P-41 tam bu yüzden "füzyon kazandırıyor" iddiasını
çürütmüştü. Gerçekten farklı bir bilgi kaynağı (ham piksel) eklenince
kazanç ilk kez ortaya çıktı.

> ⭐ Kullanıcının "üçü birlikte çalışsın" sezgisi doğruydu; eksik olan
> şey üçüncü YZ değil, **birbirinden bağımsız** bir ikinciydi.

⚠ **Kapsam dürüstlüğü:** bu birleşim "üç YZ"nin ikisini kapsıyor.
İfade/duygu yolu dâhil değil — uzaktan güvenilir değil (ölçüldü,
füzyon ağırlığı 0.10-0.15) ve RWF kliplerinde yüzler çözünmüyor.


---

### P-53 · Kademeli koşullu füzyon ölçüldü — fikir doğru, KAPI yok

**Tarih:** 08.09.2026 · **Faz:** 3 · **Kaybedilen süre:** ~1 saat

**Fikir kullanıcının:**

> *"Katmanlı bir eleme süreci olacak: önce kural tabanlılar bakacak,
> kutulara bakacak aradaki mesafe ne, temas gerçekleşti mi — o zaman
> LightGBM'e hızlıdan veririz... yanlış alarmları da engellemiş oluruz."*

**Belirti:** İlk kaskad denemesi (`evaluate_kaskad.py`) tam saldırganlık
skoruyla kapılamıştı ve batmıştı: F1 0.829 → 0.411, kavgaların **%73'ü**
elendi. O zaman "kaskad işe yaramıyor" diye kapatılmıştı.

**Araştırma:** O sonuç doğruydu ama çıkarım eksikti. P-52 kapının neden
bu kadar çok kavga elediğini gösterdi: tam skorun ağırlığının %60'ı
**ölü bileşenlerden** geliyor. Onunla kapılamak, kapıyı gürültüyle
kapatmaktı. Kaskad fikri yanlış değil, **seçilen kapı** yanlıştı.

Dört kapı yan yana ölçüldü (`evaluate_kaskad_kapi.py`). Eşik `train`de
arandı, sonuç `val`de raporlandı:

```
kapı           eşik   geçen%  kavga kaybı      F1  kesinlik  duyarlılık
tam_skor       0.00    100%          0%   0.874     0.900       0.849
yakinlik       0.00    100%          0%   0.874     0.900       0.849
etkilesim      0.00    100%          0%   0.874     0.900       0.849
durus          0.00    100%          0%   0.874     0.900       0.849
model (kapısız)   —    100%          0%   0.874     0.900       0.849
```

⭐ Arama **her kapı için eşiği 0.00 seçti** — yani "hiç kapılama"
en iyisi. Takas eğrisi neden olduğunu gösteriyor:

```
yakinlik kapısı        geçen%  kavga kaybı     F1   kesinlik  duyarlılık
  eşik 0.00              100%          0%   0.874    0.900      0.849
  eşik 0.20               76%          6%   0.863    0.898      0.830
  eşik 0.30               71%          8%   0.860    0.915      0.811
  eşik 0.40               42%         47%   0.600    0.889      0.453
  eşik 0.50                0%        100%   0.000    0.000      0.000
```

Kesinlik en fazla 0.900 → 0.915 çıkıyor (+0.015); duyarlılık aynı
noktada 0.849 → 0.811 düşüyor. Kapı sıkıldıkça F1 **tekdüze azalıyor**;
kazandığı bir çalışma noktası yok.

**Kök sebep — iki bağımsız gerekçe, ikisi de yok:**

| Gerekçe | Durum |
|---|---|
| **Hız** | ❌ Geçersiz. LightGBM çıkarımı kare başına **0.0004 ms**; boru hattının 11.10 ms'sinin **%0.004'ü**. Modeli kapılamak yanlış aşamayı kapılamak — pahalı olan tespit + poz ve ikisi de kapının ÖNÜNDE koşuyor. |
| **Doğruluk** | ❌ Ölçüldü. Hiçbir kapı, hiçbir eşikte F1'i artırmıyor. |

⭐⭐ **Ve kapının başarısızlık biçimi öğretici.** Yakınlık, kavganın
*fiziksel olarak gerekli* bir ön koşulu: iki kişi temas etmeden
kavga edemez. Buna rağmen kapı olarak çalışmıyor — çünkü ön koşulun
kendisi değil, **onun ÖLÇÜMÜ** güvenilmez. Yakınlık eşiği 0.50'de
kavgaların %100'ü eleniyor.

> ⭐ Fiziksel olarak zorunlu bir ön koşul bile, ölçümü gürültülüyse
> güvenli bir kapı değildir. Kaskadın kazancı ön koşulun
> doğruluğundan değil, **ölçümünün güvenilirliğinden** gelir.

**Karar:** Kaskad üretime **ALINMADI**. Ama fikir çöpe atılmadı:
mimaride kapının doğru yeri zaten var ve dolu — **KADEME 0 hareket
filtresi**, karelerin %70'ini pahalı aşamalardan önce eliyor. Yani
kaskad bu sistemde zaten uygulanıyor; yalnızca *pahalı* aşamanın
önünde, ucuz olanın değil.

**Öğrenilen ders:** Bir kaskadın iki gerekçesi (hız ve doğruluk)
birbirinden bağımsızdır ve **ayrı ayrı ölçülmelidir.** Hız gerekçesi
ancak kapı, maliyetin bulunduğu aşamanın önündeyse geçerlidir; kapının
ucuz bir aşamayı korumasının hiçbir anlamı yok. Doğruluk gerekçesi ise
kapının duyarlılığına bağlı ve o duyarlılık **ölçülmeden** varsayılamaz.

---

### P-52 · ⭐⭐ Kural yolu neden çöktü — elle yazılan ağırlıklar bir HALK TEORİSİ kodluyordu

**Tarih:** 08.09.2026 · **Faz:** 3 · **Kaybedilen süre:** ~2 saat

**Belirti:** Kural tabanlı tırmanma skoru iki farklı gerçek gözetim
videosunda da kavgayı normalden ayırt etmedi:

```
cam-15  (sabit CCTV, 3.0 kişi/kare) : oran 1.01
cam-15h (elde telefon, 6.5 kişi)    : oran 1.00
```

Ve skor her dönemde neredeyse aynı: normal 0.058 · kavga 0.068.

**Araştırma:** "Ayırt etmiyor" iki farklı arıza olabilir ve çözümleri
zıt: *görüyor ama ayıramıyor* (eşik/ağırlık sorunu) ya da *hiç tepki
vermiyor* (bileşenler ölü). `diagnose_kural.py` skoru beş bileşenine
ayırdı:

```
bileşen    ağırlık   normal   kavga   oran   ateşleme(kavga)
yakinlik     0.30    0.3956  0.3956   1.00        99%   ⬅ DOYMUŞ, SABİT
bilek        0.25    0.0000  0.0000    —          20%   ⬅ ÖLÜ
yaklasma     0.20    0.0000  0.0000    —          12%   ⬅ ÖLÜ
enerji       0.15    0.0000  0.0000    —          13%   ⬅ ÖLÜ
durus        0.10    0.0564  0.0900   1.60        91%   ⬅ TEK AYIRT EDEN
```

⭐ **Skorun %90'ı bilgi taşımıyor:** 0.60 ağırlık ölü, 0.30 ağırlık
sabit. Ayırt eden tek bileşen **en düşük ağırlığa** sahip.

Aynı desen RWF-2000'de de var (kavga klipleri):

```
yakinlik 92% · durus 84% · bilek 17% · enerji 10% · yaklasma 6%
```

Yani bu cam-15'e özgü bir arıza değil, **modülün genel davranışı**.

**Kök sebep 1 — ölü bölge tabanı ulaşılamayacak kadar yüksek:**

```
büyüklük              taban   normal   kavga   kavga/taban
bilek_hizi_p75        1.529    0.312   0.721      0.47
bilek_sarsintisi_p75  1.259    0.232   0.481      0.38
hareket_enerjisi      1.209    0.215   0.480      0.40
```

Kavga anındaki değer bile tabanın **yarısına varmıyor**; `_bant()`
hepsini sıfıra yuvarlıyor. Ama dikkat: **ham girdiler ayırt EDİYOR**
(kavga/normal 2.0–2.25×). Sinyal orada, ölü bölge yok ediyor.

⚠ Bu, P-48'in tam olarak tersi yönde bir düzeltme gerektiriyor.
P-48'de *"ölü bölge kural yolunda doğru, model yolunda bilgi imhası"*
denmişti. Yarısı yanlışmış: **ölü bölge, kalibrasyon dağılımı ile
uygulama dağılımı ayrıştığında kural yolunda da bilgi imha ediyor.**

**Kök sebep 2 — ve asıl olan: ağırlıklar yanlış şeye bahis yapmış.**

Kural, ağırlığının **0.40'ını uzuv hızına** (bilek 0.25 + enerji 0.15),
yalnızca **0.10'unu duruşa** veriyor. Bu bir halk teorisi: *"kavga =
hızlı yumruk."*

Gerçek gözetim görüntüsündeki şiddet çoğunlukla **boğuşma, tutma,
itme** — kollar yavaş, duruş bozuk. Ölçüm bunu doğruluyor: cam-15'te
sahnedeki azami bilek hızı kavgada **0.856**, ama kameranın kendi
p90'ı **1.438**. Yani **olay sonrası kalabalıkta bilekler kavgadakinden
daha hızlı** — el kol hareketi yapan kalabalık, yerde boğuşan iki
kişiden daha "hareketli" ölçülüyor.

⭐⭐ **LightGBM aynı şeyi bağımsız olarak söyledi.** Öğrenilen modelin
en etkili 10 özelliğinin **10'u da gövde/duruş**:

```
ham_govde_hizi_medyan            48
ham_durus_genisligi_p75          45
ham_govde_egimi_degisimi_medyan  26
ham_durus_genisligi_azami        22
ham_en_boy_orani_p75             22
ham_en_boy_orani_azami           21
ham_govde_hizi_p75               21
...
sahne_bilek_hizi_p75_medyan      20   ⬅ bilek ancak 11. sırada
```

**Kural 0.40'ı uzuv hızına, 0.10'u duruşa verdi. Model tam tersini
öğrendi.**

**Sınama — hipotez ölçüldü, varsayılmadı.** `optimize_kural.py`
ağırlıkları ızgarayla aradı; arama `train`de, rapor `val`de (aşırı
uyum koruması — K5'te bilinen yanlılığın tekrarlanmaması için):

```
ayar                       AUC      F1
mevcut (elle)            0.700   0.817
aranan (ölçülmüş)        0.752   0.768
                        +0.052  -0.049

bulunan ağırlıklar: durus 1.00 · diğerlerinin hepsi 0.00
```

⭐ Arama **dejenere bir optimuma** gitti: tüm ağırlık tek bileşende.
AUC (sıralama gücü) +0.052 arttı, F1 −0.049 düştü. Böyle bir optimum
tek bir şey söyler: **diğer bileşenler gerçekten bilgi taşımıyor.**
Yani sorun ağırlık dağılımı değil, bileşenlerin ölü olması.

**Çözüm — kısmi ve dürüstçe kısmi:**

1. **Kamera başına uyarlanabilir ölü bölge tabanı** (`aggression.py`).
   Taban artık çiftlik sabiti değil, kameranın **kendi** dağılımının
   p90'ı; çiftlik p50 ile çiftlik p90×1.5 arasına sıkıştırılmış.
   Bu, mimari kural 7'nin ("her kameranın normali ayrı öğrenilir")
   bu modülde uygulanması — kodun kendi yorumu eksikliği zaten
   itiraf ediyordu.

   ⚠ **Ve TEK BAŞINA YETMEDİ.** Ölçülen etkin taban 1.529 → **1.438**;
   kavga değeri 0.721 hâlâ tabanın yarısında. cam-15 ayrımı
   1.01 → 1.01. RWF'de regresyon yok (AUC 0.633 → 0.633, F1 0.712 →
   0.712) ama kazanç da yok.

   **Neden yetmedi:** kameranın p90'ı tüm kişilerin tüm karelerden
   gelen değerlerini içeriyor — olay sonrası kalabalık dâhil. O
   kalabalık kavgadan daha hareketli olduğu için p90'ı yukarı çekiyor.
   Doğru taban "bu kameranın NORMALİNİN p90'ı" olmalı, "bu kamerada
   görülen her şeyin p90'ı" değil — ve normali ayırmak için zaten bir
   dedektöre ihtiyaç var. Döngüsel.

2. **Ağırlıklar DEĞİŞTİRİLMEDİ.** Arama dejenere bir çözüm buldu ve
   F1'i düşürdü; "AUC arttı" diye almak, ölçütü sonuca göre seçmek
   olurdu.

**Durum:** Kural yolu hâlâ gerçek gözetim görüntüsünde ayırt etmiyor
(1.01). Bu **raporlanacak bir sonuç**, gizlenecek bir kusur değil:

> ⭐⭐ Aynı özelliklerle beslenen LightGBM aynı videoda **2.17** ayrım
> verirken, elle ağırlıklı kural kümesi **1.01** veriyor. Bu, öğrenilen
> model ⟷ elle kurallı sistem karşılaştırmasının en güçlü kanıtı —
> ve kuralın nerede yanıldığını da model söylüyor.

**Öğrenilen ders:** Elle yazılan bir kural kümesi, yazarının olay
hakkındaki **sezgisini** kodlar; sezgi yanlışsa kurallar tutarlı
biçimde yanlış olur ve hiçbir eşik ayarı bunu düzeltmez. Öğrenilen
modelin özellik önemi burada bir başarı ölçütü değil, bir **teşhis
aracı**: hangi sezginin yanlış olduğunu söylüyor.


---

### P-51 · ⭐⭐ Test videosu sistemin varsayımının DIŞINDAYDI — ve `with_reid` etkisiz bir bayrakmış

**Tarih:** 07.09.2026 · **Faz:** 3 · **Kaybedilen süre:** ~3 saat

**Belirti:** P-50'de cam-15'in (UBI-Fights `F_74`) elde tutulan bir
telefonla çekildiği görülmüştü. Kullanıcı iki soru sordu:

> *"Düzelttin mi peki o sabit kamera olayını?"*
> *"20 kamerada ReID GPU bütçesini aşıyor demişsinde bunu test ettin mi
> söylüyorsun yoksa test etmeden mi söyledin?"*

İkisinin de cevabı **hayır**dı. Birincisi yalnızca belgelenmişti,
ikincisi hiç ölçülmemişti — ve ölçülmemiş bir gerekçe kullanıcıya
ölçülmüş gibi aktarılmıştı.

---

#### 1. SABİT KAMERA — varsayım doğru, TEST VERİSİ yanlıştı

`botsort.py`'de iki ayar kapalı ve ikisinin de gerekçesi *"kameralarımız
sabit"*:

```python
gmc_method="none",   # kamera hareketi telafisi
with_reid=False,     # görünüm eşleştirme
```

Varsayım **kamera çiftliği için doğru** (20 kameranın hepsi sabit).
Yanlış olan, o varsayımın dışındaki bir videoyla test etmekti.

216 kavga videosu tarandı (`bul_sabit_kamera.py` · seyrek optik akış,
**medyan** kayma — ortalama alsaydık sahnedeki insanlar sonucu
sürüklerdi):

```
video                    kayma%   kesme   süre   olay öncesi
F_45_0_0_0_0              0.000     0     128s      25.5s   ⬅ SEÇİLEN
F_39_1_0_0_0              0.000     0     112s      40.6s
F_74_1_2_0_0 (eski cam-15) 0.197    —     160s      58.0s   ⬅ p90 %1.023
```

60 adayın **45'i tam sabit**; eski cam-15 veri setindeki en kötülerden
biriydi. Yanlış videoyu seçmişim.

⚠ **Tarama tek başına yetmedi — iki aday gözle elendi:**

| Aday | Tarama dedi | Göz gördü |
|---|---|---|
| `F_0_1_0_0_0` | sabit, 112 sn bağlam ✅ | **iki ayrı kameradan kurgulanmış**: 0-100 sn hastane koridoru, 106 sn'den sonra otopark |
| `F_202_0_0_0_0` | sabit, tek sahne ✅ | **kurgu/eğitim videosu** ("Active Self Protection" filigranı); etiketi görünen şiddetle çelişiyor |

⭐ Sahne kesmesi bizim için kamera hareketinden **daha kötü**: Katman A
her kameranın normalini ayrı öğreniyor (mimari kural 7). Ortasında
sahne değişen bir video, tek kameranın öğrenilmiş normalini geçersiz
kılar.

⚠ **Kesme dedektörünün ilk sürümü de yanlıştı.** HSV histogram
korelasyonu kullanıyordu ve F_0'ın kesmesinde **0.582** verdi — 0.5
eşiğinin üstünde, yani "kesme yok". Sebep: iki sahne de kapalı alan,
ikisi de düşük doygunluklu (bej fayans ⟷ gri beton). **Sahne değişti
ama renk değişmedi.** Gri seviye farkına geçilince aynı kesme net
göründü (43.6 ⟷ normal 15).

**Yeni cam-15: `F_45_0_0_0_0`** — gerçek CCTV, sabit (%0.000), tek
sahne (market), 22 sn temiz olay öncesi bağlam. Eski video silinmedi:
`data/videos/_arsiv/` altında ve kalabalık ölçümü için `cam-15h`
olarak duruyor (6.5 kişi/kare — yeni cam-15 yalnızca 3.0 veriyor).

**Yer gerçeği yine gözle doğrulandı:**

```
19-21s  iki kişi ayrı yürüyor — normal
22.5s   ⬅ ilk saldırgan hareket (kol uzatma)
23.0s   ayrı duruyorlar
23.5s   yakınlaşma
24.0s   ⬅ FİZİKSEL TEMAS
25.0s   veri setinin etiketi burada başlıyor
```

⭐ **Bu videonun etiketi güvenilir:** 1.5 sn sapma (F_74'te 25 sn'ydi).
Başlangıç 23.5 alındı, belirsizlik bandı [22.5, 24.0] açıkça yazıldı —
**1.5 sn'den küçük hiçbir avans iddiası bu bandın dışına çıkamaz.**

**Sonuç — sabit kamerada K8:**

```
dönem                  n    KURAL p50   MODEL p50
normal                31      0.064       0.127
tırmanma (-6 sn)      33      0.059       0.147
kavga                 86      0.067       0.416

KURAL  ❌ ayırt etmiyor (oran 1.01)
MODEL  ✅ TESPİT ediyor (oran 2.17)   ⬅ hareketli videoda 1.71'di
       ❌ ERKEN UYARI YOK (tırmanma 0.147 ⟷ normal 0.127 = 1.16)

⭐ Yanlış alarmsız eşikte tespit: olay başlangıcından +2.2 sn SONRA
   (tek eşik, sıfır yanlış alarm — hareketli videoda 1.8-5.0 sn aralığı)
```

⭐ **Sistemi kendi varsayımına uyan bir kamerada test etmek ayrımı
%27 artırdı** (1.71 → 2.17) ve tespit gecikmesini tek bir sayıya
indirdi. Ama K8 **hâlâ tutmuyor**: sistem kavgayı tespit ediyor,
önceden haber vermiyor.

⚠ İki ölçüm hatası daha bu koşuda yakalandı:

1. **Isınma kırpması yanlış yerdeydi.** Dönem tablolarından *sonra*
   uygulanıyordu: tablolar kırpılmamış seriyi, karar kırpılmış seriyi
   gösteriyordu — aynı raporun iki farklı veriye bakması.
2. **Tırmanma penceresi (20 sn) bağlamı yutuyordu.** Bu videonun olay
   öncesi bağlamı 23.5 sn; 20 sn'lik pencere "uzak normal" havuzunda
   10 örnek bırakıyor, medyanı 0.000 çıkıyor ve ayırt etme oranı
   **64 milyon** gibi anlamsız bir sayıya fırlıyordu. Pencere K8
   hedefinden türetildi (2 sn × 3 = 6 sn) ve mevcut bağlamın 1/3'üyle
   sınırlandı.

---

#### 2. `with_reid` — ölçülmemiş bir gerekçe, ve altından çıkan asıl bulgu

Koddaki gerekçe:

```python
with_reid=False,
# ReID ayrı bir sinir ağı çalıştırır. 20 kamerada GPU bütçesini
# aşar... Faz 5'te ölçülüp değerlendirilecek.
```

⭐ Son cümle gerekçenin kendisini çürütüyor: *"ölçülüp
değerlendirilecek"* = **ölçülmedi**. Ölçüm betiği yazıldı
(`benchmark_reid.py`) ve şunu verdi:

```
with_reid=False : 0.494 ms/kare
with_reid=True  : 0.519 ms/kare   → +0.025 ms (1.05×)
```

"ReID neredeyse bedava" diye raporlanabilirdi. **Ama bir sinir ağı bu
kadar ucuz olamaz.** Şüphelenip takipçinin içine bakıldı:

```python
# botsort.py · update()
raw = tracker.update(batch, img=None)   # ⬅ GÖRÜNTÜ VERİLMİYOR
```

⭐⭐ **`with_reid` bu boru hattında ETKİSİZ BİR BAYRAK.** ReID kişi
kırpıntısından gömme vektörü çıkarır; görüntü verilmezse kodlayıcı
nesnesi oluşur (`encoder=function` diye doğrulandı) ama **hiç
çağrılmaz**. Ölçüm "kapalı ReID ⟷ kapalı ReID" kıyaslamış oldu;
+0.025 ms ReID'in maliyeti değil, ölçüm gürültüsü.

⭐ **Gerçek sebep maliyet değil MİMARİ:** takipçi arayüzü piksel
almıyor — bu, mimari kural 1'in (*ham kare kuyruktan geçmez*)
doğrudan sonucu. ReID'i açmak bir bayrak değişikliği değil, kare
referansını takip katmanına taşımaktır; maliyeti **ancak ondan sonra**
ölçülebilir.

**Bunun bedeli var ve raporda yazılacak:** kimlik sürekliliği yalnızca
hareket tahminine (Kalman + IoU) dayanıyor. Kişi `track_buffer`ı
(≈10 sn) aşarak kaybolursa ya da kalabalıkta başka bir yerden
çıkarsa **yeni kimlik** alır.

Betiğe artık bir geçerlilik ön koşulu kodlandı: ölçmeden önce
"ReID gerçekten koşuyor mu" diye soruyor ve koşmuyorsa **sayı
üretmiyor, ölçümü geçersiz ilan ediyor.**

---

#### 3. Kural yoluna sahne-göreli taban — doğru ama YETMEDİ

P-49'un `max`-over-kişi bulgusu kural yoluna da taşındı, ama tanı
önce daha ince bir şey gösterdi:

```
                          cam-15 (3 kişi)   cam-15h (6.5 kişi)
sahne medyanı ayrımı          1.36 ✅            0.69 ❌
aykırılık (max−medyan)        0.81 ❌            1.39 ✅
```

⭐ **Doğru istatistik kalabalığa göre değişiyor.** 3 kişilik sahnede
"medyan" kavga edenin *kendisi* oluyor; 7 kişilik sahnede *seyirci*
oluyor. Ne `max` ne `max − medyan` her iki durumda çalışıyor.

⭐⭐ Doğru referans "herkes" değil **seyirciler**: kişinin kendisi ve
çift partneri hariç kalanların medyanı. Bu tanım her iki kalabalıkta
da aynı şeyi ölçüyor. Ölü bölge tabanı sabit sayı olmaktan çıkıp
`max(sabit_taban, seyirci_medyanı)` oldu.

**İki yönlü doğrulandı:**

```
RWF-2000 kural tabanı : AUC 0.629 → 0.633   (regresyon YOK)
cam-15  kural ayrımı  : 1.01 → 1.01         (değişmedi)
cam-15h kural ayrımı  : 0.89 → 1.00         (değişmedi)
```

⚠ **Değişiklik doğru ama kural yolunu KURTARMIYOR.** Sebep daha
derinde: kural skoru her dönemde 0.070 civarında **sabit** — ölü
bölgeler (RWF klip istatistiklerinden kalibre) bu videolarda hemen
her şeyi sıfırlıyor. Kural yolunun sorunu tek bir istatistik değil,
**bir dağılımdan kalibre edilen eşiklerin başka bir dağılıma
taşınmaması.**

⭐ Ve bu, makalenin öğrenilen model ⟷ elle kurallı sistem
karşılaştırmasının en güçlü kanıtı: aynı özelliklerle beslenen
LightGBM aynı videoda 2.17 ayrım verirken, elle ağırlıklı kural
kümesi 1.01 veriyor.

**Öğrenilen ders:** Bir varsayım, kodda gerekçe olarak yazılı olduğu
için doğrulanmış sayılamaz. Bu projede üç ayrı gerekçe ölçüldüğünde
üçü de farklı çıktı: biri **doğru ama yanlış yerde uygulanmıştı**
(sabit kamera), biri **hiç ölçülmemişti** (ReID maliyeti), biri
**yanlış sebebi gösteriyordu** (ReID'in kapalı olma nedeni). Yorum
satırı bir kanıt değil, bir **iddiadır** — ve iddialar denetlenir.

> ⭐ Kullanıcının *"test ettin mi yoksa test etmeden mi söyledin"*
> sorusu, bu kaydın tamamını açan sorudur. Bir gerekçeyi okumakla
> ölçmek arasındaki farkı sormak, denetimin en ucuz aracı.


---

### P-50 · ⭐⭐ K8'in "+20.2 sn avansı" YOK OLDU — veri setinin etiketi olayın başlangıcını vermiyordu

**Tarih:** 07.09.2026 · **Faz:** 3 · **Kaybedilen süre:** ~2 saat

**Belirti:** P-49'un sonunda K8 ✅ işaretlenmişti: *"eşik 0.90'te avans
+20.2 sn."* Kullanıcı sayıya itiraz etti — **ölçüme değil, makullüğüne**:

> *"20 saniye öncesinden kavga uyarısı normal değil gibi. Ama videoyu
> görmedim, belki doğrudur."*

Sayıyı savunmak yerine **videoya bakıldı.**

**Araştırma:** cam-15'ten (`UBI-Fights · F_74_1_2_0_0`) kareler
çıkarıldı ve gözle tarandı:

```
 20-32.0s   normal — yürüyen insanlar, bebek arabalı adam, bisikletli
 32.8s      ⬅ ilk saldırgan hamle
 33.6s      açık çatışma duruşu, kollar açılmış
 34.4s      hamle
 36.8s      ⬅ YERDE YATAN KİŞİ
 38.4s      yerdekine müdahale
 44.0s      yerde boğuşma
 52.0s      yerde boğuşma sürüyor
 75-160s    olay sonrası kalabalık (8.2 kişi/kare) — şiddet görünmüyor
```

Veri setinin etiketi ise ilk kavgayı **57.967 sn**'de başlatıyor.
Fiziksel çatışma **~32.8 sn**'de başlamış: etiket **~25 saniye GEÇ.**

⚠ Kaynak videoyla `cam-15.mp4` aynı karede birebir eşleşiyor — zaman
kayması yok, yeniden kodlama doğru. Sorun hizalamada değil, **etiketin
neyi işaretlediğinde.**

**Kök sebep:** UBI-Fights'ın etiketi **yanlış değil** — kendi tanımına
göre doğru. Veri seti üç ayrı *"şiddet penceresi"* işaretliyor, olayın
*başlangıcını* değil. Yanlış olan, o etiketi **başka bir sorunun**
cevabı sanmaktı:

| Veri setinin cevapladığı soru | K8'in sorduğu soru |
|---|---|
| "hangi karelerde şiddet var?" | "olay ne zaman **başladı**?" |

⭐ Geç bir başlangıç etiketi, erken uyarı ölçümünü **sistematik olarak
şişirir**. Aynı alarm anı (37.8 sn):

```
58.0'a göre  →  "+20.2 sn ERKEN"     ✅ başarı
32.8'e göre  →  "  5.0 sn GEÇ"       ❌ başarısızlık
```

**Aynı sayı, etikete göre başarı ya da başarısızlık okunuyor.**

**Çözüm:** Görsel doğrulamayla üretilmiş ayrı bir yer gerçeği
(`data/annotations/cam-15.gorsel.json`); veri setinin etiketi
**silinmedi**, `--etiket veriseti` ile erişilebilir durumda ve ikisinin
farkı raporlanacak bir bulgu. Ölçüme üç kısıt daha eklendi:

1. **Isınma kırpması.** İlk sürüm "+31.7 sn avans" verdi — skorun
   **1.1. saniyede** eşiği geçtiği anlamına geliyordu; özellik penceresi
   (5 sn) daha dolmamıştı. İlk 6 sn atılıyor. (Canlı sistem bu dersi
   zaten biliyordu — P-28, ilk 90 sn. Ölçüm betiği bilmiyordu.)
2. **Doğrulanmamış aralık hiçbir havuza girmiyor.** 75-160 sn olay
   sonrası kalabalık: ne normal olduğu ne olmadığı doğrulanabildi
   (veri seti 96.9-112'yi hâlâ "fight" sayıyor). 236 örnek **ölçüm
   dışı**. Etiketlenemeyen veriyi "normal" saymak, K7'de düzeltilen
   hatanın aynısı olurdu.
3. ⭐ **"Tespit" ile "ERKEN uyarı" ayrıldı.** Önceki geçerlilik
   kontrolü tırmanma + kavgayı tek havuz sayıyordu; kavgadaki güçlü
   sinyal, olay öncesi hiçbir şey olmasa bile havuzu yukarı çekiyordu.
   Artık avans iddiası ayrı bir ön koşula bağlı: **olay öncesi
   pencerenin medyanı normali aşmalı.**

**Sonuç — DÜRÜST K8:**

```
dönem                  n    KURAL p50   MODEL p50
normal (0-32.8)       36      0.066       0.297
tırmanma (-20 sn)     56      0.069       0.207   ⬅ NORMALDEN DÜŞÜK
kavga (32.8-75)      117      0.070       0.819   ⬅ güçlü
(75-160 ölçüm dışı)  236        —           —

KURAL  ❌ kavgayı normalden ayırt ETMİYOR (oran 0.89)
MODEL  ✅ TESPİT ediyor (oran 1.71 · kavga 0.819 ⟷ normal 0.297)
       ❌ ERKEN UYARI YOK (tırmanma 0.207 < normal 0.297)

⭐ Yanlış alarmsız eşiklerde (0.60-0.90) tespit:
   olay başlangıcından 1.8 – 5.0 saniye SONRA
```

> ⭐⭐ **K8 TUTMUYOR.** Sistem kavgayı güçlü biçimde tespit ediyor
> (2.8× ayrım) ama **önceden haber vermiyor** — tam tersine, olay
> öncesi 20 saniyede skoru normalin altında.

**İkinci bulgu — kamera sabit değil.** Kareler açılınca görüldü ki bu
video **elde tutulan bir telefonla** çekilmiş: görüntü kayıyor,
yakınlaşıyor, sarsılıyor. Boru hattımız sabit kamera varsayıyor ve bu
varsayım **kodda gerekçe olarak yazılı**:

```python
# botsort.py
gmc_method="none",   # "sabit kamerada bedava maliyet"
with_reid=False,     # "sabit kameralarda zaten yeterli"
```

Kamera hareketi **tüm** kutulara sahte hız ekler. Bu videodaki her hız
temelli özellik o yanlılığı taşıyor — ve normal dönemde bilek hızının
neden kavga seviyesinde çıktığının (P-49) muhtemel bir açıklaması bu.

**Öğrenilen ders:** Bir ölçümün girdisi kadar **yer gerçeğinin tanımı**
da denetlenmeli. Etiket dosyası bir *veri* değil, bir *yorumdur*:
birinin, kendi sorusuna göre çizdiği sınırdır. Başka bir soru için
kullanılacaksa, o soruya uyup uymadığı **doğrulanmalıdır** —
ve doğrulamanın en ucuz yolu videoyu açıp bakmaktı.

> ⭐ Kullanıcının itirazı bir ölçüm değildi, bir **makullük sezgisiydi**
> — ve haklı çıktı. "Sayı doğru ama anlamı şüpheli" demek, ölçüm
> denetiminin en verimli ilk adımı.


---

### P-49 · K8 üç kez yanlış karara vardı — üçünde de suçlu ölçütün TASARIMIYDI

**Tarih:** 07.09.2026 · **Faz:** 3 · **Kaybedilen süre:** ~4 saat

**Belirti:** K8 (erken uyarı avansı), cam-15 üzerinde art arda üç farklı
sonuç verdi — ve ilk ikisi yanlıştı:

| # | Betiğin verdiği karar | Neden yanlıştı |
|---|---|---|
| 1 | ✅ "+56.9 sn avans" | Görev döngüsü **%99** — dedektör sürekli açıktı. Hep "alarm" diyen bir sistem her olaydan önce de alarm der. |
| 2 | ✅ "+19.8 sn avans, görev döngüsü %1.8" | Görev döngüsü düzeltildi ama **skor kavgada normalden yüksek değildi**. Eşik geçişi öngörü değil, denk gelmiş yanlış pozitifti. |
| 3 | ❌ "ayırt etmiyor" | Bu kez ölçütün kendisi bozuktu (aşağıda). |

**Araştırma:** İkinci karardan sonra dönem bazlı bir geçerlilik kontrolü
ekledim ve karar ❌'ye döndü. Sıradaki üç şüpheli tek tek elendi:

```
tespit      : kavgada 6.5 kişi/kare, %96.7 poz başarısı   → sağlam
takip       : iz ömrü kavgada 7.5 örnek (normalde 7.0)    → kopmuyor
zamansal    : kişilerin %100'ünde bilek hızı hesaplandı   → veri var
⭐ ham özellik: kavga 1.152 · normal 1.192 · oran 0.97     → SİNYAL YOK
```

Modele giren sayının kendisi ayırt etmiyordu. Üç hipotez sınandı:

| Hipotez | Test | Sonuç |
|---|---|---|
| Takip kopuyor (örtüşme) | iz ömrü dönem kırılımı | ❌ çürüdü — kavgada ömür daha uzun |
| Çözünürlük tabanı (kişi küçük) | `diagnose_olcek.py` · RWF ⟷ cam-15 | ❌ çürüdü — cam-15'te kişiler **daha büyük** (129 px vs 105 px) |
| ⭐ Kalabalık karışması | kişi sayısı ⟷ özellik korelasyonu | ✅ **doğrulandı** |

**Kök sebep 1 — `max`-over-KİŞİ kalabalığı ölçüyor:**

```
kişi/kare    n     bilek hızı p75 medyan    o karelerin kavga oranı
 1-4        109           1.099                      4%
 5-6        162           1.049                     20%
 7-8        137           1.372                     20%
 9+          35           1.535                     23%   ⬅ kavga sabit,
                                                             hız +%40
Pearson r(kişi sayısı, bilek hızı) = +0.274
```

`max`, örneklem büyüdükçe **tanımı gereği** büyüyen bir istatistiktir.
9 kişilik bir sahnenin "en hızlı kişisi", 4 kişilik sahneninkinden
yüksek çıkar — kimse kavga etmese bile.

> ⚠⚠ **Bu P-47 ile AYNI hata, atlanmış eksende.** P-47'de
> `max`-over-ZAMAN eklem gürültüsünü ölçüyordu ve p75'e çevrildi.
> Aynı istatistik uzay ekseninde duruyordu ve kimse bakmadı.

**Çözüm 1 — sahne-göreli aykırılık.** Kavganın işareti "biri hızlı
hareket ediyor" değil, **"biri çevresindekilere göre hızlı hareket
ediyor"**:

```python
aykirilik = max(kare) - medyan(kare)   # oran değil FARK: birim korunur
```

Ölçülen (cam-15):

```
ölçüt                     kavga   normal   oran
max (mevcut)              1.152    1.192   0.97  ❌
sahne medyanı             0.345    0.501   0.69  ⬅ kavgada seyirci DONUYOR
⭐ aykırılık (max−medyan)  0.751    0.542   1.39  ✅
```

⭐ Beklenmeyen bonus: kontrast iki taraftan geliyor — kavga eden
hızlanırken **çevresi durup izliyor**. `max` bu ikinci yarıyı hiç
göremiyordu.

RWF-2000'de temiz ablasyon (**aynı çıkarım koşusu**, yalnızca sütun
kümesi farklı — `--haric-onek` bayrağı bunun için eklendi):

| | özellik | AUC | F1 | duyarlılık | kesinlik |
|---|---|---|---|---|---|
| aykırılık YOK | 55 | 0.911 | 0.874 | 0.849 | 0.900 |
| aykırılık VAR | 99 | **0.927** | **0.889** | 0.830 | **0.957** |

Kazanç kesinlikte yoğunlaşıyor (0.900 → 0.957) — kalabalık kaynaklı
yanlış pozitifin kesilmesinin beklenen imzası.

⚠ Üçüncü bir ablasyon da koşuldu: **yalnızca değişmez özellikler**
(`ham_*` düşürülmüş, 66 sütun) → AUC 0.894 · F1 0.862. Hem RWF'de hem
cam-15'te daha kötü. Yani mutlak özellikleri tamamen atmak çözüm değil;
aykırılık onların **yanına** eklenmeli.

**Kök sebep 2 — ve asıl ders: ölçütün kendisi bozuktu.**

Aykırılık özelliği eklendikten sonra bile K8 ❌ veriyordu. Sebep,
**benim geçerlilik kontrolümdü**: "kavga segmentleri" ile "geri kalan
her şeyi" kıyaslıyordu. Ama yer gerçeği segmentleri yalnızca **fiziksel
darbeleri** işaretliyor — segment 1 yalnızca **1.7 saniye**. Kavgaya
giden tartışma, yaklaşma, itişme "normal" havuzuna düşüyordu.

> ⭐ Bu ölçüt, bir **erken uyarı** dedektörünü tam da erken uyardığı
> için cezalandırır: olaydan önce yükselen skor "normal"i yükseltir ve
> oran 1'in altına iner. Ölçüt, ölçtüğü şeyi imkânsız kılıyordu.

Doğru kırılımla bakıldığında (iki farklı model, aynı desen):

```
dönem                  n    KURAL p50   MODEL p50
normal (uzak)        249      0.076       0.348
tırmanma (-20 sn)    124      0.073       0.733   ⬅ EN YÜKSEK
kavga (darbeler)      72      0.080       0.331   ⬅ EN DÜŞÜK
```

⚠ Bu bir kalabalık artefaktı değil — kişi sayısı **eşleştirilmiş**
kontrolde tırmanma her kuşakta normalin üstünde kaldı:

```
kişi/kare      normal    tırmanma     kavga
 1-4          0.329       0.848         —
 5-6          0.303       0.695       0.351
 7-8          0.447       0.512       0.291
 9+           0.448         —         0.149
```

**Sonuç (K8):**

```
skorlayıcı   olay p50   uzak normal   oran   sonuç
KURAL          0.076       0.076      0.99   ❌ ayırt etmiyor
MODEL          0.519       0.348      1.49   ✅ ayırt ediyor

MODEL · eşik 0.90 → avans +20.2 sn · görev döngüsü %2.4 · 3/3 olay yakalandı
```

**Dürüstlük sınırları — raporda böyle yazılacak:**

1. **Tek video, tek temiz başlangıç.** Avans bir vaka çalışmasıdır,
   popülasyon tahmini değil. %2.4 görev döngüsüyle 20 sn'lik bir
   pencereye tesadüfen düşme olasılığı ihmal edilebilir değil.
2. **Kural tabanı bu videoda tamamen başarısız** (0.99). RWF'de
   AUC 0.629 veren kural kümesi, budanmamış gerçek gözetim
   görüntüsünde hiçbir şey ayırt etmiyor.
3. **Ayrım kalabalıkla zayıflıyor** (2.6× → 1.14×). Ölçülebilir bir
   çalışma sınırı.
4. ⚠ **Skor darbe anında DÜŞÜYOR** (0.733 → 0.331). Model temasa
   gelişi öğrenmiş, temasın kendisini değil — RWF'nin 5 sn'lik
   kliplerinde yaklaşma payı darbelerden büyük. Erken uyarı için
   şanslı, "kavga sınıflandırma" iddiası için sınırlayıcı.
5. Saatlik alarm sayısı (118) çevrim dışı değerlendirmede histerezis
   ve soğuma **olmadan** hesaplandı; canlı sistemde ikisi de var.

**Öğrenilen ders:** Bir dedektörün "erken uyardığı", ancak olayı
normalden **ayırt ettiği** gösterildikten sonra söylenebilir; ve o
ayrımı ölçen ölçüt, olayın **tanımını** doğru çizmelidir. "Kavga"nın
yer gerçeği darbelerdir; erken uyarının hedefi ise darbelerden önceki
tırmanmadır. İkisini aynı kovaya koymak, ölçmek istediğin şeyi
ölçülemez yapar.

> ⭐⭐ Bu, projenin merkezî tezinin **altıncı** örneği ve ilk kez
> hatanın kaynağı ölçümün girdisi değil, **ölçütün tanımı**.

---

### P-48 · Ölü bölge kural yolunda doğru, model yolunda BİLGİ İMHASI

**Tarih:** 07.09.2026 · **Faz:** 3 · **Kaybedilen süre:** ~1 saat

**Belirti:** LightGBM modeli, kural tabanının bileşen skorlarıyla
eğitilince beklenenin çok altında kaldı: AUC 0.761 · F1 0.750 —
kural tabanına (0.629 / 0.712) göre kazanç neredeyse yok.

**Araştırma:** Bileşenler `_bant(deger, taban, doyum)` üzerinden
geçiyor: tabanın altındaki her şey **sıfıra** yuvarlanıyor. Bu ölü
bölge P-32'de bilinçli eklenmişti ve yanlış alarmı 610 → 0'a
indirmişti. Ama RWF dağılımına bakınca sorun görüldü:

```
normal p90        : 2.187
kavga p50 (bilek) : 0.954   ⬅ TABANIN ALTINDA
```

Kavga sinyalinin yarısından fazlası tabanın altında kalıp
sıfırlanıyordu. Model, sınırı çizilmiş bir veri görüyordu.

**Kök sebep:** Ölü bölge bir **karar** aracı; model girdisi ise bir
**gözlem** olmalı. Karar eşiğini modelin kendisi öğrenmeli — ona
önceden bantlanmış sayı vermek, öğrenmesi gereken şeyi elinden almak.

**Çözüm:** Bantlanmamış ham özellikler de toplanıp modele verildi
(`HAM_ALANLAR`, `_klip_ozellikleri`). Kural yolu ölü bölgeyi
**korudu** — orada doğru çalışıyor.

```
bantlı bileşenler       : AUC 0.761 · F1 0.750
+ ham özellikler (p75)  : AUC 0.911 · F1 0.874
```

**Öğrenilen ders:** Aynı sayı, karar yolunda ve öğrenme yolunda farklı
ön işleme ister. Bir yolda doğru olan dönüşümü diğerine taşımak,
gerekçesi unutulduğunda sessizce zarar verir.

---

### P-47 · `max` toplulaştırması hareketi değil EKLEM GÜRÜLTÜSÜNÜ ölçüyordu

**Tarih:** 07.09.2026 · **Faz:** 3 · **Kaybedilen süre:** ~1.5 saat

**Belirti:** Bilek hızı özelliği, RWF-2000'de kavgayı normalden ayırt
etmiyordu: AUC **0.558** — şans seviyesi.

**Araştırma:** Koddaki gerekçe makul görünüyordu ve aynen duruyordu:

> *"AZAMİ, ortalama değil: vuruş anlık bir olaydır ve ortalama onu
> 3 saniyeye yayıp söndürür."*

Mantık doğru, sonuç yanlıştı. `max` aynı zamanda **en gürültülü**
istatistiktir: tek bir hatalı eklem tahmini tüm pencereyi ele geçirir.
`deney_toplulastirma.py` ile 200 klipte ölçüldü:

```
toplulaştırma   AUC     kavga p50   normal p50
azami           0.558     2.577       2.077   ⬅ şans
p90             0.659     1.625       1.003
p75             0.677     0.954       0.542   ⬅ EN İYİ
medyan          0.652     0.437       0.274
```

**Kök sebep:** p99/p50 oranı **9.7** — dağılımın kuyruğu medyanın 10
katı. Saniyede 10 gövde boyu bilek hareketi **fiziksel olarak
imkânsız**; o kuyruk hareket değil, poz kestirim hatası. `max` tam
olarak o kuyruğu örneklemiş oluyordu. Ölçüm ayrıca iskelet
ölçümlerinin **%4-6'sının fiziksel olarak imkânsız** olduğunu gösterdi.

**Çözüm:** `bilek_hizi_p75` ve `bilek_sarsintisi_p75` eklendi;
skorlama bunları kullanıyor. `azami` alanları **silinmedi** —
makalede iki toplulaştırma karşılaştırılacak ve eski davranışın
yeniden üretilebilmesi gerekiyor.

**Öğrenilen ders:** Bir istatistik seçerken "neyi yakalamak
istiyorum" kadar "neyi yanlışlıkla yakalarım" da sorulmalı. `max`
sinyalin uç değerini yakalar — ama gürültünün uç değerini de. Sinyal /
gürültü oranı düşükse, ikincisi baskın gelir.

> ⚠ Bu hatanın **uzay eksenindeki ikizi** aynı gün bulundu: P-49
> (`max`-over-kişi kalabalığı ölçüyordu). Bir eksende düzeltilen
> hatanın diğer eksende aranması akla gelmedi.

---

### P-46 · Sızıntı dedektörüm yanlış alarm verdi — aynı hatanın BEŞİNCİSİ, ama bu kez yakalandı

**Tarih:** 03.09.2026 · **Faz:** 3 / Gün 18 · **Kaybedilen süre:** ~15 dk

**Belirti:** İki saatlik K4 dayanıklılık koşusu bitti ve betik şunu
yazdı:

```
K4 · 120.0 dakika · 241 örnek · 0 kesinti
  ✅ TUTUYOR

SLOT SIZINTISI · azami boş slot 46 → 41 (en düşük 22)
  ⚠ ŞÜPHELİ — azami düşmüş
```

Yani sistem iki saat çökmeden koştu ama ölçüm aracı *"paylaşımlı bellek
havuzunda sızıntı olabilir"* dedi. Bu, P-38'in tekrarı anlamına
gelirdi — koşunun asıl sınadığı şeyin başarısızlığı.

**Araştırma:** Verdikti kabul etmek yerine **ham seriye bakıldı** (ham
seri JSON'a yazılıyor; bu karar burada karşılığını verdi).

20 dakikalık pencerelerde azami boş slot:

```
2-21 dk    35
21-41 dk   46
41-61 dk   43
61-80 dk   41
80-100 dk  37
100-120 dk 41
```

⚠ **İlk pencere zaten en düşüğü.** Monoton bir düşüş yok; değerler
35-46 arasında dalgalanıyor.

Doğrusal eğim ve serinin kendi dalgalanması:

```
eğim              : −1.08 slot/saat
2 saatte toplam   : −2.16 slot   (havuz 48)
serinin std sapması:  5.9 slot   ⬅ değişimin ~3 KATI
```

Yani gözlenen "düşüş" gürültünün içinde kalıyor.

**Kök sebep:** Dedektör pencereyi ikiye bölüp **azami** değerleri
karşılaştırıyordu:

```python
ilk_yari_azami = max(slot_serisi[:orta])   # 46
son_yari_azami = max(slot_serisi[orta:])   # 41
sizinti_supheli = son_yari_azami < ilk_yari_azami   # True
```

Bu, 241 örnekli bir seriden **iki sayı** seçip onları karşılaştırmak
demek — yani örneklem büyüklüğünü 2'ye indirmek. Üstelik seçilen iki
sayı serinin **uç değerleri**, yani gürültüye en duyarlı olanları.

⭐ **Sızıntının imzası "son değer ilkinden küçük" değil, zamanla düşen
bir EĞİLİM'dir.** Tek bir uç değer, kaç örnek olursa olsun bir eğilim
göstermez.

**Çözüm:** Dedektör en küçük kareler eğimine geçirildi. Ölçüt: koşu
boyunca eğimin öngördüğü toplam düşüş, serinin standart sapmasını
aşıyor mu. Aşmıyorsa "sızıntı var" denmiyor.

Mevcut K4 dosyası yeni yöntemle **yeniden değerlendirildi** ve JSON'a
bir `DUZELTME_03_09` bloğu eklendi: eski verdikt, neden yanlış olduğu
ve yeni verdikt birlikte duruyor. ⚠ Eski sonuç **silinmedi** —
ölçümün düzeltilme geçmişi de bir bulgudur.

**Yeni verdikt: sızıntı YOK.** P-38'in iki aşamalı kurtarma düzeltmesi
iki saatlik koşuda tuttu.

**Öğrenilen ders:** Bu, projenin merkezî hatasının **beşinci** örneği —
ölçüm aracına, ölçtüğü şeye gösterilen şüpheyi göstermemek:

| # | Kayıt | Hata |
|---|---|---|
| 1 | P-17 | ölçümü sırayla koşturmak sonucu tersine çevirdi |
| 2 | P-36 | bir bozuk blok, ölçülmemiş bir şeyi ölçülmüş gösterdi |
| 3 | P-39 | koordinat uzayı karışıktı → AUC 0.483 |
| 4 | P-41 | karşılaştırma iki değişkeni birden değiştiriyordu |
| 5 | **P-46** | **eğilim testi yerine iki uç değer karşılaştırması** |

⭐ **Ama bu kez fark var ve fark rapora girmeli:** ilk dördünde hata,
sonuç kullanıldıktan *sonra* bulundu. Burada verdikt **kullanılmadan
önce** sorgulandı ve yanlış alarm yakalandı.

Bunu mümkün kılan tek şey **ham serinin JSON'a yazılmış olması.** Betik
yalnızca özeti yazsaydı elimizde "⚠ ŞÜPHELİ" cümlesinden başka bir şey
olmayacaktı ve muhtemelen saatler süren bir sızıntı avına çıkılacaktı.

> ⭐ **Özet bir yorumdur, ham seri veridir.** Yorum yanlış olabilir;
> veriden geri dönülebilir. Bu yüzden her ölçüm betiği ham seriyi de
> yazmalı — özeti yazan kişi, sonradan sorulacak soruyu bilmiyor.

⚠ İkinci ders: **yanlış alarm veren bir dedektör de bir arızadır.**
"Sızıntı yok" derken yanılmak (yanlış negatif) açıkça tehlikeli; ama
"sızıntı var" derken yanılmak da güveni aşındırıyor — ve bu proje
zaten aynı dersi ölü Prometheus hedeflerinde almıştı: *hep kırmızı
duran bir gösterge, olmayan göstergeden kötüdür.*

---

### P-45 · Klip zinciri: kesiliyor, kaydediliyor, **kimse göremiyor**

**Tarih:** 03.09.2026 · **Faz:** 3 / Gün 18 · **Kaybedilen süre:** —
(bulma: 20 dk · düzeltme: ~1 saat)

**Belirti:** Yoktu. Belirti olmaması bu kaydın konusu.

Gün 18 kapsamlı incelemesinde şu soru soruldu: *"kesilen klibe nasıl
ulaşılıyor?"* Cevap: **ulaşılmıyor.**

**Kök sebep:** Zincirin her halkası tek tek çalışıyordu:

```
alarm → klip KESİLDİ (klip.py, 32 ms remux, 12 birim testi ✅)
      → anahtar TimescaleDB'ye yazıldı (klip_anahtar sütunu ✅)
      → /api/v1/events yanıtında döndürüldü (klip alanı ✅)
      → ???
```

Son okta hiçbir şey yoktu:
- klibi getiren bir API ucu **yok**
- ön yüz `klip` alanını okumuyor bile (`store.ts` onu `TimedAlert`'e
  hiç taşımıyordu)

PLAN §1.3 kapsam maddesi *"olay öncesi/sonrası klip arşivi"* diyor.
Arşiv vardı, erişim yoktu.

⚠ **Bu, bileşen testinin göremediği bir arıza sınıfı.** `test_klip.py`
12 test ve hepsi geçiyor — çünkü hepsi klip **kesmeyi** test ediyor.
Hiçbiri "kesilen klip kullanıcıya ulaşıyor mu" diye sormuyor. Her
parçası doğru olan bir zincir, eksik bir halka yüzünden işe yaramaz
olabilir ve **parça testleri bunu asla göstermez.**

**Çözüm:**
1. `GET /api/v1/events/klip/{anahtar:path}` eklendi
   - G12: anahtar biçimi **beyaz liste** deseniyle doğrulanıyor
   - ikinci savunma: `resolve()` + `is_relative_to` (symlink'e karşı)
   - G19: her erişim denetim izine yazılıyor (klip = dışa aktarma)
   - 404 ayrım yapmıyor (biçim bozuk / dosya yok / dizin dışı → aynı)
2. `AlertPanel` içine gömülü oynatıcı (tembel yükleme)
3. `TimedAlert.klip` alanı ve `store.ts` eşlemesi
4. `test_klip_ucu.py` — 26 yol doğrulama testi

**Yan bulgu:** Desen ilk hâlinde `^...$` çapalarını kullanıyordu.
Python'da `$` **sondaki yeni satırdan önce de** eşleşir, yani
`".../115742_fall.mp4\n"` kabul ediliyordu. Tek başına sömürülebilir
değil ama doğrulayıcı "tam olarak bu biçim" derken başka bir şey
yapıyordu. `\A ... \Z` ile düzeltildi ve test eklendi.

**Öğrenilen ders:** Bir yeteneğin "yapıldı" sayılması için zincirin
**kullanıcıya ulaşan ucuna kadar** izlenmesi gerekiyor. Kapsam
maddeleri modüllerle değil, kullanıcının yapabildiği işlerle
işaretlenmeli: "klip kesiliyor" bir modül ifadesi, "operatör alarmın
videosunu izleyebiliyor" bir kapsam ifadesi.

---

### P-44 · Füzyon iz sözlüğü sınırsız büyüyordu — `buda()` yazılmış, hiç ÇAĞRILMAMIŞ

**Tarih:** 03.09.2026 · **Faz:** 3 / Gün 18 · **Kaybedilen süre:** —
(bulma: 5 dk, K4 hazırlığı sırasında)

**Belirti:** Yoktu — ve olmaması bu kaydın önemi.

**Kök sebep:** `RiskFuzyonu.buda()` 01.09'da füzyon katmanıyla birlikte
yazıldı, gerekçesi docstring'e kondu, ve **hiçbir yerden çağrılmadı.**

Analitik worker'ın 30 saniyelik bakım döngüsü şöyleydi:

```python
self._pencereler.buda(...)   # ✅
self._kurallar.buda(...)     # ✅
self._tirmanma.buda(...)     # ✅
#  füzyon → LİSTEDE YOK
self._normal.kaydet()
```

Sonuç: `_izler` sözlüğü her yeni `(kamera, iz)` çifti için kalıcı bir
kayıt tutuyordu. İz kimlikleri sürekli yenileniyor (izlerin medyan
ömrü ~4 kare), yani sözlük **sınırsız** büyüyordu.

Bu, mimari kural 5'in doğrudan ihlali: *"Her kuyruk sınırlı. Sınırsız
kuyruk = RAM patlaması."*

⚠ **İki gün fark edilmedi çünkü belirtisizdi.** Sistem çalışıyor,
alarm üretiyor, gecikme normal — yalnızca bellek büyüyor. Kısa
koşularda görünmez ve **bugüne kadar hiç uzun koşu yapılmamıştı.**

**Çözüm:** Bakım döngüsüne `self._fuzyon.buda()` (ve yeni eklenen
`self._ifade.buda()`) eklendi. `test_ifade.py` içine budama testi
yazıldı ki aynı şey bir daha atlanmasın.

**Öğrenilen ders:** İki ayrı ders çıktı ve ikisi de kayda değer.

1. **Yazılmış ama çağrılmamış bir temizleyici, olmayan temizleyiciden
   kötüdür** — çünkü kodu okuyan biri onu görür ve "temizlik var"
   sanır. `buda()` metodunun varlığı, budamanın yapıldığı izlenimi
   veriyordu.

2. ⭐ **K4 kriterinin varlık sebebi tam olarak bu sınıf arıza.**
   Bu hata, iki saatlik dayanıklılık koşusu hazırlanırken bulundu —
   koşu daha başlamadan. Yani kriter, ölçülmeden önce bile işe
   yaradı: "sistemi iki saat ayakta tutabilecek miyim" sorusu,
   kodun uzun-koşu davranışına ilk kez bakılmasını sağladı.

---

### P-43 · "Duygu analizi" ekranda vardı, KARARDA yoktu — ve kod bunun tersini iddia ediyordu

**Tarih:** 03.09.2026 · **Faz:** 3 / Gün 18 · **Kaybedilen süre:** —
(bulma: 15 dk · düzeltme: ~1 saat)

**Belirti:** `analytics/worker.py` füzyon sinyallerini kurarken:

```python
sinyaller = fusion.Sinyaller(
    saldirganlik=tirmanma_map.get(iz, 0.0),
    anomali=anomali_skor,
    kural=kural_map.get(iz, 0.0),
    ifade=0.0,            # ⬅ SABİT
    kalabalik=kalabalik,
)
```

Yanındaki açıklama şuydu (ve `fusion.py`'de de tekrarlanıyordu):

> *"KADEME 2b çalışıyor ama bu kamera çiftliğinde yüzler ~15 piksel ve
> sınıflandırma üretmiyor (2700 aday → 0). **Bağlantı yeri hazır;
> gerçek bir kurulumda beslendiğinde kod değişikliği gerekmeyecek.**"*

**Kök sebep:** İddianın ikinci yarısı **yanlıştı ve hiç sınanmamıştı.**

Bağlantı yeri hazır değildi. Analitik worker mesajdaki `expr` alanını
**hiç okumuyordu.** Yüzler 200 piksel olsa, sınıflandırma mükemmel
çalışsa bile skor füzyona ulaşmazdı — çünkü onu okuyan satır yoktu.

İfade sonucu `Track.expression` → `_serialize` → WebSocket → panel
yolunu izliyordu, yani **ekranda görünüyordu.** Ekranda görünmek,
kodun bağlı olduğu izlenimini veriyordu.

⚠ **Şartname açısından bu bir boşluktu:** "duygu analizi" verilen
görevdeki **üç yetenekten biri** ve sistemin kararına hiç
katılmıyordu. "Yüz ifadesi sınıflandırılıyor" doğru bir cümleydi;
"duygu analizi sistemin riskine katkı veriyor" değildi.

**Çözüm:** `analytics/ifade.py` yazıldı:
- etiket → risk eşlemesi (öfke 1.00 · korku 0.80 · … · nötr 0.00)
- güven **ve** kalite ile çarpım — kaliteli olmayan sınıflandırma
  füzyona giremiyor
- kalite eşiği (0.35) ayrıca ELEME yapıyor: çarpımla söndürmek
  yetmiyordu, çünkü kalite 0.15'lik bir "öfke" tam da füzyonun katkı
  eşiğine (0.15) denk geliyor ve "en az iki sinyal" kuralını
  gürültüyle doldurabiliyordu
- iz başına 5 örneklik kayan ortalama (PLAN §6.3)
- `test_ifade.py` — 14 test

**⚠ Korku da sayılıyor:** saldırganlık iki taraflı bir olay. Öfkeli
yüzün yanındaki korkmuş yüz, olayın kendisi kadar bilgi verir.
Yalnızca öfkeye bakmak tırmanmanın yarısını görmek olurdu.

**Bu kamera çiftliğinde sinyal yine de çoğunlukla 0 olacak** — ama
sebebi artık farklı ve fark raporda önemli:

| | Sebep | Türü |
|---|---|---|
| ÖNCE | kod sinyali taşımıyordu | **mühendislik eksiği** |
| ŞİMDİ | yüzler ~15 px, kalite eşiğinin altında | **veri sınırı** |

Birincisi bir hata, ikincisi bir bulgu. Bulgu raporlanır; hata
düzeltilir.

**Öğrenilen ders:** ⭐ *"Bağlantı yeri hazır"* gibi bir cümle, bir
**iddiadır** ve iddialar ölçülür. Bu cümle iki dosyada yazılıydı,
kimse "peki beslenirse gerçekten akar mı" diye sormamıştı. Kodda
yazılı bir gerekçe, doğrulandığı an bulgu; doğrulanmadığı sürece
varsayım — ve bu proje aynı dersi ADR-0006'da da almıştı
(*"bir kararın gerekçesi belgeye girdikten sonra veri gibi davranmaya
başlıyor"*).

---

### P-42 · Yapılandırma dosyaları paralel bir KURGU anlatıyordu — 16 ayar okunmuyordu, ikisi kodla çelişiyordu

**Tarih:** 03.09.2026 · **Faz:** 3 / Gün 18 · **Kaybedilen süre:** ~30 dk

**Belirti:** İki ayrı olay aynı güne denk geldi ve aynı kök sebebi
işaret ettiler.

**1 · Panel giriş istedi, `.env`'deki parola çalışmadı.**
`BOOTSTRAP_ADMIN_PASSWORD=vxqxTGF9tssBeWA9mNL9` yazıyordu; giriş
denemesi **401** döndü. Kullanıcı 30.08'de
`kullanici_ekle.py admin --uret` ile kurulmuştu — o komut **rastgele**
parola üretip ekrana basıyor ve `.env`'e yazmıyor. Yani o satır bir
kurulum kaydı değil, bir varsayımdı.

**2 · İnceleme sırasında `privacy_blur_default` arandı.** `config.py`'de
`True`, `/api/v1/system/config` ile panele **`true` diye yayınlanıyor**,
`privacy/` modülü **tamamen boş**, ön yüzde bulanıklaştırma **yok**.
API, yapmadığı bir şeyi yaptığını beyan ediyordu.

**Araştırma:** Bunun üzerine tüm ayarlar `config.py` ile karşılaştırıldı.
Sonuç: **`.env` ve `.env.example` içinde 16 ayar, kodda hiç okunmuyordu.**

| Ayar | Durum |
|---|---|
| `WEIGHT_*` (5) | `fusion.py` değerleri sabit yazıyor |
| `THRESHOLD_*` (6) | `fusion.py` sabit yazıyor **ve DEĞERLER FARKLI** |
| `ALERT_*_COOLDOWN_SECONDS` (2) | `rules.py` sabit yazıyor |
| `RETENTION_*` (3) | `schema.py` sabit yazıyor **ve DEĞER FARKLI** |
| `USE_TENSORRT` / `USE_FP16` | okunmuyor |
| `PRIVACY_BLUR_DEFAULT` | okunmuyor, üstelik yayınlanıyor |
| `MAX_WS_CONNECTIONS_PER_USER` | `config.py`'de vardı, **kullanılmıyordu** |

⚠ **İkisi doğrudan yanlış bilgi veriyordu:**

```
THRESHOLD_ALARM_IN=0.75    ← gerçek eşik 0.55  (fusion.py)
RETENTION_EVENTS_DAYS=90   ← gerçek saklama 30 (schema.py)
USE_TENSORRT=true          ← TensorRT üretimde DEĞİL (ADR-0006)
```

**Kök sebep:** `.env.example` Gün 1'de PLAN'a bakılarak yazıldı —
yani **yapılacakların listesi olarak.** Sonra kod yazıldı ve değerler
kodda sabitlendi; `.env` güncellenmedi. Zamanla dosya, sistemin
yapılandırması değil *planlanan* yapılandırması hâline geldi.

Ve `.env.example` **depoya giriyor.** Yani projeyi okuyan biri
(değerlendirici dâhil) oradaki değerleri sistemin gerçek ayarları
sanardı.

**Çözüm:**
- 16 ayar `.env` ve `.env.example`'dan kaldırıldı, yerine gerçek
  değerlerin **nerede** olduğunu söyleyen bir blok kondu
- `use_tensorrt`, `use_fp16`, `privacy_blur_default` `config.py`'den
  silindi; `privacy_blur_default` API yanıtından çıkarıldı
- `MAX_WS_CONNECTIONS_PER_USER` **canlandırıldı** — G14 artık gerçekten
  uygulanıyor (`api/ws/live.py`)
- `store_face_crops` KALDI: o ölü değil, `true` yapılırsa uygulama
  açılmıyor. Bir mekanizma, bir vaat değil
- `.env`'deki admin parolası gerçek değerle güncellendi

**Öğrenilen ders:** ⭐ **Yanlış cevap veren bir ayar, olmayan ayardan
kötüdür.** Olmayan ayar arayanı koda yönlendirir; yanlış ayar onu
durdurur ve yanlış bir sonuca ikna eder.

⚠ Bu, projede **dördüncü kez** aynı sınıf hata:

| Ne | Neden kötüydü |
|---|---|
| `npm run lint` | Kurulu değildi, patlıyordu — çalışmayan kalite kapısı yeşil sanılıyordu |
| 3 ölü Prometheus hedefi | Hep kırmızı gösterge, "kırmızıya bak" alışkanlığını bozuyordu |
| `.env` bayat admin parolası | Kurulum kaydı sanılan bir varsayım |
| 16 ölü ayar | Sistemin davranışını yanlış anlatan bir belge |

Ortak payda: **doğruluğu kimsenin kontrol etmediği bir beyan, zamanla
veri gibi davranmaya başlıyor.** Kalıcı çözüm, her beyanın ya bir
mekanizmaya ya bir teste bağlanması.

---

### P-41 · "Füzyon kendini haklı çıkardı" — desteklenmeyen bir çıkarımdı (aynı hatanın DÖRDÜNCÜSÜ)

**Tarih:** 03.09.2026 · **Faz:** 3 / Gün 18 · **Kaybedilen süre:** —
(bulma: 25 dk)

**Belirti:** K6 ölçümü (P-39) şu tabloyu üretmişti ve rapora
*"füzyon kendini haklı çıkardı"* diye yazılmak üzereydi:

```
katman_a  0.789
füzyon    0.867   ⬅ "demek ki birleştirme kazandırıyor"
```

Betiğin kendi çıktısı da bunu söylüyordu:
*"füzyon bileşenlerinden İYİ — birleştirme kazandırıyor."*

**Kök sebep:** Karşılaştırılan iki sayı **aynı işlemden geçmemişti.**

```
katman_a  = HAM, kare başına anomali skoru
füzyon    = EMA(α=0.4) ile ZAMANSAL YUMUŞATILMIŞ ağırlıklı toplam
```

Füzyona iki şey birden eklenmişti — **sinyal birleştirme** ve
**zamansal yumuşatma** — ve ölçüm hangisinin kazandırdığını
ayırmıyordu.

Eldeki sayılar ikinciyi işaret ediyordu:

1. **Diğer bileşenler şans seviyesinde.** Saldırganlık AUC 0.465
   (şansın *altı*), kural AUC 0.4996 (tam şans, çünkü Avenue'da
   kurallar neredeyse hiç ateşlemiyor — karelerin %0.07'si). Şans
   seviyesindeki iki sinyali eklemek AUC'yi 0.789'dan 0.867'ye
   çıkaramaz.

2. **Katman A karelerinin %42'si tam 0.0.** `_roc_auc` eşitlikleri
   0.5 sayıyor (doğru davranış — P-39'da bilinçli seçilmişti) ve bu
   kadar çok eşitlik AUC'ye **tavan** koyuyor. EMA geçmişten sızdırıp
   o sıfırları dolduruyor → eşitlik azalıyor → AUC **mekanik olarak**
   yükseliyor. Yani gözlenen artış, ayırt etme gücünden değil, skor
   dağılımının sürekli hâle gelmesinden geliyor olabilir.

**Çözüm:** `evaluate_k6.py`'a beşinci bir seri eklendi:
**`katman_a_ema`** — Katman A'nın tek başına, füzyonla **aynı**
EMA'dan geçmiş hâli. Kontrol grubu.

Artık doğru soru sorulabiliyor:

```
füzyon > katman_a_ema  → birleştirme gerçekten kazandırıyor
füzyon ≈ katman_a_ema  → kazandıran YUMUŞATMA; füzyon katmanı bu
                          veri setinde karşılığını vermiyor
```

Betiğin sonuç yorumu da değiştirildi: artık "füzyon ham bileşeninden
iyi mi" (yanıltıcı soru) yerine "füzyon **yumuşatılmış tek
sinyalden** iyi mi" (asıl soru) sorusunu basıyor ve JSON'a
`fuzyon_sinavi` bloğu yazıyor.

---

## ⭐ SONUÇ (05.09.2026) — HİPOTEZ DOĞRULANDI, İDDİA ÇÜRÜDÜ

Kontrol serisiyle yeniden ölçüldü (`benchmarks/k6_20260905-112405.json`):

```
SKOR               AUC   anomali p50  normal p50
katman_a (ham)    0.789        0.863       0.157
katman_a + EMA    0.860        0.864       0.319   ⬅ KONTROL GRUBU
füzyon (5+EMA)    0.867        0.217       0.057
saldırganlık      0.465        0.092       0.094
kural             0.500        0.000       0.000
```

**Kazancın dağılımı:**

```
toplam artış (0.789 → 0.867)  = +0.078
  yumuşatmadan (0.789 → 0.860) = +0.071   ⬅ %91
  birleştirmeden (0.860 → 0.867) = +0.007  ⬅ %9, gürültü içinde
```

> ⭐ **Füzyonun AUC kazancının %91'i EMA'dan geliyor.** "Birleştirme
> kazandırıyor" iddiası bu veri setinde **desteklenmiyor.**

### ⚠ Ama bu "füzyon işe yaramaz" DEMEK DEĞİL — üç ayrı nokta

**1 · Bu veri setinde füzyonun birleştirecek bir şeyi yoktu.**
Beş sinyalden dördü ölü: `kural` AUC tam **0.500** (Avenue'da hiç
ateşlemiyor — anomaliler çanta fırlatma/bisiklet, biz yalnızca insan
tespit ediyoruz), `saldırganlık` **0.465** (şansın altı), `ifade` ve
`kalabalık` sıfır. Geriye tek bilgi taşıyan sinyal kalıyor: Katman A.
**Tek sinyali "birleştirmek" tanım gereği hiçbir şey kazandıramaz.**

Yani ölçüm şunu söylüyor: *"füzyon bu veri setinde kazandırmıyor"* —
*"füzyon kazandırmaz"* değil. Fark, raporda korunacak.

**2 · Füzyonun ASIL kazancı zaten başka yerde ÖLÇÜLDÜ.**
"En az iki sinyal" kuralı yanlış alarmı **26.4 → 0.00/kamera-saat**
düşürdü (K7). Bu ayrı ve gerçek bir kazanç. Füzyonun gerekçesi
**ayırt etme gücü (AUC) değil, gürültü bastırma** imiş — ve bu
başından beri kodda yazılıydı, yalnızca yanlış kriterle savunulmuştu.

**3 · EMA'nın neden bu kadar kazandırdığı da bir bulgu.**
Katman A karelerinin **%42'si tam 0.0**. AUC hesabı eşitlikleri 0.5
sayıyor, yani bu kadar çok beraberlik AUC'ye tavan koyuyor. EMA
geçmişten sızdırıp sıfırları dolduruyor → beraberlik azalıyor → AUC
yükseliyor. Dikkat: `normal p50` da 0.157'den **0.319'a** çıkmış,
yani EMA yalnızca anomalileri değil normali de yükseltiyor. Kazanç
gerçek ama mekanizması "daha iyi ayırt etme" değil, **skorun sürekli
hâle gelmesi.**

### Alınan aksiyon

- ADR-0008'in durumu **"kabul edildi (gerekçesi düzeltildi)"** oldu:
  füzyonun dayanağı K6'dan **K7'ye** taşındı
- `evaluate_k6.py` artık `fuzyon_sinavi` bloğunu JSON'a yazıyor;
  rapor bu karşılaştırmayı yeniden koşmadan alıntılayabiliyor
- CLAUDE.md'deki *"füzyon kendini haklı çıkardı"* cümlesi kaldırıldı

**Öğrenilen ders:** ⭐ Bu, **aynı sınıf hatanın dördüncüsü:**

| # | Kayıt | Ölçüm aracındaki hata |
|---|---|---|
| 1 | P-17 | ölçümü sırayla koşturmak sonucu tersine çevirdi |
| 2 | P-36 | bir bozuk blok, ölçülmemiş bir şeyi ölçülmüş gösterdi |
| 3 | P-39 | koordinat uzayı karışıktı, AUC 0.483 çıktı |
| 4 | **P-41** | **karşılaştırma iki değişkeni birden değiştiriyordu** |

Üçü ölçümün *girdisini*, dördüncüsü ölçümün *tasarımını* bozuyordu —
ve dördüncüsü en sinsisi, çünkü sayı **makul** çıkmıştı. Yanlış bir
sayı şüphe uyandırır; **beklenen** bir sayı uyandırmaz.

⚠ Deneysel yöntemin en temel kuralı ihlal edilmişti: **iki grubu
karşılaştırırken aralarında yalnızca bir fark olmalı.** Burada iki
fark vardı.

⚠ Bu kayıt, sonucu daha ölçülmeden yazıldı — ve bilinçli olarak.
Hangi sonuç çıkarsa çıksın, hata karşılaştırmanın kendisindeydi.
İki sonuç da rapor için değerli; kötü olan tek şey, hangisi olduğunu
bilmeden birini iddia etmekti.

---

### P-40 · Grafana "Analiz hızı" paneli kare değil, TESPİT EDİLEN KİŞİ sayıyordu

**Tarih:** 03.09.2026 · **Faz:** 3 / Gün 18 · **Kaybedilen süre:** ~20 dk

**Belirti:** K4 ölçüm betiği yazılırken "analiz edilen kare sayısı"
için bir sayaç arandı. İki aday vardı ve **ikisi de yanlış kullanıldı.**

**Hata 1 — benim betiğimde (prova koşusunda yakalandı):**
`sentinel_inference_duration_seconds_count{stage="detect"}` kullanıldı
ve K2'yi **6 kat düşük** ölçtü (0.47 yerine ~2.8 FPS/kamera).

Sebep: o histogram **parti başına bir kez** gözlemleniyor
(`inference/worker.py:544`). Gözlemlenen DEĞER kare başına süre olsa
da **sayacı parti sayıyor.** Ortalama parti 6 kare olduğu için sayaç
tam 6 kat eksikti.

⚠ Genel kural: bir histogramın `_count` alanı *"kaç şey"* değil
*"kaç GÖZLEM"* demektir. İkisi ancak gözlem başına bir şey düşüyorsa
aynıdır.

**Hata 2 — canlı Grafana panosunda (asıl bulgu):**
"Analiz hızı (toplam)" paneli şunu kullanıyordu:

```promql
sum(rate(sentinel_detections_total[1m]))
```

`detections_total` **tespit edilen KİŞİ** sayıyor, kare değil.

⚠ **Bu panelin neden 17 gün fark edilmediği, hatanın kendisinden
öğretici:** kamera çiftliğinde kare başına ortalama ~1 kişi düşüyor,
yani panel **makul bir sayı gösteriyordu** (~55). Doğru sayıya yakın
olduğu için kimse sorgulamadı.

Ama panel iki durumda tamamen yanılırdı:
- **boş sahne** → 0 kişi = "analiz hızı 0" (oysa boru hattı çalışıyor)
- **kalabalık sahne** → 5 kişi = 5 kat şişmiş hız

Yani gösterge, tam da anlamlı olduğu anlarda (sistem sessiz mi, yoksa
durdu mu?) en yanıltıcı hâle geliyordu.

**Çözüm:** İkisi de `sentinel_end_to_end_latency_seconds_count`
kullanacak şekilde düzeltildi — o histogram mesaj döngüsünün İÇİNDE,
**kare başına** gözlemleniyor (`inference/worker.py:624`). Panel
açıklamasına da hatanın kendisi yazıldı.

**Öğrenilen ders:** ⭐ **Makul görünen bir sayı, doğrulanmış bir sayı
değildir.** P-33 aynı dersi vermişti ("GPU %5" cümlesi doğruydu,
ondan çıkarılan sonuç yanlıştı); burada cümlenin kendisi yanlıştı ama
sonucu doğru göründüğü için sorgulanmadı.

⚠ Pratik kural: bir metriğin adı ile hesaplandığı ifade **ayrı ayrı**
okunmalı. `title: "Analiz hızı"` ile `expr: rate(detections_total)`
yan yana duruyordu ve kimse ikisini birlikte okumamıştı.

---

### P-39 · K6 = 0.483 → 0.867: farkı yaratan model değil, ÖLÇÜM ARACIYDI

**Tarih:** 01.09.2026 · **Faz:** 2 / Gün 17 · **Kaybedilen süre:** ~2 saat (+ bir 56 dakikalık boşa koşu)

**Belirti:** K6 kriteri (anomali ROC-AUC ≥ 0.75) ilk kez ölçüldü ve
**0.483** çıktı — şans seviyesinin altı. Katman A skorlarının yalnızca
%2.8'i sıfırdan farklıydı.

Yani ölçüm *"sistem anomaliyi ayırt edemiyor"* demiyordu; **"sistem
hiçbir şey söylemiyor"** diyordu. İkisi çok farklı ve ikincisi
neredeyse her zaman ölçümün kendisini işaret eder.

**Araştırma:** Altı hata çıktı, hiçbiri modelde değildi.

**1 · Profil ısınmamıştı.** `PROFIL_ASGARI_ORNEK = 2000` eşiğine
ulaşılmadan Katman A hiçbir skor üretmiyor. İlk koşuda AUC tam
**0.500** çıktı — yani ölçüm hiçbir şey ölçmedi.
*Düzeltme:* Avenue'nun eğitim bölümüyle (tanımı gereği tümü normal)
ısıtma. Sistem sahada da böyle kurulur: temiz bir dönem izlenir,
sonra izlemeye geçilir.

**2 · Etiketsiz klipler ölçüme katılıyordu.** `10.avi` "0 anomali
segmenti" diye işlendi, oysa Avenue'nun test bölümündeki her klip
tanımı gereği anomali içerir — bizim yer gerçeğimiz yalnızca 01-09'u
kapsıyordu. Etiketsiz klibi katmak, içindeki **gerçek** anomalileri
"normal" diye etiketlemek demek: sistem onları doğru bulduğunda
**ceza alıyor.** Ölçüm, ölçtüğü şeyi cezalandırır hâle geliyor.
*Düzeltme:* 12 klip ölçüm dışı, açıkça raporlanıyor.

**3 · Isıtma 56 dakikada bitmedi.** Tam boru hattıyla yapılıyordu ve
15 328 kare, kare başına ~184 ms sürüyordu — canlı hattın ~25 ms'inin
**7 katı.**

⚠ Sebep ölçek değişimindeydi: `PencereDeposu` 3 saniyelik pencere
tutuyor. Canlı hat kamera başına ~3 FPS koşuyor → pencerede ~12 örnek.
Isıtma 25 FPS'te koşunca pencere **75 örneğe** çıktı ve `cikar()` her
karede o pencerenin tamamını dolaşıyor. **6× büyük pencere × 6× sık
çağrı = 36× maliyet.**

Bu, *"örnekleme hızını artırmak maliyeti doğrusal artırır"*
varsayımının çürüdüğü yer. Pencere tabanlı bir sistemde hız artışı
**karesel** etki yapıyor.
*Düzeltme:* Isıtma için yalın yol — pencere/özellik makinesi hiç
kurulmuyor. **56 dk → 4 dk.**

**4 · Hız ardışık kareden hesaplanıyordu.** Tanı betiği fiziksel
olarak imkânsız bir sayı gösterdi:

```
öğrenilen hız p50 : 1.645 gövde/sn   (canlı ölçüm: 0.30)
hücre sapması p50 : 4.734 gövde/sn
```

Bir insan hızını saniyede 4.7 gövde boyu değiştiremez. 25 FPS'te iki
kare arası 0.04 sn; yürüyen insan ~3 piksel yer değiştiriyor, takip
gürültüsü ise 5-20 piksel. **Gürültü sinyalden büyük.**

⚠ *"Daha yüksek kare hızı = daha iyi ölçüm"* sezgisinin çürüdüğü yer:
yer değiştirme `dt` ile küçülüyor, gürültü küçülmüyor.
*Düzeltme:* Sabit zaman tabanı (0.3 sn). Canlı hat bunu zaten doğru
yapıyordu (`person.py`: pencere üzerinden **medyan**).

**5 · ⭐ ASIL SUÇLU — koordinat uzayı karışıktı.** Tespitler **model
uzayında** (640×640 letterbox) geliyor, profil ise ızgarayı **kaynak
kare** boyutlarıyla (640×360) hesaplıyordu. Dolgu bandı yüzünden y
ekseni 140 piksel kaymış, alt hücreler tümüyle kadraj dışına taşmıştı.

Canlı boru hattı bunu doğru yapıyor (`Letterbox.to_source_box` ile geri
eşleme — Gün 8'de 2240 tespitte, 0 hatalı kutuyla doğrulanmıştı);
**ölçüm betiğinde o adım atlanmıştı.**

*Düzeltmenin etkisi:*

| | Önce | Sonra |
|---|---|---|
| Ziyaret edilen hücre | 77 (%13) | **229 (%40)** |
| Hız istatistiği yapabilen hücre | 35 | **117** |
| Öğrenilen hız p50 | 1.645 | **0.527** (canlı 0.30 ile uyumlu) |
| Katman A skor üretimi | %1.1 | **%40.7** |

**6 · Yön testi ölüydü.** Değerlendirme yolunda `yon=None`
geçiliyordu — Katman A'nın üç kolundan biri (ters yön) hiç
çalışmıyordu. Avenue'nun anomali türlerinden biri tam olarak ters yön.

**Sonuç:**

```
              ÖNCE     SONRA
füzyon        0.483    0.867   ✅ K6 TUTUYOR (hedef ≥0.75)
katman_a      0.493    0.789
```

⚠ **Hiçbir modele, eşiğe ya da ağırlığa dokunulmadı.** 0.384'lük fark
tümüyle ölçüm aracının düzeltilmesinden geldi.

⭐ **Füzyon kendini haklı çıkardı:** en iyi tek bileşen 0.789, füzyon
0.867. Bileşeninden kötü bir füzyon, karmaşıklığı boşuna eklemiş
olurdu — betik bunu açıkça raporluyor.

**Öğrenilen dersler:**

1. **Ölçüm aracına, ölçtüğü şeye gösterdiğin şüpheyi göster.** Bu
   projede aynı sınıf hata üçüncü kez çıktı: P-17 (sıralı koşu),
   P-36 (bozuk blok özeti tersine çevirdi), şimdi P-39. Üçünde de
   *sistem* suçlanmaya hazırdı, suçlu *ölçüm* çıktı.

2. **"Hiç sinyal yok" ile "yanlış sinyal" farklı teşhislerdir.**
   AUC'nin tam 0.500 çıkması bir sonuç değil, bir uyarıdır: skorların
   hepsi eşitse ölçüm çalışmıyordur.

3. **Bir sayının FİZİKSEL olarak mümkün olup olmadığına bak.**
   "Sapma 4.7 gövde/sn" hatayı tek başına ele veriyordu; istatistiğe
   bakmadan önce fiziğe bakmak gerekiyordu.

4. **Üretim yolunda çözülmüş bir problem, ölçüm yolunda yeniden
   çözülmez — ORADAN ÇAĞRILIR.** Koordinat geri eşlemesi canlı hatta
   Gün 8'de doğrulanmıştı; ölçüm betiği onu kullanmak yerine atlamıştı.

**⚠ Dürüstlük notu:** `kural` bileşeni AUC 0.500 — Katman B kuralları
Avenue'da **hiç ateşlemiyor.** Sebep veri setinin doğasında: Avenue'nun
anomalileri çanta fırlatma, bisiklet, ters yön; bizim kurallarımız
düşme/koşma/kalabalık arıyor ve boru hattımız yalnızca **insan**
tespit ediyor. Fırlatılan bir çanta bizim için görünmez.

K6'yı taşıyan şey neredeyse tümüyle Katman A (öğrenilmiş kamera
normali). Bu bir kusur değil, kapsamın dürüst sınırı.

---

### P-38 · Bir çökme, paylaşımlı bellek havuzunu KALICI olarak küçültüyordu

**Tarih:** 30.08.2026 · **Faz:** 1 / Gün 16 · **Kaybedilen süre:** ~1 saat (+ bir ölçüm koşusu boşa gitti)

**Belirti:** Parti doldurma ölçümü koşarken sonuç `0.0 kare/sn` çıktı.
Bütün süreçler ayaktaydı, panel bağlıydı, sağlık kontrolü yeşildi.

```
bos slot        : 0 / 48
frames.ready    : 95 mesaj, sabit (büyümüyor)
bekleyen        : 48
frames_dropped_total{reason="no_slot"}  →  her kamerada binlerce
```

**Kök sebep:** Tüketici grubunda `XREADGROUP` ile okunan her mesaj, ACK
gelene kadar o tüketiciye **asılı (pending)** kalır. Çıkarım worker'ı
sert kapatıldığında (ölçüm betiği `Stop-Process -Force` kullanıyor)
elindeki mesajlar asılı kalıyor ve **paylaşımlı bellek slotları havuza
geri dönmüyordu.**

Yeni worker `>` ile yalnızca YENİ mesajları okuduğu için o slotlar
sonsuza dek kayboluyordu. Ölçüm betiği worker'ı defalarca yeniden
başlattığı için havuz adım adım tükendi ve sonunda sıfırlandı.

⚠ **Arıza SESSİZ ve bu en kötü tarafı.** Alım worker'ı slot bulamayınca
kareyi atıyor ve *bunu doğru yapıyor* — `no_slot` tasarlanmış bir geri
basınç yolu. Dışarıdan bakan hiçbir gösterge "sistem durdu" demiyor;
yalnızca hiçbir şey işlenmiyor.

⚠ Gün 23'te 24 saatlik dayanıklılık koşusu var. Tek bir çökmenin havuzu
kalıcı olarak küçülttüğü bir sistemde o koşu anlamsız.

**Çözüm — iki aşamalı, ve birincisi yetmedi:**

**1. `XAUTOCLAIM` ile asılı mesajları sahiplenip slotlarını bırakmak.**
Açılışta (1 sn eşik) ve koşu sırasında 60 saniyede bir (30 sn eşik).

⚠ Eşik neden büyük: "bu mesajı işleyen tüketici ölmüştür" varsayımının
gerekçesi bu. Kısa tutulursa yavaş ama **sağ** bir tüketicinin
mesajları elinden alınır ve aynı kare iki kez işlenir.

Bu aşama **48 slotun yalnızca 5'ini** kurtardı. Çünkü akış `maxlen` ile
sınırlı: asılı bir mesaj o sırada akıştan düşmüş olabiliyor ve
`xautoclaim` onu boş alanlarla döndürüyor — **slot numarası artık
bilinmiyor.**

**2. Muhasebe.** Bir slot üç yerden birinde olmak zorunda:

```
(a) boş listede
(b) henüz işlenmemiş bir mesajın referansında
(c) tüketicinin elinde (işlenmekte)
```

Üçünde de olmayan slot sızmıştır. Açılışta (c) boş olduğu için hesap
kapalı.

**⚠ Ve burada ikinci bir hata yaptım — öğretici olan bu:**

İlk uygulamada (b) için akışın **tamamını** taradım. Çalışmadı ve
sebebi ancak sayılara bakınca göründü:

```
akıştaki mesaj : 99
farklı slot    : 48
boş slot       : 0/48
```

99 mesaj 48 slota işaret ediyordu — yani slotlar tekrar kullanılmıştı.
Sebep: **`XACK` bir mesajı akıştan SİLMİYOR**, yalnızca bekleyen
listesinden çıkarıyor. Akıştan düşme ancak `maxlen` budamasıyla oluyor.

Yani akışın tamamını taramak, çoktan işlenmiş ve slotu çoktan iade
edilmiş mesajları da "kullanımda" saymak demekti. O tarama **hiçbir
zaman sızıntı bulamazdı** — her slot her zaman "birinde görünüyordu".

Doğrusu iki küme: henüz teslim edilmemiş kayıtlar (grubun
`last-delivered-id` değerinden sonrası) + teslim edilmiş ama
ACK'lenmemiş kayıtlar (`XPENDING`).

**Doğrulama** (gerçek sızıntı üzerinde, sentetik değil):

```
       ÖNCE          SONRA
boş slot        0/48    36/48
işlenmemiş      —          13    (36 + 13 = 49 ≈ 48 ✓)
akış           sabit    75 → 100 (üretim yeniden başladı)
```

**Öğrenilen dersler:**

1. **Bir kaynağın sahibi ölürse kaynak kaybolur.** Dağıtık bir sistemde
   "ödünç alınan" her kaynağın bir geri kazanma yolu olmalı; yoksa her
   çökme sistemi biraz daha küçültür.

2. **Sessiz bozulma, gürültülü çökmeden tehlikelidir.** Sistem
   çökseydi 30 saniyede fark ederdim. "Çalışıyor ama hiçbir şey
   yapmıyor" durumu ancak ölçüm sıfır çıkınca görüldü.

3. **Bir API'nin ne yaptığını değil, ne YAPMADIĞINI da bilmek
   gerekiyor.** `XACK`'in adı "acknowledge"; sildiğini varsaymak
   makul görünüyordu ve o varsayım muhasebeyi tümden işlevsiz kıldı.

---

### P-37 · Video herkese açıktı — korumayı kolay korunan yere koymuşum

**Tarih:** 30.08.2026 · **Faz:** 1 / Gün 16 · **Kaybedilen süre:** —

**Belirti:** API'ye kimlik doğrulama eklerken, uçları tek tek gözden
geçirirken fark edildi: **video API'den geçmiyor.**

Mimari kural 2 zaten bunu söylüyordu ve bilinçliydi:

> *"Sunucu videoya kutu çizmez. Video WHEP ile ayrı gider, kutular
> WebSocket'ten JSON olarak gider."*

Yani tarayıcı doğrudan MediaMTX'e (8889) bağlanıyor. Ben API'yi
korurken (kamera listesi, olay geçmişi, webcam açma) **görüntünün
kendisini** hiç düşünmemişim. `mediamtx.yml` içinde `read` izni
`ips: []` — yani herkese açık.

**Kök sebep:** Güvenlik çalışmasını "hangi uçları yazdım" listesi
üzerinden yürüttüm, "hangi veri değerli" listesi üzerinden değil.
Kod tabanında görünen yüzey API'ydi; en mahrem çıktı ise başka bir
süreçten servis ediliyordu ve o süreç benim yazdığım kod değildi.

⚠ Genel ders: **koruma, kolay korunan yere değil değerli olana konur.**
Bir sistemin en hassas çıktısı, çoğu zaman kendi yazdığınız kodun
dışından akar.

**Çözüm:** `read` izni yerel makine ve özel ağlara kısıtlandı.

**⚠ Bu tam bir çözüm DEĞİL ve öyle raporlanmıyor.** IP kısıtı kimlik
doğrulaması değildir: aynı makinedeki ya da aynı yerel ağdaki herkes
hâlâ izleyebilir. Bu bir *derinlikli savunma* katmanı — port
yanlışlıkla dışa açılırsa internetten okunamıyor.

Tam çözüm iki yoldan biri:
1. MediaMTX `authHTTPAddress` ile her okuma isteğini API'ye sormak.
   ⚠ Tokenın **URL sorgu dizesinde** taşınmasını gerektiriyor ve sorgu
   dizeleri sunucu günlüklerine, vekil kayıtlarına, tarayıcı geçmişine
   düşüyor.
2. **Caddy'yi tek giriş noktası yapmak** (PLAN §10). Hem API hem WHEP
   onun arkasından geçer, kimlik tek yerde doğrulanır. Doğru mimari
   cevap bu; iş açık.

**Öğrenilen ders:** Bir güvenlik gözden geçirmesine "hangi uçlarım
var" diye başlamak eksik. Doğru başlangıç sorusu: *"bu sistemde en
değerli veri hangisi ve hangi yollardan çıkıyor?"*

---

### P-36 · Bir bozuk blok, ölçülmemiş bir şeyi ölçülmüş gösterdi

**Tarih:** 30.08.2026 · **Faz:** 1 / Gün 16 · **Kaybedilen süre:** ~25 dakika (bir ölçüm koşusu)

**Belirti:** Parti doldurma (`--batch-fill-ms`) özelliğinin etkisi
dönüşümlü A/B ile ölçüldü ve özet **"-%15.2 verim"** dedi. Yani özellik
zararlıydı.

Blok blok bakınca tablo başkaydı:

```
[tur 1] fill=0    36.0 kare/sn · 5.56 kare/parti · dolu %46
[tur 1] fill=60   51.7 kare/sn · 7.25 kare/parti · dolu %78
[tur 2] fill=0    49.0 kare/sn · 3.83 kare/parti · dolu %20
[tur 2] fill=60   20.4 kare/sn · 4.18 kare/parti · dolu  %0   ⬅ ?
```

**Kök sebep — ikisi birden:**

1. **Ölçüm sırasında sisteme dokundum.** Son blok koşarken MediaMTX'i
   yeniden başlattım (P-37'deki güvenlik düzeltmesi için). 20 kamera
   birden yeniden bağlandı; o blokta ölçülen şey parti doldurma değil,
   yeniden bağlanmaydı.

2. **Betik ORTALAMA raporluyordu.** İki örnekten biri bozuk olunca
   ortalama tümüyle o bozuk örneğin peşinden gitti.

⚠ İkinci sebep birincisinden daha önemli. Ölçüm sırasında bir şeyin
bozulması olağan; **bozulduğunu söylemeyen bir araç** ise her koşuda
sessizce yanlış sonuç üretir.

Üstelik geçerli bloklara bakınca bile sonuç çıkmıyor: fill=0 blokları
36.0 ve 49.0 vermiş — aralarındaki fark, fill=60'ın (51.7) farkı kadar
büyük. **Ölçülmek istenen etki, gürültünün içinde.**

**Çözüm:** Betik artık
- ortalama yerine **medyan** kullanıyor (tek aykırı bloğa dayanıklı),
- **yayılımı** basıyor: `(max−min)/medyan`,
- etki blok içi yayılımdan küçükse açıkça **"SONUÇSUZ"** yazıyor,
- yayılım %15'i aşarsa uyarıyor: *"--tur artırın ya da ölçüm sırasında
  sisteme DOKUNMAYIN (docker restart dâhil)"*.

**Öğrenilen ders:** Bir ölçüm aracının en önemli özelliği,
**ölçemediğini söyleyebilmesi.** İki örneğin ortalamasını, aralarında
%40 fark varken tek bir sayı gibi raporlamak, ölçülmemiş bir şeyi
ölçülmüş göstermektir — ve o sayı bir kez rapora girdiğinde veri gibi
davranmaya başlar (P-33'ün aynısı).

Ayrıca bu proje P-17'de aynı sınıf hatayı bir kez yaşamıştı (sıralı
koşu). Dönüşümlü koşuya geçmek gerekliydi ama **yeterli değilmiş**:
dönüşümlü koşu sistematik sürüklenmeyi çözüyor, tek seferlik bir
bozulmayı çözmüyor.

---

### P-35 · `start_all.ps1` sistemin tamamını kaldırmıyordu

**Tarih:** 30.08.2026 · **Faz:** 1 / Gün 16 · **Kaybedilen süre:** günlerce fark edilmedi

**Belirti:** Alarm kalıcılığı eklenirken betik incelendi ve
**analitik worker'ının hiç başlatılmadığı** görüldü. Betik 4 adımdı:
docker → alım → çıkarım → API.

Yani `start_all.ps1` ile başlatılan sistemde tespit ve takip
çalışıyor, panel kutuları çiziyor — ama **hiçbir anomali
üretilmiyordu.** Alarm paneli sonsuza dek boş kalıyordu.

**Neden fark edilmedi:** Ben analitik worker'ını hep elle
başlatıyordum. Betik "✓ hazır" diyordu ve söylediği her şey doğruydu;
söylemediği şey eksikti.

**Kök sebep:** Bileşen eklendikçe başlatma betiği güncellenmemiş.
Belge ile gerçek arasındaki sapmanın en sinsi türü: **belge yalan
söylemiyor, eksik konuşuyor.**

**Çözüm:** Betik 7 adıma çıkarıldı (analitik + alarm worker'ları
eklendi) ve ikisi de `Wait-Url` ile **doğrulanıyor** — açılmazsa
uyarı basıyor. `stop_all.ps1`'in açık süreç listesi de eksikti
(`analytics`, `alerting` yoktu); yalnızca venv yolu koşulu sayesinde
kapanıyorlardı. Eksik bir listeyi "zaten çalışıyor" diye bırakmak,
ilk koşul değiştiği gün sessizce bozulacak bir bağımlılık yaratır.

⚠ **Yan bulgu — port çakışması:** Alarm worker'ına 9120 vermiştim,
analitik worker zaten oradaydı. 9130'a alındı. Bu sınıf hata bu
projede P-01'de de yaşandı ve hep aynı biçimde tezahür ediyor:
**bileşen çalışır görünür, yalnızca gözlemlenemez olur.**

**Öğrenilen ders:** Belgelenen başlatma yolu sistemin **tamamını**
ayağa kaldırmalı. Kaldırmıyorsa, o belgeyi okuyan herkes (altı ay
sonraki ben dâhil) eksik bir sistemi çalışıyor sanacak.

---

### P-34 · Üç SQL tuzağı ve "hiçbir şey yok" ile "bakmadım"ın aynı görünmesi

**Tarih:** 30.08.2026 · **Faz:** 1 / Gün 16 · **Kaybedilen süre:** ~40 dakika

Olay kalıcılığı eklenirken arka arkaya üç hata çıktı. Üçü de küçük,
üçü de öğretici.

**1. `SEMA.format()` → `IndexError`**

Şema metni `kanit JSONB NOT NULL DEFAULT '{}'::jsonb` içeriyor.
`str.format()` o `{}` ifadesini bir yer tutucu sanıp konumsal argüman
aradı.

*Ders:* SQL'de süslü parantez sık geçer (JSONB, dizi literalleri,
`plpgsql` blokları). SQL şablonlarında `format` genel olarak yanlış
araç — `replace` ya da parametreli sorgu kullanılmalı.

**2. `split(";")` → `syntax error at end of input`**

Şemayı tek metin yazıp `;` ile bölüyordum. Bir SQL **yorumunun
içinde** noktalı virgül vardı:

```sql
-- ... daha az güvenilirdir; operatör bunu görmeli.
```

Bölme, ifadeyi yorumun ortasından kesti.

*Ders:* SQL'i ayırıcıya bakarak bölmek, **dizeleri ve yorumları
tanımayan bir ayrıştırıcı yazmaktır.** İfadeler artık ayrı ayrı
tutuluyor — hem doğru hem okunaklı, her ifade kendi gerekçesiyle yan
yana.

**3. ⚠ En tehlikelisi: `/api/v1/events/ozet?saat=1` BOŞ dönüyordu**

Saatlik özet uç noktası, alarmlar veritabanına yazılmış olmasına
rağmen `{"toplam_alarm": 0}` diyordu.

Sebep sessizdi: sürekli toplulaştırma yenileme politikası
`end_offset => 1 hour` kullanıyor — yani **en son saat kasten
özetlenmiyor** (yarım saatlik veriyi tam saat gibi göstermemek için,
ki bu doğru bir karar). Materyalize edilmemiş bölge sorguya hiç
girmediğinden operatör *"son 1 saatte hiçbir şey olmadı"* cevabı
alıyordu.

⚠ **Gözetim sisteminde en tehlikeli cevap budur.** *"Hiçbir şey yok"*
ile *"bakmadım"* aynı görünüyorsa, sistem sessizce yanıltıyor demektir.
Operatör alarm olmadığına inanıp başka yere bakar.

*Çözüm:* `timescaledb.materialized_only = false` — görünüm,
materyalize edilmiş eski veriyi ham tablodan gelen taze veriyle
birleştiriyor. TimescaleDB'de bu özellik tam olarak bu senaryo için
var.

⚠ `ALTER` ayrıca çağrılıyor: `CREATE MATERIALIZED VIEW IF NOT EXISTS`
var olan bir görünümü **değiştirmez.** Önceki sürümle kurulmuş bir
veritabanı yükseltilirken bu satır olmasa hata kalıcı olurdu.

---

### P-33 · "GPU boşta, o hâlde hızlandırmaya değmez" — boşta olmak ucuz olmak değildir

**Tarih:** 26.08.2026 · **Faz:** 1 / Gün 15 · **Kaybedilen süre:** ~10 gün (yanlış karar olarak taşındı)

**Belirti:** Gün 8'den beri `CLAUDE.md` şunu yazıyordu:

> *"TensorRT planlandı ama kullanılmıyor: Gün 8 ölçümü GPU'nun %0-5'te
> boş oturduğunu gösterdi (`GpuIdle`), yani modeli hızlandırmak kazanç
> getirmezdi."*

Cümle mantıklı görünüyor ve on gün boyunca kimse sorgulamadı.

**Kök sebep:** İki farklı büyüklük birbirine karıştırılmış:

| Ölçtüğüm | Sandığım |
|---|---|
| **Görev döngüsü** — GPU zamanın yüzde kaçında meşgul | **Çağrı maliyeti** — bir ileri geçiş kaç ms sürüyor |

GPU'nun %5 kullanımda görünmesi, ileri geçişin ucuz olduğunu değil,
**partiler arasında beklediğini** söyler. Tek süreçli boru hattında GPU
işini bitirir, sonra CPU'nun bir sonraki partiyi hazırlamasını bekler.
Kullanım düşük çünkü çoğu zaman *boş bekliyor* — yaptığı iş kısa
olduğu için değil.

**Ölçüm** (`scripts/benchmark_detect_breakdown.py`, boru hattı kapalı,
CUDA olayıyla, `benchmarks/detect_breakdown_20260826-181256.json`):

```
AŞAMA      kare ms    pay
TENSOR       0.960    15%   numpy yığma + H2D + permute/flip/half
FORWARD      3.372    53%   ⬅ saf ileri geçiş — TensorRT'nin alanı
ARTIK        1.970    31%   NMS + Results nesnesi kurma
CONVERT      0.004     0%   GPU→CPU + Detection listesi
TOPLAM       6.305
```

İleri geçiş bütçenin **yarısından fazlası.** Amdahl'a göre 3×
hızlanma toplamda %35.6 kazanç demek — hiç de "kazanç getirmez"
değil.

⚠ Duvar saatiyle ölçseydim bu sayı da yanlış çıkardı: CUDA çağrıları
eşzamansızdır, `time.perf_counter()` işin bitişini değil **kuyruğa
atılışını** ölçer. `torch.cuda.Event` GPU'nun kendi zaman çizgisinde
ölçüyor.

**Çözüm:** TensorRT ölçülmeye alındı (P-34'e devam ediyor).

**Öğrenilen ders:** Bir metriğin *adı* ile *anlamı* aynı şey değil.
"GPU kullanımı %5" cümlesi doğruydu; ondan çıkardığım sonuç yanlıştı.
Bir ölçüm karar veriyorsa, o ölçümün tam olarak neyi saydığını yazıya
dökmek gerekiyor — "GPU boşta" değil, "GPU zamanın %95'inde iş
beklemiyor, iş gelmesini bekliyor".

Ayrıca: bir kararın gerekçesi belgeye girdikten sonra **veri gibi
davranmaya başlıyor.** On gün boyunca "TensorRT'ye gerek yok" bir
bulgu olarak alıntılandı, oysa bir çıkarımdı ve yanlıştı.

---

### P-32 · Saldırganlık skorunun sıfır noktası yoktu — 26.4 yanlış alarm/kamera-saat

**Tarih:** 26.08.2026 · **Faz:** 1 / Gün 15 · **Kaybedilen süre:** ~3 saat

**Belirti:** 10 dakikalık canlı ölçümde 88 alarm, yani **26.4
alarm/kamera-saat** (K7 hedefi ≤3). En büyük kalem saldırganlık (88'in
30'u) ve tek başına Oxford caddesinde (cam-09) 12 uyarı. Orada kavga
yok — sadece yaya trafiği var.

**Araştırma:** İlk refleks eşikleri yükseltmekti. Yapmadım, çünkü eşik
yükseltmek yanlış alarmı her zaman düşürür — bu bir keşif değil,
aritmetik. Sebebi öğrenmeden yapılan ayar, bir sonraki sahnede yine
patlar.

Bunun yerine girdinin dağılımı ölçüldü
(`scripts/benchmark_features.py`, 20 kamera, 200 sn, 40 bin özellik
vektörü — `benchmarks/features_20260826-175748.json`):

```
ÖZELLİK              p50     p90     p99   o günkü doyum
bilek_hizi_azami    0.87    1.80    4.01     3.0
bilek_sarsintisi    0.54    1.39    3.24     2.0
hareket_enerjisi    0.45    0.85    1.39     1.5
govde_hizi          0.30    0.66    0.94       —
```

**Kök sebep:** Her bileşen `deger / doyum` ile 0-1'e eşleniyordu.
Sessiz sonucu: **sıfır noktası yok.** Yürüyen bir insanın bileği de
hareket eder; normal davranışın p90'ı doyumun %56-69'unu dolduruyordu.

Kalem kalem, p90'lık sıradan bir yaya (yanından biri geçerken):

```
bilek    0.66 × 0.25 = 0.164
enerji   0.41 × 0.15 = 0.061
duruş    0.25 × 0.10 = 0.025
yakınlık 0.38 × 0.30 = 0.113
yaklaşma 1.00 × 0.20 = 0.200
                       ─────
                       0.563   >  0.55 (uyarı eşiği)
```

İkinci hata `DOYUM_YAKLASMA = 1.0` idi ve **yorumu ölçümle
çelişiyordu**: *"bu hızda yaklaşmak koşarak gelmektir"* yazıyordu, oysa
gövde hızı p99 = 0.94 — iki kişi normal yürüyüşle karşılıklı gelince
kapanma hızı zaten 1.0'ı aşıyor. Bileşen sürekli doygundu.

Üçüncüsü yapısaldı: modül kendi başlığında *"saldırganlık tanımı gereği
etkileşimlidir"* diyordu ama **toplamsal** skor bunu uygulamıyordu.
Yalnız koşan biri bilek + enerji + duruştan skor toplayabiliyordu.

**Çözüm:** İki değişiklik, ikisi de ölçümden türetildi.

1. **Ölü bölge:** `bilesen = clamp((deger − taban)/(doyum − taban),0,1)`,
   taban = ölçülen normal p90. *Normal davranış kanıt değildir.*
2. **Etkileşim kapısı:** skor `× max(yakınlık, yaklaşma)`.
   ⚠ Kapı salt yakınlığa bağlanmadı: birbirine koşan iki kişi henüz
   yakın değildir ve projenin özgün katkısı tam o anı yakalamak.

Doğrulama için `scripts/calibrate_aggression.py` yazıldı: **tek canlı
akıştan dört ayarı aynı anda** skorluyor. Ortak zemin olmadan iki sayı
kıyaslanamaz (P-17).

```
6932 değerlendirme · 300 sn · 9 normal kamera
AYAR    dikkat  uyari    p50     p99
ESKI       610     43   0.193   0.464
BANT       173      0   0.117   0.394
KAPI        23      0   0.088   0.278
IKISI        0      0   0.053   0.189
```

**Öğrenilen ders:** Bir eşiği ayarlamadan önce, o eşiğe giren büyüklüğün
**normal koşuldaki dağılımını** bilmek gerekiyor. Bilinmeden seçilen
her eşik tahmindir; tahminin doğru çıkması ancak şanstır.

İkinci ders: bir modülün docstring'inde yazan mimari iddia
("etkileşimlidir") ile kodun yaptığı iş ayrışabiliyor ve bu ayrışma
**hiçbir testi kırmıyor.** Mimari kural 0 yalnızca belge-kod değil,
docstring-kod arası için de geçerli.

---

### P-31 · Bayat yer gerçeği: diskte kavga etiketi, ekranda kalabalık meydan

**Tarih:** 26.08.2026 · **Faz:** 1 / Gün 15 · **Kaybedilen süre:** ~20 dakika (ama bulunmasaydı ölçümü zehirleyecekti)

**Belirti:** UR Fall dizisi cam-16'ya konulurken `data/annotations/`
dizinine bakıldı ve cam-16 için **zaten bir yer gerçeği dosyası
olduğu** görüldü — içinde RWF-2000 kavga zaman damgaları.

Kontrol edilince beş dosyanın bayat olduğu çıktı:

```
cam-13  plan=PETS kalabalık   truth=RWF-2000 kavga zamanları
cam-14  plan=PETS kalabalık   truth=RWF-2000 kavga zamanları
cam-15  plan=PETS kalabalık   truth=RWF-2000 kavga zamanları
cam-18  plan=Avenue normal    truth=RWF-2000 kavga zamanları
cam-20  plan=Pexels yüzler    truth=RWF-2000 kavga zamanları
```

**Kök sebep:** Bu slotlar bir zamanlar RWF kameralarıydı. Çiftlik
yeniden düzenlenirken `data/videos/cam-NN.mp4` üzerine yazıldı ama
`data/annotations/cam-NN.truth.json` **yerinde kaldı.** Üretim betiği
yalnızca ürettiği dosyayı düşünüyordu, geride bıraktığını değil.

**Neden kimse fark etmedi:** Hiçbir betik o dosyaları okumuyordu.
`benchmark_k7.py` yalnızca cam-19'a bakıyor. Yani hata görünmez
biçimde bekliyordu — okuyan ilk ölçüm sessizce yanlış sonuç verecekti.

⚠ **Testi olmayan veri, testi olmayan koddan tehlikelidir.** Kod
yanlışsa patlar; veri yanlışsa patlamaz, sadece yanlış sayı üretir ve o
sayının üstüne kurulan her şey yanlış olur.

**Çözüm:**
- Bayat dosyalar silindi; cam-18 kontrol kamerası olarak yeniden
  yazıldı (boş segment listesi — *ölçümün kendisi budur*: cam-19 ile
  aynı sahne, tek fark anomalinin yokluğu).
- Her yer gerçeği dosyası artık **hangi kaynaktan üretildiğini**
  yazıyor (`uretim_kaynagi`).
- `build_camera_farm.py` içine `_truth_denetle()` eklendi: plandaki
  kaynakla dosyadakini karşılaştırıp uyuşmazlığı bildiriyor.
  **Silmiyor, uyarıyor** — elle yazılmış bir dosyayı bir betiğin
  silmesi, çözdüğü sorundan büyük bir sorundur.

**Öğrenilen ders:** Kısmi bir işlem, dokunmadığı kayıtları geçersiz
kılabiliyor. Aynı sınıf hata bu projede ikinci kez çıktı (manifest'in
`--only` ile ezilmesi). Ortak ders: **bir kaydı üreten kod, o kaydın
artık geçerli olup olmadığından da sorumludur.**

---

### P-30 · İki paket aynı dizini paylaşınca CUDA sağlayıcısı öksüz kaldı

**Tarih:** 18.08.2026 · **Faz:** 1 / Gün 14 · **Kaybedilen süre:** ~4 gün (fark edilmeden)

**Belirti:** Gün 13'ten beri açık madde: *"onnxruntime CUDA sağlayıcısı
etkinleştirilemedi → ifade modeli CPU'da, yüz başına ~58 ms."* Teşhis
olarak *"beklediği cuDNN sürümü yok"* yazılmıştı ve Faz 5'e ertelenmişti.

**Çürütülen hipotez:** "cuDNN eksik." Kontrol edilmemişti; makul
göründüğü için kabul edilmişti.

**Gerçek kök sebep:**

```
onnxruntime      1.28.0   ← CPU derlemesi
onnxruntime-gpu  1.28.0   ← GPU derlemesi
```

İkisi de kurulu. Ve ikisi de **aynı dizine** açılıyor:
`site-packages/onnxruntime/`. Sonra kurulan diğerinin `onnxruntime.dll`
dosyasını **eziyor**. Bizde CPU sürümü kazanmıştı:

```
get_available_providers() → ['AzureExecutionProvider', 'CPUExecutionProvider']

ama capi/ dizininde:
    onnxruntime_providers_cuda.dll        ← duruyor
    onnxruntime_providers_tensorrt.dll    ← duruyor
```

CUDA sağlayıcısının DLL'i **diskteydi**, ana kütüphane onu tanımıyordu.
Öksüz dosyalar.

CPU paketini kim çekiyor? `emotiefflib`. Bağımlılık listesinde
`onnxruntime` yazıyor — ama `onnxruntime-gpu` da `onnxruntime`
**modülünü** sağladığı için bu beyan gereğinden dar.

**Çözüm:** uv override ile CPU paketi çözüm ağacından çıkarıldı:

```toml
override-dependencies = ["onnxruntime ; python_version < '0'"]
```

Sonra `onnxruntime-gpu` yeniden kuruldu (paylaşılan dosyalar CPU
paketiyle birlikte silinmişti).

```
ÖNCE : ['Azure', 'CPU']
SONRA: ['Tensorrt', 'CUDA', 'CPU']
```

**⚠ Ama kazanç beklendiği gibi çıkmadı — ve sebebi P-15'in aynısı:**

| cihaz | 1 yüz | 4 yüz | 8 yüz | 8'de yüz başına |
|---|---|---|---|---|
| cuda | 6.78 ms | 27.00 ms | 61.41 ms | 7.68 ms |
| cpu | 7.15 ms | 26.93 ms | 62.86 ms | 7.86 ms |

GPU kazancı **%2**. Ölçek tam doğrusal: 1 yüz 6.78 → 8 yüz 61.41.
Yani `emotiefflib.predict_emotions(liste)` **toplu çağrı yapmıyor**,
içeride tek tek döngüye sokuyor. Model küçük (16 MB `enet_b0`) ve her
çağrının sabit maliyeti baskın olduğu için GPU'nun avantajı hiç
doğmuyor. Gerçek kazanç ONNX oturumunu doğrudan `(N,3,224,224)` tensörle
çağırmakla gelir — `detector/yolo.py::_as_tensor`'da yaptığımızın aynısı.

**Öğrenilen dersler:**

1. **Teşhis edilmemiş bir hipotezi "bilinen sorun" diye kaydetme.**
   "cuDNN eksik" cümlesi 4 gün boyunca dosyada durdu ve kimse
   `get_available_providers()` ile `capi/` dizinini yan yana koymadı.
   Doğrulanmamış teşhis, teşhis değil tahmindir; öyle yazılmalı.
2. **Aynı modül adını sağlayan iki paket bir arada bulunamaz.**
   Python'un paket sistemi bunu engellemiyor; ikisi de sessizce kuruluyor
   ve son kurulan kazanıyor. Bağımlılık çakışması her zaman "sürüm
   uyuşmazlığı" biçiminde görünmüyor.
3. **Sağlayıcı listesi tek satırlık bir kontrol.** `nvidia-smi`'nin
   P-18'de yaptığını burada `get_available_providers()` yapardı.

---

### P-29 · Testler iki gerçek hata buldu — biri dışarıdan ulaşılabilir çökme yolu

**Tarih:** 18.08.2026 · **Faz:** 1 / Gün 14 · **Tür:** güvenlik + dayanıklılık

**Bağlam:** Depoda **sıfır test** vardı. Ama `CLAUDE.md` "8 birim testi
geçti", P-26 "7 birim testi", P-20 "birim testi" diyordu — testler
gerçekten koşturulmuş, **commit edilmemişti.** Açığı kapatmak için 68
backend + 17 frontend testi yazıldı. İlk koşuda ikisi kırmızı yandı ve
ikisi de gerçek hataydı.

#### Hata 1 — bozuk `Origin` başlığı WS işleyicisini çökertiyordu

Kod şöyleydi:

```python
try:
    candidate = urlsplit(origin)
except ValueError:
    return False
...
for allowed in settings.origins:
    if (candidate.scheme, candidate.hostname, candidate.port) == (...)
                                              ^^^^^^^^^^^^^^
                                              ValueError BURADA fırlıyor
```

`urlsplit` **tembel çalışıyor**: çağrı bozuk girdide bile hata vermiyor,
ayrıştırmayı alan erişimine erteliyor. `.port` ise portu tam sayıya
çeviremezse `ValueError` atıyor. Yani `try` bloğu **yanlış yeri**
sarmalıyordu ve hata döngünün içinde, korumasız fırlıyordu.

Somut etki: `Origin: http://:::` başlığıyla gelen bir bağlantı işleyiciyi
çökertiyordu. **Kimlik doğrulaması gerekmeyen, el sıkışma tamamlanmadan
tetiklenebilen** bir hata yolu — yani dışarıdan ulaşılabilir.

#### Hata 2 — aynı köken kontrolü şemayı yok sayıyordu

`Host` başlığı şema taşımaz (`127.0.0.1:8001`), bu yüzden yalnızca
host:port karşılaştırılıyordu. Sonuç: `Origin: https://127.0.0.1:8001`
ile `Host: 127.0.0.1:8001` **eşleşiyordu.** Oysa aynı köken politikasının
tanımı üç bileşenlidir: **şema + host + port.**

Pratikte sömürülmesi zor (aynı host:port'ta iki şema aynı anda duramaz),
ama ikisini kontrol edip üçüncüsünü atlamak kontrolün adını yanlış
koymaktır. Şema artık bağlantının kendisinden türetiliyor
(`ws` → `http`, `wss` → `https`).

**Öğrenilen dersler:**

1. **Bir çağrıyı `try` içine almak, o çağrının ürettiği NESNEYİ
   kullanmanın da güvenli olduğu anlamına gelmiyor.** Tembel
   değerlendirme yapan kütüphanelerde hata, çağrıdan çok sonra çıkar.
2. **"Test yazdım" ile "test commit ettim" arasındaki fark, raporda
   savunulabilir olmakla olmamak arasındaki farktır.** Üç ayrı belgede
   "N birim testi geçti" yazılıydı ve depoda hiçbiri yoktu.
3. **Testler kapsama için değil, sessiz hata üreten yerler için
   yazılır.** Öncelik sırası: letterbox ters dönüşümü (yanlış yere
   çizim, hata mesajı yok), hareket filtresi (fazla elerse olaylar hiç
   görülmez), origin doğrulaması (iki kez hataya yol açmıştı).

---

### P-28 · Isınma 90 saniye sürüyor — ve ölçümlerin çoğu bunun içinde yapılmış

**Tarih:** 18.08.2026 · **Faz:** 1 / Gün 14 · **Tür:** ölçüm metodolojisi

**Belirti:** KADEME 2b bağlandıktan sonra doğrulama koşusu yapıldı,
sayılar felaketti:

```
35 sn'lik koşu:  tespit 31.5 ms · poz 245.2 ms · gecikme 1505 ms · 1.6 FPS
```

Belgelenen değerler tespit 6.5 ms, poz 9.1 ms, gecikme 181 ms. Yani
görünürde **25 kat** gerileme. İlk refleks "yeni kod boru hattını
bozdu" oldu.

**Ölçüm ne diyor:** Koşu 90 saniyeye uzatıldı ve aralık aralık raporlandı:

| süre | tespit | poz | gecikme | FPS |
|---|---|---|---|---|
| 30 sn | 19.9 ms | 141.9 ms | 1260 ms | 3.2 |
| 60 sn | 14.5 ms | 21.5 ms | 457 ms | 9.0 |
| **90 sn** | **9.6 ms** | **14.4 ms** | **189 ms** | 10.0 |

Gerileme yok. Sistem ısındıkça belgelenen değerlere yakınsıyor.

**Kök sebep:** Soğuk başlangıç. CUDA bağlamı, çekirdek derlemesi,
model yükleme, ilk batch'lerin küçüklüğü, açılışta kuyrukta biriken
karelerin eritilmesi. Hepsi ilk dakikada.

**Bu P-22'nin tekrarı** — orada da yeniden başlatma sonrası 169 ms/kare
görülüp "GPU bozuldu" sanılmıştı. Ama orada **süre ölçülmemiş**, sadece
"soğuk başlangıç" denip geçilmişti.

**Asıl bulgu şu:** ısınma **~90 saniye** sürüyor. Bu sayı ilk kez
ölçüldü ve bir ölçüm koşulu hâline getirilmesi gerekiyor.

⚠ **Etkisi geriye dönük.** Kısa koşularla alınmış her ölçüm bu payı
taşıyor olabilir. Gün 23 değerlendirme maratonunda **ilk 90 saniye
atılmalı**, yoksa K2/K3 rakamları sistematik olarak kötümser çıkar.

**Öğrenilen ders:** "Soğuk başlangıç" bir açıklama değil, bir
**büyüklük**. P-22'de doğru teşhis konmuş ama sayıya bağlanmamıştı, o
yüzden ders uygulanabilir hâle gelmedi ve aynı tuzağa tekrar düşüldü.
Bir etkiyi fark etmek yetmiyor; **ne kadar sürdüğünü ölçüp ölçüm
protokolüne yazmak** gerekiyor. `benchmarks/` betiklerine bir "ısınma
penceresi" parametresi girmeli.

---

### P-27 · `match_thresh` sezgiye ters çalışıyor — ve kimlik parçalanmasının sebebi buydu

**Tarih:** 17.08.2026 · **Faz:** 1 / Gün 12 · **Kazanç:** tek kare yaşayan iz %10 → %4.2

**Belirti:** Biten izlerin **%20'si tek kare yaşayıp ölüyordu**, yalnızca
%15'i 5 saniyeden uzun sürüyordu. Kimlik bu kadar çabuk kopunca "bu kişi
3 saniyedir hızlanıyor" cümlesi kurulamaz — saldırganlık modülünün tek
girdisi bu (PLAN.md §6.5.2).

**Çürütülen hipotez:** "Kare hızımız düşük olduğu için kişi kareler
arasında çok yol alıyor, takipçi eşleştiremiyor."

Uyarlanabilir FPS sayesinde kameralar farklı hızlarda çalışıyordu
(1, 4, 5.7 FPS) — hazır bir doğal deney. Korelasyona bakınca:

| Hedef FPS | Ortalama parçalanma |
|---|---|
| 1.0 | %50.2 |
| 4.0 | %54.2 |
| 5.7 | %56.8 |

**Korelasyon yok.** Hipotez düştü.

**Kontrollü deney:** Aynı tespit dizisi (cam-09, 250 kare, 3341 tespit)
bir kez çıkarılıp belleğe alındı, sonra her parametre ayarı **aynı
diziyi** işledi. Tek değişen parametre; sahne, kalabalık ve kare hızı
sabit.

| Ayar | tek kare | uzun ömürlü | kimlik kapsamı |
|---|---|---|---|
| varsayılan (`match_thresh` 0.8) | %10.0 | %50.9 | %90.7 |
| **0.9** | **%4.2** | **%61.1** | **%93.3** |
| 0.6 | %61.6 | %8.3 | %68.3 |
| 0.9 + `new_track_thresh` 0.7 | %2.9 | %66.7 | %79.7 |

**Kök sebep — isimlendirme tuzağı.** `match_thresh` bir **benzerlik**
eşiği gibi duruyor ama aslında **mesafe** eşiği. Ultralytics kaynağında:

```python
return 1 - ious          # cost matrix
...
linear_assignment(dists, thresh=match_thresh)   # eşleşme: maliyet < eşik
```

Yani:

```
match_thresh 0.9  →  1 - IoU < 0.9  →  IoU > 0.1  →  GEVŞEK
match_thresh 0.6  →  1 - IoU < 0.6  →  IoU > 0.4  →  SIKI
```

Varsayılan 0.8 (IoU > 0.2) bizim kare hızımız için fazla sıkıymış:
4 FPS'te kareler arası 250 ms var ve yürüyen bir kişinin ardışık iki
kutusu %20 örtüşmeyi zor yakalıyor. Eşleşemeyen iz ölüyor, kişi yeni
kimlik alıyor.

⚠ **İlk ölçümde etiketleri TERS yazdım** — 0.9'a "sıkı", 0.6'ya "gevşek"
demiştim. Sonuç tablosu anlamsız görünüyordu ("sıkılaştırınca düzeliyor,
gevşetince bozuluyor"). Kaynak koda bakıp maliyet fonksiyonunu görene
kadar açıklayamadım. **Sayı doğruydu, yorum yanlıştı** — ve öyle
raporlasaydım rapora yanlış bir çıkarım girecekti.

**Çözüm:** `match_thresh` 0.8 → 0.9.

`new_track_thresh` 0.7 parçalanmayı daha da düşürüyor (%2.9) **ama
alınmadı**: kimlik kapsamı %93 → %80'e iniyor, yani tespitlerin beşte
biri hiç kimlik alamıyor ve zamansal analizin tamamen dışında kalıyor.
Kaybedilenler düşük güvenli, yani uzaktaki kişiler — P-14'te tam da
onları kurtarmıştık.

**Öğrenilen dersler:**

1. **Bir eşiğin YÖNÜNÜ varsayma, kaynağa bak.** "thresh" adı benzerlik
   mi mesafe mi söylemiyor. Beş dakikalık kaynak okuması, yanlış bir
   raporu önledi.
2. **Tek metriğe bakarak ayar seçme.** Parçalanma tek başına bakılsaydı
   `new_track_thresh 0.7` "en iyi" görünürdü; gizli bedeli kimlik
   kapsamıydı. Her ayar için "bu neyi kötüleştiriyor" diye ayrı bir
   sütun gerekiyor.
3. **Hipotezi doğal deneyle test et.** Kare hızı hipotezini çürüten şey,
   uyarlanabilir FPS'in kameraları zaten farklı hızlarda çalıştırıyor
   olmasıydı — ek bir düzenek kurmadan korelasyona bakmak yetti.

---

### P-26 · Hizalama kaydırıcısı TERS yönde çalışıyormuş + zaman ekseni yanlıştı

**Tarih:** 17.08.2026 · **Faz:** 1 / Gün 11 · **Tür:** mantık hatası, ölçümle yakalandı

**Belirti:** Gecikme 1212 → 465 ms'e düşürüldükten sonra bile kullanıcı
kutuların yürüyen kişinin arkasından geldiğini ve **takıldığını**
bildirdi: *"bazen takip ediyor yetişiyor, bazen edemiyor."*

**İki ayrı hata vardı.**

**Hata 1 — kaydırıcının yönü ters.**

Zaman eksenini yazınca ortaya çıktı:

```
video  : sahneyi  now − 13 ms   anında gösteriyor  (WebRTC çok hızlı)
analiz : sonuç    now − 465 ms  anına ait
```

Kod `now − offset` anını çiziyordu. Yani kaydırıcıyı artırmak kutuları
**daha da geriye** alıyordu. 250 ms ayarındayken kutular aslında
`now − 250 − 465 = now − 715 ms` anını gösteriyordu — kullanıcı
düzeltmeye çalışırken sorunu büyütüyordu.

Doğrusu tam tersi: analiz zaten geride olduğu için kutuların **ileri
tahmin edilmesi** gerekiyor. Kaydırıcı artık "ne kadar ileri tahmin
et" anlamına geliyor.

**Hata 2 — tampon varış anına göre indeksleniyordu.**

Ara değerleme, sonuçların **tarayıcıya varış** zamanına (`rx`) göre
yapılıyordu. Ama boru hattı gecikmesi sabit değil (181-465 ms arası
dalgalanıyor), dolayısıyla **düzenli aralıklarla yakalanan kareler
düzensiz aralıklarla varıyor.**

Örnek — ikisi de 250 ms arayla yakalanmış:

| | yakalanma | gecikme | varış |
|---|---|---|---|
| kare 1 | 1000 | 400 ms | 1400 |
| kare 2 | 1250 | 200 ms | 1450 |

Varış farkı **50 ms**, gerçek fark **250 ms**. Varışa göre hesaplayan
kod kişiyi 5 kat hızlı sanıyor, kutuyu fırlatıyor, sonraki karede geri
çekiyor. Kullanıcının gördüğü "takılma" tam olarak buydu.

**Çözüm:** Sunucu her sonuca ölçtüğü gecikmeyi ekliyor (`lat`), böylece
yakalanma anı hesaplanabiliyor:

```
yakalanma ≈ varış − gecikme
```

Tampon bu eksene göre işleniyor. Gecikme dalgalansa da kareler arası
mesafe gerçek kalıyor.

**Doğrulama (7 birim testi):** yakalanma anı hesabı, tahmin yokken tam
sonuç, 450 ms ileri tahmin, bayatlamış sonucun ilerlemeye devam etmesi,
üst sınır (700 ms), ve kritik olan: *gecikme dalgalanması kareler arası
gerçek mesafeyi bozmuyor.*

**Öğrenilen ders:** Zamanla ilgili bir hata ayıklarken **önce zaman
eksenlerini yazmak** gerekiyor. Burada üç ayrı an vardı (yakalanma,
varış, çizim) ve kod ikisini karıştırıyordu. Eksenleri kağıda dökene
kadar "gecikmeyi düşürelim" diye yanlış yerde uğraştım — gecikme
gerçekten yüksekti ve düşürmek doğruydu (P-25), ama takılmanın sebebi
o değildi.

İkinci ders: bir kontrolün **yönünü** de test etmek gerekiyor.
Kaydırıcı çalışıyordu, değer değişiyordu, ama ters yöne. Kullanıcı
"değiştirdim, bir şey olmadı" dediğinde bu ihtimali baştan
düşünmeliydim.

---

### P-25 · "Eski kare değersizdir" ilkesini tüketici tarafında hiç uygulamamışız

**Tarih:** 17.08.2026 · **Faz:** 1 / Gün 11 · **Kazanç:** gecikme 6.7× azaldı

**Belirti:** Kullanıcı kutuların insanların 2-3 adım gerisinden geldiğini
bildirdi. Panelde ölçülen değerler sorunu tek satırda gösterdi:

```
video 14 ms  ·  analiz 1212 ms
```

Video WebRTC ile neredeyse anında geliyor; analiz 1.2 saniye geriden.
Aradaki fark tam olarak kutuların gecikmesi.

**Kök sebep:** Kuyruk beklemesi. Üretici ve tüketici dengedeydi
(58 = 58 kare/sn) ama havuz sürekli doluydu — 48 slot ÷ 29 kare/sn ≈
1.65 sn azami bekleme. Denge, gecikmenin düşük olacağı anlamına
gelmiyor: **dolu bir kuyruk dengede de olsa geciktirir.**

**Asıl utanç verici kısım:** "Eski kare değersizdir, beklemek yerine
atmak doğrudur" cümlesi P-12'den beri PLAN.md'de ve kod yorumlarında
yazılı. Ama bunu yalnızca **üretici** tarafında uygulamışız (slot yoksa
kareyi at). **Tüketici** tarafında hiç uygulanmamış: kuyruğa bir kez
giren kare, ne kadar beklerse beklesin sonunda işleniyordu.

**Çözüm:** Çıkarım worker'ı artık `max_frame_age_ms`'ten (400 ms) eski
kareleri **işlemeden** atıyor, slotu hemen iade ediyor.

Neden işe yarıyor: eski kareyi işlemek iki kez zarar veriyor —
(1) sonucu zaten değersiz, (2) o sırada taze kare işlenemiyor. Atmak
ikisini de çözüyor ve sistem kendi kendini toparlıyor: birikim ne
kadar büyükse o kadar hızlı eritiliyor.

**Sonuç:**

| | Önce | Sonra |
|---|---|---|
| Gecikme p50 | 1212 ms | **181 ms** |
| Gecikme p95 | 4438 ms | **293 ms** |
| Azami gecikme | sınırsız | **317 ms** |
| Ortalama batch | 8.0 (doygun) | 4.8 (pay var) |
| Verim | 57 kare/sn | 58 kare/sn (değişmedi) |
| Bedel | — | karelerin **%0.7'si** atılıyor |

**Öğrenilen ders:** Bir ilkeyi yazmak onu uygulamak değildir. "Eski
kare atılır" kuralımız vardı, kod yorumlarında tekrar tekrar
geçiyordu, ama boru hattının **yarısında** hiç kod karşılığı yoktu.
Bir mimari kural yazdığında, o kuralın **her sınırda** nerede
uygulandığını göstermek gerekiyor — yoksa kural belge olarak var,
sistemde yok.

İkinci ders: **gecikmeyi sınırlayan bir mekanizma yoksa gecikme
sınırsızdır.** Denge (üretim = tüketim) yeterli değil; dolu bir kuyruk
dengede de gecikme üretir. Azami gecikme ancak açıkça bir yerde
kesilirse bağlanır.

---

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
### P-60 · ⭐⭐ "Açıklanamayan p95 değişkenliği" — üç ayrı sebebi vardı, üçü de ölçüm aracında

**Tarih:** 09.09.2026 · **Faz:** 3

**Neden bakıldı:** P-58 kapanırken dürüst bir açık bırakılmıştı:

> *"Düzeltmeden sonraki iki koşu arasında değişkenlik yüksek:
> p50 172.50 vs 247.66 ms. İkisinde de CPU aynı (%402), GPU %35,
> çıkarım kapasitesi 410 kare/sn (28 yapıyor). **Hiçbir kaynak dolu
> değil.** Muhtemel aday: sistem RAM'i %90."*

RAM hipotezi test edilmeden önce, **iddiayı taşıyan sayının kendisi**
kontrol edildi. İyi ki edilmiş.

---

#### 1. 🔴 Sayı, ölçüm penceresinin değil worker'ın TÜM ÖMRÜNÜN p95'iydi

`measure_canli.py` yüzdeliği doğrudan Prometheus histogramından
alıyordu:

```python
k = _kovalar(o, "sentinel_end_to_end_latency_seconds")
veri["gecikme_p50_ms"] = (_yuzdelik(k, 0.50) or 0) * 1000
```

Prometheus histogramı **kümülatif**: süreç başından beri her şeyi
sayar. Yani bildirilen p50/p95, ölçüm penceresinin değil, worker'ın
**başlangıcından o ana kadarki** dağılımıydı.

İki sonucu vardı:

1. **Sonuç, worker'ın ölçümden önceki uptime'ına bağlıydı.** Yeni
   başlatılmış bir worker'da ısınma kütlenin büyük kısmıydı; saatlerdir
   koşan birinde seyrelmişti. Aynı sistem, aynı kod, **farklı sayı**.
2. ⭐ **`--isinma` bayrağı yalan söylüyordu.** Attığı şey ilk 90
   saniyenin *örnekleriydi*; ama o saniyelerin gecikmeleri histogramda
   sonsuza dek kalıyordu. P-28 tam da bunu engellemek için yazılmıştı.

⚠⚠ **`measure_k4.py` bunu DOĞRU yapıyor** — içinde `_kova_farki` adlı
bir fonksiyon var ve docstring'i sebebi açıkça yazıyor. `measure_canli.py`
ondan **sonra** yazıldı ve düzeltmeyi devralmadı.

> ⭐ Düzeltme koda değil, **bir dosyaya** konmuştu. Bir sonraki dosya
> aynı hatayı sıfırdan yaptı.

⭐ Daha ince bir ayrıntı: aynı betik **verim** sayılarını (`analiz_kare`,
`kare_yayinlandi`) fark alarak doğru hesaplıyordu. Yani hata unutkanlık
değil, **iki metrik tipini (sayaç vs histogram) aynı sanmak**tı.

---

#### 2. ⭐ Arşivlenmiş 8 koşuya bakılınca: değişkenlik rastgele DEĞİLDİ

"Açıklanamayan değişkenlik" diye kaydedilen sayılar sıralanınca
p50 ile analiz FPS'i neredeyse mükemmel ters korelasyonda çıktı:

```
kosu         fps    p50     p95  ANALITIK%   ALIM%  toplam%  ram%
0908-1443   1.66    450     739     1138.9   295.9   1525.1   84.4
0908-1459   1.67    455     723     1039.6   290.9   1420.6   87.9
0909-0842   1.69    454    1047     1005.0   305.3   1401.5   90.1
0909-0913   1.62    457    1075      821.3   327.1   1235.7   81.2
0909-0853   2.75    149     477       70.7   185.5    344.3   86.2   (model KAPALI)
0909-0924   2.68    172     424       96.7   197.1    382.0   89.4
0909-1003   2.84    181     634       91.7   190.4    370.9   76.1
0909-0936   1.42    248     726       55.4   275.2    416.0   90.4   ⬅ AYKIRI
```

⭐ **İki ayrık rejim var, aralarında hiçbir şey yok:**

| rejim | ANALITIK CPU | analiz FPS | p50 |
|---|---|---|---|
| BLAS düzeltmesi YOK | 821–1139% | 1.62–1.69 | ~455 ms |
| BLAS düzeltmesi VAR | 55–97% | 2.68–2.84 | 149–181 ms |

Yani "değişkenlik" sanılan şeyin çoğu, **farklı kod sürümlerinin
karşılaştırılmasıydı.** P-58'in kendi tablosundaki 149 ms'lik koşu ise
`skor_ureten_kamera: 0` — yani **model KAPALI kontrol koşusu**, bir
tekrar değil.

> ⭐ Denetimde yazdığım cümle burada kendi başıma geldi:
> *"Hiçbir kriter aynı kod sürümünde ölçülmedi."*

---

#### 3. ⭐⭐ Geriye TEK aykırı koşu kaldı — ve PID'leri aynıydı

`0909-0936` (fps 1.42) ile `0909-1003` (fps 2.84) karşılaştırılınca:

```
                   0936      1003
alim   pid        11740     11740   ⬅ AYNI SÜREÇ
cikarim pid       13408     13408   ⬅ AYNI SÜREÇ
analitik pid      19768     19768   ⬅ AYNI SÜREÇ
analiz FPS         1.42      2.84
alim CPU %        275.2     190.4
cikarim RSS MB   2982.0    1070.0
sistem RAM %       90.4      76.1
```

**Hiçbir şey yeniden başlatılmadı, kod değişmedi, ölçüm aracı aynıydı
— verim iki katına çıktı.** Değişen tek şey bellek baskısı.

Bu, P-58'in RAM hipotezini destekliyor ama **kanıtlamıyor**: iki koşu,
tek gözlem. Kontrollü tekrar gerekiyor.

---

#### 4. ⭐⭐⭐ Kareler nereye gidiyor — ölçen metrik VARDI, kimse okumuyordu

Bütün koşularda `ornekleme_fps` sabit (2.72–2.84) ama `analiz_fps`
1.42 ile 2.84 arasında. Aradaki kareler bir yere gidiyor. `no_slot`
atılma sayısı ise **rejimden bağımsız** sabit (183–263) — yani
paylaşımlı bellek havuzu suçlu değil.

Kalan tek yol: kareler **sınırlı akışın (`maxlen`) kuyruğundan
düşüyor.** `frames_dropped_total` bunu saymıyor, çünkü kayıp alım
tarafında değil, Valkey akışının kuyruk sonunda oluyor.

⭐⭐ Ve bunu ölçen metrik **Gün 1'den beri yayınlanıyordu**:

```python
# src/sentinel/metrics.py
queue_depth = Gauge("sentinel_queue_depth",
                    "Kuyruktaki mesaj sayısı — geri basınç göstergesi",
                    ["queue"])
# ingest/worker.py:491 ve inference/worker.py:832-833 → set ediliyor
```

**Hiçbir ölçüm betiği okumuyordu** — ne `measure_k4.py` ne
`measure_canli.py`. Sistemin en önemli geri basınç göstergesi
üretiliyor, Prometheus'a gidiyor, ve karar veren hiçbir araç bakmıyordu.

> ⭐ P-40'ın (panel kare yerine kişi sayıyordu) kardeşi: orada alet
> **yanlış** ölçüyordu, burada alet **doğru** ölçüyor ama **kimse
> bakmıyor**. İkisinin sonucu aynı: körlük.

---

#### Yapılan düzeltmeler — `measure_canli.py`

1. `_kova_farki()` eklendi; yüzdelik artık pencerenin **iki ucu
   arasındaki farktan** alınıyor → sonuç uptime'dan bağımsız, `--isinma`
   gerçekten çalışıyor.
2. `queue_depth` ve `shm_slots_free` okunuyor, medyan+azami raporlanıyor.
3. ⭐ **Kare muhasebesi** eklendi: `yayınlanan − analiz edilen =
   izlenmeyen kayıp`. %5'i aşarsa uyarı basıyor. Bu fark daha önce
   hiçbir yerde yazılmıyordu.
4. `pipeline_capacity` okunuyor; gecikme örneği sayısı (pencere içi)
   raporlanıyor — az örnekte yüzdelik gürültülü, artık görünüyor.

---

#### ✅ SONUÇ — düzeltilmiş araçla üç kontrollü koşu

Aynı worker süreçleri, aynı kod, arka arkaya üç ölçüm (her biri 400 sn,
150 sn ısınma atıldı, panel kapalı):

| koşu | p50 (ms) | p95 (ms) | analiz FPS | yayın | analiz | izlenmeyen |
|---|---|---|---|---|---|---|
| 1 | 172.5 | 321.9 | 2.78 | 13 049 | 13 050 | ~0 |
| 2 | 177.5 | 392.6 | 2.78 | 13 101 | 13 093 | 8 |
| 3 | 177.4 | 396.0 | 2.82 | 13 235 | 13 197 | 38 |

```
p50 yayılım : 172.5 – 177.5   (%2.8)    ⬅ eskiden 149 – 457
p95 yayılım : 321.9 – 396.0   (%20.0)   ⬅ eskiden 423 – 1075
```

⭐ **"Açıklanamayan değişkenlik" büyük ölçüde ölçüm aracındaydı.** p50
artık %3'lük bir bantta. Kalan %20'lik p95 yayılımı 13 bin örneklik bir
**kuyruk istatistiği** için olağan örnekleme gürültüsü — açıklanacak bir
gizem değil, `p95`'in doğası.

⚠ **RAM hipotezi test edilemedi ve ASKIDA kalıyor.** Üç koşunun üçünde
de sistem RAM'i %83-85'teydi; %90 eşiğine hiç çıkılmadı, dolayısıyla o
rejim yeniden üretilemedi. Dürüst ifade: *"Ölçüm aracı düzeltildikten
sonra %83-85 RAM'de değişkenlik kalmadı; %90'da gözlenen tek seferlik
verim düşüşü doğrulanamadı da çürütülemedi de."*

⚠ **Kare kaybı hipotezi ÇÜRÜDÜ.** "Kareler sınırlı akışın kuyruğundan
düşüyor" diye tahmin etmiştim; muhasebe eklenince kayıp **%0.3'ün
altında** çıktı. Sağlıklı rejimde kayıp yok. Örnekleme 2.77 iken analiz
1.42 ölçülen koşu, yalnızca **bozuk rejime** ait.

#### ⚠ Bu kaydın kendi sınırı — dürüstçe

**Öğrenilen ders (P-58'in dersinin devamı):** Bir ölçümde
"açıklanamayan değişkenlik" varsa, aranacak ilk yer sistem değil
**ölçüm aracıdır**. Bu projede dokuzuncu kez.

Ve bu sefer yeni bir tür: **düzeltme yapıldı ama taşınmadı.** P-28'in
çözümü `measure_k4.py`'da duruyordu; sonraki betik aynı hatayı sıfırdan
yaptı. Bir düzeltmenin gerçekten yapılmış sayılması için, aynı hatayı
yapabilecek **diğer yerlere de** taşınması gerekiyor.


---

### P-61 · ⭐⭐ `decode_duration` düzeltildi — ve düzeltmenin kendisi iki yeni şey buldu

**Tarih:** 09.09.2026 · **Faz:** 3

**Neden bakıldı:** P-56'da not düşülmüştü: *"`decode_duration` çözme
süresini değil kareler arası BEKLEMEYİ ölçüyor."* Kayıt vardı, düzeltme
yoktu.

---

#### 1. Hata: metrik kendi ayarımızı ölçüyordu

```python
last = time.perf_counter()          # önceki karenin İŞİ BİTTİĞİNDE
for frame in decoder.frames():
    now = time.perf_counter()       # yeni kare GELDİĞİNDE
    decode_duration.observe(now - last)
```

Aradaki süre çözme işi değil, **bir sonraki karenin gelmesini bekleme**
süresi. Ve o bekleme, hedef FPS'in belirlediği kare aralığıyla tanımlı:
2.75 FPS'te ~360 ms. Yani metrik, çözücünün maliyetini değil **kendi
örnekleme ayarımızı** raporluyordu. Kova tavanı 0.25 sn olduğu için de
gözlemlerin neredeyse tamamı `+Inf`'e düşüyordu — histogram hiçbir
şekilde okunamıyordu bile.

⭐ 17 gün panoda durdu. Sayı **makul** göründüğü için kimse bakmadı.

#### 2. ⚠ Doğrusunu duvar saatiyle yapmak da mümkün DEĞİLDİ

İlk düzeltme denemem, çözmeyi `perf_counter` ile ölçmekti. Yanlış olurdu:
`container.decode()` ağdan veri beklerken **bloke oluyor**, yani ölçüm
yine beklemeyi içerirdi — hata bir kat aşağıda tekrarlanmış olurdu.

Çözüm P-58'in dersinden geldi: **duvar saati ≠ CPU zamanı.**
`time.thread_time()` yalnızca o iş parçacığının harcadığı CPU'yu sayar;
bloke geçen süre girmez. Kamera başına bir iş parçacığı olduğu için
ölçtüğümüz şey tam olarak "bu kameranın çözme işi".

İki yeni sayaç: `sentinel_decode_cpu_seconds_total` (her çözülen kare —
örneklemeyle atılanlar dâhil, çünkü decode bedeli yine ödeniyor) ve
`sentinel_bgr_cpu_seconds_total` (yalnızca yayınlanan kareler). Eski
metrik silinmedi, **adı dürüst hale getirildi**:
`sentinel_frame_interval_seconds` — sayının kendisi işe yarıyor,
yanlış olan adıydı.

#### 3. ⭐⭐ İLK ÖLÇÜM: çözme, alım worker'ının CPU'sunun yalnızca %5'i

20 kamera, ~600 sn, üretim koşusu:

```
örneklenen kare başına  : çözme 1.58 ms + BGR 1.61 ms CPU
20 kamera bütçesinde    : çözme 0.118 + BGR 0.121 = 0.239 çekirdek
alım worker'ının ölçülen toplamı            : 2.10 çekirdek
                                              ─────────────
çözme + BGR'nin payı                        : %11
çözmenin tek başına payı                    : %5.6
```

⭐ **BGR renk dönüşümü, H.264 çözmekle neredeyse aynı pahada** (1.61 vs
1.58 ms). Bu ikisini ayrı ölçmenin pratik değeri şu: örnekleme hızını
düşürmek **decode bedelini düşürmüyor** (her kare yine çözülüyor) ama
**BGR bedelini doğrudan düşürüyor**. Yani uyarlanabilir FPS'in
kazandırdığı şeyin yarısı buradaydı ve daha önce hiç ayrıştırılmamıştı.

⭐ Ve "decode darboğaz" iddiası (P-07/P-09'da zaten çürütülmüştü) artık
**sayıyla** kapandı: alım worker'ının 2.1 çekirdeğinin 0.12'si çözme.
Geri kalanı hareket filtresi, letterbox ön işleme ve paylaşımlı bellek
yazımı.

⚠ **Bu sayının sınırı:** Windows'ta iş parçacığı CPU çözünürlüğü
~15.6 ms; tek bir çözme parçası ~0.17 ms. Sayaç monoton biriktiği için
**toplam** güvenilir, ama çözme/BGR arasındaki payın kesinliği bu
çözünürlükle sınırlı. Büyüklük mertebesi sağlam, virgülden sonrası
değil.

#### 4. ⭐ Yan bulgu: `fflags=nobuffer` dosya çözmeyi TAMAMEN bozuyor

Dekoderin testi yazılırken çıktı: aynı mp4, canlı akış seçenekleriyle
**0 kare** çözüyor, seçeneksiz 45 kare. Beş seçenek tek tek çıkarıldı,
suçlu tek başına `nobuffer`:

```
çıkarılan: rtsp_transport -> 0 kare        çıkarılan: fflags -> 45 kare ✅
çıkarılan: timeout        -> 0 kare        çıkarılan: flags  -> 0 kare
çıkarılan: max_delay      -> 0 kare        TAM SET            -> 0 kare
```

`nobuffer` ve `low_delay` canlı akışta gecikme kırpmak için var; dosyada
yıkıcı. Seçenekler artık yalnızca ağ kaynaklarına uygulanıyor. Üretim
yalnızca `rtsp://` kullandığı için **üretim davranışı değişmedi** — ama
dekoder ilk kez gerçek bir videoyla test edilebilir hale geldi.

#### 5. ⚠ Testin kendisi de bir kez yanlış yazıldı — ve ölçülerek yakalandı

İlk yazdığım test docstring'inde *"bu test eski kodda düşerdi"* diyordu.
Ölçünce yanlış çıktı:

```
duvar saati toplam      :  554.4 ms
ESKİ metrik toplasaydı  :   46.3 ms   ⬅ küçük!
YENİ çözme CPU          :   15.6 ms
```

Sebep: eski metriğin şiştiği yer **canlı akışın tempo sınırı**. Yerel
dosyada sonraki kare anında hazır — bekleme yok, eski metrik de küçük.
Yani birim testi üretimdeki hatayı **yeniden üretemez**.

> ⭐ Test etmediği şeyi test ettiğini söyleyen bir test, yanlış bir
> sayıdan daha tehlikelidir: yeşil yanar ve soru sordurmaz. P-49'un
> (ölçütün TANIMI yanlıştı) birim testi kılığındaki hâli.

Test, kanıtlayabildiği şeye daraltıldı: **atıf sınırı** — tüketicinin
harcadığı CPU çözmenin hanesine yazılmamalı. Sonra kod bilerek bozulup
testin gerçekten yakaladığı doğrulandı:

```
`yield` sonrası CPU işareti kaldırıldı
  -> çözme CPU'su 328 ms okundu (tüketicinin yaktığı 300 ms dâhil)
  -> test DÜŞTÜ ✅
```

**Öğrenilen ders:** Bir testin geçmesi, bir şey doğruladığı anlamına
gelmiyor. Yeni yazılan her kritik test, **kodu bilerek bozup**
düştüğü görülerek kabul edilmeli.

---

### P-62 · ⭐⭐ İki saattir kimsenin bakmadığı 180 analiz sonucu

**Tarih:** 09.09.2026 · **Faz:** 3

**Neden bakıldı:** P-60'ta eklenen `consumer_lag` metriği doğrulanırken
`XPENDING` de okundu. Beklenen: birkaç kayıt. Görülen:

```
bekleyen kayıt : 180   (hepsi `analytics-0` tüketicisinde)
boşta kalma    : en az 737 ms
                 medyan 7 427 130 ms  ≈ 2 saat 4 dakika
                 en çok 9 924 258 ms  ≈ 2 saat 45 dakika
```

**Mekanizma:** `XREADGROUP` ile okunan her kayıt, ACK gelene kadar o
tüketiciye **asılı** kalıyor. Analitik worker sert kapatılırsa (kill,
çökme, `stop_all`) elindeki kayıtlar asılı kalıyor. Yeni worker `>` ile
yalnızca YENİ kayıtları okuduğu için o kayıtlar **sonsuza dek
işlenmiyor**.

Arıza tam anlamıyla sessiz: worker ayakta, akış akıyor, sayaçlar
artıyor, panel çalışıyor — yalnızca o 180 sonuç hiç analiz edilmiyor.

⭐⭐ **Bu, P-38'in birebir aynısı — bir akış aşağıda.** P-38'de bir
çökme, paylaşımlı bellek slotlarını kalıcı sızdırıyordu ve çözümü
`FrameStream.sahipsizleri_topla()` (XAUTOCLAIM) idi. O düzeltme
**kare akışına** yazıldı, docstring'i sebebini üç paragraf anlattı —
ve **sonuç akışına hiç taşınmadı.**

> ⭐ P-60 ile aynı ders, aynı gün, ikinci kez: **bir düzeltmenin bir
> yerde yapılmış olması, onu diğerinde yapılmış saymıyor.** Bu sefer
> düzeltmenin kendi docstring'i, taşınması gereken yeri tarif ediyordu.

**Çözüm:** `AnalyticsWorker._sahipsizleri_topla()` — 30 saniyede bir
(budama ile aynı periyot) `XAUTOCLAIM` ile sahipsiz kayıtları geri alıp
işliyor. MAXLEN ile akıştan düşmüş ama hâlâ asılı kayıtlar (boş alanla
dönerler) ACK'lenip listeden düşürülüyor.

⚠ **Etkisinin büyüklüğü küçük, sınıfı büyük.** 180 kayıt ~3 saniyelik
analiz demek; kimse fark etmezdi. Ama mekanizma sınırsız: her sert
kapanış kalıcı bir tortu bırakıyordu ve hiçbir şey onları temizlemiyordu.


---

### P-63 · ⭐⭐⭐ Bir DENEY, üretim modelinin üzerine yazmıştı — bir gün fark edilmedi

**Tarih:** 09.09.2026 · **Faz:** 3

**Neden bakıldı:** Birleşim iddiasına (AUC 0.968) bootstrap eklenip
betik yeniden koşuldu. Beklenen: aynı sayılar + güven aralıkları.
Görülen:

```
                    08.09'daki      09.09'daki
iskelet (LightGBM)     0.9267          0.836    ⬅ 0.09 DÜŞMÜŞ
video (R3D-18)         0.9366          0.937    ⬅ aynı
ortalama               0.9684          0.950
```

Video modeli aynı, iskelet yolu düşmüş. Aynı betik, aynı val kümesi,
aynı özellik dosyası. Değişen tek şey **model dosyası**.

---

#### Kök sebep: FPS taraması üretim yapıtını beş kez ezdi

`deney_fps.py`, FPS eğrisini çıkarmak için `train_aggression.py`'ı beş
kez alt süreçte çağırıyor (2.75 / 4.00 / 8.25 / 16.50 / 24.75 FPS). Her
çağrı sonunda tek bir satır koşuyordu:

```python
model.booster_.save_model(str(MODEL_DOSYASI))   # models/saldirganlik_lgbm.txt
```

Yani **beş model, tek dosya**. Üretimde kalan, döngünün en son
bitirdiği modeldi. Eğitim JSON'ları zaman sırasına dizilince eşleşme
kesin:

| sıra | FPS | deney AUC | eğitim JSON AUC |
|---|---|---|---|
| 1 | 2.75 (üretimin hızı) | 0.906 | 0.9057 |
| 2 | 4.00 | 0.903 | 0.9026 |
| 3 | 8.25 | 0.936 | 0.9359 |
| 4 | **16.50 (en iyi)** | **0.949** | 0.9487 |
| 5 | **24.75** | 0.918 | **0.9184 ⬅ SON YAZAN** |

⭐⭐⭐ **Üretimde 24.75 FPS'te eğitilmiş bir model oturuyordu.** En
iyisi (16.50) değil; üretimin kendi hızı (2.75) hiç değil. Seçilmiş bile
değildi — sadece döngünün son adımıydı.

#### Neden önemli: eğitim/servis kare hızı uyuşmazlığı

Özellikler **5 saniyelik pencere** üzerinde hesaplanıyor. Kare hızı
değişince pencerenin içindeki kare sayısı değişiyor ve hız/ivme
türevleri sistematik olarak kayıyor. Yani model, eğitildiğinden farklı
bir dağılımla besleniyordu.

Bedeli ölçüldü — aynı 96 klip, aynı özellikler, yalnızca model farklı:

```
2.75 FPS modeli  (doğru)  : AUC 0.927 · F1 0.889
24.75 FPS modeli (yanlış) : AUC 0.836
                            ─────────
                            −0.091 AUC
```

⚠ **Mevcut sütun kontrolü bunu yakalayamazdı.** Kod zaten
`booster.num_feature() != len(sutunlar)` kontrolü yapıyor — ama beş
varyantın hepsi **99 sütun** üretiyor. Uyuşmazlık sayıda değil,
**dağılımda**. Yapısal kontroller dağılım hatalarını görmez.

#### ⚠ Ve arıza tam anlamıyla sessizdi

Model yükleniyordu. Sütun sayısı doğruydu. Skor üretiyordu (18/20
kamerada, medyan 0.075). Alarm da üretiyordu. Canlı doğrulama betiği
"✅ Model canlıda skor üretiyor" diyordu — **ve doğru söylüyordu.**
Üretilen skorların yanlış modelden geldiğini gösteren hiçbir sinyal
yoktu.

> ⭐ "Çalışıyor" ile "doğru çalışıyor" arasındaki farkı hiçbir sağlık
> kontrolü göstermiyordu. Model dosyası **kendisinin ne olduğunu
> söylemiyordu.**

#### Üç ayrı düzeltme

**1. Deney artık üretim yapıtına dokunmuyor.** `train_aggression.py`'a
`--model-cikti` eklendi; `deney_fps.py` her FPS için `models/_deney/`
altına yazıyor. Bir araştırma aracı üretim durumunu değiştirmemeli.

**2. Modelin yanına KÜNYE yazılıyor** (`saldirganlik_lgbm.kunye.json`):
hangi özellik dosyası, hangi kare hızı, kaç klip, AUC/F1. Model dosyası
artık kendisinin ne olduğunu söylüyor.

**3. Üretim yüklerken künyeyi DOĞRULUYOR** (`analytics/model.py ·
_kunye_dogrula`). Üretimde doğrulandı:

```
[info] saldirganlik_modeli_yuklendi        ozellik=99
[info] saldirganlik_model_kunyesi_uyumlu   egitim_fps=2.75 uretim_bandi=1.0-8.0
```

⚠ **Neden hata değil uyarı, ve neden "bant":** ilk yazdığım kontrol
`settings.target_fps` (4) ile eşitlik arıyordu ve **yanlış alarm
verecekti** — üretim kapasite sınırı yüzünden ~2.75'te koşuyor,
hareketsiz kamerada 1'e iniyor. Üretimin tek bir kare hızı yok, bir
**bandı** var (`target_fps_idle` … `target_fps_high_risk` = 1–8). Doğru
soru "eşit mi" değil "bandın içinde mi". 24.75 bandın çok dışında,
2.75 içinde.

**Öğrenilen ders:** Bir deney, üretimin okuduğu hiçbir dosyaya
yazmamalı. Yazıyorsa, o dosya **kendisinin ne olduğunu söylemeli** ve
okuyan taraf **doğrulamalı**. Üçünden biri eksikse arıza sessiz olur.

⚠ **Bu kaydın asıl rahatsız edici yanı:** hata 08.09 akşamı oluştu ve
09.09'da yalnızca **başka bir iş için** (bootstrap) betik yeniden
koşulduğu için ortaya çıktı. Kimse aramıyordu. Bir gün boyunca
"üretimde öğrenilmiş model var" diye rapor edilen şey, yanlış modeldi.

---

### P-64 · ⭐⭐ Birleşim iddiası bootstrap sınavını GEÇTİ — ama kıl payı

**Tarih:** 09.09.2026 · **Faz:** 3

**Neden yapıldı:** CLAUDE.md, P-54'ü *"ilk kez bir iddia ölçülünce DOĞRU
çıktı"* diye kutluyordu: birleşim AUC 0.968 vs en iyi tek model 0.937.
Ama o sayı **96 klip** üzerindeydi ve hiç güven aralığı hesaplanmamıştı.
96 örnekte 0.031'lik bir fark gürültü de olabilirdi.

#### Yöntem: EŞLEŞTİRİLMİŞ bootstrap

10 000 tekrar. Her tekrarda 96 klip yerine koyarak yeniden örnekleniyor
ve **aynı örneklem üzerinde** iki AUC de hesaplanıp farkı alınıyor.

⚠ Eşleştirme şart: iki model **aynı kliplerde** değerlendiriliyor, yani
hataları ilişkili — "zor" klipler ikisini birden aşağı çeker. Ayrı ayrı
bootstrap'layıp aralıklara bakmak, P-41'in hatasının istatistiksel
karşılığı olurdu (kıyasta değişmemesi gereken şeyin değişmesi).

#### Sonuç

```
yöntem                    Δ AUC     %2.5    %97.5   P(Δ>0)  karar
ortalama                 +0.032   +0.001   +0.069    0.980  ✅ ANLAMLI
azami (VEYA)             +0.027   -0.007   +0.068    0.930  ❌ sıfırı içeriyor
çarpım                   +0.020   -0.006   +0.048    0.930  ❌
asgari (VE)              +0.002   -0.032   +0.033    0.529  ❌
iskelet (LightGBM)       -0.010   -0.080   +0.058    0.384  ❌
```

⭐ **İddia ayakta: ortalama birleşim, en iyi tek modelden anlamlı
biçimde iyi.** Ama alt sınır **+0.001** — sıfırın kıl payı üstünde.

**Raporda yazılacak dürüst ifade:**

> *"İki bağımsız kaynağın ortalaması, en iyi tek modelden 0.032 AUC
> daha iyi (%95 GA: +0.001 … +0.069; 10 000 eşleştirilmiş bootstrap,
> 96 doğrulama klibi). Fark istatistiksel olarak anlamlı, ancak güven
> aralığının alt sınırı sıfıra çok yakındır: bu örneklem büyüklüğü
> farkın YÖNÜNÜ desteklemekte, BÜYÜKLÜĞÜNÜ hassas biçimde
> kestirmemektedir."*

⚠ Dört birleşim kuralından yalnızca biri anlamlı. "VEYA" kuralı
gözlemde 0.964 ile çok yakın ama aralığı sıfırı içeriyor — yani
"hangi kural daha iyi" sorusu bu veriyle **cevaplanamıyor**.

#### ⭐ Kazananın laneti ölçüldü

"0.968", dört kural arasından **en iyisi** ve seçim F1'in hesaplandığı
aynı 96 klipte yapıldı. Bu tanımı gereği iyimser. Büyüklüğü ölçüldü:

```
'en iyi kural' ile ÖNCEDEN seçilmiş kural (ortalama) farkı: +0.0014 AUC
```

Küçük — çünkü "ortalama" zaten en iyilerden biri. Yine de raporda
bildirilecek sayı **önceden seçilmiş kural** olmalı, "kuralları
deneyip en iyisini aldık" değil.

#### ⭐⭐ Ve K5'in Gün 12'den beri işaretli yanlılığı SAYIYA çevrildi

CLAUDE.md şunu yazıyordu ama hiç ölçmemişti:

> *"`en_iyi_esik`, F1'in hesaplandığı aynı 120 klip üzerinde aranıyor.
> Yani bildirilen F1 optimistik."*

"Optimistik" bir uyarı; **ne kadar** olduğu bir sayı. Tekrarlı katmanlı
yarı-yarıya bölmeyle ölçüldü (eşik bir yarıda seçiliyor, F1 diğer yarıda
ölçülüyor, 400 tekrar):

```
yöntem                  F1 (aynı küme)  F1 (ayrı yarı)  iyimserlik
iskelet (LightGBM)               0.889           0.858      +0.031
video (R3D-18)                   0.911           0.883      +0.028
ortalama                         0.937           0.916      +0.020
azami (VEYA)                     0.936           0.918      +0.018
```

⭐ **K5 yanlılık düzeltmesinden SONRA da tutuyor: F1 0.916 ≥ 0.85.**
Hedefin geçilmesi eşik seçiminin bir yan ürünü değil.

⚠ Bu yöntem bir **ÜST sınır** veriyor: eşik yarım veriyle (48 klip)
seçildiği için gerçek yanlılık bundan biraz küçüktür.

**Öğrenilen ders:** Bir yanlılığı *işaretlemek* onu raporlamak değildir.
"Bu sayı optimistik" cümlesi okuyucuya karar verdirmiyor; "+0.020"
verdiriyor. Uyarılar sayıya çevrilmediği sürece dipnot olarak kalıyor.

---

### P-65 · ⭐⭐⭐ K2 neden tutmuyor: darboğaz GPU değil, TEK ÇEKİRDEK

**Tarih:** 09.09.2026 · **Faz:** 3

**Neden bakıldı:** Kullanıcının sorusu, P-63'ün üzerine geldi:

> *"Bu 24.75 FPS'lik model 20 kamerada mı çalışıyordu? Eğer 20 kamera
> için 24.75 FPS'lik bir analizimiz varsa neden onu kullanmıyoruz,
> fazla analiz daha kaliteli sonuç değil midir? Hedef 4 demiştik, bu
> 4'ü neye göre söylemişiz? Sisteme sınır mı vermişiz?"*

Üç ayrı soru ve üçünün de cevabı ölçülmemişti.

---

#### 1. Önce bir kavram düzeltmesi: "24.75 FPS modeli" canlıda hiç koşmadı

`train_aggression.py · _klip_ozellikleri` bir **video dosyasını**
`cv2.VideoCapture` ile açıyor ve kare atlıyor:

```python
adim = max(1, round(kaynak_fps / ornek_fps))   # RWF klipleri 30 FPS
```

- `ornek_fps=2.75` → adım 11 → 11 karede bir
- `ornek_fps=24.75` → adım 1 → **her kare**

Yani "24.75 FPS" = *çevrimdışı, tek klip, GPU'yu tek başına kullanarak,
5 saniyelik bir dosyanın her karesini işlemek*. 20 kameralı canlı
sistemde böyle bir analiz **hiçbir zaman olmadı**. P-63'teki hata,
canlı sistemin hızını değiştirmedi — yalnızca canlı sisteme, farklı
bir kare hızının dağılımıyla eğitilmiş bir model koydu.

---

#### 2. ⭐⭐⭐ "Kapasite" metriği kapasiteyi ölçmüyordu — ÜÇÜNCÜ kez

`sentinel_pipeline_capacity_fps` 58.5 kare/sn gösteriyordu ve
"kapasitenin %95'indeyiz" diye okunuyordu. Hesabı şu:

```python
anlik = (self.processed - self._capacity_window_processed) / pencere
```

Bu **gerçekleşen verim** — worker yetişiyorken bu sayı *gelen kare
hızına* eşit. `consumer_lag = 0` ölçüldüğüne göre worker geride
değildi, **kare bekliyordu**. Yani 58.5 bir tavan değil, **arz**.

> ⭐ Aynı hafta üçüncü kez: `decode_duration` beklemeyi ölçüyordu
> (P-61), `queue_depth` geri basıncı ölçmüyordu (P-60), şimdi de
> `pipeline_capacity` kapasiteyi ölçmüyor. Üçü de **adının vadettiğini
> ölçmeyen** metrikler.

---

#### 3. Doyma noktası ÖLÇÜLDÜ: girdiyi artırmak analizi YAVAŞLATTI

`TARGET_FPS` geçici olarak 4 → 8 yapıldı (`.env`'e dokunulmadan, ortam
değişkeniyle), aynı ölçüm tekrarlandı:

```
ölçüt                    TARGET_FPS=4   TARGET_FPS=8
örnekleme (yayınlanan)        2.78          4.37   ↑ arz arttı
ANALİZ EDİLEN                 2.78          1.88   ↓ %32 DÜŞTÜ
gecikme p50 (ms)               173           433   ↑ 2.5 kat
izlenmeyen kayıp              ~%0         %56.9   ⬅ 10 260 kare
tüketici gecikmesi (lag)         0            40   ⬅ gerçek birikme
alım CPU (çekirdek)           2.10          3.79   ↑
ÇIKARIM CPU (çekirdek)        0.89          0.89   ⬅ DEĞİŞMEDİ
sistem RAM                     %84           %92
```

⭐⭐⭐ **Çıkarım worker'ı ne verirsen ver 0.89 çekirdekte sabit
kalıyor** — ve daha çok kare verildiğinde verimi *düşüyor*.

Mekanizma: çıkarım worker'ının ana döngüsü **seri**. Tavanı bir
çekirdek. Alım katmanı daha çok kare üretince aynı çekirdekleri
paylaşan çıkarım sürecinden CPU çalıyor (alım 2.10 → 3.79 çekirdek),
ve sınırlı akış (MAXLEN) fazlalığı sessizce atıyor.

⚠ Bu mekanizma `_refresh_capacity` docstring'inde **zaten yazılıydı**:

> *"Üretimi kısmak tüketimi HIZLANDIRIYOR. Alışılmadık ama mekanizma
> net: daha az kare → daha az alım CPU'su → çıkarıma daha çok
> çekirdek."*

Yazılıydı ama **ölçülmemişti**, ve o yüzden `capacity_backpressure_enabled`
`False`'ta duruyordu. Şimdi hem ölçüldü hem büyüklüğü belli.

---

#### 4. ⭐⭐ Donanımda yer var, MİMARİDE yok

Doymuş rejimde ölçülen:

```
çıkarım worker CPU : 0.89 çekirdek   /  20 mantıksal çekirdek   ⬅ %4.5
GPU kullanımı      : %41
VRAM               : 571 MB / 8192 MB                          ⬅ %7
```

**19 çekirdek boşta, GPU'nun yarısı boşta, VRAM'in %93'ü boşta** — ve
sistem yine de 20 kamerada 2.78 FPS'te sıkışıyor.

Ve çıkarımın tek çekirdeği nereye gidiyor:

```
aşama       ms/KARE
pose           2.50
detect         1.80
track          0.22
emotion        0.06
─────────────────────
ölçülen        4.58
GERÇEK        15.2   (0.89 çekirdek / 58.5 kare-sn)
─────────────────────
ÖLÇÜLMEYEN    10.6   ⬅ %70
```

⚠ **Model çıkarımı, çıkarım worker'ının CPU'sunun yalnızca %30'u.**
Kalan %70 ölçülmüyor: Valkey okuma, paylaşımlı bellek erişimi, sonuç
JSON'unun kurulması, yayınlama, ACK, slot iadesi. Aşama histogramları
döngünün üçte birini kapsıyor.

---

#### 5. Kullanıcının sorularının cevapları — tek tek

| Soru | Cevap |
|---|---|
| Panelde 24.75 FPS'lik model mi vardı? | Evet, o model yüklüydü — ama 20 kameranın hepsi için ve **2.75 FPS'lik veriyle besleniyordu** |
| Çalışıyor muydu, kuyruğa yatıyor muydu? | Evet. Skor üretiyordu (18/20 kamera), alarm üretiyordu, panel canlıydı. Arıza tam da bu yüzden sessizdi |
| Tek kamerada mı 20 kamerada mı? | 20 kamerada. Model tek kopya, kamera başına ayrı kayan pencere |
| 24.75 FPS analizimiz varsa neden kullanmıyoruz? | **Öyle bir analizimiz yok.** 24.75 yalnızca çevrimdışı eğitim verisi hazırlama ayarıydı. 20 kamerayı 24.75 FPS'te işlemek 495 kare/sn ister; ölçülen tavan ~58 |
| "Hedef 4" neye göre? | `.env · TARGET_FPS=4`, elle yazılmış bir ayar. **Ölçüme dayanmıyordu** — ve kapasite geri basıncı (`capacity_backpressure_enabled`) `False` olduğu için gerçek bir tavan da uygulanmıyordu |
| 4'ten fazlası çalışıyorsa neden kullanmıyoruz? | Denendi (8 FPS): analiz 2.78 → 1.88 **düştü**, gecikme 2.5 kat arttı, karelerin %57'si atıldı |
| Sınır mı verdik? | İki sınır var: (a) elle yazılmış `TARGET_FPS=4`, (b) sınırlı akış `MAXLEN`. Ama **asıl sınır ikisi de değil** — çıkarım döngüsünün tek çekirdeği |

---

#### ⭐ Ve bu, P-60'ta askıda kalan RAM sorusunu da kapatıyor

P-58/P-60'ta "sistem RAM'i %90'a çıkınca verim yarıya düşüyor"
gözlemi askıda bırakılmıştı. Bu deney onu **yeniden üretti ve
açıkladı**: 8 FPS koşusunda RAM yine %92'ye çıktı ve verim yine
düştü — ama sebep RAM değil, **aşırı arzın kendisi**. Daha çok kare
= daha çok uçuşan tampon (RAM ↑) + daha çok alım CPU'su (çıkarım ↓).

RAM yükselişi bir **yan etki**, bir sebep değil. Korelasyon gerçekti,
nedensellik yanlıştı.

> ⭐ Askıda bırakılan bir soru, başka bir sorunun ölçümüyle kapandı.
> Rami bilerek şişirmek gerekmedi — doğru deney zaten başka bir
> kapıdan geliyordu.

---

#### Bu ne DEĞİŞTİRİYOR — dürüst kapsam

⚠ **Bu kayıt bir düzeltme değil, bir teşhis.** Çıkarım döngüsünü
paralelleştirmek (kare çözme/serileştirme işini ana döngüden ayırmak)
gerçek çözüm ama mimari bir değişiklik ve kalan sürede kapsam dışı.
`CLAUDE.md · ASKIDA` listesinde "boru hattı paralelleştirmesi" olarak
zaten duruyordu; artık **gerekçesi ölçülmüş** halde duruyor.

**K2 için raporda yazılacak dürüst ifade:**

> *"K2 (≥4 analiz FPS/kamera) tutmadı: ölçülen 2.78. Sebep GPU ya da
> VRAM yetersizliği değildir — ölçüm sırasında GPU %41, VRAM %7, 20
> mantıksal çekirdeğin 19'u boştaydı. Bağlayıcı kısıt, çıkarım
> worker'ının seri ana döngüsüdür: yükü ne olursa olsun 0.89 çekirdekte
> doyuyor. Örnekleme hızı 8 FPS'e çıkarıldığında analiz edilen kare
> hızı artmadı, 2.78'den 1.88'e DÜŞTÜ ve karelerin %57'si atıldı;
> çünkü artan alım yükü aynı çekirdekleri paylaşan çıkarım sürecinden
> CPU çalmaktadır. Bu, donanım değil mimari bir sınırdır ve çözümü
> boru hattının paralelleştirilmesidir."*

⭐ Bu ifade, "yetmedi" demekten çok daha güçlü: **neyin yetmediğini,
neyin boşta durduğunu ve çözümün ne olduğunu** söylüyor.

**Öğrenilen ders:** "Sistem kapasitesinin %95'inde" cümlesi, kapasiteyi
ölçtüğünü sandığın bir metrikten geliyorsa hiçbir şey ifade etmez.
Bir tavanı öğrenmenin tek yolu **ona dayanmaktır** — arzı artırıp
sistemin nerede kırıldığını görmek. Gözlemsel veri doyma noktasını
gösteremez; müdahaleli deney gösterir.

---

### P-66 · ⭐⭐⭐ "Ölçülmeyen %70 tutkal" diye bir şey YOKMUŞ — kendi bulgumu çürüttüm

**Tarih:** 09.09.2026 · **Faz:** 3

**Ne iddia etmiştim (P-65 · §4):**

> *"Model çıkarımı, çıkarım worker'ının CPU'sunun yalnızca %30'u.
> Kalan %70 ölçülmüyor: Valkey okuma, paylaşımlı bellek erişimi, sonuç
> sözlüğünün kurulması, JSON serileştirme, yayınlama, ACK, slot iadesi."*

Bu iddia **yanlıştı** ve üzerine bir mimari öneri listesi kurmuştum.

---

#### Nasıl ortaya çıktı

Kullanıcı "önce A'yı yap, o %70'i ölç" dedi. Ölçmek için eksik
aşamalara metrik eklendi — ve eklenince hesap **tutmadı**: aşamalar
6.97 ms/kare veriyordu, parti toplamı 31 ms/kare. Sonra parti toplamı
da ölçüldü, açık büyüdü.

Açığı kovalarken hata bulundu.

#### Kök sebep: AYNI METRİKTE İKİ FARKLI BİRİM

`sentinel_inference_duration_seconds` altındaki aşamalar iki farklı şey
yazıyordu:

```python
# KARE başına (mevcut aşamalar — bölüyorlar)
metrics.inference_duration.labels(stage="detect").observe(infer_s / len(batch))
metrics.inference_duration.labels(stage="pose").observe(pose_s / len(batch))

# PARTİ başına (benim eklediklerim — bölmüyorlardı)
metrics.inference_duration.labels(stage="publish").observe(_yayin / 1000.0)
metrics.inference_duration.labels(stage="serialize").observe(_seri / 1000.0)
```

İkisini aynı tabloda topladım. Üstüne bir hata daha: parti toplamını
bir zaman penceresinde, aşamaları başka bir pencerede okuyup
karşılaştırdım.

⭐ **Üç hata, üçü de bu projenin klasiği:**

| # | hata | daha önce |
|---|---|---|
| 1 | kümülatif histogramdan doğrudan ortalama | P-60 |
| 2 | iki farklı birimi toplamak | ⭐ yeni tür |
| 3 | iki farklı pencereyi karşılaştırmak | P-17, P-36 |

---

#### Düzeltilmiş ölçüm — tek pencere, fark alarak, tek birim

150 sn · 6941 kare · 1040 parti · 6.67 kare/parti · 46.3 kare/sn

```
aşama              ms/KARE   partinin %
pose                 11.64      50%      ⬅ EN BÜYÜK KALEM
detect                7.43      32%
track                 1.56       7%
publish               1.19       5%
serialize             0.59       3%
emotion               0.47       2%
slot_release          0.33       1%
shm_read              0.00       0%
────────────────────────────────────────
ölçülen aşamalar     23.22     100%
PARTİ TOPLAMI        23.26
AÇIKLANMAYAN          0.04       0%     ✅ hesap KAPANIYOR
```

⭐ **Doğrulama:** aşamaların toplamı parti toplamına 0.04 ms farkla
eşit, ve parti meşguliyeti %108 (ölçüm hatası içinde %100). Yani
döngünün tamamı açıklandı. Önceki tabloda böyle bir kapanış kontrolü
**yoktu** — olsaydı hata ilk gün görülürdü.

> ⭐⭐ **Parçaları ölçüp TOPLAMI ölçmemek, "kalan sıfırdır" demeyi
> sessizce varsaymaktır.** Toplam ölçülünce fark görünür hale geliyor
> ve ancak o zaman kovalanabiliyor. Her kırılım ölçümü bir kapanış
> kontrolü içermeli.

---

#### Gerçek tablo, ve öneri listesinin DEĞİŞMESİ

| | iddia (P-65) | ölçülen (P-66) |
|---|---|---|
| model işi (pose+detect+track+emotion) | %30 | **%91** |
| tutkal (publish+serialize+release+shm) | %70 | **%9** |

Bu, `mimari-hizlandirma.md`'deki sıralamayı ters çeviriyor:

| seçenek | P-65'e göre | P-66'ya göre |
|---|---|---|
| C · döngüyü boru hattına çevir (tutkalı örtüştür) | ⭐ büyük kazanç | ❌ **tutkal %9, tavan %9 kazanç** |
| D · tutkalı ucuzlat (msgpack, pipeline) | ⭐ değerli | ❌ **aynı sebeple değersiz** |
| B · çok worker (kamera bölüştürerek) | ⭐⭐ en iyi | ⭐⭐ **hâlâ en iyi** — iş GPU işi, süreçler paralelleşir |
| E · TensorRT | ❌ "kaldıraç değil, %3" | ⭐ **yeniden değerli: detect+pose bütçenin %82'si** |

⚠ **TensorRT hakkındaki "kaldıraç değil" cümlem de aynı yanlış tablodan
türemişti.** `detect` bütçenin %3'ü sanılıyordu; ölçülen **%32**. Poz
da eklenince hızlandırılabilir GPU işi **%82**. ADR-0006 yeniden
değerlendirilmeli.

⭐ Ve asıl hedef netleşti: **poz tek başına bütçenin yarısı.** Kaldıraç
sırası artık `pose > detect >> diğer her şey`.

---

**Öğrenilen ders:** Bir ölçüm aracı eklerken **birimi metriğin adına
yazmak** gerekiyor. `stage="publish"` iki farklı şeyi ifade edebilir
ve etti. Bu yüzden yeni aşamalar kare başına normalize edildi ve
`parti_TOPLAM` ile `bekleme_IS_DEGIL` adları birimi/anlamı ada
gömüyor — okuyan bir daha aynı hatayı yapmasın diye.

⚠ Ve daha rahatsız edici olan: yanlış tablo bir **öneri listesi**
doğurmuştu ve o liste commit'lenmişti. Ölçüm hatası yalnızca bir sayıyı
değil, **verilecek kararı** bozuyordu. Kullanıcı "önce ölç" demeseydi
bir günü yanlış seçeneği (C) kovalayarak geçirecektik.


---

### P-67 · ⭐⭐⭐ Çok worker'lı bölüştürme ÖLÇÜLDÜ — ve ilk uygulamam karelerin yarısını yok etti

**Tarih:** 09.09.2026 · **Faz:** 3

**Fikir kullanıcınındı:**

> *"Bu çıkarım worker'ı sadece tek çekirdekte çalışıyor ve 20 kameradan
> da çıkarım yapıyorsa, ilk 4 kameranın çıkarımını 1 çekirdeğe, sonraki
> 4 kamerayı başka bir çekirdeğe diyerekten 20 kamerayı 5 çekirdeğe
> paylaştırsak nasıl olur?"*

Doğru fikir, doğru gerekçe. P-65/P-66 tam da bunu gösteriyordu: çıkarım
worker'ı **0.89 çekirdekte** doyuyor, GPU %41'de, VRAM %7'de, 19
çekirdek boşta.

---

#### 1. Önce engel sanılan kural: mimari kural 3 ÇÜRÜDÜ

> *"Modeller tek süreçte tek kopya. 4 worker × 4.6 GB = VRAM patlar."*

Bu sayı **hiç ölçülmemişti**. Ölçüldü:

```
tek worker  :  571 MB / 8192 MB   (PyTorch'un ayırdığı 415 MB)
iki worker  : 1134 MB / 8192 MB   → worker başına 567 MB
```

**4.6 GB varsayımı 8 kat fazlaydı.** Kural, ölçülmemiş bir sayıya
dayanarak bir mimari seçeneği 18 gün boyunca kapalı tuttu.

---

#### 2. 🔴 İLK UYGULAMAM KARELERİN YARISINI YOK ETTİ

En basit yol denendi: tek akış, tek tüketici grubu, her worker
kendisine ait olmayan kareyi atsın (`--cameras` filtresi).

**Ölçüm:**

```
90 sn penceresinde
  alım yayınladı        : 5236
  çıkarım analiz etti   : 2626
  "baska_worker" atıldı : 2610
  analiz/yayın          : %50
```

⭐⭐⭐ **Tam yarısı yok oldu.** Sebep: Valkey tüketici grubu her kareyi
**tek** tüketiciye verir. Kendisine ait olmayanı atan worker, o kareyi
ötekine geçirmiyor — **imha ediyor.**

⚠⚠ **Ve tuzak sinsiydi: metrikler İYİLEŞMİŞ göründü.**

```
                 tek worker    "bölüştürülmüş" (bozuk)
verim              46.3            28.0 kare/sn   ⬅ düştü
gecikme p50         172             104 ms        ⬅ İYİLEŞTİ (!)
gecikme p95         322             238 ms        ⬅ İYİLEŞTİ (!)
```

İşin yarısı atılınca kuyruk boşaldı ve gecikme düzeldi. Yalnızca
gecikmeye bakan biri bunu **başarı** sanardı.

> ⭐ **Bir metriğin iyileşmesi sistemin iyileştiği anlamına gelmiyor.**
> Kare muhasebesi (P-60'ta eklenmişti) olmasaydı bu hata "bölüştürme
> gecikmeyi yarıya indirdi" diye rapora girecekti.

---

#### 3. Doğru tasarım: PARÇA BAŞINA AYRI AKIŞ

Kayıp, filtrelemenin doğasında. Çözüm yönlendirmeyi **üretici** tarafına
almak: alım katmanı her kamerayı kendi parça akışına yazıyor
(`frames.ready.0`, `frames.ready.1`), her worker yalnızca kendi akışını
okuyor. Her kare tam olarak bir akışta, bir grupta, bir worker'da.

```python
ozet = zlib.crc32(camera.encode("utf-8")) % parca_sayisi
return f"{settings.stream_frames}.{ozet}"
```

⚠ **`hash()` KULLANILMADI.** Python'ın string hash'i süreçler arasında
rastgeleleştirilir (PYTHONHASHSEED); alım ve çıkarım süreçleri farklı
sonuç üretir, kameralar kaybolur ve hata **sessiz** olurdu. `crc32`
deterministik.

⚠ **Aynı kamera her zaman aynı parçaya gitmeli:** BoT-SORT durumu
worker'ın içinde kamera başına tutuluyor. Bölünürse izler kopar.

⚠ **Havuz sıfırlama artık TÜM parça akışlarını temizliyor.** Biri
atlanırsa eski mesajlar geçersiz slot referanslarıyla kalır ve aynı
slot iki kez dağıtılır (P-10'un çok akışlı hâli).

Doğrulandı: `baska_worker = 0`, kayıp yolu kapandı.

---

#### 4. ✅ TEMİZ A/B — aynı kod, aynı yöntem, aynı ölçüm aracı

| ölçüt | 1 parça | 2 parça | fark |
|---|---|---|---|
| **verim** | 45.1 kare/sn (2.25 FPS/kam) | **53.7 (2.68)** | **+%19** |
| **gecikme p50** | 359 ms | **183 ms** | **−%49** |
| **gecikme p95** | 638 ms | **411 ms** | **−%36** |
| çıkarım CPU | 0.90 çekirdek | 1.77 (2 × 0.89) | ×2 |
| toplam CPU | 4.13 çekirdek | 5.37 | +%30 |
| VRAM | 571 MB | 1134 MB | ×2 |
| GPU kullanımı | %41 | %38 | ~aynı |
| **sistem RAM** | %84 | **%98** | ⚠ |
| model skoru medyan | 0.184 | 0.209 | +%14 |

⭐ **Asıl kazanç verimde değil GECİKMEDE: p50 yarıya indi.** Sebep
mekanik: iki worker aynı anda çalışınca bir karenin kuyrukta bekleme
süresi yarılanıyor.

⭐⭐ **Her iki worker da tam 0.89 çekirdekte doydu** — P-65'in "tavan
bir çekirdek" tahmini worker başına birebir doğrulandı.

---

#### 5. ⚠ Verim neden 2× DEĞİL: darboğaz YUKARI TAŞINDI

```
ALIM        2.67 çekirdek   ⬅ artık en büyük tüketici
CIKARIM p0  0.89
CIKARIM p1  0.89
atılan: gate_idle 8535 · stale 4843 · no_slot 4482
```

İki worker ~86 kare/sn tüketebilir ama alım 55 kare/sn üretiyor. Ve
`no_slot` 4482: **48 slotluk paylaşımlı bellek havuzu tükeniyor.**

Yani bölüştürme çıkarım tavanını kaldırdı; kısıt alım katmanına ve slot
havuzuna geçti. Bir ölçekleme deneyinin göstermesi gereken tam olarak
budur.

**Sonraki kaldıraçlar (ölçülmüş sırayla):**
1. `shm_slot_count` artır (48 → 96) — `no_slot` 4482 diyor
2. Alım katmanı: BGR dönüşümü kare başına 1.61 ms CPU (P-61)
3. TensorRT: detect+pose bütçenin %82'si (P-66)

---

#### 6. ⚠⚠ BEDELİ — dürüstçe

**Sistem RAM %84 → %98.** İki worker × ~2.75 GB. 16 GB'lık makinede bu
sınır. P-65'te bozuk rejim %92 RAM'de görülmüştü; %98 rahat değil.

⚠ Bu yüzden `inference_shards` **varsayılan 1** bırakıldı. Açmak
bilinçli bir karar olmalı ve RAM izlenmeli.

⚠ **Model skoru medyanı 0.184 → 0.209 (+%14) değişti.** P-65 §3'teki
uyarı doğrulandı: analiz hızı değişince 5 saniyelik pencerenin içeriği
ve türevler kayıyor, skorlar kayıyor. **Hızlandırma doğruluğu
değiştiriyor** — bu yüzden her yapılandırmada eşikler yeniden
kalibre edilmeli.

⚠ Alarm sayısı bu pencerelerde 0 çıktı (her iki koşuda da), yani alarm
oranı üzerinden kıyas YAPILAMADI. Daha uzun koşu gerekiyor.

---

**Öğrenilen ders:** Bir ölçekleme değişikliğini yalnızca hız
metrikleriyle değerlendirmek, işin yarısını atan bir uygulamayı
"başarı" diye kaydetmeye yol açar. **Muhasebe (giren = çıkan + atılan)
hız ölçümünden önce gelir.**

⭐ Ve fikrin sahibi haklı çıktı: 18 gündür ölçülmemiş bir varsayım
(4.6 GB/worker) yüzünden kapalı duran seçenek, açıldığında gecikmeyi
yarıya indirdi.

---

### P-68 · ⭐⭐⭐ Alarmların DOĞRULUĞU hiç doğrulanamıyordu — yer gerçeği eklendi

**Tarih:** 09.09.2026 · **Faz:** 3

**Kullanıcının tespiti — projenin en büyük bilimsel açığı:**

> *"Bu alarmların yanlış olduğunu nereden biliyorsun, elle doğruladın mı?
> Sistem alarm veriyor ama bu alarmı doğrulayan bir şey yok. Bu bizim
> projenin en büyük sıkıntılarından biri olmaz mı?"*

⚠ **Ve haklıydı — üstelik ben aynı gün o hatayı yapmıştım.** 8 FPS
deneyinde "yanlış alarm artıyor" diye yazmıştım. Ölçtüğüm şey alarm
SAYISIYDI; hangisinin yanlış olduğunu bilmiyordum ve bilemezdim.
Doğrusu: *"skorlar şişti, alarm oranı arttı; ne kadarının yanlış olduğu
ölçülmedi."*

---

#### Durum: yer gerçeği VARDI ama YANLIŞ YERDE

| kaynak | seviye | hangi kriter |
|---|---|---|
| RWF-2000 | klip (kavga var/yok) | K5 |
| Avenue | **kare seviyesi** | K6 |
| cam-16 (UR Fall) | olay anı biliniyor | düşme kuralı |
| cam-15 | elle görsel (07.09) | tek kamera |
| cam-18 | kontrol (tanımı gereği olay yok) | K7 |

**Eksik olan: 20 kameralık çiftliğin geneli — ve K7 tam da orada
ölçülüyor.** Bu yüzden bildirilen "11.69 alarm/kamera-saat" bir *alarm
oranı*dır, yanlış alarm oranı değil. CLAUDE.md bunu zaten dürüstçe
yazıyordu ama **çözmüyordu**.

---

#### ⭐ Çözüm mümkündü, çünkü kameralarımız VİDEO DOSYASI

Gerçek bir IP kamerada geçmişe dönüp "o alarm anında ne oluyordu"
diye bakmak imkânsız olurdu — kayıt yoksa kanıt da yok. Bizim
kameralarımız sonsuz döngüdeki dosyalar; her alarmın kaynak videoda
tam olarak nereye denk geldiği **bulunabilir**.

⚠ **Eksik olan ölçüm değil, ölçümün TAŞINMASIYDI.**

`FrameMessage.pts` (kaynak videodaki saniye) boru hattında **Gün 1'den
beri vardı** (`bus/streams.py:157`). Çıkarım worker'ı sonucu
yayınlarken onu düşürüyordu. Olay kaydında yalnızca duvar saati (`ts`)
kalıyordu — ve kameralar döngüde olduğu için duvar saati videodaki ana
çevrilemiyordu.

> ⭐ P-60 ve P-62 ile aynı kalıp, üçüncü kez: **bilgi sistemde vardı,
> ihtiyaç duyulan yere ulaşmıyordu.** Orada `queue_depth` yayınlanıyordu
> kimse okumuyordu; burada `pts` üretiliyordu, kimse taşımıyordu.

---

#### Yapılan — üç küçük değişiklik

1. `_serialize(..., pts=message.pts)` → sonuç yüküne `"pts"` eklendi
2. Analitik kamera başına son `pts`'i tutuyor, olay yayınlarken yazıyor
3. `Olay.akistan` onu `kanit["video_pts"]` olarak kaydediyor

⭐ **`kanit` zaten `jsonb` → VERİTABANI ŞEMASI DEĞİŞMEDİ.** Yeni sütun,
migrasyon, indeks gerekmedi.

⚠ `-1` = "ölçemedim", `0.0` = "videonun başı". İkisi karıştırılmıyor;
`-1` olan olaylar kayda hiç girmiyor.

**Canlıda doğrulandı:**

```
cam-03   running      video_pts=436.445
cam-16   risk         video_pts=432.392
cam-13   crowd        video_pts=427.866
cam-16   fall         video_pts=376.912
```

#### Araç: `scripts/alarm_klipleri.py`

Her alarmın etrafından **6 saniyelik klip** kesiyor (alarm anı ortada,
3 sn öncesinden başlıyor) ve etiketleme için CSV şablonu üretiyor.
Sınandı: **12/12 klip kesildi.**

⚠ **Alarm anı klibin ORTASINDA, başında değil.** Bir alarmın doğru olup
olmadığına karar vermek olayın ÖNCESİNİ görmeyi gerektiriyor; yalnızca
alarm anından itibaren kesmek "neden alarm verdi" sorusunu
cevaplanamaz kılardı.

⚠ **`ffmpeg` CLI kullanılmadı** — bu makinede PATH'te yok (PyAV
kütüphaneyi gömüyor, komut satırı aracını değil). OpenCV zaten
bağımlılık; dış araca bağlanmak betiği "benim makinemde çalışıyor"
sınıfına sokardı.

---

#### ⚠ Bu yöntemin sınırı — dürüstçe, ÖNCEDEN

Bu yöntem **kesinlik** (precision) ölçer: *"sistemin verdiği
alarmların kaçı gerçek?"*

**Duyarlılık (recall) ÖLÇÜLEMEZ:** kaçırılan olayları bulmak için
videoların TAMAMININ etiketlenmesi gerekirdi. Yani bu ölçüm
"sistem olayları kaçırıyor mu" sorusunu cevaplamıyor ve raporda
böyle yazılacak.

⚠ **Etiketleme kuralı önce yazılmalı, klipler izlenmeden.** Sonradan
tanımlamak, gördüğünü haklı çıkaracak bir tanım seçmek olurdu —
P-49'un dersi: ölçütün TANIMI olayın tanımını yanlış çizebiliyor.

**Öğrenilen ders:** Bir sistemin ürettiği kararı doğrulayamıyorsan,
o sistem hakkında söylediğin her doğruluk cümlesi bir varsayımdır.
Ve bu projede yer gerçeği eksikliği, ölçüm aracı hatalarından daha
uzun süre (18 gün) fark edilmeden durdu — çünkü **bir sayıyı
yanlış ölçmek şüphe uyandırır, hiç ölçmemek uyandırmaz.**


---

### P-69 · ⭐⭐⭐ En büyük hızlanma tek satırlık bir AYARDAN geldi — ve mimari değişikliği gereksiz kıldı

**Tarih:** 09.09.2026 · **Faz:** 3

**Neden bakıldı:** P-67'de kamera bölüştürme ölçülürken atılan kareler
arasında `no_slot = 4482` göze çarptı. Paylaşımlı bellek havuzu
tükeniyordu.

---

#### Bulgu: `.env` kodun varsayılanını ÜÇTE BİRE düşürmüş

```
backend/src/sentinel/config.py :  shm_slot_count = 128   ⬅ kod varsayılanı
.env                           :  SHM_SLOT_COUNT=48      ⬅ yürürlükteki
```

48 slot × 2.76 MB = 133 MB. 96 slot = 265 MB. Yani kısıtlama bir bellek
zorunluluğu değildi — 16 GB'lık makinede 130 MB fark yaratıyordu.

Bu değer `.env`'e ne zaman ve neden konduğu **belgelenmemişti**.

---

#### ⭐⭐ Ölçüm: tek satır, en büyük kazanç

Tek çıkarım worker'ı, aynı kod, aynı ölçüm aracı:

| ölçüt | 48 slot | **96 slot** | fark |
|---|---|---|---|
| verim | 45.1 kare/sn (2.25 FPS/kam) | **55.7 (2.78)** | **+%23** |
| gecikme p50 | 359 ms | **147 ms** | **−%59** |
| gecikme p95 | 638 ms | **240 ms** | **−%62** |

⭐ **Gecikme neredeyse üçte birine indi.** Mekanizma: havuz tükenince
alım katmanı kareyi atıyordu (`no_slot`) ve hayatta kalan kareler daha
uzun kuyrukta bekliyordu. Havuz büyüyünce hem daha az kare atılıyor hem
kuyruk boşalıyor.

---

#### ⭐⭐⭐ VE ASIL BULGU: İKİ İYİLEŞTİRME TOPLANMIYOR

Dört yapılandırma, aynı ölçüm aracı, aynı 240-300 sn pencereler:

| yapılandırma | verim (kare/sn) | p50 | p95 | sistem RAM |
|---|---|---|---|---|
| 1 parça + 48 slot (taban) | 45.1 | 359 | 638 | %84 |
| 2 parça + 48 slot | 53.7 | 183 | 411 | %98 |
| **1 parça + 96 slot** | **55.7** | **147** | **240** | **%80** |
| 2 parça + 96 slot | 50.8 | 170 | 387 | %98 |

⭐ **En iyi yapılandırma en basit olanı: tek worker + yeterli slot.**

İkisini birleştirmek **geriye götürdü** (55.7 → 50.8). Sebep: slot
düzeltmesi, bölüştürmenin çözmeye çalıştığı darboğazı ortadan
kaldırdı. Kalan tek etki, ikinci worker'ın CPU ve RAM çekişmesi — yani
saf zarar.

> ⭐⭐ **Bölüştürme bir BELİRTİYİ tedavi ediyormuş.** Worker'ın "kare
> bekliyor" görünmesinin sebebi seri döngü değil, **üreticinin slot
> bulamamasıydı.** İki worker koyunca her biri daha az beklediği için
> toplam iyileşiyordu; asıl sebep düzeltilince ikinci worker'ın
> yapacak işi kalmadı.

⚠ **Bu, P-65'teki teşhisimi kısmen çürütüyor.** "Çıkarım worker'ı tek
çekirdekte doyuyor, darboğaz mimaride" demiştim. Doğruydu ama **eksikti**:
worker 0.89 çekirdekte doyuyordu, evet — ama sistemin verimini
sınırlayan şey o değil, **kendisine kare ulaşamamasıydı.** Doğru teşhis
"tek çekirdek tavanı" değil, "üretici-tüketici arasındaki tampon
yetersiz".

---

#### Rapor için ⭐ neden değerli

Makalede kullanılacak dört satırlık bir tablo ve tek cümlelik bir ders:

> *"Aynı donanımda dört yapılandırma aynı ölçüm aracıyla kıyaslandı.
> Mimari bir değişiklik (süreç düzeyinde paralelleştirme) gecikmeyi
> %49 iyileştirdi; tek satırlık bir tampon ayarı ise %59 iyileştirdi ve
> ek kaynak gerektirmedi. İkisi birleştirildiğinde sonuç, yalnızca
> ayarın uygulandığı duruma göre KÖTÜLEŞTİ (%23 verim kaybı), çünkü
> mimari değişiklik ayarın çözdüğü darboğaza yönelikti."*

**Öğrenilen ders:** Bir mimari değişikliği ölçmeden önce, o mimarinin
çözmeye çalıştığı darboğazın **gerçekten mimari olduğundan** emin
olunmalı. Aksi hâlde doğru ölçülmüş, doğru raporlanmış ve **gereksiz**
bir karmaşıklık eklenmiş olur.

⚠ Ve daha basit bir ders: **çalışma zamanı ayarları, kod
varsayılanlarıyla birlikte denetlenmeli.** `.env` sessizce kodun
varsayılanının üçte birini dayatıyordu ve bunu 18 gün kimse fark
etmedi. P-42'de "16 ayar okunmuyordu" bulunmuştu; bu onun tersi —
**ayar okunuyordu ama yanlış değerdeydi ve gerekçesi yoktu.**


---

### P-70 · ⭐⭐ TensorRT 1.61× — ama üretimde PARTİ BOYUTUNDA KIRILIYOR

**Tarih:** 09.09.2026 · **Faz:** 3

**Neden bakıldı:** P-66 kırılımı, hızlandırılabilir GPU işinin bütçenin
**%82'si** olduğunu gösterdi (`pose` %50 + `detect` %32). Daha önce
*"TensorRT kaldıraç değil, %3"* demiştim ve o cümle yanlış tablodan
türemişti.

---

#### İzole ölçüm: kazanç GERÇEK ve tespitler AYNI

```
             parti ms   kare ms      p90
PyTorch        30.233     3.779   31.324
TensorRT       18.741     2.343   20.310
HIZLANMA: 1.61×   (+%38 süre kazancı)
```

⭐ Önceki ölçüm 1.40× idi; TensorRT 10.13 ve FP16 ile **1.61×**.

**Tespit eşdeğerliği — hız doğru sonuçla mı geliyor:**

```
PyTorch tespit  : 20        eşleşen                   : 20
TensorRT tespit : 20        PyTorch'ta var TRT'de yok : 0
ortalama IoU    : 0.9915    TRT'de var PyTorch'ta yok : 0
```

⚠ Bu kontrol **zorunluydu**: hızlanma, sonucu bozarak da elde edilebilir.
Ölçmeden "hızlandı" demek, neyi kaybettiğini bilmemek olurdu.

---

#### 🔴 ÜRETİMDE ÇALIŞMADI — ve sebebi tam olarak belgeliydi

Motor üretime alınıp canlı boru hattı başlatıldı:

```
AssertionError: input size torch.Size([5, 3, 640, 640])
                not equal to max model size (8, 3, 640, 640)
AssertionError: input size torch.Size([1, 3, 640, 640]) ...
```

**Her kısmi parti hata veriyor.** Motor `dynamic=False` ile ihraç
edilmek zorundaydı (YOLO26'nın dikkat bloğu dinamik şekillerde TensorRT
çekirdeği bulamıyor — `export_tensorrt.py` bunu belgeliyor) ve sabit
parti **yalnızca tam 8 kare** kabul ediyor.

Üretimde parti dağılımı: medyan **6.67 kare**, sık sık 1, 5, 6, 7.

⭐ **ADR-0006 bunu zaten öngörmüştü** ve TensorRT'yi tam da bu yüzden
üretime almamıştı. Bugünkü ölçüm o kararı **doğruladı** — ama artık
tahminle değil, canlı hatayla.

---

#### Dolgu yapılırsa ne kazanılır — hesaplandı, uygulanmadı

Kısmi partiyi 8'e tamamlamak (kare tekrarı) mümkün; bedeli, boş yerlerin
tam parti kadar maliyet üretmesi:

```
üretim medyan partisi          : 6.67 kare
TRT dolgulu etkin maliyet      : 8/6.67 × 2.343 = 2.81 ms/kare
PyTorch (aynı koşul)           : 3.78 ms/kare
                                 ─────────────
net kazanç                     : ~1.34×  (izoledeki 1.61× değil)
```

Üretim kırılımında `detect` 7.43 ms/kare ve toplam 23.22 ms/kare.
1.34× uygulanırsa: 7.43 → 5.54, toplam 23.22 → 21.3 ms → **~%9 verim**.

⚠ **Uygulanmadı.** Gerekçe: dolgu kodu, sahte karelerin sonuçlarının
atılmasını da gerektiriyor ve yanlış yapılırsa **hayalet tespitler**
üretir — sessiz ve tehlikeli bir hata sınıfı. Kalan sürede %9 için
alınacak risk değil. Kayıt olarak bırakılıyor.

---

#### ⚠ Yan bulgu: ihraç betiği YANLIŞ DİZİNE yazıyor

Motor `backend/models/yolo26s.engine`'e yazıldı; üretim
`<kök>/models/` okuyor. Bu, `.gitignore`'da **08.09'da belgelenmiş**
"iki model dizini" hatasının tekrarı:

> *"Üretim `<kök>/models/` okuyor; ölçüm betikleri `backend/models/`
> yazıyordu. Eğitilen model üretimin BAKMADIĞI yere kaydediliyordu."*

O gün 16 betik düzeltilmişti; `export_tensorrt.py` Ultralytics'in kendi
çıktı yolunu kullandığı için düzeltmenin dışında kalmış.

> ⭐ P-60 ve P-62 ile aynı ders, üçüncü kez: **düzeltme taşınmadıysa
> yapılmamıştır.** Bu sefer kaçan yer, yolu kendisi belirlemeyen bir
> üçüncü taraf kütüphanesiydi.

---

#### Karar

**TensorRT üretime ALINMADI.** Gerekçe artık iki katmanlı:
1. Sabit parti, üretim parti dağılımıyla uyumsuz (canlıda doğrulandı)
2. Dolgu ile net kazanç ~%9; taşıdığı hayalet-tespit riski buna değmez

⭐ Ama ölçüm **saklanıyor ve raporlanacak**: 1.61× hızlanma, tespitler
birebir aynı (IoU 0.9915). Bu, "denendi ve şu sebeple alınmadı"
demenin ölçülmüş hâli — "denenmedi"den çok farklı.


---

### P-72 · ⭐⭐⭐ "Duygu analizi neden tek kamerada" — iki aşamalı kapı ölçüldü, açıklamam YANLIŞTI

**Tarih:** 10.09.2026 · **Faz:** 3

**Neden bakıldı:** Kullanıcı duygu analizine detaylı girmek istedi.
Şartname üç yetenek istiyor (anomali · **duygu** · saldırganlık) ve
duygu tarafı bugüne kadar en az incelenen taraftı.

---

#### 1. Önce eksik olan aleti eklemek gerekti

Canlıda "duygu analizi çalışıyor mu" sorusunun cevabı **yoktu**.
`sentinel_risk_score` yalnızca BİRLEŞİK skoru gösteriyor; bir sinyalin
hiç ateşlemediği oradan görünmüyor — P-43'te ifade tam olarak öyle
sessizdi ve **17 gün fark edilmedi**.

Eklendi: `sentinel_fusion_signal{cam, signal}` — füzyona giren her ham
sinyalin kamera başına azamisi.

**İlk okuma (16 aktif kamera):**

| sinyal | sıfırdan farklı |
|---|---|
| saldırganlık | **16/16** |
| anomali | **16/16** |
| kural | 2/16 |
| **ifade** | **1/16** ⬅ yalnızca cam-20 (0.291) |
| kalabalık | 1/16 |

⭐ **İyi haber:** ifade sinyali cam-20'de **0.291** — yani P-43'ün
düzeltmesi gerçekten çalışıyor, duygu analizi karara ulaşıyor.
⚠ **Kötü haber:** 20 kameranın yalnızca birinde.

---

#### 2. ⚠ "Neden tek kamerada" sorusuna verdiğim cevap YANLIŞTI

Kodun docstring'i (Gün 13'ten beri) şunu diyordu ve ben de tekrarladım:

> *"Gün 13 ölçümü kamera çiftliğinde yüzlerin ~15 px olduğunu gösterdi;
> bu ölçek kaybı onun üstüne biniyor. Sonuç: sabit kameralarda bu kademe
> neredeyse hiç aday bulamayacak."*

Yani açıklama **"kişi kutusu kapısını geçemiyorlar"** idi. Ölçüldü:

```
kapı: kişi kutusu yüksekliği ≥ 180 px (çıkarım uzayı 640×640)

kamera    kişi  medyan   p90  azami   kapıyı geçen
cam-09     346      61    84    110        0 (%0)
cam-12     157      62    71     92        0 (%0)
cam-13      82     143   203    280       18 (%22)   ⬅ GEÇİYOR
cam-14      95     139   246    399       25 (%26)   ⬅ GEÇİYOR
cam-15      87     151   211    244       19 (%22)   ⬅ GEÇİYOR
cam-16      24     234   280    290       20 (%83)   ⬅ GEÇİYOR
cam-17      72      88   246    368       19 (%26)   ⬅ GEÇİYOR
cam-19     150     108   140    295       10 (%7)    ⬅ GEÇİYOR
cam-20      25     308   339    340       25 (%100)
```

⭐⭐ **8 kamera kişi kapısını geçiyor**, ama canlıda yalnızca cam-20
ifade üretiyor. **Açıklama yanlıştı: kapı bağlayıcı kısıt değil.**

---

#### 3. Gerçek kısıt: YÜZ GÖRÜNMÜYOR, küçük değil

Kapıyı geçen kırpıntılara YuNet uygulandı:

```
kamera    kırpıntı  yüz bulundu   oran   medyan yüz px
cam-13          18            0     %0        —
cam-14          25            0     %0        —
cam-15          19            0     %0        —
cam-15h         35            0     %0        —
cam-16          20            0     %0        —
cam-17          19            0     %0        —
cam-19          10            0     %0        —
cam-20          25           25   %100      110 px
```

⭐⭐⭐ **Yedi kamerada 146 kırpıntının HİÇBİRİNDE yüz bulunmadı.**
cam-20'de 25/25 bulundu ve yüzler **110 piksel** — küçük bile değil.

**Doğru açıklama:** sorun yüzün *boyutu* değil, **kameraya dönük
olmaması.** Gözetim kamerası tipik olarak yüksekten ve açılı bakar;
insanlar yandan, arkadan ya da eğik görünür. YuNet önden yüz arıyor.
cam-20 ise tanımı gereği yakın plan, kameraya bakan yüz videosu.

> ⭐ İki açıklama da "kademe çalışmıyor" sonucuna varıyordu ama
> **farklı çözümler öneriyorlar** — ve bu yüzden hangisinin doğru
> olduğu önemli:
>
> | yanlış açıklama (boyut) | doğru açıklama (açı) |
> |---|---|
> | çözüm: daha yüksek çözünürlük, kapıyı düşür | çözüm: **YOK** — kamera açısı veri toplama kararı |
> | "donanım alırsak düzelir" | "bu kurulumda düzelmez" |
>
> Yanlış açıklamayla ilerleseydik, çözünürlük artırmaya emek harcayıp
> hiçbir şey kazanmayacaktık.

---

#### 4. Raporda yazılacak dürüst ifade

> *"Yüz ifadesi kademesi (KADEME 2b) 21 kameranın 8'inde kişi boyutu
> kapısını geçmekte, ancak yalnızca 1'inde (cam-20) yüz tespiti
> yapılabilmektedir. Kapıyı geçen diğer 7 kamerada 146 kişi
> kırpıntısının hiçbirinde yüz bulunamamıştır. Sınırlayıcı etken yüz
> çözünürlüğü değil (cam-20'de tespit edilen yüzlerin medyanı 110 px),
> **kamera açısıdır**: gözetim kameraları yüksekten ve açılı baktığı
> için özneler önden görünmemektedir. Bu, kurulumun bir özelliğidir ve
> daha yüksek çözünürlükle giderilemez."*

⚠ Ve bu, füzyon ağırlığının neden düşük tutulduğunu (0.10) **ölçümle**
destekliyor: sinyal 20 kameranın 19'unda hiç gelmiyor. Ağırlığın
yüksek olması, gelmediği yerde sistemi köreltirdi.

**Öğrenilen ders:** Bir kademenin "çalışmadığı" gözlemi ile **neden**
çalışmadığı ayrı sorular. İkincisini ölçmeden birincisine çözüm
aramak, yanlış yere emek harcamaktır. Ve bu projede açıklama, iki yıl
boyunca kodun docstring'inde **yazılı** duruyordu — yazılı olması onu
doğru yapmadı.


---

### P-73 · ⭐⭐ "Gülümseyen yüze şaşkınlık" — iki hata, biri benim aceleci teşhisim

**Tarih:** 10.09.2026 · **Faz:** 3

**Kullanıcının tespiti (canlı panelden ekran görüntüsüyle):** açıkça
gülümseyen bir yüz **"şaşkınlık %100"** etiketlenmiş.

> *"Yanlış etiketliyorsa neden yapıyoruz ki? Yüz duygu analizine
> kesinlikle bak."*

---

#### 1. ⚠ İLK TEŞHİSİM YANLIŞTI — dağılıma bakıp hüküm verdim

Canlı sayaçlara baktım:

```
cam-20 · 1222 sınıflandırma
Happiness %27 · Surprise %22 · Contempt %19 · Neutral %15
Fear %11 · Sadness %6 · Disgust %0
```

*"Altı sınıfa neredeyse eşit dağılmış — bu ayırt etmeyen bir modelin
imzası"* dedim. **Yanlıştı.** Kırpıntıları diske döküp bakınca cam-20'nin
**tek kişilik değil, çok kişilik bir yakın plan derlemesi** olduğu
görüldü: farklı insanlar, farklı ifadeler. Dağılımın çeşitli olması
videonun çeşitli olmasından.

> ⭐ Bir dağılıma bakıp "model bozuk" demek, veriye bakmadan hüküm
> vermektir. **Bakmak** on dakika sürdü ve teşhisi çevirdi.

---

#### 2. Gerçek hata #1: KANAL SIRASI (BGR → RGB dönüşümü YOKTU)

Boru hattı baştan sona BGR (PyAV `bgr24`, OpenCV). EmotiEffLib ise
ImageNet ön işlemesi kullanan bir CNN sarıyor — o modeller **RGB** ile
eğitiliyor. `grep -rn "cvtColor.*RGB" inference/emotion/` **boştu**:
hiçbir yerde dönüşüm yoktu.

**Ölçüldü (40 yüz, aynı kırpıntılar iki kez):**

```
BGR (üretim)     ortalama güven 0.582
RGB (dönüşümlü)  ortalama güven 0.594
aynı etiketi veren: 31/40  (%78)
→ etiketlerin %22'si DEĞİŞİYOR
```

⚠ **Etki abartılmamalı:** hata gerçek ama sistemi tek başına
bozmuyordu. Yine de düzeltildi — bir modele eğitildiğinden farklı kanal
sırasıyla girdi vermek sonucu **ölçülemez** biçimde bozar. *"Fark
küçük"* bir gerekçe değil.

---

#### 3. Gerçek hata #2 (ASIL SEBEP): GÜVEN EŞİĞİ ÇOK DÜŞÜKTÜ

12 yüz kırpıntısı diske döküldü ve **elle (görsel olarak)**
değerlendirildi:

| güven | model | görsel değerlendirme |
|---|---|---|
| 0.98 | Happiness | ✅ gülümsüyor |
| 0.88 | Fear | ✅ endişeli, kaşlar çatık |
| 0.79 | Happiness | ✅ gülümsüyor |
| 0.59 | Neutral | ✅ nötr, konuşuyor |
| 0.57 | Happiness | ✅ gülüyor |
| **0.48** | **Surprise** | ❌ **nötr bir yüz** |
| **0.43** | **Contempt** | ❌ **nötr bir yüz** |

⭐⭐ **Ayrım keskin: 0.55 üstü doğru, 0.50 altı yanlış.** Ve eski eşik
**0.40**'tı — yani tam da hatalı bandı geçiriyordu.

**Düzeltme:** eşik 0.40 → **0.55**, hem sunucuda (`ExpressionResult.usable`)
hem panelde (`EXPR_MIN_CONF`).

⚠ İkisinin AYNI olması zorunlu: ayrışırlarsa panel, sunucunun
güvenilmez saydığı bir etiketi gösterir ve iki taraf farklı şey iddia
eder.

⚠ **Bedeli kabul edildi:** daha az etiket gösterilecek. Gözetim
sisteminde **yanlış bir duygu etiketi, etiket olmamasından kötüdür** —
operatör ona göre karar verir.

---

#### 4. ⚠ Bu ölçümün sınırı — dürüstçe

n = 12, **tek değerlendirici** (ben), yer gerçeği yok. Bu bir *doğruluk
ölçümü değil*, eşik seçimi için bir **gözlem**. Gerçek doğruluk ancak
etiketli bir yüz ifadesi veri setiyle (AffectNet, RAF-DB) ölçülebilir
ve o kapsam dışı bırakıldı.

Raporda böyle yazılacak: *"Sınıflandırıcının doğruluğu etiketli veri
setiyle ölçülmemiştir; kullanılan güven eşiği, 12 örneklik görsel bir
incelemeye dayanarak 0.40'tan 0.55'e yükseltilmiştir."*

---

#### 5. Yan düzeltme: etiket ekranda GÖRÜNMÜYORDU

Etiket kutunun **altına** çiziliyordu (`y + h`). Kişi kadrajın alt
yarısındaysa kutucuğun dışına taşıyor ve operatör onu hiç göremiyordu.
Kullanıcı canlı panelde yakaladı.

Yeni konum: kutunun **sağ üstü** (sol üstte zaten iz kimliği rozeti
var). Kenara sığmazsa içeri alınıyor.

> ⭐ Üç bulgunun üçü de **paneli açıp bakmakla** çıktı. Sistem 20 gündür
> ölçülüyor ama ekranı kimse dikkatle izlememişti: etiket konumu,
> yanlış etiketler ve (ayrıca) bir kameranın siyah kalması. **Ölçüm
> aracı da gözle doğrulanmalı.**

**Öğrenilen ders:** Bir sınıflandırıcının çıktısını "doğru mu" diye
sorarken önce **girdisine bakmak** gerekiyor — kırpıntılar kusursuzdu,
suçlu eşikti. Ve dağılım istatistiğine bakıp model hakkında hüküm
vermek, veriye bakmamanın kestirme yoluydu.


---

### P-74 · ⭐⭐⭐ cam-15 SİYAH KALIYORDU — sebep B-KARELERİ, ve ilk iki teşhisim yanlıştı

**Tarih:** 10.09.2026 · **Faz:** 3

**Kullanıcının tespiti:** *"paneli açtım, kamera 15'in videosu ekrana
gelmedi, donuk kaldı öyle siyah ekranda."*

⚠ **Ve sunucu tarafındaki HİÇBİR metrik bunu göstermiyordu:**

```
sentinel_camera_up{cam="cam-15"}  1.0
sentinel_camera_fps{cam="cam-15"} 4.15
MediaMTX: hazir=True · H264 · okuyucu=1
```

Alım worker'ı kamerayı sorunsuz okuyor, analiz ediyor, alarm üretiyor.
Bozuk olan tek şey **operatörün gördüğü şey** — ve sistemin hiçbir
sağlık göstergesi oraya bakmıyordu.

---

#### Önce ölçülebilir hâle getirmek gerekti

Bir kutucuğun çizilmesi videonun geldiğini göstermez. Tek gözlemlenebilir
kanıt tarayıcıda: `video.videoWidth > 0` ve `readyState >= 2`.

Playwright tanısı yazıldı (`e2e/panel-tani.spec.ts`) ve **hatayı
yeniden üretti**:

```
20 hazır kameradan 19'unda video geldi · cam-15 SİYAH
```

⭐ Bu, "kullanıcı öyle gördü" ile "ölçüldü" arasındaki fark. Artık
düzeltmenin işe yarayıp yaramadığı da ölçülebilirdi.

---

#### ⚠ Teşhis 1 — YANLIŞ: "çözünürlük/kare hızı farklı"

```
cam-14: 900x720 @25fps    cam-16: 960x720 @25fps
cam-15: 640x360 @30fps    ⬅ tek farklı
```

Makul görünüyordu ama bir mekanizma önermiyordu: 640×360 H264'ü hiçbir
tarayıcı reddetmez.

#### ⚠ Teşhis 2 — YANLIŞ (ve düzeltmesi işe yaramadı): "GOP çok uzun"

Anahtar kare aralıkları ölçüldü:

```
cam-01/14/16 : 2.00 sn      ⬅ prepare_videos.py normalizasyonu
cam-15       : 8.33 sn      ⬅ 4 KAT uzun
```

cam-15 07.09'da arşivden değiştirilmiş ve normalizasyondan geçmemişti.
WebRTC izleyicisi çözmeye başlamak için anahtar kare bekler — sebep
buymuş gibi göründü.

**Yeniden kodlandı, GOP 2.00 sn'ye indirildi, RTSP akışında doğrulandı
— ve cam-15 YİNE SİYAH kaldı.** Teşhis çürüdü.

> ⚠ Bu iki teşhisin ortak kusuru aynı: **farklı olan bir şey bulup onu
> sebep saymak.** Fark, sebep değildir. İkisi de "şu değişken farklı"
> diyordu, hiçbiri "şu mekanizma bozuluyor" demiyordu.

---

#### ⭐⭐⭐ Gerçek sebep: MediaMTX'in kendi günlüğü söyledi

Henüz bakılmamış tek yer sunucunun günlüğüydü. WHEP oturumu sırasında
günlük yakalandı:

```
INF [WebRTC] [session daec9b0f] closed:
    WebRTC doesn't support H264 streams with B-frames
```

**Kare türleri sayıldı (ilk 300 kare):**

```
cam-15 (eski) : I=2   P=76   B=222   ⬅ %74 B-KARE
cam-15 (yeni) : I=6   P=294  B=0
```

WebRTC belirtimi H264'te B-kare desteklemiyor. Kaynak video B-kare
içeriyordu ve MediaMTX `-c copy` ile yayınladığı için (yeniden kodlama
YAPMAMASI mimari bir karar) B-kareler tarayıcıya kadar gidiyordu.

⚠ **İlk yeniden kodlamam sorunu ÇÖZMEDİ çünkü `libx264` varsayılan
olarak B-kare üretiyor.** GOP'u düzeltirken B-kareleri yeniden
ürettim — yani düzeltme, hatayı koruyarak uygulanmıştı.

**Doğru komut:** `-bf 0 -profile:v baseline`

```
[1sn] {"w":640,"h":360,"hazir":4}   ⬅ 1 SANİYEDE geldi
tam tarama: 20/20 kamerada video ✅
```

---

#### Neden bu hata 3 gün görünmedi

cam-15 07.09'da değiştirildi. O günden beri:
- alım worker'ı okudu ✅
- analiz etti, alarm üretti ✅
- K8/K6 ölçümleri kullandı ✅
- **paneli kimse dikkatle izlemedi** ❌

> ⭐⭐ Sistemin gözlemlenebilirliği **sunucuda** güçlü, **istemcide**
> sıfırdı. 30'dan fazla Prometheus metriği var ve hiçbiri "operatör
> gerçekten görüntü görüyor mu" sorusuna cevap vermiyor. Bu, P-43/44/45
> ile aynı sınıf: zincirin son halkası ölçülmüyordu.

**Yapılan:** `panel-tani.spec.ts` artık her koşuda 20 kameranın
hepsini açıp videonun geldiğini doğruluyor. Bu hata bir daha sessizce
oluşamaz.

⚠ Orijinal dosya **silinmedi**: `data/videos/cam-15.gop833.mp4`
(B-kareli, 8.33 sn GOP). Ölçüm zinciri gerekirse ona dönebilir.

**Öğrenilen ders:** İki teşhisim de "farklı olanı bul" yöntemiyle
üretilmişti ve ikisi de yanlıştı. Doğru cevap, **sistemin kendi
söylediği yerdeydi** — sunucu günlüğü hatayı açık açık yazıyordu ve
oraya en son bakıldı. Ölçmeden önce **okumak** gerekiyor.


---

### P-75 · ⭐⭐ K10 ÖLÇÜLDÜ (✅ 30.0 FPS) — ve kontrol serisi ölçümü kurtardı

**Tarih:** 10.09.2026 · **Faz:** 3

**Durum:** K10 (UI akıcılığı ≥30 FPS) Gün 1'den beri **hiç
ölçülmemişti** — 10 kriterden ölçülmeyen tek kriterdi.

---

#### 1. Önce ölçütün NE olduğunu tanımlamak gerekti

PLAN §1.4 *"20 kutucukta ≥30 FPS"* diyor ama **hangi FPS** olduğunu
söylemiyor. Üç ayrı büyüklük var ve karıştırmak ölçümü anlamsız kılar:

| # | büyüklük | nasıl ölçülür |
|---|---|---|
| 1 | **çizim (paint) hızı** — arayüz saniyede kaç kez tazeleniyor | `requestAnimationFrame` sayımı |
| 2 | **video çözme hızı** — 20 akıştan saniyede kaç kare çözülüyor | `getVideoPlaybackQuality().totalVideoFrames` |
| 3 | **düşen kare** — çözülüp ekrana basılamayan | `droppedVideoFrames` |

⚠ Yalnızca (1)'e bakmak yanıltıcı olurdu: arayüz 60 FPS çizerken
videolar 5 FPS'te takılıyor olabilir ve kullanıcı "akmıyor" der.
Üçü birden raporlanıyor.

---

#### 2. ⭐⭐ İLK SONUÇ ŞÜPHELİYDİ VE KONTROL SERİSİ GEREKTİ

İlk ölçüm **tam 30.0 FPS** verdi. Tam sayı çıkması şüpheliydi: başsız
(headless) tarayıcı `requestAnimationFrame` hızını **sabitliyor**
olabilirdi. Öyleyse "30.0" tarayıcının tavanıydı ve bizim uygulamamız
hakkında **hiçbir şey** söylemiyordu.

Kontrol serisi eklendi: **hiç kamera açmadan** aynı ölçüm.

```
KONTROL (0 kamera açık) : 60.2 FPS   ⬅ tarayıcı tavanı 60
20 kamera açık          : 30.0 FPS
yükün getirdiği düşüş   : %50.1
```

⭐ Tavan 60 çıktı. Yani 30.0 bir artefakt değil, **yükün gerçek
etkisi**: 20 kamera arayüzün çizim hızını tam yarıya indiriyor.

> ⚠ Kontrol olmasaydı iki yanlıştan biri yazılacaktı: ya "K10 sınırda
> tutuyor" (tavan 30 ise anlamsız) ya da "tarayıcı yetersiz" (gerçekte
> yetiyor). P-41'in dersi bir kez daha: **kıyasta değişmemesi gereken
> şey sabit tutulmalı.**

---

#### 3. Sonuç: K10 ✅ TUTUYOR

```
açık kamera              : 20 / 20 (hepsinde görüntü var)
çizim (paint) FPS        : 30.0     (hedef ≥30)      ✅
video kare (toplam/sn)   : 275.0
video FPS / kamera       : 13.8
düşen kare               : 0 / 8254  (%0.0)          ⭐
kontrol (0 kamera)       : 60.2 FPS
```

⭐⭐ **Düşen kare SIFIR.** Tarayıcı 20 H.264 akışını CPU'da çözüyor ve
tek bir kare bile düşürmüyor. Bu, beklediğimizden çok daha iyi.

⚠ **Beklentim yanlıştı ve bunu yazmak gerekiyor.** CLAUDE.md şöyle
diyordu:

> *"⚠ Beklenen sonuç kötü: tarayıcı 20 H.264 akışını CPU'da çözüyor
> (P-24). Donanım/tarayıcı sınırı, kod hatası değil — raporda böyle
> yazılacak."*

Ölçülünce kriter **tuttu**. "Beklenen sonuç kötü" bir tahmindi ve
ölçülmeden 20 gün kriterin yanında durdu.

---

#### 4. ⚠ Bu ölçümün sınırları — dürüstçe

1. **Başsız tarayıcı.** Gerçek bir kullanıcının ekranında GPU
   birleştirme (compositing) devreye girer; sonuç farklı olabilir.
   Kontrol serisi tavanın 60 olduğunu gösteriyor, yani ortam makul —
   ama birebir aynı değil.
2. **Kutucuk boyutu.** Varsayılan 1280×720 pencerede 20 kutucuk küçük
   ölçekleniyor. Tam ekran tek kamerada çözme maliyeti farklıdır.
3. **13.8 FPS/kamera**, kaynak videoların 25 FPS'inin altında. Yani
   video akıcı ama **kaynak hızında değil** — WebRTC/ağ tamponlaması
   bir miktar kare atlıyor olabilir. Düşen kare 0 olduğuna göre bu
   tarayıcı tarafında değil, akış tarafında oluyor.

**Raporda yazılacak ifade:**

> *"K10 ölçüldü: 20 kamera kutucuğu açıkken tarayıcı arayüzü 30.0 FPS
> çizmekte, hedef olan 30 FPS'i sağlamaktadır. Kamera açılmadan ölçülen
> kontrol değeri 60.2 FPS'tir; yani 20 eşzamanlı WebRTC akışı çizim
> hızını %50 düşürmektedir. Video karelerinin hiçbiri düşmemiştir
> (0/8254). Ölçüm başsız tarayıcıda yapılmıştır."*


---

### P-76 · ⭐⭐⭐ G18 — video ARTIK gerçekten kimlik doğrulamasından geçiyor (P-37'nin tam çözümü)

**Tarih:** 10.09.2026 · **Faz:** 3

**Bağlam:** Makale siber güvenlik ve teknoloji alanında yayımlanacak.
Kullanıcının tespiti: *"bu Caddy dediğin şey siber güvenlikle alakalı
olmuyor mu?"* — evet, ve projedeki en büyük açık kalıntısını kapatıyor.

---

#### Açık neydi (P-37, 30.08.2026)

**API kimlik doğrulamalıydı, VİDEO değildi.** `/api/*` uçları JWT
istiyordu; MediaMTX'in WHEP video akışı (`:8889`) hiçbir kimlik
sormuyordu. Kamera görüntüsünü almak için tek gereken **adresi
bilmekti**.

O gün uygulanan çözüm bir **ağ kısıtıydı**: port `127.0.0.1`'e
bağlandı.

⚠ **Bu açığı kapatmaz, erişimi sınırlar.** Makinede çalışan herhangi
bir süreç — ya da tarayıcıdaki herhangi bir sekme — hâlâ canlı
görüntüyü çekebilirdi. Gözetim sisteminde bu ayrım önemli: kayıtları
koruyup canlı görüntüyü açık bırakmak, kapıyı kilitleyip pencereyi
açık bırakmaktır.

---

#### ⭐ Çözümün anahtarı: TEK KÖKEN, kolaylık değil ZORUNLULUK

Token `HttpOnly` çerezde tutuluyor (`sentinel_token`) — bilinçli bir
karar: JavaScript okuyamadığı için XSS tokenı çalamıyor.

⭐ Ama bunun bir sonucu var: **tarayıcı çerezi yalnızca AYNI KÖKENE
gönderir.** Video ayrı portta (`:8889`) kaldığı sürece çerez oraya
gitmez ve video kimlik doğrulaması **mimari olarak imkânsızdır.**

Yani "tek giriş noktası" bir düzen tercihi değil, kimlik
doğrulamasının **ön koşulu**. Caddy'nin buradaki rolü TLS'ten önce bu.

```
tarayıcı ──HTTPS──> Caddy ─┬─ /api, /ws, /app  → FastAPI
                           └─ /<kamera>/whep   → forward_auth → MediaMTX
                                 │
                                 └─ önce FastAPI'ye sorulur:
                                    "bu istek yetkili mi?"  (401 ise
                                    video baytı bile akmaz)
```

---

#### ✅ İDDİA ÖLÇÜLDÜ — dört uçtan da

```
istek                                        sonuç
─────────────────────────────────────────────────────────────
doğrudan MediaMTX'e kimliksiz WHEP (:8889)    400  ⬅ isteği KABUL ediyor
Caddy üzerinden KİMLİKSİZ WHEP                401  ⬅ ENGELLENDİ ✅
Caddy üzerinden GİRİŞ YAPMIŞ WHEP             400  ⬅ GEÇTİ ✅
Caddy üzerinden panel                         200  ✅
Caddy üzerinden API (kimliksiz)               401  ✅
```

⚠ **"Giriş yapmış → 400" iyi bir sonuçtur:** Caddy isteği geçirdi ve
MediaMTX geçerli bir SDP teklifi bekliyordu (biz `v=0` gönderdik).
Yetki kapısı açıldı demektir.

⭐ **Her iki yön de sınandı.** Yalnızca "kimliksiz engelleniyor mu"
bakmak yarım bir testtir: meşru kullanıcıyı da kesen bir güvenlik
katmanı **"güvenli ama çalışmıyor"** durumudur ve o da bir arızadır.

---

#### Ek olarak uygulanan güvenlik başlıkları

Uygulama kodunda yapılamayacak, tam da vekilin işi olan korumalar:

| başlık | ne yapıyor |
|---|---|
| `Strict-Transport-Security` | tarayıcı bir daha HTTP denemesin |
| `X-Content-Type-Options: nosniff` | MIME tahminini kapat (XSS vektörü) |
| `X-Frame-Options: DENY` | çerçeveye gömülmeyi engelle (clickjacking) |
| `Referrer-Policy: no-referrer` | yönlendiren bilgisi sızmasın |
| `-Server` | sunucu sürümünü gizle |

Dördü de E2E testiyle doğrulanıyor (`e2e/g18-tls.spec.ts`, 4/4 geçti).

---

#### ⚠ Kararlar ve sınırlar — dürüstçe

1. **Varsayılan KAPALI** (`--profile tls`). Sebep: geliştirmede
   sertifika uyarısı iterasyonu yavaşlatıyor ve mevcut ölçüm betikleri
   düz HTTP kullanıyor. Açmak: `docker compose --profile tls up -d caddy`.
   ⚠ Bu, "güvenlik özelliği yazıldı ama açılmadı" durumudur ve raporda
   böyle yazılacak — sessizce kapalı bırakmak P-42'nin hatası olurdu.

2. **`tls internal`** — Caddy'nin yerel CA'sı. Let's Encrypt gerçek bir
   alan adı ister; bu yerel bir kurulum. Tarayıcı ilk açılışta uyarı
   gösterir. **Üretimde aynı yapılandırma, gerçek alan adıyla ve
   otomatik ACME ile değişmeden çalışır.**

3. **Port 8443**, 443 değil: 443 ayrıcalıklı ve bu makinede başka bir
   proje çalışıyor.

4. ⚠ **Kimlik doğrulaması yalnızca "oturum geçerli mi" diye soruyor,
   "bu kullanıcı BU kameraya bakabilir mi" diye sormuyor.** Kamera
   bazlı yetki (G05) kullanıcı kararıyla kapsam dışı; `forward_auth`
   yapısı onu eklemeye hazır (uç değiştirmek yeter).

**Öğrenilen ders:** Bir açığı **ağ katmanında** kapatmak (portu
`127.0.0.1`'e bağlamak) çoğu zaman "kapatıldı" diye kaydedilir. Ama
ağ kısıtı bir **erişim sınırı**dır, kimlik doğrulaması değildir. İkisi
farklı sorulara cevap verir: "kim ulaşabilir" ile "kim yetkilidir".


---

### P-77 · ⭐⭐⭐ İLK GERÇEK YANLIŞ ALARM ÖLÇÜMÜ — ve alarm sayısı DÖNGÜYLE ŞİŞİYOR

**Tarih:** 10.09.2026 · **Faz:** 3

**Bağlam:** P-68'de yer gerçeği altyapısı kurulmuştu (`video_pts` olay
kaydına taşındı). Bu kayıt onu **kullanıyor** ve K7'nin 20 gündür açık
duran sorusunu ilk kez cevaplıyor: *"bu alarmların kaçı gerçek?"*

---

#### 0. ⚠ ÖNCE ARACIN KENDİSİ BOZUKTU — ve "başarılı" diyordu

Klipler kesildi, hepsi **257 bayt** çıktı. Açılmıyorlardı. Ama betik
**"12/12 klip kesildi"** diye raporlamıştı (P-68, dün).

**İki hata üst üste:**

**(a) `pts` dosya içi konum DEĞİL.** MediaMTX kaynak videoları
`-stream_loop -1 -fflags +genpts` ile sonsuz döngüde yayınlıyor;
`genpts` zaman damgasını her turda sıfırlamıyor, **birikimli** üretiyor.
`pts = 2037.73`, 300 saniyelik bir videoda "2037. saniye" demek değil,
"yayın başlayalı 2037 saniye oldu" demek. Betik bunu doğrudan konum
sanıp dosyanın sonunun ötesine atlıyordu.
→ Düzeltme: `konum = pts % video_suresi`

**(b) Başarı kontrolü yalan söylüyordu.** Kontrol `dosya var ve
boyut > 0` idi; 257 baytlık, hiç kare içermeyen, açılamayan bir dosya
bu testi **geçiyordu**.
→ Düzeltme: dosya gerçekten açılıp ilk karesi okunuyor.

> ⭐ Bir çıktının **var olması**, kullanılabilir olması demek değil.
> Kontrol, dosyanın yapacağı işi yapmalı. Bu, P-61'deki
> "test etmediği şeyi test ettiğini söyleyen test" ile aynı sınıf.

---

#### 1. Etiketleme ölçütü — klipler İZLENMEDEN ÖNCE yazıldı

`docs/report/alarm-etiketleme-kurali.md`. Her tür için ölçüt, kuralın
**kodda ne iddia ettiğinden** türetildi ("bana anormal göründü" bir
ölçüt değil). Üç seçenek: 1 (haklı) / 0 (yanlış) / boş (karar
veremedim → analiz dışı).

⚠ Sebep P-49: ölçütü gördükten sonra yazmak, gördüğünü haklı
çıkaracak tanımı seçmektir.

**Seçim yanlılığı olmasın diye ilk 20 alarm SIRAYLA** etiketlendi —
"ilginç olanları seçmek" değil.

---

#### 2. Ham sonuç

```
tür        etiketli  gerçek  yanlış  kesinlik
crowd             8       8       0     1.00
fall              7       6       1     0.86
risk              4       4       0     1.00
─────────────────────────────────────────────
GENEL                                  0.947
```

**Tek yanlış alarm:** cam-19 `fall` — bir kişi **eğilip çanta alıyor**,
düşme yok. Kuralın "eğim değişim hızı >40°/sn" koruması bu hareketi
elemeye yetmemiş.

---

#### 3. ⭐⭐⭐ AMA BU SAYI OLDUĞU GİBİ RAPORLANAMAZ: BAĞIMSIZLIK SORUNU

Alarmların kaynak dağılımına bakılınca aynı olayların tekrarladığı
görüldü. `pts % video_süresi` ile döngüdeki konum hesaplandı:

```
video süreleri: cam-16 = 5 sn (!) · cam-13 = 114 · cam-15 = 128
                cam-04/05/17 = 300 · cam-19 = 345

cam-16 fall  konumlar [3.9, 3.9, 3.9, 4.9, 4.9]  → 1 AYRI olay
cam-15 risk  konumlar [63.8, 67.3, 72.6]         → 1 AYRI olay
cam-13 crowd konumlar [99.4, 99.4]               → 1 AYRI olay
cam-17 crowd konumlar [55, 129, 200, 275]        → 4 AYRI olay
```

⭐ **cam-16 videosu 5 SANİYE.** Düşme her 5 saniyede bir yeniden
oynuyor ve her turda alarm üretiyor. Beş "düşme alarmı" tek bir
düşmedir.

```
19 etiketli alarm  →  12 BAĞIMSIZ olay
düzeltilmiş kesinlik: 11/12 = 0.917
```

---

#### 4. ⚠⚠ BU, K7'NİN YORUMUNU DEĞİŞTİRİYOR

K7 "yanlış alarm ≤3/kamera-saat" diyor ve ölçülen **11.69/kamera-saat**
idi. Şimdi biliniyor ki bu sayı **döngüyle şişmiş**: aynı olay, video
her başa sardığında yeniden alarm üretiyor. cam-16'da bu **saatte 720
kez** demek (3600 ÷ 5).

⚠ **Gerçek bir kamerada böyle bir tekrar olmaz.** Bu, kurulumun
(kaynak olarak döngüdeki video dosyası kullanmanın) bir yan etkisidir,
sistemin davranışı değil.

**Raporda yazılacak dürüst ifade:**

> *"Alarm oranı ölçümleri, kaynak videoların sonsuz döngüde
> yayınlanmasından etkilenmektedir: kısa bir kaynak videoda (cam-16,
> 5 saniye) aynı olay saatte yüzlerce kez yeniden alarm üretmektedir.
> Bu nedenle ham alarm/kamera-saat oranı sistemin gerçek yanlış alarm
> davranışını temsil etmez. Döngüdeki konuma göre tekilleştirildiğinde
> 19 alarm 12 bağımsız olaya karşılık gelmekte ve kesinlik 0.917
> ölçülmektedir."*

---

#### 5. ⚠ Bu ölçümün sınırları — önceden yazıldı, sonradan değil

1. **Kesinlik ölçüldü, DUYARLILIK ölçülmedi.** Yalnızca sistemin
   ürettiği alarmlara bakıldı; "kaçırdığı olay var mı" sorusu için
   videoların tamamı etiketlenmeliydi.
2. **n = 12 bağımsız olay.** Küçük. Güven aralığı geniş olurdu.
3. **Tek değerlendirici**, ikinci gözle uyum ölçülmedi.
4. **`loitering` hiç ölçülemedi** — 45 saniyelik bir kuralı 6 saniyelik
   klip doğrulayamaz. "0 örnek" olarak raporlanacak, "%100" değil.
5. **Klipler sahne kesiği içeriyor:** kaynak videolar derleme
   (cam-17'nin bir klibi ofis → sokak → havaalanı geçiyor). Bu, Katman
   A'nın "kamera normali" varsayımını da zorluyor (aşağıya bakınız).

---

#### 6. ⭐ Yan bulgu: "her kameranın normali ayrı öğrenilir" varsayımı zorlanıyor

Mimari kural 7: *"Her kameranın normali ayrı öğrenilir."* Ama kliplerde
görüldü ki bazı kaynak videolar **birden çok sahnenin derlemesi**
(cam-17: ofis, gece sokak, havaalanı, restoran). Bir kameranın
"normali" böyle bir derlemede **alakasız sahnelerin ortalamasıdır** ve
olağandışılık skoru buna göre üretiliyor.

⚠ Bu bir kod hatası değil, **veri seti kurgusunun** bir sonucu —
gerçek bir sabit kamerada sahne değişmez. Raporda kapsam sınırı olarak
yazılacak.

**Öğrenilen ders:** Bir sistemin doğruluğunu ölçmek yetmiyor;
**ölçümün kendi bağımsızlık varsayımını** da kontrol etmek gerekiyor.
19 alarm 19 kanıt gibi görünüyordu; döngüdeki konum hesaplanınca 12
çıktı. Aynı olayı beş kez saymak, örneklem büyüklüğünü beş kat
abartmaktır.


---

### P-78 · ⭐⭐ Öğrenilen "kamera normali" UNUTMUYOR — sahne değişince kalıcı olarak yanlış kalıyor

**Tarih:** 10.09.2026 · **Faz:** 3

**Kullanıcının sorusu:** *"Bu anomalilerde her kameranın kendi normali
farklı olur şeyi vardı; şimdi bazı kameralar değişti, biz o kameraların
normalini de öğretmemiz gerekmiyor mu?"*

⭐ Haklıydı — ve sorun ölçülebilir çıktı.

---

#### Mimari kural 7 ve onun sessiz varsayımı

> *"Her kameranın normali ayrı öğrenilir. Koridorda koşmak anomali,
> spor salonunda değil."*

Doğru bir kural. Ama içinde **yazılmamış bir varsayım** var: *kameranın
sahnesi değişmez.*

`NormalProfilDeposu` kümülatif istatistik tutuyor — ziyaret ızgarası,
kişi sayısı, hız, yön, durağanlık. **Hiçbir unutma/yaşlandırma
mekanizması yok:** `toplam_ornek` en baştan artıyor, eski örnekler
hiç ağırlık kaybetmiyor.

---

#### Ölçülen kanıt: cam-15'in profili İKİ VİDEONUN KARIŞIMI

cam-15'in kaynak videosu 07.09.2026'da değiştirildi (CLAUDE.md'de
kayıtlı):

| | eski cam-15 (F_74) | yeni cam-15 (F_45) |
|---|---|---|
| kamera | elde telefon | sabit CCTV |
| **kişi/kare** | **6.5** | **3.0** |

Profilde ölçülen:

```
cam-15 · toplam_ornek 745 102 · kişi_sayısı ortalaması 4.01
```

⭐⭐ **4.01, 6.5 ile 3.0'ın arasında.** Profil iki farklı sahnenin
karışımını "normal" olarak öğrenmiş. Yani sistem, gerçekte hiç var
olmamış bir sahneyi normal sayıyor ve olağandışılığı ona göre ölçüyor.

⚠ Ve bu kamera canlıda en çok `risk` alarmı üreten kamera (93 alarmın
76'sı). Skorlarının dayandığı taban yanlış.

---

#### Yapılan

cam-15 profili **sıfırlandı** (silinmedi — yedeği
`data/profiles/_yedek_cam-15-karisik-20260910.json`). Boru hattı
çalışırken yeniden öğreniyor: eşik `PROFIL_ASGARI_ORNEK = 2000` ve
kamera ~2.8 örnek/sn ürettiği için **~12 dakikada** hazır oluyor.

⚠ Yalnızca cam-15 etkilenmişti; diğer 19 kameranın kaynak videosu
değişmedi (dosya tarihleri 13-26.08).

---

#### ⚠⚠ ASIL BULGU: BU BİR VERİ SORUNU DEĞİL, TASARIM AÇIĞI

cam-15'i sıfırlamak bu vakayı çözüyor ama **mekanizma duruyor.**
Gerçek bir kurulumda kameranın sahnesi şu durumlarda değişir:

- kamera yeniden yönlendirilir / kaydırılır (bakım, darbe)
- mevsim/aydınlatma değişir (yaz-kış, gece lambası takılır)
- alan yeniden düzenlenir (raf, duvar, mobilya)
- kalıcı davranış değişimi (yeni bir kapı açılır, yaya akışı değişir)

Unutmayan bir profil bunların hiçbirine uyum sağlayamaz ve **sessizce
yanlış kalır** — hata belirti vermez, yalnızca anomali skorları
anlamsızlaşır.

**Çözüm yönü (uygulanmadı, gerekçesiyle):** üstel ağırlıklı
istatistikler (eski örneklerin ağırlığı yarılanma süresiyle azalsın)
ya da kayan pencere. İkisi de `normalcy.py`'da yapısal değişiklik
demek ve kalan sürede kapsam dışı.

**Raporda yazılacak dürüst ifade:**

> *"Katman A'nın öğrendiği kamera normali kümülatiftir ve unutma
> mekanizması içermez. Bu, sahnenin sabit kaldığı varsayımına dayanır.
> Kaynak videosu değiştirilen bir kamerada (cam-15) profilin iki farklı
> sahnenin karışımını öğrendiği ölçülmüştür (kişi/kare ortalaması 4.01;
> gerçek değerler 6.5 ve 3.0). Üretim kurulumunda kamera yönü,
> aydınlatma veya alan düzeni değişikliklerinde aynı sorunun oluşacağı
> ve profilin elle sıfırlanması gerekeceği raporlanmaktadır. Kalıcı
> çözüm üstel yaşlandırmadır ve bu çalışmanın kapsamı dışında
> bırakılmıştır."*

**Öğrenilen ders:** Bir öğrenme mekanizmasının **ne öğrendiği** kadar
**ne unuttuğu** da tasarım kararıdır. "Unutma" varsayılan olarak
"yok"tur ve bu, açıkça seçilmemiş bir karardır — kurulumun sabit
kalacağını varsaymak, varsaydığını bilmeden varsaymaktır.


---

### P-79 · ⭐⭐⭐ KAYNAK VİDEOLAR DÖNGÜDE — alarm oranları bu yüzden karşılaştırılamaz

**Tarih:** 10.09.2026 · **Faz:** 3

**Kullanıcının tespiti:**

> *"Bu kameraların döngüdeki videolar olduğunu raporlarda kesinlikle
> vurgulamamız lazım. Çünkü senin de gördüğün gibi 5 sn'de bir video
> tekrarlanıyor ve kavga gerçekleşiyor sonra da alarm çıkıyor; sistem
> şişer bu şekilde ve bu da normal."*

Haklı, ve etkisi ölçüldü.

---

#### Kurulum: gerçek IP kamera yok, döngüdeki video dosyaları var

MediaMTX her kamerayı `-stream_loop -1` ile **sonsuz döngüde**
yayınlıyor (`infra/mediamtx/mediamtx.yml`). Bir olay içeren video
bittiğinde başa sarıyor ve **aynı olay yeniden gerçekleşiyor**.

**Ölçülen video süreleri ve saatlik tekrar sayısı:**

| kamera | süre | saatte tekrar |
|---|---|---|
| **cam-16** | **5 sn** | **667** ⬅⬅ |
| cam-08 | 42 sn | 86 |
| cam-07 | 70 sn | 51 |
| cam-20 | 65 sn | 55 |
| cam-10…cam-14 | 114 sn | 32 |
| cam-15 | 128 sn | 28 |
| cam-01…cam-06, cam-09, cam-17 | 300 sn | 12 |
| cam-18 / cam-19 | 328 / 345 sn | 11 / 10 |

⭐⭐ **cam-16'daki tek düşme olayı saatte 667 kez yeniden oynuyor** ve
her turda alarm üretiyor. Bu bir hata değil, kurulumun doğrudan
sonucudur.

---

#### Bunun bozduğu ölçüt: K7 (alarm/kamera-saat)

K7 *"yanlış alarm ≤3/kamera-saat"* diyor ve ham ölçüm
**11.69/kamera-saat** idi. Bu sayı **kaynak videonun uzunluğuyla ters
orantılı** olarak şişiyor:

```
aynı sistem, aynı algoritma, aynı olay
  5 saniyelik kaynakta   → saatte 667 alarm
300 saniyelik kaynakta   → saatte  12 alarm
```

⚠ Yani K7'nin ham değeri **sistemin davranışını değil, test
videolarının uzunluk dağılımını** ölçüyor. İki farklı kurulumun K7
sayıları karşılaştırılamaz.

⭐ P-77'de bu doğrulandı: 19 alarm, döngüdeki konuma göre
tekilleştirilince **12 bağımsız olaya** düştü.

---

#### Raporda kullanılacak ifade — zorunlu

> *"Sistem gerçek IP kameralarla değil, sonsuz döngüde yayınlanan video
> dosyalarıyla test edilmiştir. Bir kameranın kaynak videosu bittiğinde
> başa sarmakta ve içerdiği olay yeniden gerçekleşmektedir. Kaynak
> süreleri 5 ile 345 saniye arasında değişmekte; en kısa kaynakta
> (cam-16) tek bir düşme olayı saatte 667 kez tekrarlanmaktadır. Bu
> nedenle 'alarm/kamera-saat' türü ham oranlar sistemin yanlış alarm
> davranışını değil, test videolarının uzunluk dağılımını
> yansıtmaktadır. Alarm doğruluğu, döngüdeki konuma göre
> tekilleştirilmiş bağımsız olaylar üzerinden raporlanmıştır (P-77:
> 12 bağımsız olayda kesinlik 0.917)."*

⚠ **Bu bir kusur itirafı değil, ölçüm koşulunun tanımıdır.** Gerçek
kamerayla yapılmış bir çalışmada bu sorun olmaz; bizim kurulumumuzda
vardır ve belirtilmezse okuyucu K7'yi yanlış yorumlar.

---

#### ⭐ Ve bu, tasarımın bir yerini DOĞRULUYOR

Sistem aynı olayı tekrar tekrar gördüğünde her seferinde alarm
üretiyor — yani **histerezis ve soğuma mekanizmaları olayı
bastırmıyor.** İlk bakışta kusur gibi görünüyor ama doğru davranış
budur: 5 saniye sonra *yeniden* düşen bir insan, gerçekten yeni bir
olaydır. Sistem videonun döngüde olduğunu bilemez ve bilmemelidir.

**Öğrenilen ders:** Bir ölçütün birimi (`alarm/kamera-saat`) test
düzeneğinin bir özelliğine bağlıysa, o ölçüt **taşınabilir değildir**.
Sayıyı raporlamak yetmez; hangi koşulda üretildiğini raporlamak
gerekir — yoksa okuyucu onu kendi kurulumuyla kıyaslar ve yanılır.

