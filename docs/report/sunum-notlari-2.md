# 2. Ara Sunum — Konuşma Metni (4-5 dakika)

> **Kapsam:** Gün 5 (ilk video) → Gün 15. Ara: **35 commit**.
> **Hedef süre:** 4-5 dakika. Her bölümün yanında süre var.
> **Kural:** Her iddia bir sayıya dayanıyor. Sayıyı söyle.

---

## ⏱ 0:00-0:30 · Nerede kalmıştık

> "İlk videoda tek kameradan canlı kutu çizdirmiştim — Kilometre Taşı 1.
> O günden bugüne on iş günü geçti ve sistem artık **20 kamerayı birden**
> işliyor, üstüne **iskelet çıkarıyor**, **kimlik takip ediyor** ve
> bugün itibarıyla **anomali tespit ediyor**.
>
> Bu videoda üç şey anlatacağım: gecikmeyi nasıl düşürdüğümüz, yolda
> hangi teşhislerin **yanlış** çıktığı, ve anomali katmanının nasıl
> çalıştığı."

---

## ⏱ 0:30-2:00 · Gecikmeyle savaş — dört ayrı ders

> "Projenin gerçek zorluğu model seçmek değil. Modeller hazır. Zorluk
> 20 akışı tek laptop GPU'sunda **gerçek zamanlı** döndürmek."

### 1. Darboğaz GPU sanılıyordu, CPU çıktı

> "Sistem 20-37 FPS'te takılıydı. Kare başına 16 milisaniye ölçmüştüm,
> bu 62 FPS'e denk gelmeliydi. Aradaki açığı açıklayamıyordum.
>
> GPU'yu izledim: **%0-5 kullanımda**, 32 watt çekiyor — kartın bütçesi
> 125 watt. Kısıtlama sebebi `GpuIdle`. **GPU boş oturuyordu.**
>
> Ölçtüm: `predict()` süresinin **%53'ü** Ultralytics'in CPU tarafı ön
> işlemesinde geçiyordu. Yeniden boyutlandırma, renk dönüşümü,
> normalizasyon — hepsi CPU'da.
>
> Ön işlemeyi **alım katmanına taşıdım**. Neden orası: alım 20 kamera
> iş parçacığına dağılıyor ve OpenCV C kodunda GIL'i bırakıyor, yani
> gerçekten paralel koşuyor. Çıkarım worker'ı tek süreç — aynı işi orada
> yapmak seri kalırdı.
>
> **Gecikme 600 milisaniyeden 144'e düştü.**"

### 2. "Eski kare değersizdir" — ilkeyi yarım uygulamışım

> "Gecikme yine 1212 milisaniyeye çıktı. Üretim ve tüketim dengedeydi,
> saniyede 58 kare hem üretiliyor hem tüketiliyordu. Ama havuz sürekli
> doluydu.
>
> Şunu fark ettim: *'eski kare değersizdir, beklemek yerine atmak
> doğrudur'* cümlesi planımda ve kod yorumlarımda yazılıydı — ama
> yalnızca **üretici** tarafında uygulanmıştı. Tüketici tarafında hiç
> kod karşılığı yoktu. Kuyruğa giren kare, ne kadar beklerse beklesin
> sonunda işleniyordu.
>
> Çıkarım worker'ı artık 400 milisaniyeden eski kareyi **işlemeden**
> atıyor.
>
> **Gecikme 1212'den 181 milisaniyeye indi — 6.7 kat.** Bedeli
> karelerin yüzde 0.7'si.
>
> Buradan çıkan ders: **bir ilkeyi yazmak onu uygulamak değil.** Bir
> mimari kural koyduğunda, o kuralın **her sınırda** nerede
> uygulandığını göstermen gerekiyor."

### 3. Kutular insanların arkasından geliyordu

