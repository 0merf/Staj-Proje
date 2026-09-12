# SENTINEL — Çok Kameralı Akıllı Gözetim Sistemi

## KAPAK

**T.C. DÜZCE ÜNİVERSİTESİ**
**MÜHENDİSLİK FAKÜLTESİ**
**BİLGİSAYAR MÜHENDİSLİĞİ BÖLÜMÜ**

**STAJ RAPORU**

**Proje Adı:** SENTINEL — Çok Kameralı Akıllı Gözetim Sistemi
(Anomali Tespiti, Duygu Analizi ve Saldırgan Davranışın Erken Tespiti)

**Öğrenci:** Ömer Faruk Kanat
**Staj Yeri:** Düzce Üniversitesi
**Staj Danışmanı:** Dr. Öğr. Üyesi Ahmet Albayrak
**Staj Süresi:** 25 iş günü (12 Ağustos – 12 Eylül 2026)
**Depo:** https://github.com/0merf/Staj-Proje

---

## İÇİNDEKİLER

1. Giriş
2. Firma Hakkında Bilgi
3. Projenin ve Yapılacak İşin Tanımı
4. Yapılan Proje ve İş
&nbsp;&nbsp;&nbsp;&nbsp;4.1. Teknoloji Seçimleri ve Gerekçeleri
&nbsp;&nbsp;&nbsp;&nbsp;4.2. Sistem Mimarisi
&nbsp;&nbsp;&nbsp;&nbsp;4.3. Kademeli İşleme
&nbsp;&nbsp;&nbsp;&nbsp;4.4. Veri Seti ve Kamera Çiftliği
&nbsp;&nbsp;&nbsp;&nbsp;4.5. Anomali Tespiti
&nbsp;&nbsp;&nbsp;&nbsp;4.6. Saldırganlık Tespiti
&nbsp;&nbsp;&nbsp;&nbsp;4.7. Duygu Analizi
&nbsp;&nbsp;&nbsp;&nbsp;4.8. Alarm Zinciri ve Kanıt Klibi
&nbsp;&nbsp;&nbsp;&nbsp;4.9. Web Arayüzü
&nbsp;&nbsp;&nbsp;&nbsp;4.10. Güvenlik
&nbsp;&nbsp;&nbsp;&nbsp;4.11. Test ve Kalite Kapıları
&nbsp;&nbsp;&nbsp;&nbsp;4.12. Ölçüm Yöntemi ve Karşılaşılan Sorunlar
&nbsp;&nbsp;&nbsp;&nbsp;4.13. Başarı Kriterleri ve Sonuçlar
5. Sonuç
6. Ekler
7. Kaynaklar

---

## 1. GİRİŞ

Bu rapor, Düzce Üniversitesi Bilgisayar Mühendisliği Bölümü staj yükümlülüğü kapsamında 12 Ağustos – 12 Eylül 2026 tarihleri arasında yürütülen 25 iş günlük çalışmayı anlatmaktadır.

Staj kapsamında verilen görev şuydu: **en az 20 kameranın izlendiği, anomali tespiti, duygu analizi ve saldırgan davranışın erken tespitini yapan yapay zekâ modellerinin koştuğu web tabanlı bir uygulama geliştirmek.** Teknik detaylar bilinçli olarak belirtilmemiş, seçimler geliştiriciye bırakılmıştı. Bu, görevin asıl sınavının model seçmek değil, **her seçimi gerekçelendirebilmek** olduğu anlamına geliyordu.

Çalışmaya başlarken problemin zorluğunu yanlış konumlandırmıştım. "Hangi modeli kullanmalıyım" sorusunun merkezde olduğunu sanıyordum. Birkaç gün içinde asıl zorluğun başka bir yerde olduğu ortaya çıktı: **20 eşzamanlı video akışını tek bir orta seviye dizüstü ekran kartında gerçek zamanlı işleyebilen bir mimari kurmak.** Model seçimi bu kısıtın bir sonucu oldu, sebebi değil.

Raporun yazım biçimi hakkında bir not: bu belge yalnızca "şunu yaptım" listesi değil, **neyi neden yaptığımı ve nerede yanıldığımı** da anlatmaktadır. Proje boyunca tutulan mühendislik günlüğünde 87 kayıt birikti ve bunların 43'ünde doğru sandığım bir şey ölçümle çürüdü (Tablo 4.8). Bu kayıtlar raporun en öğretici kısmını oluşturuyor; bu yüzden gizlenmek yerine ayrı bir bölümde (4.12) ele alınmıştır.

Çalışma boyunca kullanılan tüm kaynak kod, ölçüm betikleri ve ölçüm çıktıları genel erişime açık bir depoda toplanmıştır: https://github.com/0merf/Staj-Proje

Projenin sonuçları ayrıca bir dergi makalesine dönüştürülmüş ve *Siber Güvenlik ve Dijital Ekonomi Dergisi*'ne (CDEJ, Düzce Üniversitesi) sunulmak üzere hazırlanmıştır.

---

## 2. FİRMA HAKKINDA BİLGİ

**Kurum adı:** Düzce Üniversitesi
**Adres:** Düzce Üniversitesi Konuralp Yerleşkesi, 81620 Düzce
**Faaliyet alanı:** Yükseköğretim, akademik araştırma ve geliştirme
**Staj danışmanı:** Dr. Öğr. Üyesi Ahmet Albayrak

Staj, Düzce Üniversitesi bünyesinde ve Dr. Öğr. Üyesi Ahmet Albayrak'ın danışmanlığında yürütülmüştür. Çalışma, ticari bir ürün geliştirme değil, **araştırma nitelikli bir prototip geliştirme** çalışmasıdır.

Bu ayrımın rapor açısından iki sonucu vardır. Birincisi, başarı ölçütü bir müşteri gereksinimi değil, baştan tanımlanmış ve sayısal olarak ölçülebilen on kriterdir (Bölüm 4.13). İkincisi, ticari bir kurulumda zorunlu olacak bazı işlevler (örneğin kişisel verilerin korunması kapsamında yüz bulanıklaştırma) kapsam dışı bırakılmış ve bu karar gerekçesiyle kaydedilmiştir.

Çalışma yöntemi olarak akademik bir disiplin benimsenmiştir: her adımda tek bir hipotez kurulmuş, izole bir deneyle ölçülmüş, sonuca göre karar verilmiş ve karar gerekçesiyle birlikte belgelenmiştir. Bu yöntemin ürünü, koddan bağımsız olarak tutulan üç belge kümesidir: mimari karar kayıtları (`docs/decisions/`), mühendislik günlüğü (`docs/report/problems.md`) ve ölçüm çıktıları (`benchmarks/`).

---

## 3. PROJENİN VE YAPILACAK İŞİN TANIMI

### 3.1. Görev tanımı

Görev üç yetenek istiyordu ve üçü de aynı anda, aynı donanımda çalışmalıydı. Bu yetenekler Tablo 3.1'de özetlenmiştir.

**Tablo 3.1** Şartnamenin istediği üç yetenek ve her birinden beklenen davranış.

| Yetenek | Ne yapması bekleniyor |
|---|---|
| Anomali tespiti | Her kameranın kendi "normal"ini öğrenip bu normalden sapmayı bildirmek |
| Duygu analizi | Görüntüdeki kişilerin yüz ifadesini sınıflandırmak |
| Saldırgan davranışın erken tespiti | Şiddet olayını, mümkünse başlamadan önce fark etmek |

Buna ek olarak sistem web tabanlı olacak, en az 20 kamerayı eşzamanlı izleyecek ve gerçek zamanlı çalışacaktı.

### 3.2. Çalışma ortamı ve kısıtlar

Kısıtlar en baştan netti ve tüm mimari kararları belirlediler. Tablo 3.2 bu kısıtları ve her birinin mimariye nasıl yansıdığını göstermektedir.

**Tablo 3.2** Projenin donanım, veri ve zaman kısıtları ile bu kısıtların mimariye yansıması.

