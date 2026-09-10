# Kısıtlı Donanımda Yirmi Kameralı Gerçek Zamanlı Gözetim Sistemi: Başarım ve Doğruluk İddialarının Ölçülebilirliği Üzerine Bir Vaka Çalışması

**Ömer Faruk Kanat**¹*

¹ Düzce Üniversitesi, Mühendislik Fakültesi, Bilgisayar Mühendisliği Bölümü (İngilizce), Düzce, Türkiye. `ror.org/04175wc52`

\* Yazışma yazarı: omerfk0121@gmail.com
ORCID: 0009-0006-9229-6217

**Makale Türü:** Araştırma Makalesi

---

## ÖZ

Bileşen düzeyinde ölçülen başarım değerlerinin, aynı bileşenler tek bir donanımı paylaşan bütünleşik bir sistemde de geçerli olup olmadığı bu çalışmada deneysel olarak incelenmiştir. Bu çalışmada, yirmi eşzamanlı kamera akışının tek bir orta seviye dizüstü grafik işlemcisi (RTX 3070 Laptop, 8 GB) üzerinde işlendiği bir gözetim sistemi geliştirilmiş; nesne tespiti, çoklu nesne takibi, poz kestirimi, yüz ifadesi sınıflandırması, anomali tespiti ve saldırgan davranış kestirimi tek bir işlem hattında birleştirilmiştir. Sistemin uçtan uca gecikmesi 378 ms (p50) ve 652 ms (p95) olarak ölçülmüş, kamera başına analiz edilen kare hızı 2,34 kare/saniye düzeyinde kalmıştır. Şiddet tespitinde iskelet tabanlı bir gradyan artırma modeli ile ham piksel tabanlı üç boyutlu evrişimli bir modelin skor ortalaması alındığında F1 skoru 0,937 (eşik seçim yanlılığı düzeltildiğinde 0,917) elde edilmiş; bu kazancın kaynağının iki modelin hatalarının yalnızca %10 oranında örtüşmesi olduğu gösterilmiştir. Anomali tespitinde füzyon yaklaşımının eğri altındaki alan değeri 0,869 (küme önyükleme %95 güven aralığı [0,806–0,929]) ölçülmüş; ancak kontrol serisiyle yapılan karşılaştırma, kazancın sinyal birleştirmeden değil zamansal yumuşatmadan kaynaklandığını ortaya koymuştur. Çalışmanın ikinci ve daha genel katkısı ölçüm tarafındadır: geliştirme süreci boyunca kaydedilen 87 problem kaydının incelenmesi, sistem başarımına ilişkin iddiaların önemli bir bölümünün sistemin kendisinden değil, ölçüm aracının doğrulanmamasından kaynaklanan hatalar taşıdığını göstermiştir. Bu hatalar üç başlıkta toplanmıştır: ölçütün üst sınırının hedefin altında kalması, ölçüt eşiğinin ölçüm çözünürlüğünün altında olması ve gözlem biriminin bağımsızlık varsayımını karşılamaması. Güvenlik tarafında ise, tek giriş noktası mimarisi kurulmuş olmasına rağmen bu noktadan geçen uç noktaların envanterinin çıkarılmaması nedeniyle gözlemlenebilirlik arayüzünün kimlik doğrulaması olmaksızın dışarıya açık kaldığı tespit edilmiş ve giderilmiştir.

**Anahtar Kelimeler:** Video gözetim, Anomali tespiti, Kenar hesaplama, Ölçüm geçerliliği, Sistem güvenliği

---

## ABSTRACT

`[Türkçe öz kesinleştikten sonra çevrilecek]`

**Keywords:** Video surveillance, Anomaly detection, Edge computing, Measurement validity, System security

---

## I. GİRİŞ

Video gözetim sistemlerinin otomatikleştirilmesi, bilgisayarlı görü alanının en yoğun çalışılan uygulama başlıklarından biridir. Nesne tespiti, çoklu nesne takibi, poz kestirimi ve video tabanlı eylem tanıma alanlarının her birinde son yıllarda hem doğruluk hem hız bakımından belirgin ilerlemeler kaydedilmiştir. Bu bileşenler tek tek değerlendirildiğinde, kare başına maliyetleri ve doğruluk değerleri ayrıntılı biçimde raporlanmaktadır.