> "Gecikme düştü ama kullanıcı hâlâ kutuların takıldığını söylüyordu.
> İki ayrı hata vardı.
>
> Birincisi: hizalama kaydırıcısı **ters yönde** çalışıyordu. Analiz
> zaten geride olduğu için kutuların ileri tahmin edilmesi gerekiyordu;
> kod ise daha da geriye alıyordu.
>
> İkincisi daha ilginç: tampon, sonuçların **varış anına** göre
> indeksleniyordu. Ama boru hattı gecikmesi sabit değil. Düzenli
> aralıklarla yakalanan kareler **düzensiz aralıklarla varıyor.**
>
> Somut örnek: iki kare 250 milisaniye arayla yakalanmış, ama gecikmeleri
> farklı olduğu için tarayıcıya **50 milisaniye** arayla varıyor. Kod
> kişiyi beş kat hızlı sanıyor, kutuyu fırlatıyor, sonraki karede geri
> çekiyor. Kullanıcının gördüğü 'takılma' tam olarak buydu.
>
> Çözüm: sunucu her sonuca kendi ölçtüğü gecikmeyi ekliyor, böylece
> tarayıcı **yakalanma anını** hesaplayabiliyor. Zaman ekseni düzelince
> hareket düzgünleşti.
>
> Ders: zamanla ilgili hata ayıklarken **önce zaman eksenlerini yazmak**
> gerekiyor. Burada üç ayrı an vardı — yakalanma, varış, çizim — ve kod
> ikisini karıştırıyordu."

### 4. İskeletlerin yarısı çıkmıyordu

> "Kırpıntıların yalnızca **%47'sinden** iskelet çıkıyordu. Başarısızlık
> küçük kutularda yoğunlaşıyordu, yani 'çözünürlük sınırı' gibi
> görünüyordu. Bu açıklama veriye uyuyordu ve kabul etmeye hazırdım.
>
> **Yanlıştı.** Gerçek sebep **en-boy oranıydı.** Uzaktaki bir kişi ince
> ve uzun bir kutu verir — 40'a 130 piksel gibi. Bunu 192'ye 192'ye
> sıkıştırmak kişiyi yatay olarak üç kat şişiriyor ve model artık insan
> şekli görmüyor. En uzun kutular da tam olarak en uzaktaki, yani en
> küçük alanlı kişiler. **Alanla korelasyon sahteydi.**
>
> En-boy oranını koruyarak dolgulayınca: **%47'den %88'e.** En küçük
> kutularda %18'den %94'e.
>
> Bu gözetim açısından kritik: uzaktaki kişi tam da izlenmesi gereken
> kişi. 'Küçük kutulara poz çalıştırma' filtresini eklemiş olsaydım
> koridorun ucundaki kavgayı hiç göremezdik — ve sebebini de
> bilemezdik."

---

## ⏱ 2:00-3:00 · Yanlış çıkan teşhisler

> "Bu on günün en öğretici kısmı, doğru çıkan çözümler değil **yanlış
> çıkan teşhisler** oldu. Üçünü anlatayım."

### "58 milisaniye" ~8 kat yanlışmış

> "Yüz ifadesi modülünün maliyetini 'yüz başına 58 milisaniye' diye
> kaydetmiştim ve modülün **tüm bütçe tasarımı** buna dayanıyordu.
> Yeniden ölçtüm: **7.4 milisaniye.** Muhtemelen ısınma karesini ölçüme
> dahil etmişim.
>
> Ölçümü üreten betiği o zaman commit etmemişim — sayı vardı ama tekrar
> üretilemiyordu. Şimdi betik depoda."

### "cuDNN eksik" teşhisi dört gün dosyada durdu ve yanlıştı

> "ONNX Runtime'ın CUDA sağlayıcısı yüklenmiyordu ve sebebini 'cuDNN
> sürümü uyumsuz' diye kaydetmiştim. **Doğrulamamıştım.**
>
> Gerçek sebep: `onnxruntime` ve `onnxruntime-gpu` PyPI'da ayrı paketler
> ama **aynı dizine** açılıyorlar. Sonra kurulan diğerinin DLL'ini
> eziyor. CUDA sağlayıcısının dosyası **diskteydi**, ana kütüphane onu
> tanımıyordu.
>
> Ders: **doğrulanmamış teşhis, teşhis değil tahmindir** — öyle
> yazılmalı."

### GPU'da kırpıntı hazırlama fikri de çürüdü

> "Poz kademesi bütçenin %59'uydu ve GPU boştaydı. 'Kırpıntı hazırlığını
> GPU'ya taşırsak kazanırız' dedim, yazdım, ölçtüm:
> **3.6 kat daha yavaş** çıktı.
>
> Sebep: benim uygulamam kareleri poz için yeniden GPU'ya yüklüyordu,
> oysa dedektör onları zaten yüklemişti.
>
> Bu üçü aynı dersin farklı yüzleri: **makul görünen bir hipotez,
> ölçülmeden uygulanırsa yanlış olabiliyor.** Ölçüm olmadan
> optimizasyon, tahminle mühendislik yapmaktır."