| Kısıt | Değer | Sonucu |
|---|---|---|
| Ekran kartı | RTX 3070 Laptop, 8 GB | Modeller tek kopya yüklenmeli |
| İşlemci | 20 mantıksal çekirdek | Ön işleme ile çıkarım aynı çekirdekleri paylaşıyor |
| Sistem belleği | 16 GB | Çok süreçli mimariye sınır |
| Gerçek IP kamera | **Yok** | 20 kamera video dosyalarından benzetilecek |
| Süre | 25 iş günü | Kapsam sıkı tutulmalı |
| Geliştirici | 1 kişi | Paralel iş yapılamaz |

Dizüstü ekran kartının, aynı adı taşıyan masaüstü modelin yaklaşık %65-75'i başarım verdiğini ve termal kısıtlamaya açık olduğunu da baştan not etmek gerekiyor. Yani elimizdeki donanım "orta seviye"nin de altında bir bütçeydi.

### 3.3. Başarı kriterleri

Çalışmaya başlamadan önce on başarı kriteri sayısal olarak tanımlandı. Bunun sebebi basit: **sonradan tanımlanan bir kriter, elde edilen sonuca göre şekillenir.** Kriterler ve hedefleri Tablo 4.10'da verilmiştir.

Planın kendi ifadesiyle: *"Hedefi tutturamamak başarısızlık değildir; ölçmemek başarısızlıktır."* Bu cümle raporun geri kalanının da tonunu belirliyor.

---

## 4. YAPILAN PROJE VE İŞ

### 4.1. Teknoloji Seçimleri ve Gerekçeleri

Her teknoloji seçimi bir gerekçeyle birlikte kaydedildi. Tablo 4.1'de ana seçimler ve nedenleri özetlenmiştir.

**Tablo 4.1** Teknoloji seçimleri ve gerekçeleri.

| Katman | Seçim | Gerekçe |
|---|---|---|
| Dil ve arka uç | Python 3.13 + FastAPI | Yapay zekâ ekosistemi Python'da. ASP.NET Core değerlendirildi ve elendi |
| Mesaj kuyruğu | Valkey 8 | Redis'in BSD lisanslı çatallanması; aynı istemci kütüphanesi çalışıyor |
| Veritabanı | PostgreSQL 17 + TimescaleDB | Olay kayıtları zaman serisi; sürekli toplulaştırma gerekiyordu |
| Medya sunucusu | MediaMTX | Hem sahte kamera üretiyor hem WebRTC veriyor, yeniden kodlama yapmıyor |
| Video çözme | PyAV | Kütüphane olarak kullanılıyor, kabuğa çıkmıyor: komut enjeksiyonu yüzeyi yok |
| Nesne tespiti | YOLO26-s | NMS gerektirmeyen mimari, gerçek zamanlı hedefe uygun |
| Takip | BoT-SORT (Aharon vd., 2022) | Kamera başına ayrı örnek; sabit kamera olduğu için CMC kapalı |
| Poz kestirimi | YOLO26-pose | Yukarıdan aşağı: tespit kutusu kırpılıp modele veriliyor |
| Yüz ve ifade | YuNet (Wu vd., 2023) + EmotiEffLib | Hafif; ifade sınıflandırma füzyonda düşük ağırlıklı |
| Ön yüz | React 19 + TypeScript + Vite | Canlı kutu çizimi için canvas denetimi gerekiyordu |
| Ters vekil | Caddy | Otomatik TLS ve `forward_auth` desteği |
| Gözlem | Prometheus + Grafana | Ölçüm altyapısı projenin omurgası oldu |

Seçimlerin bir kısmı proje sırasında **değişti** ve bu değişiklikler de gerekçeleriyle kaydedildi. Örneğin nesne deposu olarak Garage seçilmişti; tek makineli bir kurulumda nesne deposunun çözdüğü sorun (dağıtık depolama) bulunmadığı için kapsam dışı bırakıldı ve klipler yerel diske yazıldı.

### 4.2. Sistem Mimarisi

Sistem beş bağımsız süreçten oluşuyor ve süreçler arası iletişim Valkey akışları üzerinden sağlanıyor. Şekil 4.1 bu akışı ve her adımın ölçülen maliyetini göstermektedir.

**[GORSEL: diagrams/01-veri-akisi.png]**
**Şekil 4.1** Sistemin veri akışı ve ölçülen maliyetler. Kutuların üzerindeki sayılar tahmin değil, ölçüm sonuçlarıdır.

Mimaride dört kural benimsendi ve bu kurallar doğrudan donanım kısıtından türedi.

**Ham video karesi mesaj kuyruğundan geçmiyor.** 1080p bir kare yaklaşık 6 MB. Yirmi kameradan saniyede birkaç kare hızıyla bu veriyi kuyruğa yazmak, kuyruğun kendisini darboğaza çevirir. Bunun yerine kareler **paylaşımlı belleğe** yazılıyor, kuyruktan yalnızca bir referans geçiyor. Havuz 96 yuvadan oluşuyor, her yuva tam bir 720p kare tutuyor (1280 × 720 × 3 bayt = 2,76 MB), toplam 265 MB.

Havuzun bu kadar küçük olması bir depolama kararı değil, bir **kuyruk kararı**. Yuvalar yalnızca alım ile çıkarım arasında yolda olan kareleri tutuyor. Havuzu büyütmek belirli bir noktadan sonra fayda vermiyor: tüketici doymuşsa daha büyük bir tampon verimi artırmaz, yalnızca kuyrukta bekleyen karelerin daha eski olmasına, dolayısıyla gecikmenin artmasına yol açar.

**Sunucu videonun üzerine kutu çizmiyor.** Video tarayıcıya WebRTC tabanlı WHEP protokolüyle doğrudan medya sunucusundan gidiyor; tespit kutuları ayrı bir WebSocket bağlantısından JSON olarak gidiyor ve çizimi tarayıcı yapıyor. Bu ayrım sayesinde sunucuda 20 ayrı video akışını yeniden kodlamak gerekmiyor.

**Modeller tek süreçte, tek kopya.** Ölçülen video belleği kullanımı 571 MB, yani 8 GB'ın %7'si.

**Bütün kuyruklar sınırlı.** Sınırsız kuyruk, üretici tüketiciden hızlı olduğunda bellek tükenmesi demek. Eski kareler bekletilmek yerine düşürülüyor ve düşen kare sayısı ayrıca ölçülüyor.

### 4.3. Kademeli İşleme

Yirmi akışın tek ekran kartında işlenebilmesi, her kareye her modelin uygulanmamasıyla mümkün oluyor. Kademeler ve maliyetleri Şekil 4.2'de gösterilmiştir.

**[GORSEL: diagrams/02-kademeli-isleme.png]**
**Şekil 4.2** Kademeli işleme ve her kademenin ölçülen maliyeti. Sağdaki çubuklar kare başına milisaniye cinsindendir.

- **Kademe 0 — Hareket kapısı (işlemcide).** Ardışık kareler arasındaki farka bakılarak hareketsiz sahneler eleniyor. Ayrıca uyarlanabilir örnekleme var: uzun süre hareket görülmeyen bir kamerada örnekleme hızı 4 kare/saniyeden 1 kare/saniyeye düşüyor.
- **Kademe 1 — Nesne tespiti (ekran kartında).** Yalnızca insan sınıfı aranıyor.
- **Kademe 1b — Takip.** Her kamera için ayrı takipçi örneği tutuluyor; takip durumu kamera içinde saklandığı için bir kameranın hep aynı sürece gitmesi zorunlu.
- **Kademe 2a — Poz kestirimi.** Tespit edilen her kişi kutusuna uygulanıyor. Döngünün en pahalı kalemi: kare başına 10,96 ms, bütçenin %48'i.
- **Kademe 2b — Yüz ve ifade.** İki basamaklı bir kapıyla seyreltiliyor (Bölüm 4.7).

Planlanan ama **gerçekleştirilmeyen** bir kademe var: Kademe 3, video tabanlı eylem doğrulayıcı. Tırmanma skoru eşiği aştığında kısa bir video kesitini üç boyutlu bir evrişimli ağa verip alarmı doğrulaması ya da reddetmesi öngörülmüştü. Yapılmama gerekçesi Bölüm 5'te açıklanmıştır. Belgede duran bir kademenin kodda olmaması yanlış beyandır; bu yüzden sessizce atlanmamış, açıkça yazılmıştır.