Bu çalışmanın çıkış noktası, söz konusu bileşen düzeyindeki değerlerin bütünleşik bir sisteme taşınıp taşınmadığı sorusudur. Soru, geliştirme sırasında yapılan bir ölçümle somutlaşmıştır: bu çalışmada kullanılan nesne tespit modeli, yalnızca kendisine ayrılmış bir grafik işlemcisi üzerinde, tam dolu yığınlarla ölçüldüğünde kare başına **3,78 ms** harcamaktadır. Aynı model, yirmi kameralı işlem hattının içinde, diğer kademelerle aynı donanımı paylaşırken ölçüldüğünde kare başına **7,46 ms** harcamaktadır (Tablo 5). Aradaki yaklaşık iki katlık fark modelin kendisinden değil, çalıştığı bağlamdan kaynaklanmaktadır: yığın boyutu üretimde tam dolmamakta, işlemci diğer kademelerle paylaşılmakta ve bellek erişim örüntüsü değişmektedir.

Bu gözlem tek bir bileşenle sınırlı değildir. Sistem düzeyinde yapılan müdahaleli bir deneyde, kameralardan alınan kare hızının iki katına çıkarılması, analiz edilen kare hızını artırmak yerine %32 oranında **düşürmüştür** (Bölüm III.A.3). Bileşen düzeyindeki hiçbir ölçüm bu davranışı öngörememektedir; çünkü davranış bileşenlerin kendisinden değil, kaynak paylaşımından doğmaktadır.

Bu ayrımın pratik önemi, gözetim sistemlerinin fiilen kurulduğu ortamlarda ortaya çıkmaktadır. Küçük ve orta ölçekli kurumların elindeki kaynak, ölçeklenebilir bir bulut altyapısı değil, çoğunlukla tek bir sunucu ya da tek bir iş istasyonudur. Böyle bir ortamda "yirmi kamera gerçek zamanlı işlenebilir mi" sorusunun cevabı, kullanılan modellerin tekil başarımından çok, bu modellerin bir arada nasıl konumlandırıldığına ve sistemin hangi noktalarda doyuma ulaştığına bağlıdır.

### A. Çalışmanın kapsamı ve kısıtları

Bu çalışma, bir staj projesi kapsamında yirmi beş iş gününde, tek geliştirici tarafından ve aşağıdaki kısıtlar altında yürütülmüştür. Kısıtlar, sonuçların hangi koşullarda geçerli olduğunu belirlediği için baştan ve açıkça belirtilmektedir:

**Donanım.** Tüm ölçümler tek bir dizüstü bilgisayar üzerinde yapılmıştır: NVIDIA RTX 3070 Laptop GPU (8 GB VRAM), 20 mantıksal işlemci çekirdeği, 16 GB sistem belleği. Dizüstü varyantı, aynı adı taşıyan masaüstü grafik işlemcisinin yaklaşık %65–75 başarımını sunmakta ve termal kısıtlamaya açık bulunmaktadır.

**Kamera kaynağı.** Çalışmada gerçek IP kamera kullanılmamıştır. Yirmi kamera, farklı veri setlerinden derlenen video dosyalarının bir medya sunucusu üzerinden sonsuz döngüde yayınlanmasıyla benzetilmiştir. Bu kurulumun ölçümler üzerindeki etkisi Bölüm III.C.3'te niceliksel olarak ele alınmaktadır; kısaca, "alarm/kamera-saat" türü ham oranların kaynak videoların uzunluk dağılımına doğrudan bağımlı hale gelmesine yol açmaktadır.

**Süre ve kapsam.** Proje, başlangıçta bir staj çalışması olarak tasarlanmış; geliştirme sürecinin ilerleyen aşamasında akademik yayına dönüştürülmesine karar verilmiştir. Bu karar, ölçüm titizliğinin proje boyunca değil, sürecin belirli bir aşamasından sonra artırılmasına neden olmuştur. Erken dönem ölçümlerinin bir bölümü daha sonra tekrarlanmış, tekrarlanamayanlar ise Bölüm III'te açıkça belirtilmiştir.