---

## ⏱ 3:00-4:15 · Anomali katmanı — bugünkü iş

> "Bugün sistem ilk kez **anlam** üretmeye başladı. Şimdiye kadar
> 'burada bir insan var, şu hızda hareket ediyor' diyordu. Artık
> **'bu kişi düştü'** diyebiliyor."

### Neden kural, neden model değil

> "Anomali için etiketli veri toplanamaz — tanımı gereği 'daha önce
> görülmemiş olan'dır. 'Kavga' için iki bin klip bulunur ama 'anormal'
> diye bir sınıf yoktur. **Otoparkta koşmak anormal, spor salonunda
> değil.**
>
> Bu yüzden iki katmanlı yaptım."

### Katman B — kanıt zinciri

> "Fizikle tanımlanabilen olayları yakalıyor: düşme, koşma, oyalanma,
> kalabalık. İlk günden çalışıyor, öğrenme süresi beklemiyor.
>
> Ama kritik tasarım kararı şu: **her kural bir eşik değil, bir kanıt
> zinciri.**
>
> 'Kutu oranı birden büyükse düşmedir' demek yanlış olurdu — eğilip bir
> şey alan kişi de o oranı verir. Gerçek düşme **üç şeyin birlikte**
> olmasıdır: kutu oranı tersine döner, gövde yatay olur, **ve eğim ani
> değişir.** Asıl ayırt edici üçüncüsü: düşme ani bir olaydır, eğilerek
> çanta almak yavaştır.
>
> Test ettim: ayakta duran kişi alarm vermiyor, **yavaş eğilen kişi de
> vermiyor**, düşen kişi veriyor."

### Katman A — her kameranın kendi normali

> "Bugün eklediğim ikinci katman **öğreniyor.** Kareyi 32'ye 18'lik bir
> ızgaraya bölüyor ve her hücre için üç şey tutuyor: buraya ne sıklıkla
> gidilir, burada ne hızda hareket edilir, buradan hangi yöne gidilir.
>
> Güzel tarafı şu: **'ters yön' kuralını ayrıca yazmadım.** Koridorda
> herkes bir yöne gidiyorsa, ters yön o hücrede zaten nadir bir kova
> oluyor. Profil, kural yazmadan kural üretiyor.
>
> Üç koruma koydum. Birincisi: profil iki bin örnek görmeden **hiç skor
> üretmiyor** — yoksa sistem her açılışta alarm yağdırırdı, çünkü hiçbir
> şey öğrenilmemişken her gözlem 'hiç görülmemiş' olur. İkincisi: her
> gözlem **önce skorlanıyor, sonra öğreniliyor** — tersi olsaydı olay
> kendi normalini yükseltip kendini gizlerdi. Üçüncüsü: profil diske
> yazılıyor, çünkü **profil kaybı sistem körlüğü demek.**"

### Yanlış alarmla savaş

> "İlk sürümde yalnızca histerezis vardı. 90 saniyelik koşuda 13 anomali
> çıktı ve aynı kamera tekrar tekrar alarm verdi. Hesapladım:
> **kamera-saat başına 18 alarm.** Kriterim üçten az.
>
> Sebep: histerezis 'sınırdaki değer titremesin' diye vardır; **soğuma**
> ise 'aynı olay tekrar tekrar bildirilmesin' diye. Farklı problemler,
> ikisi birden gerekiyor. Soğumayı ekledim: **18'den 11'e** indi. Hedefe
> henüz ulaşmadım, çalışma devam ediyor.
>
> Ve kullanıcı testinde bir şey daha çıktı: panelde koşma alarmları
> vardı ama **videolarda koşan kimse yoktu.** Hızları ölçtüm — 13 bin
> örnek: doksan dokuzuncu persentil 0.94, alarmlar ise 1.58 ile 2.21
> arasında. Yani ölçümün **üç katı**.
>
> Bunlar koşan insan değil, **takip gürültüsü**: takipçi bir kimliği
> başka kişiye atadığında konum sıçrıyor ve sahte bir hız doğuyor.
> Koşma kuralına ayrı bir güvenilirlik şartı ekledim."

---

## ⏱ 4:15-5:00 · Dürüst tablo ve sırada ne var