### 4.4. Veri Seti ve Kamera Çiftliği

Gerçek IP kamera bulunmadığı için 20 kamera, farklı veri setlerinden derlenen video dosyalarının bir medya sunucusu üzerinden **sonsuz döngüde** yayınlanmasıyla benzetildi. Sistem açısından bu akışlar gerçek RTSP kameralarından ayırt edilemiyor. Kullanılan kaynak veri setleri ve her birinin hangi kameralara beslendiği Tablo 4.2'de verilmiştir.

**Tablo 4.2** Kamera çiftliğinin kaynak veri setleri.

| Veri seti | Kameralar | İçerik | Kullanım amacı |
|---|---|---|---|
| VIRAT Ground 2.0 (Oh vd., 2011) | cam-01 – cam-08 | Sabit gözetim: otopark, kampüs, bina girişi | Anomali modülünün "normal"i öğrenmesi |
| Oxford Town Centre (Benfold ve Reid, 2011) | cam-09 | Yoğun yaya trafiği, yer gerçekli | Takip doğruluğu referansı |
| PETS 2009 (Ferryman ve Shahrokni, 2009) | cam-10 – cam-14 | Çok kameralı kalabalık, ani dağılma | Kalabalık ve dağılma kuralları |
| UBI-Fights (Degardin ve Proença, 2020) | cam-15 | Uzun süreli gözetim, şiddet olaylı | Erken uyarı, bağlamlı ölçüm |
| UR Fall Detection (Kwolek ve Kepski, 2014) | cam-16 | Kontrollü düşme kayıtları | Düşme kuralının doğrulanması |
| RWF-2000 (Cheng vd., 2021) | cam-17 | Gözetim kaynaklı kavga klipleri | Saldırganlık modülü |
| CUHK Avenue (Lu vd., 2013) | cam-18, cam-19 | Kampüs gözetimi, kare düzeyli etiket | Anomali kontrolü ve testi |
| Pexels | cam-20 | Yakın plan yüz içeren sahneler | İfade modülü testi |

Buna ek olarak dizüstü bilgisayarın kendi kamerası "cam-21 — canlı" olarak sisteme bağlandı; demo sırasında sistemin gerçek bir kamerayla da çalıştığını göstermek için.

**Döngünün ölçümler üzerindeki etkisi.** Kaynak videoların süreleri 5 saniye ile 345 saniye arasında değişiyor. En kısa kaynaktaki tek bir düşme olayı saatte yaklaşık 720 kez yeniden oynuyor ve her turda alarm üretiyor. Bu, "alarm/kamera-saat" türü ham oranları kullanılamaz hale getiriyor: aynı sistem, aynı algoritma ve aynı olay, 5 saniyelik bir kaynakta saatte 720, 300 saniyelik bir kaynakta 12 alarm üretiyor. Ham oran sistemin davranışını değil, test videolarının uzunluk dağılımını ölçüyor. Bu bulgu ölçüt tanımının değiştirilmesine yol açtı (Bölüm 4.13).

### 4.5. Anomali Tespiti

Anomali tespiti iki katman ve bir birleştirme aşamasından oluşuyor.

**Katman A — öğrenilmiş normal.** Her kamera için ayrı bir profil tutuluyor. Profil, o kameradaki kişilerin konum dağılımı, hız dağılımı ve yoğunluk dağılımından oluşuyor. Bir gözlem bu profilden ne kadar sapıyorsa anomali skoru o kadar yükseliyor. Mimari kural açık: **her kameranın normali ayrı öğrenilir.** Koridorda koşmak anomali, spor salonunda değil.

**Katman B — fiziksel kurallar.** Düşme, koşma, oyalanma, kalabalık gibi olaylar poz ve takip verisinden türetilen kurallarla aranıyor. Örneğin düşme kuralı gövde en-boy oranına, gövde eğimine ve eğim değişim hızına bakıyor.

**Füzyon.** Takip edilen her kişi için beş sinyal 0-1 aralığında üretiliyor ve Tablo 4.3'teki ağırlıklarla toplanıyor.

**Tablo 4.3** Füzyon katmanının birleştirdiği beş sinyal ve ağırlıkları. Ağırlıklar toplamı 1,00'dir.

| Sinyal | Ağırlık |
|---|---|
| Saldırganlık | 0,40 |
| Profil sapması (Katman A) | 0,25 |
| Fiziksel kural ihlali (Katman B) | 0,20 |
| Yüz ifadesi | 0,10 |
| Kalabalık yoğunluğu | 0,05 |

Toplam skor ardından **üstel hareketli ortalama** ile zamansal olarak yumuşatılıyor ve histerezis uygulanıyor. Yumuşatma, ardışık pencerelerde hesaplanan skorun doğrudan kullanılması yerine önceki değerle harmanlanması demek; amaç tek bir gürültülü pencerenin alarm çaldırmasını engellemek.

**Ölçüm sonucu ve çürütülen bir iddia.** Anomali tespiti CUHK Avenue veri setinde ölçüldü (9 klip, 1439 kare). Füzyonun eğri altı alan değeri **0,869**, küme önyükleme (Efron, 1979; Field ve Welsh, 2007) %95 güven aralığı [0,806 – 0,929].

Ancak "füzyon kazandırıyor" iddiasını sınamak için bir **kontrol serisi** tanımlandı: tek bir sinyale, füzyonla *aynı* yumuşatma uygulandı. Sonuçlar Tablo 4.4'te verilmiştir.

**Tablo 4.4** Kontrol serisi: yumuşatmanın ve sinyal birleştirmenin katkıları ayrı ayrı ölçülmüştür (CUHK Avenue, 9 klip, 1439 kare).

| Sinyal | AUC |
|---|---|
| Profil sapması, ham | 0,789 |
| Profil sapması + yumuşatma (kontrol) | 0,860 |
| Füzyon (5 sinyal + yumuşatma) | 0,869 |

Yumuşatma 0,071 puan kazandırıyor, beş sinyali birleştirmek 0,009 puan ekliyor. Anlamlılık eşiği ölçümden **önce** 0,02 olarak belirlenmişti; fark bu eşiğin altında. Yani bu veri setinde kazancı sağlayan sinyal birleştirme değil, zamansal yumuşatma.