**Değerlendirme verisinin sınırları.** Bu çalışmanın yöntemsel iddiası, ölçüm tasarımının sonuçlar üzerindeki etkisine ilişkindir; dolayısıyla aynı ölçütün bu çalışmanın kendi değerlendirme verisine de uygulanması gerekmektedir. Kullanılan değerlendirme kümeleri küçüktür ve bu durum sonuçların güven aralıklarına doğrudan yansımaktadır: anomali tespiti dokuz klip (1439 kare) üzerinden, şiddet tespiti doksan altı klip üzerinden, alarm kesinliği ise on dokuz bağımsız olay üzerinden ölçülmüştür. Bu nedenle çalışma boyunca nokta tahminler tek başına raporlanmamış; her doğruluk değeri güven aralığıyla birlikte verilmiş, aralıkların hesabında gözlem biriminin bağımsızlığı ayrıca denetlenmiştir (Bölüm II.C.5). Bu çalışmanın iddiası, elde edilen doğruluk değerlerinin genel geçerliliği değil, **bu değerlerin hangi koşullarda ve hangi belirsizlikle elde edildiğinin gösterilmesidir.**

### B. Katkılar

Çalışmanın katkıları dört başlıkta toplanmaktadır:

**(a) Kısıtlı donanımda uçtan uca ölçülmüş bir mimari.** Yirmi kamera akışının tek bir grafik işlemcisi üzerinde işlendiği, kademeli filtrelemeye dayalı bir işlem hattı tasarlanmış; her kademenin maliyeti kare başına ayrı ayrı ölçülmüş ve ölçülen maliyetlerin toplamının bağımsız olarak ölçülen döngü toplamına eşit olduğu doğrulanmıştır (Bölüm III.A).

**(b) Model birleşiminin kazancı ve mekanizması.** İskelet tabanlı ve ham piksel tabanlı iki bağımsız şiddet tespit modelinin birleştirilmesinin sağladığı kazanç ölçülmüş; kazancın kaynağının iki modelin hata kümelerinin yalnızca %10 oranında örtüşmesi olduğu gösterilmiştir. Böylece birleşimin başarısı bir gözlem olmaktan çıkarılıp bir mekanizmaya bağlanmıştır (Bölüm III.B.1).

**(c) Ölçüt–veri uyuşmazlığı.** Sistemin üç başarı kriterinde, hedefin tutturulamamasının nedeninin sistemin başarımı değil ölçütün kendisi olduğu gösterilmiştir: bir kriterde ölçütün ulaşabileceği üst sınır hedefin altında kalmakta, bir diğerinde ölçüt eşiği ölçüm aracının çözünürlüğünün altına düşmekte, üçüncüsünde ise gözlem birimi bağımsızlık varsayımını karşılamamaktadır (Bölüm III.C).

**(d) Tek giriş noktası mimarisinde envanter eksikliği.** Kimlik doğrulamasının tek noktada toplandığı bir mimaride, bu noktadan geçen uç noktaların envanterinin çıkarılmaması nedeniyle gözlemlenebilirlik arayüzünün korumasız kaldığı tespit edilmiş; bulgunun tekrar eden yapısı ve giderilme yöntemi belgelenmiştir (Bölüm III.D).

### C. Makalenin düzeni

Bölüm II sistem mimarisini, kullanılan veri setlerini ve — bu çalışmada ayrı bir başlık olarak ele alınan — ölçüm yöntemini tanıtmaktadır. Bölüm III başarım, doğruluk, ölçüt geçerliliği ve güvenlik bulgularını sunmakta ve sınırları ayrı bir alt bölümde tartışmaktadır. Bölüm IV sonuçları ve gelecek çalışma önerilerini içermektedir.

---

## II. MATERYAL VE YÖNTEM

### A. Sistem mimarisi

Sistem, birbirinden bağımsız beş süreçten oluşmaktadır: alım, çıkarım, analitik, alarm ve uygulama programlama arayüzü (API). Süreçler arasındaki iletişim bir bellek içi veri yapısı sunucusu (Valkey) üzerindeki akışlarla sağlanmaktadır. Genel akış Şekil 1'de gösterilmiştir.

**[ŞEKİL 1 — `diagrams/01-veri-akisi.svg`]**
*Şekil 1. Sistem veri akışı ve ölçülen maliyetler.*

Mimari tasarımda, donanım kısıtından doğrudan türeyen dört kural benimsenmiştir:

**Ham video karesi mesaj kuyruğundan geçirilmemektedir.** 1080p çözünürlükte bir kare yaklaşık 6 MB yer kaplamakta; yirmi kameradan saniyede birkaç kare hızıyla bu verinin bir mesaj kuyruğuna yazılması, kuyruğun kendisini darboğaza dönüştürmektedir. Bunun yerine kareler paylaşımlı belleğe yazılmakta, kuyruktan yalnızca bir referans ve üst veri geçirilmektedir. Paylaşımlı bellek havuzu 96 yuvadan oluşmakta ve toplam 265 MB yer kaplamaktadır.