> "Şimdi dürüst olmam gereken kısım.
>
> **Kriterimi tutturamadım.** Hedef kamera başına saniyede 4 analiz.
> Örnekleme hedefini tutturdum ama gerçekleşen analiz hızı daha düşük.
> Çıkarımı tek başına ölçtüm: bu donanım saniyede 12 kare işleyebiliyor,
> 20 kamera için 80 gerekiyor.
>
> Bu, risk kaydımda **R2** olarak zaten öngörülmüştü: *'20 kamera hedefi
> tutmazsa gerçek sayıyı ölç ve X kamerada Y FPS olarak dürüstçe
> raporla.'* Şimdi yaptığım tam olarak bu.
>
> Ayrıca bir ölçümüm kirli çıktı: çekişmeyi 10 kat diye raporlamıştım,
> sonra o ölçümün yavaş bir kod yolu açıkken alındığını fark ettim.
> **İddiayı geri aldım**, yeniden ölçülecek.
>
> Sırada: saldırganlığın erken tespiti. Elimde iki bin klipli RWF-2000
> veri seti hazır ve özellik çıkarım motoru çalışıyor. Ondan sonra
> füzyon, alarm motoru, olay veritabanı ve güvenlik katmanı var.
>
> Son olarak sayılar: on gün önce depoda **sıfır test** vardı, şimdi
> **105 test** var. Ve testler yazılırken **iki gerçek güvenlik hatası**
> buldular — bunlardan biri bozuk bir başlıkla dışarıdan tetiklenebilen
> bir çökme yoluydu.
>
> Teşekkürler."

---

# 🎬 EKRAN ÇEKİM SIRASI

| Sıra | Ne gösterilecek | Süre |
|---|---|---|
| 1 | Panel açılışı — 20 kamera ızgarası | 10 sn |
| 2 | Bir kutucuk büyüt: **kutular + iskelet** çiziliyor | 15 sn |
| 3 | **cam-20** — yakın plan yüz, ifade etiketi | 10 sn |
| 4 | Kesikli çizgili kutu — "kimlik henüz onaylanmadı" | 5 sn |
| 5 | **Alarm paneli** — anomaliler ve kanıt satırları | 20 sn |
| 6 | Sakin kamera — `sakin · hareket yok` rozeti | 5 sn |
| 7 | Hizalama kaydırıcısı — video tamponu etkisi | 10 sn |

## ⚠ Çekim öncesi kontrol listesi

- [ ] **Docker Desktop açık** (şu an kapalı!)
- [ ] `docker compose up -d` — Valkey, MediaMTX, PostgreSQL
- [ ] Alım, çıkarım, **analitik** worker'ları ve API çalışıyor
- [ ] **90 saniye bekle** — ısınma süresi ölçüldü, öncesindeki sayılar kötümser
- [ ] **4-6 kutucuk aç, 20 değil** — bütçe 40 FPS, 20 kutucukta kamera başına 2 FPS düşer; az kutucukta kutular çok daha iyi oturur
- [ ] Alarm panelinde en az birkaç anomali birikmiş olsun

## 💬 Muhtemel sorular

**"Neden 20 kamerada 4 FPS tutmuyor?"**
> Ölçtüm: çıkarım tek başına saniyede 12 kare işliyor, 80 gerekiyor.
> Bu bir laptop GPU'su ve modeller tek kopya. Riski baştan öngörmüştüm,
> gerçek sayıyı ölçüp raporluyorum. Çözüm yönleri belli: boru hattı
> paralelleştirmesi ve TensorRT — ama önce ölçüp sonra uygulayacağım.

**"Anomali dediğin şeyler normal davranışlar değil mi?"**
> Doğru soru. Anomali mutlak değil bağlamsaldır. Katman B fizikî
> olayları yakalıyor, Katman A ise her kameranın kendi normalini
> öğreniyor. İkisi birlikte "bu olay **burada** olağandışı" diyebiliyor.

**"Yüz tanıma yapıyor musun?"**
> Hayır — ve bu bilinçli. Yüz **tanıma** kimlik eşleştirmedir, biz yüz
> **ifadesi** sınıflandırıyoruz. Yüz görüntüsü saklanmıyor, gömme
> vektörü de saklanmıyor; sadece etiket ve güven skoru. KVKK'da yüz
> verisi özel nitelikli kişisel veri ve kodda `store_face_crops`
> ayarının açılması doğrulayıcıyla engelli.