Bu, füzyonun gereksiz olduğu anlamına gelmiyor. Bu veri setinde beş sinyalden ikisi işlevsiz: fiziksel kural sinyalinin AUC değeri tam 0,500, yani hiç ateşlemiyor (Avenue'nun anomalileri çanta fırlatma, bisiklet ve ters yön; bizim kurallarımız insan hareketi üzerine tanımlı). Saldırganlık sinyali 0,457 ile şans düzeyinin altında. **İşlevsiz sinyalleri birleştirmek bir şey kazandıramaz.** Füzyonun ölçülen asıl katkısı ayırt etme gücünde değil, gürültü bastırmada.

### 4.6. Saldırganlık Tespiti

Saldırganlık tespiti için üç yaklaşım sırayla geliştirildi ve ölçüldü.

**Birinci: kural tabanlı.** Poz kestiriminden gelen eklem konumlarından bilek hızı, gövde eğimi, hareket enerjisi ve kişiler arası yakınlık türetildi; bunlar elle belirlenen ağırlıklarla birleştirildi. 120 kliplik bir alt kümede AUC 0,62-0,66, F1 yaklaşık 0,71 verdi.

Bu yaklaşımın neden sınırlı kaldığı ayrıca incelendi ve sonuç öğreticiydi: ağırlıklar, şiddetin **hızlı ve ani** hareket içerdiği varsayımına dayanıyordu. Ölçüm bu varsayımı desteklemedi. Veri setindeki gerçek şiddet olaylarının önemli bir bölümü **boğuşma** biçiminde ve boğuşma sırasında ölçülen hareket hızı, kalabalık içinde normal yürüyüşten düşük çıkabiliyor. Elle yazılan ağırlıklar, ölçülmemiş bir sezgiyi kodluyordu.

**İkinci: iskelet öznitelikleri + gradyan artırma modeli (LightGBM, Ke vd., 2017).** Öznitelikler aynı, değişen tek şey nasıl birleştirildikleri.

**Üçüncü: ham piksel + üç boyutlu evrişimli ağ (R3D-18, Tran vd., 2018).** Bu yaklaşım iskelet çıkarımına hiç bağlı değil, dolayısıyla poz kestiriminin başarısız olduğu durumlarda da çalışıyor.

Son iki modelin ve birleşimlerinin sonuçları Tablo 4.5'te verilmiştir.

**Tablo 4.5** Şiddet tespiti sonuçları (RWF-2000 doğrulama kümesi, 96 klip).

| Model | AUC | AUC %95 GA | F1 |
|---|---|---|---|
| İskelet + LightGBM | 0,9267 | 0,8676 – 0,9722 | 0,8889 |
| Ham piksel (R3D-18) | 0,9366 | 0,8820 – 0,9796 | 0,9107 |
| **Birleşim (ortalama)** | **0,9684** | **0,9352 – 0,9917** | **0,9369** |

**Kazancın mekanizması.** Birleşimin daha iyi sonuç vermesi tek başına bir açıklama değil; iki modelin neden birbirini tamamladığı gösterilmeli. Hata kümeleri karşılaştırıldı: yalnızca iskelet modelinin yanıldığı 10 klip, yalnızca video modelinin yanıldığı 9 klip, **ikisinin birden yanıldığı 1 klip**. Örtüşme %10. Modeller aynı kliplerde değil, farklı kliplerde hata yapıyor; kazanç buradan geliyor.

**Eşik seçim yanlılığı.** F1 değerleri, en iyi eşiğin aynı küme üzerinde aranmasıyla elde ediliyor ve bu nedenle iyimser. 400 tekrarlı katmanlı yarı bölme ile ölçülen iyimserlik birleşim için 0,0204 puan: yani 0,9369 yerine **0,9165**. Raporda her iki değer de veriliyor.

**Erken uyarı — ve ölçütün tavanı.** Kriter, şiddet başlamadan en az 2 saniye önce uyarı üretilmesini istiyordu. Ölçüm negatif çıktı: medyan avans **−1,10 saniye**, yani uyarı olaydan sonra geliyor.

Ancak asıl bulgu bu sayı değil. Ölçütün bu veri setinde ulaşabileceği **en yüksek değer** hesaplandı: kliplerde şiddet başlangıcından önceki bağlam süresinin medyanı 0,58 saniye, azamisi 3,07 saniye. 20 klibin yalnızca 2'sinde 2 saniyelik bir avans fiziksel olarak mümkün. Dahası, etiketleri ben işaretledim ve işaretleme kendi tepki sürem içeriyor; klipler izlendiğinde şiddetin fiilen 0-0,5 saniye aralığında başladığı görülüyor. **Kusursuz çalışan bir dedektör bile bu ölçütü sağlayamaz.**

Bulgu, farklı özellikte ikinci bir veri setinde de sınandı. Olay öncesinde 58 saniyelik bağlam içeren bir klipte model kavga anını normalden ayırt edebiliyor (medyan skor oranı 2,756), ama kavgaya giden **tırmanma** penceresi normal bölümlerden daha düşük skorlanıyor (0,184 ⟷ 0,282) ve tespit olaydan 1,76 saniye sonra gerçekleşiyor. İki veri seti farklı yollardan aynı sonuca varıyor: sistem şiddeti tespit ediyor, şiddet öncesi tırmanmayı ayırt etmiyor.

### 4.7. Duygu Analizi

Yüz ifadesi sınıflandırması iki basamaklı bir kapıyla seyreltiliyor: önce kişi kutusunun yüksekliği 180 pikselin üzerinde olmalı, sonra yüz tespiti başarılı olmalı.

21 kamera ve kamera başına 25 kare üzerinde yapılan ölçüm Tablo 4.6'da verilmiştir.

**Tablo 4.6** İfade kademesinin iki basamaklı kapısından geçen kişi ve yüz sayıları (21 kamera, kamera başına 25 kare).

| Basamak | Sonuç |
|---|---|
| 1. Kişi kutusu ≥ 180 piksel | 2087 kişiden **171'i** geçti (%8,2) |
| 2. Yüz tespit edilebildi mi | Kapıyı geçen 8 kameranın **7'sinde hiç yüz bulunamadı** |

Yüz yalnızca yakın plan içeren kamerada (cam-20) bulunabiliyor, orada da 25 kırpıntının 25'inde.

Bu sonucun iki anlamı var. Birincisi, ifade kademesinin ucuz olması (kare başına 0,46 ms, döngünün %2'si) bir verimlilik başarısı değil; **kapının neredeyse her şeyi elemesinin sonucu.** İkincisi ve daha önemlisi: ifade sinyali pratikte tek bir kamerada üretiliyor. Füzyon eksik sinyali sıfır saydığı için, ifade ağırlığı diğer kameralarda fiilen devre dışı.

Bu, ifade modelinin kötü olduğu anlamına gelmiyor; **gözetim görüntüsünde yüzlerin kapıyı geçecek büyüklükte olmadığı** anlamına geliyor. Yakın plan kamerada kapının tamamen geçilmesi bu yorumu destekliyor.

Bu modülle ilgili proje boyunca yaşanan en öğretici olay şuydu: ifade sinyali ekranda görünüyordu, ama **karara hiç girmiyordu.** Kod bunun tersini iddia ediyordu. Sinyal füzyona bağlandığında ilk kez karara katılmaya başladı. Ayrıca bir noktada ONNX çalışma zamanı bozulmuştu ve kademe hiç kurulamıyordu; ekranda etiket göründüğü için sorun uzun süre fark edilmedi.

### 4.8. Alarm Zinciri ve Kanıt Klibi

Alarm zinciri şöyle işliyor: füzyon skoru bir eşiği aştığında ve soğuma süresi dolmuşsa bir olay üretiliyor; bu olay aynı anda üç yere gidiyor. Kalıcı kayıt için veritabanına yazılıyor, kanıt klibi kesiliyor ve WebSocket üzerinden panele canlı olarak gönderiliyor.

Olaylar TimescaleDB'ye yazılıyor; hypertable ve saklama politikası kullanılıyor. Panel son 24 saatin geçmişini açılışta yüklüyor, böylece panel kapalıyken üretilen alarmlar da görülebiliyor.

**Kanıt klibi.** Bir alarm üretildiğinde, olay anının ±10 saniyesi kaynak kayıttan kesilip saklanıyor ve panelde oynatılabiliyor. Kesim yeniden kodlama yapmadan (remux) yapılıyor, maliyeti yaklaşık 32 ms. Kesilen bir klibin gerçekten olayı içerdiğinin doğrulanması Şekil 6.3'te gösterilmiştir.

Bu zincirle ilgili iki ders çıktı. Birincisi: klipler uzun süre kesiliyor ve veritabanına yazılıyordu ama **panelde erişilebilir değildi** — yani zincir kâğıt üzerinde tamamdı, pratikte yarımdı. İkincisi: klip kesme betiği "12/12 klip kesildi" diye başarı raporluyordu, oysa üretilen dosyalar 257 baytlık, hiç kare içermeyen, açılamayan dosyalardı. Başarı kontrolü "dosya var ve boyutu sıfırdan büyük" diye yazılmıştı. Kontrol, dosyanın yapacağı işi yapacak şekilde değiştirildi: dosya gerçekten açılıp ilk karesi okunuyor.

### 4.9. Web Arayüzü

Arayüz React 19 + TypeScript + Vite ile geliştirildi. Üç sayfadan oluşuyor: kamera ızgarası (Şekil 4.3), olay zaman çizelgesi (Şekil 4.4) ve kamera detayı. Giriş ekranı Şekil 6.1'de, ızgaranın açılış hâli Şekil 6.2'de verilmiştir.

**[GORSEL: screenshots/03-canli-kutular.png]**
**Şekil 4.3** Kamera ızgarası: canlı video üzerine çizilen tespit kutuları, iz kimlikleri, güven skorları ve iskeletler. Sağdaki panelde alarmlar ve her alarmın kanıt alanları görünüyor.

**Kutuların videoyla hizalanması.** Bu, arayüzün en zor kısmıydı. Analiz sonucu video karesinden birkaç yüz milisaniye sonra geliyor; kutuyu nereye çizmeli?

İlk yaklaşım kişinin şu an nerede olduğunu hız vektöründen **tahmin etmekti** (ekstrapolasyon). İnsan yavaşlar, döner, durur; tahmin tutmaz ve bir sonraki gerçek sonuç kutuyu sıçratarak doğru yere çeker. Kullanıcının bildirdiği "takılma" tam olarak buydu.

Çok oyunculu oyun ağ literatüründeki yerleşik çözüm tersini söylüyor: **tahmin etme, görüntüyü geciktir.** Video, analiz kadar geriden gelirse ekranda gösterilen an için elde iki gerçek ölçüm olur ve aradaki konum hesaplanır. Tarayıcının bunun için hazır bir düğmesi var: `jitterBufferTarget`. Bedeli tazelik; gözetimde kabul edilebilir, çünkü operatör için kutunun doğru yerde olması yarım saniye daha taze olmasından önemli ve alarm zaten ayrı kanaldan gecikmesiz geliyor.

**[GORSEL: screenshots/05-zaman-cizelgesi.png]**
**Şekil 4.4** Olay zaman çizelgesi ve olay tablosu. Üstteki ısı haritasında satırlar kamera, sütunlar saat; bir hücreye tıklandığında alttaki tablo o kameranın o saatine daralıyor.

Zaman çizelgesi ilk sürümünde yalnızca bir ısı haritasıydı ve hücreler tıklanabilir değildi. Bilgi üretiliyordu ama kullanıcıya ulaşmıyordu. Hücreler düğmeye çevrildi ve altına gerçek bir olay tablosu eklendi: zaman, kamera, tür, kişi, şiddet, kanıt gücü ve kanıt alanları. Satıra tıklandığında tüm kanıt alanları ve varsa kanıt klibi açılıyor.

Arayüze ayrıca açık/koyu tema seçeneği eklendi. Renkler CSS değişkeni olarak tanımlı; tercih tarayıcıda saklanıyor ve sayfa React yüklenmeden önce uygulanıyor, böylece açılışta tema atlaması olmuyor.

### 4.10. Güvenlik

Güvenlik gereksinimleri proje başında 20 maddelik öncelikli bir liste olarak tanımlandı ve geliştirme boyunca izlendi. Tek giriş noktasının ve video akışı kimlik doğrulamasının yapısı Şekil 4.5'te gösterilmiştir. Uygulananlar arasında Argon2id ile parola saklama, kısa ömürlü JWT belirteçleri, `HttpOnly` çerez, üç rollü yetkilendirme (izleyici/operatör/yönetici), giriş hız sınırı, sadece-eklemeli denetim kaydı, dizin geçişi koruması ve TLS bulunuyor.

**[GORSEL: diagrams/03-kimlik-dogrulama.png]**
**Şekil 4.5** Tek giriş noktası ve video akışının kimlik doğrulaması.

Güvenlik tarafında iki bulgu, aynı dersi iki kez verdi.

**Birinci bulgu: API korunuyordu ama video korunmuyordu.** Uygulama arayüzü kimlik doğrulaması istiyordu; video akışını sunan medya sunucusu hiçbir doğrulama yapmıyordu. Görüntüye erişmek için tek gereken adresi bilmekti. İlk çözüm bir ağ kısıtı oldu: port yerel arayüze bağlandı. Bu, açığı kapatmaz — yalnızca erişimi aynı makineyle sınırlar. Kalıcı çözüm, videonun uygulama ile **aynı kökenden** sunulması ve ters vekilin her video isteği için uygulamaya yetki sorgusu yapmasıydı. Bu tasarımda tarayıcı kimlik çerezini video isteklerine de ekliyor; yani tek giriş noktası bir kolaylık değil, video kimlik doğrulamasının ön koşulu.

**İkinci bulgu: tek giriş noktası kuruldu ama geçenler sayılmadı.** Ters vekildeki "diğer her şeyi geçir" kuralı, uygulamanın kimlik doğrulaması olmayan uçlarını da dışarı açıyordu. Denetimde gözlemlenebilirlik arayüzünün (`/metrics`) kimlik doğrulaması olmaksızın ve tek giriş noktası üzerinden erişilebilir olduğu görüldü. Bu arayüz kamera adlarını, kamera başına alarm sayılarını, kare hızlarını ve uç nokta envanterini içeriyor; bir gözetim sisteminde sisteme girmeden keşif yapmaya yeter. Uç, ters vekil düzeyinde kapatıldı.

Kimlik doğrulamasını uygulama düzeyinde eklemek tercih edilmedi, çünkü ölçüm toplama süreci bu arayüzü yerel olarak ve vekilden geçmeden kullanıyor; uygulama düzeyinde koruma gözlemlenebilirliği bozardı. **Doğru katman, dışarıya bakan katman.**

Denetim sırasında bir şey daha görüldü ve not edilmeye değer: envanteri çıkaran ilk araç, uygulama çatısının nesne grafiğini gezerek 10 uç buldu. Alt yönlendiricilerle eklenen uçlar bu gezinmede görünmüyordu; gerçek sayı 16. Araç yüzeyin bir bölümünü göremiyordu ve bunu söylemiyordu. Yöntem değiştirildi: arayüz tanımından alınan **tüm** uçlara kimliksiz gerçek istek gönderildi ve dönen durum kodları kaydedildi. Envanteri çıkaran aracın kendisi de doğrulanmalı.

**Üçüncü bulgu: yapılandırma yanlış beyan üretiyordu.** 69 ayarın 11'i hiçbir kod yolunda okunmuyordu. İkisi doğrudan güvenlik beyanı niteliğindeydi: biri imzalı ve süreli klip bağlantılarının yapılandırıldığını, diğeri tüm API'de istek hızı sınırlaması olduğunu düşündürüyordu. Gerçekte imzalı bağlantı özelliği uygulanmamış, hız sınırlaması yalnızca giriş ucunda. Bu bir kod hatası değil — hiçbir işlev bozulmuyor — ama yapılandırmayı inceleyen biri sistemde olmayan korumaların var olduğu sonucuna varır. Ayarlar, uygulanmadıkları açıkça belirtilerek işaretlendi.

### 4.11. Test ve Kalite Kapıları

Projede üç test katmanı var; katmanlar, test sayıları ve her katmanın neyi doğruladığı Tablo 4.7'de özetlenmiştir.

**Tablo 4.7** Projedeki üç test katmanı, test sayıları ve her katmanın neyi doğruladığı.

| Katman | Adet | Ne doğruluyor |
|---|---|---|
| Arka uç birim testleri | 229 | Altyapı gerektirmeden çalışan mantık |
| Ön yüz birim testleri | 44 | Zaman ekseni matematiği, kutu çizimi, tür sözlüğü |
| Uçtan uca testler (Playwright) | 22 | Canlı sisteme karşı, kullanıcının yapabildiği işler |

Kalite kapıları: `ruff` (biçim ve hata), `mypy` (tip denetimi), `eslint` ve `tsc`. Dördü de temiz.

**Uçtan uca testlerin gerekçesi.** Proje boyunca üç kez şu oldu: her parçası tek tek çalışan bir sistem uçtan uca çalışmadı ve parça testleri bunu göstermedi. İfade sinyali sınıflandırılıyor ve ekrana gidiyordu ama karara girmiyordu. Füzyonun bellek budama işlevi yazılmıştı ama hiç çağrılmıyordu. Klipler kesiliyor ve veritabanına yazılıyordu ama erişilemiyordu. Üçü de birim testlerinden geçerdi.

Bu yüzden uçtan uca testlerin adları modül değil **iş** tarif ediyor: "operatör bir olaya tıklayıp kanıtını görebiliyor", "kimliksiz video isteği engelleniyor", "açılan her kamerada video gerçekten geliyor".

**Bir testin geçmesi yeterli değil.** Proje sırasında yazılan bir birim testi "eski hatayı yakalıyorum" diye iddia ediyordu; ölçüldüğünde yakalamadığı görüldü. O günden sonra yeni yazılan testler, **kod bilerek bozulup düştüğü görülene kadar** kabul edilmedi. Aynı kural diyagram doğrulama testinde de uygulandı: test "taşma kontrolü" diyordu ama yalnızca sayfa kenarına bakıyordu; gerçek bir taşmayı (bir etiketin başka bir kutunun altında kalması) göremiyordu. Test düzeltildi, sonra bilerek bozulup düştüğü doğrulandı.

### 4.12. Ölçüm Yöntemi ve Karşılaşılan Sorunlar

Bu bölüm, projenin en çok şey öğreten kısmı. Proje boyunca tutulan mühendislik günlüğünde 87 kayıt var. Bu kayıtların tamamı bilimsel bulgu değil; sınıflandırıldığında şöyle dağılıyor:

**Tablo 4.8** Mühendislik günlüğündeki 87 kaydın türlerine göre dağılımı.

| Grup | Adet | İçerik |
|---|---|---|
| Bir iddianın ölçümle **çürütüldüğü** kayıtlar | 43 | Raporun asıl malzemesi |
| Mimari ya da uygulama düzeyinde bulgu | 35 | Kuyruk, bellek, eşzamanlılık |
| Kurulum ve ortam sorunu | 9 | Port çakışması, araç yapılandırması |

Son gruba "bulgu" demek doğru olmaz; bu yüzden ayrıldı.

Birinci gruptaki 43 kaydın ortak yanı şu: **hata modelde ya da sistemde değil, ölçüm zincirindeydi.** En sık tekrarlanan hata türleri ve alınan önlemler Tablo 4.9'da toplanmıştır.

**Tablo 4.9** Karşılaşılan ölçüm hatası türleri ve düzeltmeleri.

| Hata türü | Belirtisi | Düzeltme |
|---|---|---|
| Kümülatif sayaçtan yüzdelik okuma | Aynı koşulda farklı sonuçlar | Pencere farkı almak |
| Duvar saati ile işlemci zamanını karıştırmak | Maliyetin olduğundan düşük görünmesi | `thread_time` ile ölçmek |
| Aynı metrikte iki farklı birim | Bileşen toplamının döngü toplamını tutmaması | Tek birim + kapanış kontrolü |
| Ölçülmeyeni sıfır saymak | Açıklanamayan maliyetin görünmemesi | Kapanış kontrolü |
| Aracın tavanını sistem sanmak | Şüphe uyandırmayan yuvarlak değerler | Kontrol serisi |
| Bağımlı gözlemleri bağımsız saymak | Güven aralığının dar çıkması | Küme önyükleme |
| Eşiği ölçüm kümesinde seçmek | İyimser F1 | Tekrarlı yarı bölme |

Birkaç somut örnek:

**"Çözme darboğaz" yanlış teşhisi.** Erken dönemde video çözmenin darboğaz olduğu düşünüldü ve donanım hızlandırmalı çözme (NVDEC) denendi. Ölçüldüğünde NVDEC'in işlemciden **daha yavaş** olduğu ve çözmenin zaten darboğaz olmadığı görüldü. Daha sonra alım worker'ının CPU'sunun yalnızca %5,6'sının çözmeye gittiği ölçüldü.

**"Ölçülmeyen %70" diye bir şey yokmuş.** Bir aşamada işlem hattı maliyetinin %70'inin ölçülmeyen ek yük olduğu raporlandı ve üzerine mimari öneriler kuruldu. Hata, aynı metrik altında iki farklı birimin toplanmasıydı: bazı aşamalar kare başına, bazıları yığın başına yazıyordu. **Kapanış kontrolü** eklendiğinde — yani bileşenlerin toplamı bağımsız ölçülen döngü toplamıyla karşılaştırıldığında — açığın %0 olduğu görüldü. Ölçüm bir gün sonra farklı bir araçla tekrarlandı ve aynı çıktı.

**Girdiyi artırmak çıktıyı düşürdü.** Örnekleme hızı kamera başına 4'ten 8 kare/saniyeye çıkarıldığında analiz edilen kare hızı artmadı, **%32 düştü** (2,78'den 1,88'e). Mekanizma ölçümde göründü: alım sürecinin işlemci kullanımı 2,10'dan 3,79 çekirdeğe çıktı, çıkarım sürecininki sabit kaldı. Artan alım yükü aynı çekirdekleri paylaşan çıkarımdan zaman çalıyordu.

**Bir ölçüm, yapıtı kaydedilmediyse yapılmamıştır.** Paylaşımlı bellek havuzu 48'den 96 yuvaya çıkarıldığında belirgin bir iyileşme gözlendi ve günlüğe yazıldı — ama ölçüm çıktısı dosyaya kaydedilmedi. Ertesi gün aynı yapılandırmayla yapılan ölçümler o değerleri tekrar üretmedi. Bu yüzden raporda ve makalede tekrar üretilebilen, çıktısı saklanan ölçümler esas alındı.

**Paralelleştirme denemesi.** Çıkarım süreci tek çekirdekte doyduğu için kameraların birden çok sürece paylaştırılması denendi. İlk uygulama karelerin **yarısını yok etti**: aynı akışı okuyan süreçler, kendilerine ait olmayan kareyi diğerine aktarmak yerine imha ediyordu. Üstelik ölçütler *iyileşmiş* göründü — iş yarıya inince kuyruk boşaldı ve gecikme düştü. Yalnızca gecikmeye bakan bir değerlendirme bunu başarı sanardı. Hata, yayınlanan ve analiz edilen kare sayıları ayrı ayrı sayıldığı için görüldü.

Düzeltilmiş uygulamada yönlendirme üretici tarafına alındı ve her kamera kendi alt akışına yazıldı. Sonuç: verim %19 arttı, gecikme %49 düştü. Ama sistem belleği %84'ten **%98'e** çıktı; 16 GB'lık bir makinede bu sınır uzun süreli çalışma için güvenli değil. Bu yüzden seçenek üretimde etkinleştirilmedi.

### 4.13. Başarı Kriterleri ve Sonuçlar

**Tablo 4.10** Başarı kriterleri ve ölçülen değerler.

| # | Kriter | Hedef | Ölçülen | Durum |
|---|---|---|---|---|
| K1 | Eşzamanlı kamera | ≥ 20 | 20 / 20 | Sağlandı |
| K2 | Analiz kare hızı (kamera başına) | ≥ 4 kare/sn | 2,34 | Sağlanmadı, nedeni ölçüldü |
| K3 | Uçtan uca gecikme | ≤ 1500 ms | p50 378 ms, p95 652 ms | Sağlandı |
| K4 | İki saat kesintisiz çalışma | Kesinti yok | 120 dk, 0 kesinti | Sağlandı (eski sürüm) |
| K5 | Şiddet tespiti F1 | ≥ 0,85 | 0,937 (yanlılık düzeltilmiş 0,917) | Sağlandı |
| K6 | Anomali tespiti AUC | ≥ 0,75 | 0,869 (küme GA 0,806 – 0,929) | Sağlandı |
| K7 | Yanlış alarm | ≤ 3/kamera-saat | Kesinlik 0,895 (19 bağımsız olay) | Ölçüt yeniden tanımlandı |
| K8 | Erken uyarı avansı | ≥ 2 sn | −1,10 sn | Sağlanmadı, ölçüt tavanı hedefin altında |
| K9 | Güvenlik öncelikli liste | %100 | 18 / 19 | Kısmen |
| K10 | Arayüz akıcılığı | ≥ 30 kare/sn | Medyan 30,00 | Ölçüt ayırt edici değil |

**Kaynak kullanımı.** Sistem 20 kamerayla kararlı durumda çalışırken ölçülen bellek ve işlemci değerleri Tablo 4.11'de verilmiştir.

**Tablo 4.11** Yirmi kamerayla kararlı durumda süreç başına ölçülen bellek ve işlemci kullanımı.

| Bileşen | Bellek (MB) | İşlemci (çekirdek) |
|---|---|---|
| Alım | 1295,0 | 2,42 |
| Çıkarım | 1077,2 | 0,89 |
| Analitik | 133,5 | 0,93 |
| Alarm | 57,9 | 0,00 |
| API | 74,1 | 0,02 |
| **Toplam** | **2633,9** | **4,27** |

Ekran kartı kullanımı medyan %28,5, video belleği 571 MB (8192 MB'ın %7'si).

**K2 neden tutmadı.** Sistem hedefin altında kalırken 20 mantıksal çekirdeğin yaklaşık 15'i, ekran kartının yaklaşık %70'i ve video belleğinin %93'ü kullanılmıyor. Sınırlayıcı unsur donanım değil, **çıkarım sürecinin ana döngüsünün seri olması.** Döngü bir yığını baştan sona işliyor ve bu sırada tek çekirdek kullanıyor; ölçülen değer 0,89 çekirdek ve yük ne olursa olsun bunun üzerine çıkmıyor. Bekleme süresi ayrıca ölçüldü: kare başına 1,69 ms. Yani süreç boşta beklemiyor, zamanının %93'ünde iş yapıyor.

**K7 neden yeniden tanımlandı.** "Alarm/kamera-saat" ölçütü, kaynak videoların döngüde yayınlandığı bir kurulumda sistemin davranışını ölçmüyor (Bölüm 4.4). Ölçüt, bağımsız olay başına kesinlik olarak yeniden tanımlandı. 40 alarmın 39'u elle etiketlendi (biri için karar verilemedi, analiz dışı bırakıldı) ve döngüdeki konuma göre tekilleştirildiğinde 19 bağımsız olaya karşılık geldi.

Sonuçlar Tablo 4.12'de verilmiştir.

**Tablo 4.12** Alarm kesinliği. Güven aralıkları Wilson (1927) yöntemiyle hesaplanmıştır.

| | n | Doğru | Kesinlik | %95 GA |
|---|---|---|---|---|
| Ham etiketli alarm | 39 | 37 | 0,949 | 0,831 – 0,986 |
| **Bağımsız olay** | **19** | **17** | **0,895** | **0,686 – 0,971** |
| Kalabalık | 9 | 9 | 1,00 | 0,70 – 1,00 |
| Birleşik risk | 5 | 5 | 1,00 | 0,57 – 1,00 |
| **Düşme** | **5** | **3** | **0,60** | **0,23 – 0,88** |

Toplu değer 0,895 ama tür bazında dağılım düzgün değil: iki yanlış alarmın ikisi de düşme türünde ve ikisi de aynı mekanizmadan kaynaklanıyor — eğilerek yere uzanan bir kişi düşme sanılıyor. Toplu bir sayı bir bulguyu gizleyebilir; yalnızca 0,895 raporlansaydı sistemin zayıf halkasının belirli bir kural olduğu görülmeyecekti.

Burada bir sınırı açıkça belirtmek gerekiyor. Bu yöntem yalnızca **kesinlik** ölçüyor. **Duyarlılık ölçülmedi**; sistemin kaçırdığı olayları belirlemek için kaynak videoların tamamının etiketlenmesi gerekirdi.

**K10 neden ayırt edici değil.** Arayüz akıcılığı 7 bağımsız koşuda ölçüldü. Çizim hızı medyan 30,00 (aralık 29,43 – 30,02), kamera açılmadan yapılan kontrol ölçümü ise 60 civarında. Çizim hızı ölçümü tarayıcının dikey senkronizasyonuna bağlı ve 60 Hz bir ekranda pratikte 60, 30, 20, 15 gibi **kesikli** değerler alıyor. Ölçütün eşiği tam 30, yani sistemin oturduğu basamağın üzerinde; ölçülen değerin 29,43 mü 30,02 mi çıkacağını sistemin başarısı değil, sayım penceresinin kenar etkileri belirliyor.

Daha bilgilendirici olan düşen kare oranı: medyan %2,3, aralık %0 – %33,4. Erken bir ölçümde bu oran sıfır bulunmuş ve "beklediğimden iyi" diye yorumlanmıştı; 7 koşuluk dağılım bu yorumu geçersiz kıldı. **Tek gözleme dayanan bir sonuç, özellikle beklenenden iyi çıktığında, tekrarlanmadan kabul edilmemeli.**

---

## 5. SONUÇ

25 iş günü sonunda, 20 eşzamanlı kamera akışını tek bir orta seviye dizüstü ekran kartında işleyen, tespit-takip-poz-yüz zincirini anomali tespiti ve saldırganlık kestirimiyle birleştiren, olayları kalıcı olarak saklayan ve web arayüzünden canlı izlenebilen bir sistem çalışır durumda teslim edildi.

**Tutturulan hedefler.** Uçtan uca gecikme hedefin oldukça altında kaldı (p50 378 ms, hedef 1500 ms). Şiddet tespitinde iki bağımsız modelin birleşimi F1 0,937 verdi (yanlılık düzeltilmiş 0,917) ve bu kazancın **neden** ortaya çıktığı da gösterildi: iki modelin hata kümeleri yalnızca %10 örtüşüyor. Anomali tespiti 0,869 AUC ile hedefi geçti. 20 kameranın tamamı eşzamanlı çalıştı.

**Tutturulamayan hedefler ve nedenleri.** Üç kriter hedefe ulaşamadı ve üçünün de nedeni ölçüldü:

- **Analiz kare hızı (K2).** Sınır donanım değil, çıkarım döngüsünün seri olması. Donanımda belirgin boşluk var: ekran kartı %28,5, video belleği %7, çekirdeklerin çoğu boşta.
- **Erken uyarı (K8).** Kullanılan veri setinde ölçütün ulaşabileceği en yüksek değer hedefin altında. Kusursuz bir dedektör bile geçemez. Bu bir sistem başarısızlığı değil, ölçüt ile veri arasındaki uyuşmazlık.
- **Arayüz akıcılığı (K10).** Ölçüt eşiği, ölçüm aracının çözünürlük basamağının üzerine düşüyor; karar ölçüm gürültüsüyle değişiyor.

**Kapsam dışı bırakılanlar.** Kademe 3 (video tabanlı eylem doğrulayıcı) gerçekleştirilmedi. Model aslında eğitildi ve şiddet tespitinde kullanıldı, ama canlı hatta bir doğrulama aşaması olarak bağlanması tetikleme mantığı, kesit tamponlama ve alarm geri alma akışı gerektiriyor. Ayrıca ölçümler alarm kesinliğinin zaten 0,895 olduğunu ve yanlış alarmların tek bir kural türünde yoğunlaştığını gösterdi; bu durumda hedefli bir düzeltme genel bir doğrulama aşamasından daha verimli. Kamera bazlı yetkilendirme de tek operatörlü bir kurulumda karşılığı bulunmadığı için kapsam dışı bırakıldı.

**Bu stajda öğrendiklerim.** Teknik bilgi dışında üç şey öğrendim ve üçü de ölçmekle ilgili.

Birincisi: **ölçüm aracı da bir bileşendir ve o da bozulabilir.** Bu projede bir iddianın ölçümle çürütüldüğü 43 kaydın çoğunda hata modelde değil, ölçüm zincirindeydi. Kümülatif bir sayaçtan yüzdelik okumak, duvar saatiyle işlemci zamanını karıştırmak, aynı metrikte iki farklı birimi toplamak — bunların hiçbiri modeli ilgilendirmiyor ama hepsi sonucu değiştiriyor.

İkincisi: **bir ölçüt raporlanmadan önce kendisi denetlenmeli.** Üç soru yetiyor: Bu ölçütün eldeki veriyle ulaşabileceği en yüksek değer nedir? Eşiği, ölçüm aracının çözünürlüğünün üzerinde mi? Gözlem birimi gerçekten bağımsız mı? Bu üç soru sorulmadığında elde edilen sayı yanlış olmayabilir, ama yanlış bir soruyu yanıtlıyor olabilir.

Üçüncüsü: **her parçası tek tek çalışan bir sistem uçtan uca çalışmayabilir ve parça testleri bunu göstermez.** Kapsam maddeleri modüllerle değil, kullanıcının yapabildiği işlerle işaretlenmeli. "Klip kesiliyor" bir modül ifadesi; "operatör alarmın videosunu izleyebiliyor" bir kapsam ifadesi.

**Gelecek çalışma.** Üç yön öne çıkıyor. Birincisi, erken uyarı ölçütünün anlamlı değerlendirilebilmesi için **olay öncesi bağlam içeren** bir veri seti kullanmak; bu çalışmada kullanılan iki veri setinin de bu özelliği taşımadığı ölçülerek gösterildi. İkincisi, etiketlemenin birden çok değerlendiriciyle yapılması ve değerlendiriciler arası uyumun raporlanması. Üçüncüsü, sistemin gerçek ağ koşullarında ve gerçek kameralarla doğrulanması.

---

## 6. EKLER

**Ek A — Ek ekran çıktıları.**

**[GORSEL: screenshots/01-giris.png]**
**Şekil 6.1** Giriş ekranı. Panelin tamamı kimlik doğrulaması arkasında; kimliksiz bir istek doğrudan bu sayfaya yönlendiriliyor. Parolalar Argon2id ile saklanıyor, oturum kısa ömürlü bir JWT belirteciyle ve `HttpOnly` çerezle taşınıyor.

**[GORSEL: screenshots/02-izgara-20-kamera.png]**
**Şekil 6.2** Kamera ızgarasının açılış hâli. Yirmi kutucuk listeleniyor ama video akışı hiçbirinde otomatik başlamıyor; her kutucuk "izlemek için tıkla" diyor. Bunun nedeni Bölüm 4.9'da anlatılan tarayıcı tarafı çözme maliyeti: yirmi H.264 akışını aynı anda açmak tarayıcıyı doyuruyor, bu yüzden akış isteğe bağlı başlatılıyor. Sağdaki alarm paneli ise kutucuklar kapalıyken de çalışmaya devam ediyor, çünkü alarmlar videodan bağımsız bir kanaldan geliyor.

**[GORSEL: screenshots/07-klip-zinciri-dogrulama.png]**
**Şekil 6.3** Kanıt klibi zincirinin doğrulanması. Bir düşme alarmı için kesilen klipten alınan altı ardışık kare; okuma soldan sağa, üstten alta. Klip doğru anı içeriyor: kişi ayakta, yürüyor, dengesini kaybediyor ve yere düşüyor. Bu doğrulama, dosyanın açılabilmesine değil gerçekten olayı içermesine bakmak gerektiği için elle yapıldı (Bölüm 4.8).

**Ek B — Depo yapısı.** Kaynak kod, ölçüm betikleri ve ölçüm çıktıları: https://github.com/0merf/Staj-Proje

```
backend/          Python: alım, çıkarım, analitik, alarm, API
  src/sentinel/   Uygulama kodu
  scripts/        Ölçüm ve değerlendirme betikleri
  tests/          229 birim testi
frontend/         React + TypeScript panel
  src/            Uygulama
  e2e/            22 uçtan uca test (Playwright)
infra/            Docker, Caddy, MediaMTX, Prometheus yapılandırmaları
benchmarks/       Ölçüm çıktıları (JSON) — tekrar üretilebilir
docs/
  decisions/      Mimari karar kayıtları
  report/         Bu rapor, dergi makalesi, diyagramlar, ekran görüntüleri
    problems.md   Mühendislik günlüğü (87 kayıt)
```

**Ek C — Kurulum ve çalıştırma.**

```
docker compose up -d                      # altyapı
pwsh backend/scripts/start_all.ps1        # yapay zekâ süreçleri
# Panel: http://127.0.0.1:8001/app
```

**Ek D — Ölçüm betikleri.** Raporda geçen her sayı Tablo 6.1'deki betiklerle tekrar üretilebilir.

**Tablo 6.1** Raporda geçen sayıları yeniden üreten ölçüm betikleri.

| Betik | Ne ölçüyor |
|---|---|
| `measure_canli.py` | Uçtan uca gecikme, analiz kare hızı, kaynak kullanımı |
| `asama_kirilimi.py` | Çıkarım döngüsünün aşama kırılımı ve kapanış kontrolü |
| `evaluate_k6.py` | Anomali tespiti AUC ve kontrol serisi |
| `evaluate_birlesim.py` | Şiddet tespiti, birleşim, önyükleme, eşik yanlılığı |
| `evaluate_k8.py` | Erken uyarı avansı ve ölçüt tavanı |
| `alarm_tekillestir.py` | Alarm kesinliği (döngü tekilleştirmesi ile) |
| `benchmark_tensorrt.py` | PyTorch – TensorRT karşılaştırması |

**Ek E — Kaynak kodun konumu.** Rapor sayfa sınırını aşmamak için kaynak kod bu belgeye gömülmemiş, depoya bırakılmıştır. Ana bileşenlerin dosya yolları Tablo 6.2'de verilmiştir.

**Tablo 6.2** Ana bileşenlerin depo içindeki dosya yolları.

| Bileşen | Dosya |
|---|---|
| Alım worker'ı | `backend/src/sentinel/ingest/worker.py` |
| Çıkarım worker'ı | `backend/src/sentinel/inference/worker.py` |
| Analitik ve füzyon | `backend/src/sentinel/analytics/` |
| Alarm motoru ve klip | `backend/src/sentinel/alerting/` |
| Paylaşımlı bellek | `backend/src/sentinel/bus/shm.py` |
| Panel | `frontend/src/` |

---

## 7. KAYNAKLAR

Aharon, N., Orfaig, R., Bobrovsky, B.Z., *BoT-SORT: Robust Associations Multi-Pedestrian Tracking*, arXiv:2206.14651, 2022.

Benfold, B., Reid, I., "Stable Multi-Target Tracking in Real-Time Surveillance Video," *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, Haziran 2011, ss. 3457-3464.

Cheng, M., Cai, K., Li, M., *RWF-2000: An Open Large Scale Video Database for Violence Detection*, 25th International Conference on Pattern Recognition (ICPR), Ocak 2021, ss. 4183-4190.

Degardin, B., Proença, H., *Human Activity Analysis: Iterative Weak/Self-Supervised Learning Frameworks for Detecting Abnormal Events*, IEEE International Joint Conference on Biometrics (IJCB), Eylül 2020.

Efron, B., "Bootstrap Methods: Another Look at the Jackknife," *The Annals of Statistics*, Ocak 1979, ss. 1-26.

Ferryman, J., Shahrokni, A., *PETS2009: Dataset and Challenge*, IEEE International Workshop on Performance Evaluation of Tracking and Surveillance, Aralık 2009.

Field, C.A., Welsh, A.H., "Bootstrapping Clustered Data," *Journal of the Royal Statistical Society: Series B*, Haziran 2007, ss. 369-390.

Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., Liu, T.Y., *LightGBM: A Highly Efficient Gradient Boosting Decision Tree*, Advances in Neural Information Processing Systems (NeurIPS), Aralık 2017, ss. 3146-3154.

Kwolek, B., Kepski, M., "Human Fall Detection on Embedded Platform Using Depth Maps and Wireless Accelerometer," *Computer Methods and Programs in Biomedicine*, Aralık 2014, ss. 489-501.

Lu, C., Shi, J., Jia, J., *Abnormal Event Detection at 150 FPS in MATLAB*, IEEE International Conference on Computer Vision (ICCV), Aralık 2013, ss. 2720-2727.

Oh, S., Hoogs, A., Perera, A. vd., *A Large-Scale Benchmark Dataset for Event Recognition in Surveillance Video*, IEEE Conference on Computer Vision and Pattern Recognition (CVPR), Haziran 2011, ss. 3153-3160.

Tran, D., Wang, H., Torresani, L., Ray, J., LeCun, Y., Paluri, M., *A Closer Look at Spatiotemporal Convolutions for Action Recognition*, IEEE Conference on Computer Vision and Pattern Recognition (CVPR), Haziran 2018, ss. 6450-6459.

Wilson, E.B., "Probable Inference, the Law of Succession, and Statistical Inference," *Journal of the American Statistical Association*, Haziran 1927, ss. 209-212.

Wu, W., Peng, H., Yu, S., "YuNet: A Tiny Millisecond-Level Face Detector," *Machine Intelligence Research*, Ekim 2023, ss. 656-665.