**Sunucu, video görüntüsünün üzerine tespit kutusu çizmemektedir.** Video, tarayıcıya WebRTC tabanlı bir protokol (WHEP) ile doğrudan medya sunucusundan iletilmekte; tespit kutuları ise ayrı bir WebSocket bağlantısı üzerinden JSON biçiminde gönderilmekte ve çizim işlemi tarayıcıda yapılmaktadır. Bu ayrım, sunucu tarafında yirmi ayrı video akışının yeniden kodlanmasını gereksiz kılmaktadır.

**Modeller tek süreçte ve tek kopya olarak yüklenmektedir.** Çıkarım süreci, tespit, poz ve yüz modellerini tek kopya halinde barındırmakta; ölçülen toplam video belleği kullanımı 571 MB (8 GB'ın %7'si) düzeyinde kalmaktadır.

**Tüm kuyruklar sınırlıdır.** Sınırsız bir kuyruk, üretici tüketiciden hızlı olduğunda bellek tükenmesine yol açmaktadır. Sistemde eski kareler beklenmek yerine düşürülmekte; düşürülen kare sayısı ayrıca ölçülmektedir.

#### A.1. Kademeli işleme

Yirmi akışın tek bir grafik işlemcisinde işlenebilmesi, her kareye tüm modellerin uygulanmaması sayesinde mümkün olmaktadır. İşlem hattı kademeli olarak kurgulanmıştır (Şekil 2):

**[ŞEKİL 2 — `diagrams/02-kademeli-isleme.svg`]**
*Şekil 2. Kademeli işleme ve ölçülen maliyet dağılımı.*

- **Kademe 0 — Hareket kapısı (CPU).** Ardışık kareler arasındaki farka bakılarak hareketsiz sahneler elenmekte, ayrıca kamera bazında uyarlanabilir örnekleme uygulanmaktadır: uzun süre hareket gözlenmeyen bir kamerada örnekleme hızı 4 kare/saniyeden 1 kare/saniyeye düşürülmektedir.
- **Kademe 1 — Nesne tespiti (GPU).** Yalnızca insan sınıfı tespit edilmektedir.
- **Kademe 1b — Çoklu nesne takibi.** Her kamera için ayrı bir takipçi örneği tutulmaktadır.
- **Kademe 2a — Poz kestirimi (GPU).** Tespit edilen her kişi kutusuna, yukarıdan aşağı (top-down) yaklaşımla uygulanmaktadır.
- **Kademe 2b — Yüz tespiti ve ifade sınıflandırması.** İki basamaklı bir kapıyla seyreltilmektedir (Bölüm III.B.4).

Planlanan ancak gerçekleştirilmeyen bir kademe (video tabanlı eylem doğrulayıcı) bulunmaktadır; bu durum Bölüm III.E'de kapsam kararı olarak belirtilmiştir.

### B. Veri setleri ve yer gerçeği

Çalışmada kullanılan veri setleri ve her birinin beslediği değerlendirme ölçütü Tablo 1'de özetlenmiştir.

*Tablo 1. Kullanılan veri setleri ve değerlendirme ölçütleriyle ilişkileri.*

| Veri seti | İçerik | Etiket düzeyi | Beslediği ölçüt |
|---|---|---|---|
| RWF-2000 (Cheng vd., 2021) | 2000 gözetim klibi (kavga/kavga değil) | Klip | Şiddet tespiti F1; erken uyarı avansı |
| CUHK Avenue (Lu vd., 2013) | 37 kampüs gözetim klibi | Kare | Anomali tespiti AUC |
| UR Fall Detection (Kwolek & Kepski, 2014) | Kontrollü ortamda düşme kayıtları | Olay | Düşme kuralı doğrulaması |
| UBI-Fights (Degardin & Proença, 2020) | Uzun süreli gözetim kayıtları | Kare | Erken uyarı avansı (bağlamlı ölçüm) |
| Kamera çiftliği (bu çalışma) | 20 kamera + 1 web kamerası | Yok / kısmi | Sistem başarımı, alarm kesinliği |

Değerlendirmede kullanılan iki etiket kümesi bu çalışma kapsamında elle üretilmiştir:

**Şiddet başlangıç etiketleri.** RWF-2000 doğrulama kümesinden seçilen 20 kavga klibinde, şiddetin başladığı kare tek bir değerlendirici tarafından, sistem skorları görülmeden işaretlenmiştir.

**Alarm doğrulama etiketleri.** Sistemin ürettiği 40 alarmın her biri için kaynak videodan ±3 saniyelik klip çıkarılmış ve alarmın haklı olup olmadığı değerlendirilmiştir. Değerlendirme ölçütü, klipler izlenmeden önce yazılmış ve her alarm türü için kuralın koddaki iddiasından türetilmiştir. Değerlendirici için üç seçenek tanımlanmıştır: haklı (1), yanlış (0), karar verilemedi (boş → analiz dışı). Kararsızlığı "yanlış" saymak sistemi haksız biçimde cezalandırmak, "haklı" saymak ise kayırmak anlamına geleceğinden üçüncü seçenek zorunlu görülmüştür.

Her iki etiket kümesinin de bilinen sınırı, tek değerlendirici ile üretilmiş olmaları ve değerlendiriciler arası uyum katsayısının hesaplanmamış olmasıdır.

### C. Ölçüm yöntemi

Bu bölüm, çalışmanın ikinci katkı ekseninin yöntemsel temelini oluşturmaktadır. Aşağıda sıralanan yedi uygulamanın her biri, geliştirme sürecinde ortaya çıkan somut bir ölçüm hatasının ardından benimsenmiştir.

**C.1. Kümülatif histogramdan pencere farkı alınması.** Sistem ölçümleri Prometheus biçimli histogramlar üzerinden toplanmaktadır. Bu histogramlar kümülatiftir; süreç başlangıcından itibaren tüm gözlemleri saymaktadır. Bir yüzdelik değerin doğrudan kümülatif histogramdan okunması, ölçüm penceresinin değil sürecin tüm yaşam süresinin yüzdeliğini vermektedir. Bu durumda aynı sistem, aynı kod ve aynı yük altında, yalnızca sürecin ne kadar süredir çalıştığına bağlı olarak farklı değerler üretmektedir. Tüm yüzdelik hesapları, pencere başlangıcı ve sonundaki iki anlık görüntünün farkı üzerinden yapılmaktadır.

**C.2. Duvar saati yerine işlemci zamanının ölçülmesi.** Bir kod bölümünün `perf_counter` benzeri bir duvar saati sayacıyla ölçülmesi, o bölümün bloke geçirdiği süreyi de maliyete dâhil etmektedir. Ayrıca, altta yatan sayısal kütüphanelerin (BLAS) iş parçacığı havuzu kullanması durumunda duvar saati süresi, harcanan toplam işlemci zamanının çok altında kalmaktadır. Bileşen maliyetleri `time.thread_time()` ile, yalnızca ilgili iş parçacığının harcadığı işlemci zamanı üzerinden ölçülmektedir.

**C.3. Kapanış kontrolü.** Bir işlem hattının bileşenleri tek tek ölçülüp toplandığında, elde edilen toplamın bağımsız olarak ölçülen döngü toplamına eşit olup olmadığı denetlenmektedir. Bu denetim yapılmadığında, ölçülmeyen bileşenlerin maliyeti örtük olarak sıfır kabul edilmiş olmaktadır. Bu çalışmada söz konusu denetimin eksikliği, bir aşamada işlem hattı maliyetinin %70'inin "ölçülmeyen ek yük" olarak yanlış raporlanmasına yol açmış; denetim eklendiğinde açığın %0 olduğu görülmüştür.

**C.4. Kontrol serisi kullanılması.** Bir ölçümün, ölçülen sistemin değil ölçüm aracının tavanını yansıtma olasılığına karşı, yük uygulanmadan yapılan bir kontrol ölçümü alınmaktadır. Arayüz akıcılığı ölçümünde tam olarak 30 kare/saniye değerinin elde edilmesi, tarayıcının bu değeri sabitliyor olabileceği şüphesini doğurmuş; kamera açılmadan yapılan kontrol ölçümünün 60 kare/saniye vermesi, gözlenen değerin yükün gerçek etkisi olduğunu göstermiştir. Benzer biçimde füzyon değerlendirmesinde, füzyonla aynı zamansal yumuşatmayı uygulayan tek sinyalli bir kontrol serisi tanımlanmıştır.

**C.5. Bağımsızlık biriminin belirlenmesi.** Güven aralıkları hesaplanırken gözlemlerin bağımsız olduğu varsayımı, video verisinde çoğunlukla geçerli değildir: aynı klipten gelen ardışık kareler aynı sahneyi, aynı kişileri ve aynı aydınlatmayı içermektedir. Bu çalışmada kare düzeyinde (naif) ve klip düzeyinde (küme) önyükleme aralıklarının ikisi de hesaplanmış ve raporlanmıştır; aradaki fark, bağımsızlık varsayımının sonuç üzerindeki etkisinin niceliksel ölçüsüdür.

**C.6. Eşik seçim yanlılığının ölçülmesi.** F1 gibi eşiğe bağlı ölçütlerde, en iyi eşiğin ölçütün hesaplandığı kümede aranması iyimser bir sonuç üretmektedir. Bu yanlılık, veri kümesinin tekrarlı ve katmanlı biçimde yarıya bölünmesi, eşiğin bir yarıda seçilip diğerinde uygulanmasıyla ölçülmüştür (400 tekrar).

**C.7. Kazananın laneti düzeltmesi.** Birden çok aday kural arasından en iyisinin aynı veri üzerinde seçilmesi, seçilen kuralın başarımını iyimser göstermektedir. Bu iyimserlik önyükleme ile kestirilmiş ve raporlanmıştır. Ayrıca, birleştirme kuralı ölçüm yapılmadan önce belirlenmiştir.

Tablo 2, bu çalışmada karşılaşılan ölçüm hatası türlerini ve karşılık gelen düzeltmeleri özetlemektedir.

*Tablo 2. Gözlenen ölçüm hatası türleri ve uygulanan düzeltmeler.*

| Hata türü | Belirtisi | Düzeltme |
|---|---|---|
| Kümülatif sayaçtan yüzdelik okuma | Aynı koşulda farklı sonuçlar | Pencere farkı (C.1) |
| Duvar saati ile işlemci zamanının karıştırılması | Maliyetin olduğundan düşük görünmesi | `thread_time` (C.2) |
| Aynı metrikte iki farklı birim | Bileşen toplamının döngü toplamını tutmaması | Tek birim + kapanış kontrolü (C.3) |
| Ölçülmeyenin sıfır sayılması | Açıklanamayan maliyetin görünmemesi | Kapanış kontrolü (C.3) |
| Aracın tavanının sistem sanılması | Şüphe uyandırmayan "yuvarlak" değerler | Kontrol serisi (C.4) |
| Bağımlı gözlemlerin bağımsız sayılması | Güven aralığının olduğundan dar çıkması | Küme önyükleme (C.5) |
| Eşiğin ölçüm kümesinde seçilmesi | İyimser F1 | Tekrarlı yarı bölme (C.6) |
| Aday kurallar arasından seçim | İyimser en iyi skor | Kazananın laneti kestirimi (C.7) |

### D. Güvenlik yaklaşımı

Güvenlik gereksinimleri proje başlangıcında yirmi maddelik bir öncelikli liste olarak tanımlanmış ve geliştirme boyunca izlenmiştir. Kimlik doğrulaması Argon2id ile saklanan parolalar ve kısa ömürlü JWT belirteçleri üzerine kurulmuş; belirteçler `HttpOnly` çerezde tutulmuştur. Yetkilendirme, üç rollü (izleyici, operatör, yönetici) bir modelle her uç noktada bağımlılık olarak denetlenmektedir.

Mimarinin güvenlik açısından belirleyici bileşeni, ters vekil sunucu (Caddy) üzerinden kurulan **tek giriş noktasıdır**. Bu bileşenin gerekçesi, geliştirme sırasında tespit edilen bir açıktan doğmuştur: uygulama programlama arayüzü kimlik doğrulaması gerektirirken, video akışını sunan medya sunucusu hiçbir doğrulama yapmamaktaydı. Video akışının uygulama ile aynı köken üzerinden sunulması, tarayıcının kimlik çerezini bu isteklere de eklemesini ve dolayısıyla video isteklerinin de doğrulanabilmesini sağlamaktadır. Vekil sunucu, video isteğini medya sunucusuna iletmeden önce uygulama arayüzüne yönlendirerek yetki sorgusu yapmaktadır (Şekil 3).

**[ŞEKİL 3 — yeni çizilecek: kimlik doğrulama akışı]**
*Şekil 3. Tek giriş noktası ve video akışının kimlik doğrulaması.*
