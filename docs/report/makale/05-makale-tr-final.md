# Kısıtlı Donanımda Yirmi Kameralı Gerçek Zamanlı Gözetim Sistemi: Başarım ve Doğruluk İddialarının Ölçülebilirliği Üzerine Bir Vaka Çalışması

**Ömer Faruk Kanat**¹*

¹ Düzce Üniversitesi, Mühendislik Fakültesi, Bilgisayar Mühendisliği Bölümü (İngilizce), Düzce, Türkiye. `ror.org/04175wc52`

* Yazışma yazarı: Ömer Faruk Kanat, omerfk0121@gmail.com
ORCID: 0009-0006-9229-6217

**Makale Türü:** Araştırma Makalesi

## ÖZ

Bilgisayarlı görü bileşenlerinin tek tek ölçülen başarım değerlerinin, aynı bileşenler tek bir donanımı paylaşan bütünleşik bir sistemde de geçerli olup olmadığı bu çalışmada deneysel olarak incelenmiştir. Çalışmada yirmi eşzamanlı kamera akışının tek bir orta seviye dizüstü grafik işlemcisi (RTX 3070 Laptop, 8 GB) üzerinde işlendiği bir gözetim sistemini konu almaktadır. Sistemde nesne tespiti, çoklu nesne takibi, poz kestirimi, yüz ifadesi sınıflandırması, anomali tespiti ve saldırgan davranış kestirimi tek bir işlem hattında birleştirilmiştir. Uçtan uca gecikme 378 ms (p50) ve 652 ms (p95) olarak ölçülmüş, kamera başına analiz edilen kare hızı 2,34 kare/saniyede kalmıştır. Şiddet tespitinde iskelet tabanlı bir gradyan artırma modeli ile ham piksel tabanlı üç boyutlu evrişimli bir modelin skor ortalaması alındığında F1 skoru 0,937 (eşik seçim yanlılığı düzeltildiğinde 0,917) elde edilmiş; kazancın kaynağının iki modelin hatalarının yalnızca %10 oranında örtüşmesi olduğu gösterilmiştir. Anomali tespitinde füzyon yaklaşımı 0,869 eğri altı alan değeri vermiş (küme önyükleme %95 güven aralığı 0,806 ile 0,929), ancak aynı zamansal yumuşatmayı tek sinyale uygulayan kontrol serisi 0,860 vermiştir; bu, kazancın sinyal birleştirmeden değil yumuşatmadan geldiğini göstermektedir. Çalışmanın ikinci katkısı ölçüm tarafındadır: geliştirme günlüğündeki 87 kaydın 43'ünde bir başarım ya da doğruluk iddiası sonraki bir ölçümle çürütülmüştür. Bu çürütmeler üç başlıkta toplanmıştır: ölçütün üst sınırının hedefin altında kalması, ölçüt eşiğinin ölçüm çözünürlüğünün altında olması ve gözlem biriminin bağımsızlık varsayımını karşılamaması. Güvenlik tarafında, tek giriş noktası mimarisi kurulmuş olmasına karşın bu noktadan geçen uç noktaların envanteri çıkarılmadığı için gözlemlenebilirlik arayüzünün kimlik doğrulaması olmaksızın dışarıya açık kaldığı tespit edilmiş ve giderilmiştir.

**Anahtar Kelimeler:** Çok kameralı gözetim, Gerçek zamanlı video analizi, Şiddet tespiti, Kaynak kısıtlı çıkarım, Ölçüm geçerliliği

---

## ABSTRACT

This study examines whether performance values measured for individual computer vision components remain valid when they share a single hardware platform. The system presented here processes twenty concurrent camera streams on one mid-range laptop graphics processor (RTX 3070 Laptop, 8 GB), combining object detection, tracking, pose estimation, facial expression classification, anomaly detection and aggression estimation in a single pipeline. End-to-end latency was 378 ms (p50) and 652 ms (p95); the analysed frame rate remained at 2.34 frames per second per camera. For violence detection, averaging a skeleton-based gradient boosting model with a raw-pixel three-dimensional convolutional model gave an F1 of 0.937 (0.917 after correcting threshold selection bias); the gain is attributable to the two models' error sets overlapping by only 10%. For anomaly detection, fusion gave an area under the curve of 0.869 (95% cluster bootstrap interval 0.806 to 0.929), while a control series applying the same temporal smoothing to a single signal gave 0.860, showing that the gain comes from smoothing rather than from signal combination. The second contribution is methodological: in 43 of 87 development-log entries, a performance or accuracy claim was refuted by a later measurement. These refutations fall into three classes: a criterion whose attainable upper bound lies below its target, a threshold below the measuring instrument's resolution, and an observation unit violating the independence assumption. In security, although a single entry point was established, the endpoints passing through it were never enumerated; the observability interface was consequently reachable without authentication, and this was corrected.

**Keywords:** Multi-camera surveillance, Real-time video analytics, Violence detection, Resource-constrained inference, Measurement validity

---

## I. GİRİŞ

Video gözetim sistemlerinin otomatikleştirilmesi, bilgisayarlı görü alanının en yoğun çalışılan uygulama başlıklarından biridir. Nesne tespiti, çoklu nesne takibi, poz kestirimi ve video tabanlı eylem tanıma alanlarının her birinde son yıllarda hem doğruluk hem hız bakımından belirgin ilerlemeler kaydedilmiştir. Bu bileşenler tek tek değerlendirildiğinde, kare başına maliyetleri ve doğruluk değerleri ayrıntılı biçimde raporlanmaktadır.

Gözetim videosunda şiddet tespiti, bu uygulama alanları içinde ayrı bir çalışma hattı oluşturmaktadır. Yaklaşımlar iki ana gruba ayrılmaktadır. Birinci grup, insan iskeletinden türetilen özniteliklere dayanmakta ve gerçek zamanlı çalışabilmeyi hedeflemektedir (Zhang vd., 2023; Mittal vd., 2026). İkinci grup, video kesitlerini doğrudan ham piksel olarak işleyen uzay-zamansal ağlar kullanmaktadır (Senadeera vd., 2024; Pathak vd., 2024). Video anomali tespitinde ise son dönemde görü-dil modellerinin denetimsiz ya da zayıf denetimli biçimde kullanıldığı yaklaşımlar öne çıkmaktadır (Zou vd., 2025; Shao vd., 2025; Borodin vd., 2025).

Bu çalışmada söz konusu yaklaşımlardan tekil olarak en iyi başarımı vereni seçmek değil, birden çok bileşenin tek bir donanım üzerinde birlikte çalıştırılması hedeflenmiştir. Bu nedenle bileşen seçimlerinde başarım kadar hesaplama maliyeti de belirleyici olmuştur.

Bu çalışmanın çıkış noktası, söz konusu bileşen düzeyindeki değerlerin bütünleşik bir sisteme taşınıp taşınmadığı sorusudur. Soru, geliştirme sırasında yapılan bir ölçümle somutlaşmıştır. Bu çalışmada kullanılan nesne tespit modeli, yalnızca kendisine ayrılmış bir grafik işlemcisi üzerinde ve tam dolu yığınlarla ölçüldüğünde kare başına **3,78 ms** harcamaktadır. Aynı model, yirmi kameralı işlem hattının içinde, diğer kademelerle aynı donanımı paylaşırken ölçüldüğünde kare başına **7,46 ms** harcamaktadır (Tablo 7). Aradaki yaklaşık iki katlık fark modelin kendisinden değil, çalıştığı bağlamdan kaynaklanmaktadır: yığın boyutu üretimde tam dolmamakta, işlemci diğer kademelerle paylaşılmakta ve bellek erişim örüntüsü değişmektedir.

Bu gözlem tek bir bileşenle sınırlı değildir. Sistem düzeyinde yapılan müdahaleli bir deneyde, kameralardan alınan kare hızının iki katına çıkarılması, analiz edilen kare hızını artırmak yerine %32 oranında **düşürmüştür** (Bölüm III.A.3). Bileşen düzeyindeki hiçbir ölçüm bu davranışı öngörememektedir, çünkü davranış bileşenlerin kendisinden değil kaynak paylaşımından doğmaktadır.

Bu ayrımın pratik önemi, gözetim sistemlerinin fiilen kurulduğu ortamlarda ortaya çıkmaktadır. Küçük ve orta ölçekli kurumların elindeki kaynak, ölçeklenebilir bir bulut altyapısı değil, çoğunlukla tek bir sunucu ya da tek bir iş istasyonudur. Böyle bir ortamda "yirmi kamera gerçek zamanlı işlenebilir mi" sorusunun cevabı, kullanılan modellerin tekil başarımından çok, bu modellerin bir arada nasıl konumlandırıldığına ve sistemin hangi noktalarda doyuma ulaştığına bağlıdır.

### A. Çalışmanın kapsamı ve kısıtları

Bu çalışma, bir staj projesi kapsamında yirmi beş iş gününde, tek geliştirici tarafından ve aşağıdaki kısıtlar altında yürütülmüştür. Kısıtlar, sonuçların hangi koşullarda geçerli olduğunu belirlediği için baştan ve açıkça belirtilmektedir.

**Donanım.** Tüm ölçümler tek bir dizüstü bilgisayar üzerinde yapılmıştır: NVIDIA RTX 3070 Laptop GPU (8 GB VRAM), 20 mantıksal işlemci çekirdeği, 16 GB sistem belleği. Dizüstü varyantı, aynı adı taşıyan masaüstü grafik işlemcisinin yaklaşık %65 ile %75 arası başarımını sunmakta ve termal kısıtlamaya açık bulunmaktadır.

**Kamera kaynağı.** Çalışmada gerçek IP kamera kullanılmamıştır. Yirmi kamera, farklı veri setlerinden derlenen video dosyalarının bir medya sunucusu üzerinden sonsuz döngüde yayınlanmasıyla benzetilmiştir. Bu kurulumun ölçümler üzerindeki etkisi Bölüm III.C.3'te niceliksel olarak ele alınmaktadır. Kısaca, "alarm/kamera-saat" türü ham oranlar kaynak videoların uzunluk dağılımına doğrudan bağımlı hale gelmektedir.

**Süre ve kapsam.** Proje başlangıçta bir staj çalışması olarak tasarlanmış, geliştirme sürecinin ilerleyen aşamasında akademik yayına dönüştürülmesine karar verilmiştir. Bu karar, ölçüm titizliğinin proje boyunca değil sürecin belirli bir aşamasından sonra artırılmasına neden olmuştur. Erken dönem ölçümlerinin bir bölümü daha sonra tekrarlanmış, tekrarlanamayanlar ise Bölüm III'te açıkça belirtilmiştir.

**Değerlendirme verisinin sınırları.** Bu çalışmanın yöntemsel iddiası ölçüm tasarımının sonuçlar üzerindeki etkisine ilişkindir, dolayısıyla aynı ölçütün bu çalışmanın kendi değerlendirme verisine de uygulanması gerekmektedir. Kullanılan değerlendirme kümeleri küçüktür ve bu durum sonuçların güven aralıklarına doğrudan yansımaktadır: anomali tespiti dokuz klip (1439 kare) üzerinden, şiddet tespiti doksan altı klip üzerinden, alarm kesinliği ise on dokuz bağımsız olay üzerinden ölçülmüştür. Bu nedenle çalışma boyunca nokta tahminler tek başına raporlanmamış, her doğruluk değeri güven aralığıyla birlikte verilmiş ve aralıkların hesabında gözlem biriminin bağımsızlığı ayrıca denetlenmiştir (Bölüm II.C.5). Çalışmanın iddiası, elde edilen doğruluk değerlerinin genel geçerliliği değil, **bu değerlerin hangi koşullarda ve hangi belirsizlikle elde edildiğinin gösterilmesidir.**

### B. Katkılar

Çalışmanın katkıları dört başlıkta toplanmaktadır.

**(a) Kısıtlı donanımda uçtan uca ölçülmüş bir mimari.** Yirmi kamera akışının tek bir grafik işlemcisi üzerinde işlendiği, kademeli filtrelemeye dayalı bir işlem hattı tasarlanmıştır. Her kademenin maliyeti kare başına ayrı ayrı ölçülmüş ve ölçülen maliyetlerin toplamının bağımsız olarak ölçülen döngü toplamına eşit olduğu doğrulanmıştır (Bölüm III.A).

**(b) Model birleşiminin kazancı ve mekanizması.** İskelet tabanlı ve ham piksel tabanlı iki bağımsız şiddet tespit modelinin birleştirilmesinin sağladığı kazanç ölçülmüş, kazancın kaynağının iki modelin hata kümelerinin yalnızca %10 oranında örtüşmesi olduğu gösterilmiştir. Böylece birleşimin başarısı bir gözlem olmaktan çıkarılıp bir mekanizmaya bağlanmıştır (Bölüm III.B.1).

**(c) Ölçüt ile veri arasındaki uyuşmazlık.** Burada "ölçüt", sistemin başarılı sayılması için önceden tanımlanmış sayısal hedeftir; örneğin "şiddet başlamadan en az 2 saniye önce uyarı üret" bir ölçüttür. Bu çalışmada üç ölçütte, hedefin tutturulamamasının nedeninin sistemin başarımı değil ölçütün kendisi olduğu gösterilmiştir. Bir ölçütte, kullanılan veri setinde ulaşılabilecek en yüksek değer hedefin altında kalmaktadır; bir diğerinde ölçüt eşiği ölçüm aracının çözünürlüğünün altına düşmektedir; üçüncüsünde ise gözlem birimi bağımsızlık varsayımını karşılamamaktadır (Bölüm III.C).

**(d) Tek giriş noktası mimarisinde envanter eksikliği.** Kimlik doğrulamasının tek noktada toplandığı bir mimaride, bu noktadan geçen uç noktaların envanterinin çıkarılmaması nedeniyle gözlemlenebilirlik arayüzünün korumasız kaldığı tespit edilmiş, bulgunun tekrar eden yapısı ve giderilme yöntemi belgelenmiştir (Bölüm III.D).

### C. Makalenin düzeni

Bölüm II sistem mimarisini, kullanılan veri setlerini ve bu çalışmada ayrı bir başlık olarak ele alınan ölçüm yöntemini tanıtmaktadır. Bölüm III başarım, doğruluk, ölçüt geçerliliği ve güvenlik bulgularını sunmakta, sınırları ayrı bir alt bölümde tartışmaktadır. Bölüm IV sonuçları ve gelecek çalışma önerilerini içermektedir.

---

## II. MATERYAL VE YÖNTEM

### A. Sistem mimarisi

Sistem, birbirinden bağımsız beş süreçten oluşmaktadır: alım, çıkarım, analitik, alarm ve uygulama programlama arayüzü. Süreçler arasındaki iletişim bir bellek içi veri yapısı sunucusu (Valkey) üzerindeki akışlarla sağlanmaktadır. Genel akış Şekil 1'de gösterilmiştir.

**[ŞEKİL 1]**
*Şekil 1. Sistem veri akışı ve ölçülen maliyetler.*

Mimari tasarımda, donanım kısıtından doğrudan türeyen dört kural benimsenmiştir.

**Ham video karesi mesaj kuyruğundan geçirilmemektedir.** 1080p çözünürlükte bir kare yaklaşık 6 MB yer kaplamaktadır. Yirmi kameradan saniyede birkaç kare hızıyla bu verinin bir mesaj kuyruğuna yazılması, kuyruğun kendisini darboğaza dönüştürmektedir. Bunun yerine kareler paylaşımlı belleğe yazılmakta, kuyruktan yalnızca bir referans ile üst veri geçirilmektedir. Paylaşımlı bellek havuzu 96 yuvadan oluşmakta, her yuva tam bir 720p BGR karesi (1280 × 720 × 3 bayt = 2,76 MB) barındırmakta ve havuz toplam 265 MB yer kaplamaktadır. Havuzun boyutu bir depolama kararı değil bir kuyruk kararıdır; gerekçesi Bölüm III.A.5'te ele alınmaktadır.

**Sunucu, video görüntüsünün üzerine tespit kutusu çizmemektedir.** Video, tarayıcıya WebRTC tabanlı bir protokol (WHEP) ile doğrudan medya sunucusundan iletilmekte, tespit kutuları ise ayrı bir WebSocket bağlantısı üzerinden JSON biçiminde gönderilmekte ve çizim işlemi tarayıcıda yapılmaktadır. Bu ayrım, sunucu tarafında yirmi ayrı video akışının yeniden kodlanmasını gereksiz kılmaktadır.

**Modeller tek süreçte ve tek kopya olarak yüklenmektedir.** Çıkarım süreci; tespit, poz ve yüz modellerini tek kopya halinde barındırmaktadır. Ölçülen video belleği kullanımı 571 MB düzeyindedir (8192 MB'ın %7'si).

**Tüm kuyruklar sınırlıdır.** Sınırsız bir kuyruk, üretici tüketiciden hızlı olduğunda bellek tükenmesine yol açmaktadır. Sistemde eski kareler beklenmek yerine düşürülmekte, düşürülen kare sayısı ayrıca ölçülmektedir.

#### A.1. Kademeli işleme

Yirmi akışın tek bir grafik işlemcisinde işlenebilmesi, her kareye tüm modellerin uygulanmaması sayesinde mümkün olmaktadır. İşlem hattı kademeli olarak kurgulanmıştır (Şekil 2).

**[ŞEKİL 2]**
*Şekil 2. Kademeli işleme ve ölçülen maliyet dağılımı.*

**Kademe 0, hareket kapısı (işlemci).** Ardışık kareler arasındaki farka bakılarak hareketsiz sahneler elenmekte, ayrıca kamera bazında uyarlanabilir örnekleme uygulanmaktadır. Uzun süre hareket gözlenmeyen bir kamerada örnekleme hızı 4 kare/saniyeden 1 kare/saniyeye düşürülmektedir.

**Kademe 1, nesne tespiti (grafik işlemci).** Yalnızca insan sınıfı tespit edilmektedir.

**Kademe 1b, çoklu nesne takibi.** Her kamera için ayrı bir takipçi örneği tutulmaktadır (Aharon vd., 2022). Takipçi seçiminde, düşük güvenli tespitleri de ilişkilendirme aşamasına dâhil eden yaklaşımların kimlik kararlılığını artırdığı yönündeki bulgular gözetilmiştir (Zhang vd., 2023b).

**Kademe 2a, poz kestirimi (grafik işlemci).** Tespit edilen her kişi kutusuna, yukarıdan aşağı yaklaşımla uygulanmaktadır.

**Kademe 2b, yüz tespiti ve ifade sınıflandırması.** Yüz tespiti için hafif bir dedektör kullanılmakta (Wu vd., 2023), sınıflandırma ise iki basamaklı bir kapıyla seyreltilmektedir (Bölüm III.B.4). Yüz davranışı çözümlemesinde gerçek zamanlı çalışabilen bütünleşik araçlar mevcuttur (Hu vd., 2025); bu çalışmadaki kısıt modelin kendisi değil, gözetim görüntüsündeki yüz çözünürlüğüdür.

Planlanan ancak gerçekleştirilmeyen bir kademe bulunmaktadır. Kademe 3 olarak tasarlanan video tabanlı eylem doğrulayıcı, tırmanma skoru belirli bir eşiği aştığında kısa bir video kesitini üç boyutlu bir evrişimli ağa vererek alarmı doğrulaması ya da reddetmesi öngörülen bir aşamadır. Gerçekleştirilmeme gerekçesi Bölüm III.E'de kapsam kararı olarak açıklanmaktadır.

### B. Veri setleri ve yer gerçeği

Yirmi kameralı çiftliğin kaynakları ile değerlendirme veri setleri Tablo 1 ve Tablo 2'de verilmiştir.

*Tablo 1. Kamera çiftliğinin kaynak veri setleri.*

| Veri seti | Kameralar | İçerik | Kullanım amacı |
|---|---|---|---|
| VIRAT Ground 2.0 (Oh vd., 2011) | cam-01 ile cam-08 | Sabit gözetim: otopark, kampüs, bina girişi | Anomali modülünün "normal" profilini öğrenmesi |
| Oxford Town Centre (Benfold & Reid, 2011) | cam-09 | Yoğun yaya trafiği, yer gerçekli | Takip doğruluğu referansı |
| PETS 2009 (Ferryman & Shahrokni, 2009) | cam-10 ile cam-14 | Çok kameralı kalabalık, ani dağılma | Kalabalık ve dağılma kuralları |
| UBI-Fights (Degardin & Proença, 2020) | cam-15 | Uzun süreli gözetim, şiddet olaylı | Erken uyarı, bağlamlı ölçüm |
| UR Fall Detection (Kwolek & Kepski, 2014) | cam-16 | Kontrollü düşme kayıtları | Düşme kuralı doğrulaması |
| RWF-2000 (Cheng vd., 2021) | cam-17 | Gözetim kaynaklı kavga klipleri | Saldırganlık modülü |
| CUHK Avenue (Lu vd., 2013) | cam-18, cam-19 | Kampüs gözetimi, kare düzeyli etiket | Anomali kontrolü ve testi |
| Pexels | cam-20 | Yakın plan yüz içeren sahneler | İfade modülü testi |

Veri setleri kendi lisans koşulları çerçevesinde ve yalnızca araştırma amacıyla kullanılmıştır.

*Tablo 2. Değerlendirme veri setleri ve besledikleri ölçütler.*

| Veri seti | Etiket düzeyi | Büyüklük | Beslediği ölçüt |
|---|---|---|---|
| RWF-2000 doğrulama | Klip | 96 klip | Şiddet tespiti F1 |
| RWF-2000, elle işaretli | Kare (başlangıç anı) | 20 kavga klibi | Erken uyarı avansı |
| CUHK Avenue | Kare | 9 klip / 1439 kare | Anomali tespiti AUC |
| Kamera çiftliği alarmları | Olay | 40 alarm, 19 bağımsız olay | Alarm kesinliği |

Değerlendirmede kullanılan iki etiket kümesi bu çalışma kapsamında elle üretilmiştir.

**Şiddet başlangıç etiketleri.** RWF-2000 doğrulama kümesinden seçilen 20 kavga klibinde, şiddetin başladığı kare tek bir değerlendirici tarafından, sistem skorları görülmeden işaretlenmiştir.

**Alarm doğrulama etiketleri.** Sistemin ürettiği 40 alarmın her biri için kaynak videodan yaklaşık 6 saniyelik kesit çıkarılmış ve alarmın haklı olup olmadığı değerlendirilmiştir. Değerlendirme ölçütü, kesitler izlenmeden önce yazılmış ve her alarm türü için kuralın koddaki iddiasından türetilmiştir. Değerlendirici için üç seçenek tanımlanmıştır: haklı, yanlış ve karar verilemedi. Kararsızlığı "yanlış" saymak sistemi haksız biçimde cezalandırmak, "haklı" saymak ise kayırmak anlamına geleceğinden üçüncü seçenek zorunlu görülmüştür.

Her iki etiket kümesinin de bilinen sınırı, tek değerlendirici ile üretilmiş olmaları ve değerlendiriciler arası uyum katsayısının hesaplanmamış olmasıdır.

### C. Ölçüm yöntemi

Bu bölüm, çalışmanın ikinci katkı ekseninin yöntemsel temelini oluşturmaktadır. Aşağıda sıralanan yedi uygulamanın her biri, geliştirme sürecinde ortaya çıkan somut bir ölçüm hatasının ardından benimsenmiştir.

**C.1. Kümülatif histogramdan pencere farkı alınması.** Sistem ölçümleri Prometheus biçimli histogramlar üzerinden toplanmaktadır. Bu histogramlar kümülatiftir, yani süreç başlangıcından itibaren tüm gözlemleri saymaktadır. Bir yüzdelik değerin doğrudan kümülatif histogramdan okunması, ölçüm penceresinin değil sürecin tüm yaşam süresinin yüzdeliğini vermektedir. Bu durumda aynı sistem, aynı kod ve aynı yük altında, yalnızca sürecin ne kadar süredir çalıştığına bağlı olarak farklı değerler üretmektedir. Tüm yüzdelik hesapları, pencere başlangıcı ile sonundaki iki anlık görüntünün farkı üzerinden yapılmaktadır.

**C.2. Duvar saati yerine işlemci zamanının ölçülmesi.** Bir kod bölümünün duvar saati sayacıyla ölçülmesi, o bölümün bloke geçirdiği süreyi de maliyete dâhil etmektedir. Ayrıca, altta yatan sayısal kütüphanelerin iş parçacığı havuzu kullanması durumunda duvar saati süresi, harcanan toplam işlemci zamanının çok altında kalmaktadır. Bileşen maliyetleri `time.thread_time()` ile, yalnızca ilgili iş parçacığının harcadığı işlemci zamanı üzerinden ölçülmektedir.

**C.3. Kapanış kontrolü.** Bir işlem hattının bileşenleri tek tek ölçülüp toplandığında, elde edilen toplamın bağımsız olarak ölçülen döngü toplamına eşit olup olmadığı denetlenmektedir. Bu denetim yapılmadığında, ölçülmeyen bileşenlerin maliyeti örtük olarak sıfır kabul edilmiş olmaktadır. Bu denetimin eksikliğinin bu çalışmada yol açtığı hata Bölüm III.A.4'te ele alınmaktadır.

**C.4. Kontrol serisi kullanılması.** Bir ölçümün, ölçülen sistemin değil ölçüm aracının tavanını yansıtma olasılığına karşı, yük uygulanmadan yapılan bir kontrol ölçümü alınmaktadır. Bu çalışmada iki yerde kontrol serisi tanımlanmıştır: arayüz akıcılığı ölçümünde kamera açılmadan yapılan ölçüm (Bölüm III.C.2) ve füzyon değerlendirmesinde, füzyonla aynı zamansal yumuşatmayı uygulayan tek sinyalli seri (Bölüm III.B.2).

**C.5. Bağımsızlık biriminin belirlenmesi.** Güven aralıkları hesaplanırken gözlemlerin bağımsız olduğu varsayımı video verisinde çoğunlukla geçerli değildir, çünkü aynı klipten gelen ardışık kareler aynı sahneyi, aynı kişileri ve aynı aydınlatmayı içermektedir. Bu çalışmada kare düzeyinde ve klip düzeyinde önyükleme aralıklarının (Efron, 1979; Field & Welsh, 2007) ikisi de hesaplanmış ve raporlanmıştır. Aradaki fark, bağımsızlık varsayımının sonuç üzerindeki etkisinin niceliksel ölçüsüdür.

**C.6. Eşik seçim yanlılığının ölçülmesi.** F1 gibi eşiğe bağlı ölçütlerde, en iyi eşiğin ölçütün hesaplandığı kümede aranması iyimser bir sonuç üretmektedir. Bu yanlılık, veri kümesinin tekrarlı ve katmanlı biçimde yarıya bölünmesi, eşiğin bir yarıda seçilip diğerinde uygulanmasıyla ölçülmüştür (400 tekrar). Model seçiminin aynı küme üzerinde yapılmasının yol açtığı iyimserlik literatürde ayrıntılı biçimde ele alınmıştır (Varma & Simon, 2006).

**C.7. Kazananın laneti düzeltmesi.** Birden çok aday kural arasından en iyisinin aynı veri üzerinde seçilmesi, seçilen kuralın başarımını iyimser göstermektedir. Bu iyimserlik önyükleme ile kestirilmiş ve raporlanmıştır. Ayrıca birleştirme kuralı, ölçüm yapılmadan önce belirlenmiştir.

Tablo 3, bu çalışmada karşılaşılan ölçüm hatası türlerini ve karşılık gelen düzeltmeleri özetlemektedir.

*Tablo 3. Gözlenen ölçüm hatası türleri ve uygulanan düzeltmeler.*

| Hata türü | Belirtisi | Düzeltme |
|---|---|---|
| Kümülatif sayaçtan yüzdelik okuma | Aynı koşulda farklı sonuçlar | Pencere farkı (C.1) |
| Duvar saati ile işlemci zamanının karıştırılması | Maliyetin olduğundan düşük görünmesi | İş parçacığı zamanı (C.2) |
| Aynı metrikte iki farklı birim | Bileşen toplamının döngü toplamını tutmaması | Tek birim ile kapanış kontrolü (C.3) |
| Ölçülmeyenin sıfır sayılması | Açıklanamayan maliyetin görünmemesi | Kapanış kontrolü (C.3) |
| Aracın tavanının sistem sanılması | Şüphe uyandırmayan yuvarlak değerler | Kontrol serisi (C.4) |
| Bağımlı gözlemlerin bağımsız sayılması | Güven aralığının olduğundan dar çıkması | Küme önyükleme (C.5) |
| Eşiğin ölçüm kümesinde seçilmesi | İyimser F1 | Tekrarlı yarı bölme (C.6) |
| Aday kurallar arasından seçim | İyimser en iyi skor | Kazananın laneti kestirimi (C.7) |

### D. Güvenlik yaklaşımı

Güvenlik gereksinimleri proje başlangıcında yirmi maddelik bir öncelikli liste olarak tanımlanmış ve geliştirme boyunca izlenmiştir. Kimlik doğrulaması Argon2id ile saklanan parolalar ve kısa ömürlü JWT belirteçleri üzerine kurulmuş, belirteçler `HttpOnly` çerezde tutulmuştur. Yetkilendirme; izleyici, operatör ve yönetici olmak üzere üç rollü bir modelle her uç noktada bağımlılık olarak denetlenmektedir.

Mimarinin güvenlik açısından belirleyici bileşeni, ters vekil sunucu üzerinden kurulan tek giriş noktasıdır. Uygulama arayüzü, panel ve video akışı aynı köken üzerinden sunulmakta; vekil sunucu her video isteğini medya sunucusuna iletmeden önce uygulama arayüzüne yönlendirerek yetki sorgusu yapmaktadır (Şekil 3). Bu tasarımın hangi açıktan doğduğu ve sonradan hangi eksiği ortaya çıkardığı Bölüm III.D'de ele alınmaktadır.

**[ŞEKİL 3]**
*Şekil 3. Tek giriş noktası ve video akışının kimlik doğrulaması.*

---

## III. BULGULAR VE TARTIŞMA

### A. Başarım

Sistemin yirmi kamerayla kararlı durumda ölçülen değerleri Tablo 4'te, başarı ölçütleriyle karşılaştırmalı olarak verilmiştir.

*Tablo 4. Başarı ölçütleri ve ölçülen değerler.*

| Ölçüt | Hedef | Ölçülen | Durum |
|---|---|---|---|
| Eşzamanlı kamera | ≥ 20 | 20 / 20 | Sağlandı |
| Analiz kare hızı (kamera başına) | ≥ 4 kare/sn | 2,34 | Sağlanmadı, nedeni ölçüldü |
| Uçtan uca gecikme | ≤ 1500 ms | p50 378 ms, p95 652 ms | Sağlandı |
| İki saat kesintisiz çalışma | Kesinti yok | 120 dk, 0 kesinti | Sağlandı, eski sürüm |
| Şiddet tespiti F1 | ≥ 0,85 | 0,937 (yanlılık düzeltilmiş 0,917) | Sağlandı |
| Anomali tespiti AUC | ≥ 0,75 | 0,869 (küme GA 0,806 ile 0,929) | Sağlandı |
| Alarm kesinliği | Yanlış alarm ≤ 3/kamera-saat | Kesinlik 0,895 (GA 0,686 ile 0,971) | Ölçüt yeniden tanımlandı |
| Erken uyarı avansı | ≥ 2 sn | −1,10 sn | Sağlanmadı, ölçüt tavanı hedefin altında |
| Güvenlik öncelikli liste | %100 | 18 / 19 | Kısmen |
| Arayüz akıcılığı | ≥ 30 kare/sn | Medyan 30,00 | Ölçüt ayırt edici değil |

İki ölçüt hedefin altında kalmıştır ve her ikisinin de nedeni ölçülmüştür. Bir ölçüt (alarm kesinliği) yeniden tanımlanmış, bir diğeri (arayüz akıcılığı) ölçülebilir bulunmamıştır. Bu dört durumun gerekçeleri aşağıdaki alt bölümlerde sunulmaktadır.

#### A.1. Darboğaz donanımda değil mimaridedir

Analiz kare hızının hedefin altında kalması ilk bakışta donanım yetersizliğine işaret etmektedir. Kaynak kullanımının ölçülmesi bu açıklamayı desteklememektedir (Tablo 5).

*Tablo 5. Kararlı durumda kaynak kullanımı (yirmi kamera, panel kapalı).*

| Bileşen | Bellek (MB) | İşlemci (çekirdek) | İş parçacığı |
|---|---|---|---|
| Alım | 1295,0 | 2,42 | 356 |
| Çıkarım | 1077,2 | 0,89 | 7 |
| Analitik | 133,5 | 0,93 | 2 |
| Alarm | 57,9 | 0,00 | 2 |
| Uygulama arayüzü | 74,1 | 0,02 | 3 |
| **Toplam** | **2633,9** | **4,27** | |

Grafik işlemci kullanımı altmış örneklik bir pencerede medyan %28,5 (ortalama %26,7, aralık %0 ile %85), video belleği kullanımı ise 571 MB (toplam 8192 MB'ın %7'si) ölçülmüştür. Yani sistem hedefin altında kalırken yirmi mantıksal çekirdeğin yaklaşık on beşi, grafik işlemcisinin yaklaşık yüzde yetmişi ve video belleğinin yüzde doksan üçü kullanılmamaktadır.

Sınırlayıcı unsur, çıkarım sürecinin ana döngüsünün seri olmasıdır. Döngü bir yığını baştan sona işlemekte ve bu sırada tek bir çekirdek kullanmaktadır. Ölçülen değer 0,89 çekirdektir ve yük ne olursa olsun bu değerin üzerine çıkmamaktadır. Bekleme süresi ayrıca ölçülmüş ve kare başına 1,69 ms bulunmuştur; yani süreç boşta beklememekte, zamanının yaklaşık yüzde doksan üçünde iş yapmaktadır.

#### A.2. Arz ile talep arasındaki açık

Alım süreci saniyede 56,8 kare yayınlamakta, çıkarım süreci 46,8 kare işleyebilmektedir. Ölçüm penceresinde yayınlanan 11501 karenin 2017'si (%17,5) analiz edilmeden kuyrukta kalmıştır. Bu açık, kare muhasebesi eklenene kadar görünür değildi. Düşürülen kare sayacı yalnızca paylaşımlı bellek yuvası bulunamadığı durumları saymakta, kuyruk tavanında elenen kareleri saymamaktaydı.

#### A.3. Girdiyi artırmak çıktıyı düşürmüştür

Doyum noktasının nerede olduğu gözlemsel veriyle belirlenememektedir. Bunun nedeni, sistem tüketiciden yavaş beslendiğinde ölçülen verimin tüketicinin kapasitesini değil üreticinin hızını yansıtmasıdır. Bu ayrımı görebilmek için müdahaleli bir deney yapılmış, kamera başına hedef örnekleme hızı 4 kare/saniyeden 8 kare/saniyeye çıkarılmış ve ölçüm tekrarlanmıştır (Tablo 6).

*Tablo 6. Örnekleme hızının iki katına çıkarılmasının etkisi.*

| Ölçüt | 4 kare/sn | 8 kare/sn | Değişim |
|---|---|---|---|
| Yayınlanan (kamera başına) | 2,78 | 4,37 | Arttı |
| **Analiz edilen (kamera başına)** | **2,78** | **1,88** | **%32 düştü** |
| Gecikme p50 (ms) | 173 | 433 | 2,5 kat arttı |
| İzlenmeyen kare kaybı | Yaklaşık %0 | %56,9 | |
| Tüketici gecikmesi (kayıt) | 0 | 40 | Gerçek birikme |
| Alım işlemci kullanımı (çekirdek) | 2,10 | 3,79 | Arttı |
| Çıkarım işlemci kullanımı (çekirdek) | 0,89 | 0,89 | **Değişmedi** |

Sonuç sezgiye aykırıdır: daha çok kare göndermek daha çok analiz üretmemiş, tersine analiz edilen kare sayısını düşürmüştür. Mekanizma ölçümde görünmektedir. Alım sürecinin işlemci kullanımı 2,10 çekirdekten 3,79 çekirdeğe çıkmış, çıkarım sürecinin kullanımı ise sabit kalmıştır. Artan alım yükü, aynı işlemcileri paylaşan çıkarım sürecinden zaman çalmaktadır. Ayrıca kuyruk dolduğu için kareler analiz edilmeden elenmekte, hayatta kalan kareler daha uzun beklediğinden gecikme artmaktadır.

Bu deney, giriş bölümünde öne sürülen savın sistem düzeyindeki karşılığıdır. Bileşen düzeyindeki hiçbir ölçüm, girdiyi artırmanın çıktıyı düşüreceğini öngöremez, çünkü bu davranış bileşenlerin kendisinden değil kaynak paylaşımından doğmaktadır.

#### A.4. Çıkarım döngüsünün aşama kırılımı ve kapanış kontrolü

Darboğazın hangi aşamada olduğunu belirlemek için çıkarım döngüsünün her aşaması ayrı ayrı ölçülmüştür. Ölçümde iki kural uygulanmıştır. Birincisi, tüm aşamaların aynı birimde (kare başına milisaniye) ve aynı zaman penceresinde okunmasıdır. İkincisi, aşamaların toplamının bağımsız olarak ölçülen döngü toplamıyla karşılaştırılmasıdır. Sonuçlar Tablo 7'dedir.

*Tablo 7. Çıkarım döngüsünün aşama kırılımı (120 sn, 863 yığın, 6,5 kare/yığın).*

| Aşama | ms/kare | Pay |
|---|---|---|
| Poz kestirimi | 10,96 | %48 |
| Nesne tespiti | 7,46 | %33 |
| Takip | 1,56 | %7 |
| Yayınlama | 1,24 | %5 |
| Serileştirme | 0,56 | %2 |
| Yüz ve ifade | 0,46 | %2 |
| Yuva iadesi | 0,37 | %2 |
| Paylaşımlı bellek okuma | 0,00 | %0 |
| **Ölçülen aşamaların toplamı** | **22,62** | |
| **Bağımsız ölçülen döngü toplamı** | **22,65** | |
| **Açıklanamayan** | **0,04** | **%0** |

Son üç satır, bu tablonun asıl değerini oluşturmaktadır. Bileşenlerin toplamı, bağımsız olarak ölçülen döngü toplamına 0,04 ms farkla eşittir; yani döngünün tamamı açıklanmıştır. Bu denetim önceki bir ölçümde yapılmamış ve sonuç olarak döngü maliyetinin yüzde yetmişinin "ölçülmeyen ek yük" olduğu yönünde yanlış bir bulgu üretilmişti. Gerçekte ölçüm aracı aynı metrik altında iki farklı birim toplamaktaydı: bazı aşamalar kare başına, bazıları yığın başına yazıyordu. Kapanış kontrolü eklendiğinde hata ilk koşuda görülmüştür.

Tablo, aynı zamanda Bölüm I'de sunulan gözlemin kaynağıdır. Nesne tespiti burada kare başına 7,46 ms harcamaktadır; aynı model izole koşulda ve tam dolu yığınla 3,78 ms harcamaktadır (Tablo 8).

Aynı kırılım, bir gün arayla ve farklı bir ölçüm betiğiyle tekrarlanmıştır. İkinci ölçümde aşama toplamı 23,22 ms, döngü toplamı 23,26 ms ve açık yine 0,04 ms bulunmuştur. Bu tekrar, tablonun tek bir koşunun rastlantısı olmadığını göstermektedir.

#### A.5. Çıkarım motoru hızlandırma denemesi

Tablo 7, hızlandırılabilir grafik işlemci işinin döngü bütçesinin yüzde seksen birini oluşturduğunu göstermektedir (poz %48, tespit %33). Bu nedenle TensorRT ile hızlandırma ölçülmüştür (Tablo 8).

*Tablo 8. PyTorch ile TensorRT karşılaştırması (izole ölçüm).*

| | Yığın (ms) | Kare (ms) | p90 (ms) |
|---|---|---|---|
| PyTorch FP16 | 30,233 | 3,779 | 31,324 |
| TensorRT FP16 | 18,741 | 2,343 | 20,310 |
| Hızlanma | 1,61 kat | | |

Hızlanmanın doğruluğu bozmadan elde edildiği ayrıca denetlenmiştir. Her iki motor da aynı görüntüde yirmi tespit üretmiş, eşleşme tam olmuş, ortalama kesişim oranı 0,9915 bulunmuştur. Bu denetim zorunludur, çünkü hızlanma sonucu bozarak da elde edilebilir.

Buna karşılık motor üretime alınamamıştır. Kullanılan tespit mimarisinin dikkat blokları dinamik girdi şekilleriyle TensorRT çekirdeği bulamadığından motor sabit yığın boyutuyla ihraç edilmek zorunda kalmış, bu da yalnızca tam sekiz karelik yığınların kabul edilmesi anlamına gelmiştir. Üretimde ölçülen yığın medyanı 6,67 karedir ve kısmi yığınlar hata üretmektedir. Eksik yerleri kare tekrarıyla doldurmak mümkündür; bu durumda etkin kazanç 1,61 kattan yaklaşık 1,34 kata, verim kazancı ise yaklaşık yüzde dokuza inmektedir. Dolgu yapılan karelerin sonuçlarının ayıklanması gerekmekte, yanlış yapıldığında sistem var olmayan tespitler üretmektedir. Kalan süre içinde yüzde dokuz verim için bu risk alınmamış ve karar gerekçesiyle kaydedilmiştir.

#### A.6. Çıkarım sürecinin paralelleştirilmesi denenmiştir

Bölüm III.A.1'deki bulgu doğrudan bir çözüm önermektedir: çıkarım süreci tek çekirdekte doyuyorsa, kameralar birden çok çıkarım süreci arasında paylaştırılabilir. Bu seçenek uygulanmış ve ölçülmüştür.

Seçeneğin uzun süre değerlendirilmemesinin nedeni, proje başında konulmuş bir tasarım kuralıdır: modellerin tek süreçte tek kopya tutulması, aksi hâlde video belleğinin yetmeyeceği varsayılmıştır. Bu varsayım hiç ölçülmemişti. Ölçüldüğünde tek sürecin 571 MB, iki sürecin toplam 1134 MB kullandığı görülmüştür; yani başlangıçtaki tahmin gerçek değerin yaklaşık sekiz katıdır. Ölçülmemiş bir sayıya dayanan bir kural, bir mimari seçeneği uzun süre kapalı tutmuştur.

**İlk uygulama karelerin yarısını yok etmiştir.** En basit yol denenmiş, tüm süreçler aynı mesaj akışını okumuş ve her süreç kendisine atanmamış kameraya ait kareleri atmıştır. Ölçümde doksan saniyelik pencerede yayınlanan 5236 karenin yalnızca 2626'sının analiz edildiği görülmüştür. Nedeni, kullanılan akış yapısında her mesajın tüketici grubundaki yalnızca **bir** tüketiciye verilmesidir; kendisine ait olmayan kareyi atan süreç, o kareyi diğerine aktarmamakta, imha etmektedir.

Bu hatanın önemli yanı, ölçütlerin iyileşmiş görünmesidir:

*Tablo 9. Hatalı bölüştürme uygulamasının etkisi.*

| Ölçüt | Tek süreç | Hatalı bölüştürme |
|---|---|---|
| Verim (kare/sn) | 46,3 | 28,0 |
| Gecikme p50 (ms) | 172 | 104 |
| Gecikme p95 (ms) | 322 | 238 |

İşin yarısı atıldığında kuyruk boşalmakta ve gecikme düşmektedir. Yalnızca gecikmeye bakan bir değerlendirme bunu başarı olarak yorumlayacaktır. Hatanın görülebilmesi, yayınlanan ve analiz edilen kare sayılarının ayrı ayrı sayılması sayesinde mümkün olmuştur. Bir ölçütün iyileşmesi sistemin iyileştiği anlamına gelmemektedir.

**Doğru tasarımda yönlendirme üretici tarafına alınmıştır.** Alım katmanı her kamerayı, kamera adının sağlamasından türetilen bir alt akışa yazmakta, her çıkarım süreci yalnızca kendi alt akışını okumaktadır. Böylece her kare tam olarak bir akışta ve bir süreçte işlenmektedir. Sağlama işlevi olarak süreçler arasında değişmeyen bir sağlama fonksiyonu seçilmiştir; dilin yerleşik karma işlevi süreçler arasında rastgeleleştirildiğinden, alım ve çıkarım süreçleri farklı sonuç üretecek ve kameralar sessizce kaybolacaktı. Ayrıca aynı kameranın her zaman aynı sürece gitmesi zorunludur, çünkü takip durumu süreç içinde kamera bazında tutulmaktadır.

**Düzeltilmiş uygulamanın ölçümü** Tablo 10'de verilmiştir.

*Tablo 10. Bölüştürmenin ölçülen etkisi (tek süreç ile iki süreç).*

| Ölçüt | Tek süreç | İki süreç | Değişim |
|---|---|---|---|
| Verim (kare/sn) | 45,1 | 53,7 | %19 artış |
| Gecikme p50 (ms) | 359 | 183 | %49 azalma |
| Gecikme p95 (ms) | 638 | 411 | %36 azalma |
| Çıkarım işlemci (çekirdek) | 0,90 | 1,77 | İki katı |
| Video belleği (MB) | 571 | 1134 | İki katı |
| **Sistem belleği kullanımı** | **%84** | **%98** | |

Her iki çıkarım sürecinin de 0,89 çekirdekte doyması, Bölüm III.A.1'deki tek çekirdek tavanı gözlemini süreç başına doğrulamaktadır. Kazancın verimde iki kat olmaması beklenen bir sonuçtur: bölüştürme çıkarım tarafındaki sınırı kaldırmış, kısıt alım katmanına ve paylaşımlı bellek havuzuna geçmiştir.

**Buna karşılık seçenek üretimde etkinleştirilmemiştir.** Gerekçe sistem belleğidir: iki süreçle kullanım %98 düzeyine çıkmaktadır ve on altı gigabaytlık bir makinede bu sınır, uzun süreli çalışmada güvenli değildir. Ayrıca paylaşımlı bellek havuzu büyütüldükten sonra tek süreçli yapılandırmanın verimi, iki süreçli yapılandırmayı yakalamıştır; yani bölüştürmenin çözmeye çalıştığı darboğazın bir bölümü daha ucuz bir düzeltmeyle ortadan kalkmıştır.

**Bu alt bölümdeki ölçümlerin bilinen sınırı.** Bölüştürme karşılaştırmasının ve havuz boyutu karşılaştırmasının çıktı dosyaları saklanmamış, değerler yalnızca geliştirme günlüğüne yazılmıştır. Sonraki günlerde aynı yapılandırmayla yapılan ölçümler bu değerleri birebir tekrar üretmemiştir. Değerler, yönü ve büyüklük mertebesi bakımından raporlanmakta; makalenin diğer bölümlerinde kullanılan sayılar ise çıktısı saklanmış ölçümlerden alınmaktadır. Bu ayrım Bölüm III.E'de ele alınan kayıt tutma sorununun bu çalışmadaki somut örneğidir.

#### A.7. Paylaşımlı bellek havuzunun boyutu bir kuyruk kararıdır

Paylaşımlı bellek havuzu doksan altı yuvadan oluşmakta ve 265 MB yer kaplamaktadır. Sistem belleğinin 16 GB olduğu düşünüldüğünde bu değer düşük görünmektedir. Havuzun işlevi depolama değil tamponlamadır: yuvalar yalnızca alım ile çıkarım arasında yolda olan kareleri tutmaktadır. Çıkarım süreci yetişebildiği sürece aynı anda kullanılan yuva sayısı azdır.

Havuzun büyütülmesi belirli bir noktadan sonra fayda sağlamamaktadır. Tüketici doymuş durumdaysa daha büyük bir tampon verimi artırmak yerine yalnızca kuyrukta bekleyen karelerin daha eski olmasına, dolayısıyla gecikmenin artmasına yol açmaktadır. Bu davranış kuyruk kuramında bilinen bir sonuçtur ve sistemde de gözlenmiştir (Bölüm III.A.3).

Geliştirme sırasında havuz boyutu kırk sekiz yuvadan doksan altı yuvaya çıkarıldığında belirgin bir iyileşme gözlenmiştir. Bunun nedeni kırk sekiz değerinin fazla küçük olması ve üreticinin yuva bulamadığı için kare düşürmesidir. Ancak burada bir dürüstlük notu gereklidir: söz konusu karşılaştırmaya ait ölçüm çıktısı dosyaya kaydedilmemiş, yalnızca geliştirme günlüğüne yazılmıştır. Ertesi gün aynı yapılandırmayla yapılan ölçümler o değerleri tekrar üretmemiştir. Bu nedenle bu makalede tekrar üretilebilen ve çıktısı saklanan ölçümler esas alınmış, tekrar üretilemeyen değerler kullanılmamıştır.

### B. Doğruluk

#### B.1. Şiddet tespiti ve iki modelin birleşimi

Şiddet tespiti için üç yaklaşım sırayla geliştirilmiş ve değerlendirilmiştir.

**Birincisi kural tabanlı yaklaşımdır.** Poz kestiriminden elde edilen eklem konumlarından bilek hızı, gövde eğimi, hareket enerjisi ve kişiler arası yakınlık gibi büyüklükler türetilmiş, bunlar elle belirlenen ağırlıklarla birleştirilmiştir. Bu yaklaşım doksan kavga ve doksan normal klipten oluşan yüz yirmi klipli bir alt kümede değerlendirilmiş ve 0,62 ile 0,66 arasında eğri altı alan, 0,71 civarında F1 skoru vermiştir. Elde edilen değer, sonraki modellerin aşması gereken taban olarak kullanılmıştır.

Kural tabanlı yaklaşımın neden sınırlı kaldığı ayrıca incelenmiştir. Ağırlıklar, şiddetin hızlı ve ani hareket içerdiği varsayımına dayanmaktadır. Ölçüm bu varsayımı desteklememektedir: veri setindeki gerçek şiddet olaylarının önemli bir bölümü boğuşma biçimindedir ve boğuşma sırasında ölçülen hareket hızı, kalabalık içinde normal yürüyüşten daha düşük çıkabilmektedir. Elle yazılan ağırlıklar, ölçülmemiş bir sezgiyi kodlamaktadır.

**İkincisi, aynı iskelet özniteliklerini elle belirlenen ağırlıklar yerine bir gradyan artırma modeline (Ke vd., 2017) veren yaklaşımdır.** Öznitelikler aynıdır; değişen yalnızca bunların nasıl birleştirildiğidir.

**Üçüncüsü, kısa video kesitlerini doğrudan ham piksel olarak işleyen üç boyutlu bir evrişimli ağdır (Tran vd., 2018).** Bu yaklaşım iskelet çıkarımına hiç bağlı değildir ve dolayısıyla poz kestiriminin başarısız olduğu durumlarda da çalışabilmektedir.

İkinci ve üçüncü yaklaşımın sonuçları ile bunların birleşimleri Tablo 11'de verilmiştir.

Tablo 11'de kural tabanlı yaklaşım yer almamaktadır. Bunun nedeni, söz konusu yaklaşımın farklı bir alt küme (yüz yirmi klip) üzerinde değerlendirilmiş olmasıdır. Farklı değerlendirme kümelerinde elde edilmiş değerleri aynı tabloda karşılaştırmak, bu çalışmanın Bölüm II.C'de eleştirdiği hata türlerinden biridir; bu nedenle kural tabanlı sonuç metin içinde ve kendi küme büyüklüğüyle birlikte verilmiştir.

*Tablo 11. Şiddet tespiti sonuçları (RWF-2000 doğrulama, 96 klip).*

| Model | AUC | AUC %95 GA | F1 | Kesinlik | Duyarlılık |
|---|---|---|---|---|---|
| İskelet ve gradyan artırma | 0,9267 | 0,8676 ile 0,9722 | 0,8889 | 0,9565 | 0,8302 |
| Ham piksel (3B evrişim) | 0,9366 | 0,8820 ile 0,9796 | 0,9107 | 0,8644 | 0,9623 |
| **Birleşim (ortalama)** | **0,9684** | **0,9352 ile 0,9917** | **0,9369** | 0,8966 | 0,9811 |
| Birleşim (azami) | 0,9636 | 0,9257 ile 0,9909 | 0,9358 | 0,9107 | 0,9623 |
| Birleşim (asgari) | 0,9381 | 0,8868 ile 0,9770 | 0,8889 | 0,8727 | 0,9057 |
| Birleşim (çarpım) | 0,9561 | 0,9168 ile 0,9850 | 0,9009 | 0,8621 | 0,9434 |

Birleşim, en iyi tek modelden 0,032 AUC puanı daha yüksek sonuç vermektedir. Bu farkın raporlanabilmesi için üç ek denetim yapılmıştır.

**Eşik seçim yanlılığı.** F1 değerleri, en iyi eşiğin aynı küme üzerinde aranmasıyla elde edilmektedir ve bu nedenle iyimserdir. Dört yüz tekrarlı katmanlı yarı bölme ile ölçülen iyimserlik, birleşim için 0,0204 puandır; yani 0,9369 yerine 0,9165. Diğer modellerin iyimserliği 0,018 ile 0,033 arasındadır. Makalede her iki değer de verilmektedir.

**Kazananın laneti.** Dört farklı birleştirme kuralı arasından en iyisinin aynı veri üzerinde seçilmesi, seçilen kuralın başarımını iyimser göstermektedir. Bu iyimserlik önyükleme ile 0,0014 AUC puanı olarak kestirilmiştir. Ayrıca ortalama alma kuralı ölçüm yapılmadan önce belirlenmiş olduğundan bu etki asgari düzeydedir.

**Kazancın mekanizması.** Birleşimin daha iyi sonuç vermesi tek başına bir açıklama değildir; iki modelin neden birbirini tamamladığının gösterilmesi gerekmektedir. Hata kümeleri karşılaştırılmıştır. Yalnızca iskelet tabanlı modelin yanıldığı on klip, yalnızca ham piksel modelinin yanıldığı dokuz klip, her ikisinin birden yanıldığı ise yalnızca bir klip bulunmaktadır. Örtüşme oranı yüzde ondur. Modeller aynı kliplerde değil farklı kliplerde hata yapmakta ve birleşimin kazancı buradan gelmektedir. Bu ölçüm, birleşimi bir gözlem olmaktan çıkarıp bir mekanizmaya bağlamaktadır.

**Hesaplama maliyeti.** Ham piksel modelinin bir pencere için maliyeti 6,44 ms'dir. Yirmi kamera için saniyede yaklaşık 354 ms karşılık gelmekte, bu da gerçek zamanlı bütçeye sığmaktadır.

#### B.2. Anomali tespiti ve füzyonun sınanması

Anomali tespiti beş sinyalin ağırlıklı birleşimine dayanmaktadır. Bu birleşime bu çalışmada füzyon adı verilmektedir ve şu şekilde çalışmaktadır. Takip edilen her kişi için saldırganlık (ağırlık 0,40), öğrenilmiş kamera profilinden sapma (0,25), fiziksel kural ihlali (0,20), yüz ifadesi (0,10) ve kalabalık yoğunluğu (0,05) sinyalleri sıfır ile bir arasında üretilmekte, ağırlıklı toplamları alınmakta, sonuç üstel hareketli ortalama ile zamansal olarak yumuşatılmakta ve histerezis uygulanarak tek bir risk skoruna dönüştürülmektedir. Zamansal yumuşatma, ardışık pencerelerde hesaplanan skorların doğrudan kullanılması yerine önceki değerle harmanlanmasıdır; amaç tek bir gürültülü pencerenin alarma yol açmasını engellemektir.

Füzyonun katkısının ölçülebilmesi için bir kontrol serisi tanımlanmıştır: tek bir sinyale, füzyonla aynı zamansal yumuşatma uygulanmaktadır. Böylece iki değişken ayrıştırılmaktadır; birleştirme ile yumuşatma. Sonuçlar Tablo 12'dedir.

*Tablo 12. Anomali tespiti sonuçları (CUHK Avenue, 9 klip ve 1439 kare).*

| Sinyal | AUC | Kare düzeyi GA | Klip düzeyi GA |
|---|---|---|---|
| **Füzyon (5 sinyal ve yumuşatma)** | **0,8691** | 0,8257 ile 0,9060 | **0,8057 ile 0,9286** |
| Profil sapması, ham | 0,7891 | 0,7476 ile 0,8250 | 0,7494 ile 0,8275 |
| **Profil sapması ve yumuşatma (kontrol)** | **0,8602** | 0,8128 ile 0,9019 | 0,8142 ile 0,9004 |
| Fiziksel kurallar | 0,500 | | 0,499 ile 0,500 |
| Saldırganlık | 0,457 | | 0,444 ile 0,486 |

Füzyon ile kontrol serisi arasındaki fark 0,0089 puandır. Anlamlılık eşiği ölçüm yapılmadan önce 0,02 olarak belirlenmiştir; gerekçesi, dokuz klip ve altmış dokuz anomali karesi üzerinde AUC belirsizliğinin bu mertebede olmasıdır. Fark bu eşiğin altındadır.

Bu durumda dürüst çıkarım şudur: bu veri setinde kazancı sağlayan sinyal birleştirme değil zamansal yumuşatmadır. Ham profil sapmasından yumuşatılmış profil sapmasına geçiş 0,071 puan kazandırmakta, beş sinyalin birleştirilmesi ise 0,009 puan eklemektedir.

Bu sonuç füzyonun gereksiz olduğu anlamına gelmemektedir; sonucun geçerli olduğu koşulun belirtilmesi gerekmektedir. Kullanılan veri setinde beş sinyalden ikisi işlevsizdir. Fiziksel kural sinyalinin AUC değeri tam olarak 0,500'dür, yani hiç ateşlememektedir. Bunun nedeni söz konusu veri setindeki anomalilerin çanta fırlatma, bisiklet ve ters yönde yürüme gibi olaylar olması, buna karşılık bu çalışmadaki kuralların insan hareketi üzerine tanımlanmış olmasıdır. Saldırganlık sinyalinin değeri ise 0,457 ile şans düzeyinin altındadır. İşlevsiz sinyalleri birleştirmenin bir kazanç üretmesi beklenemez. Füzyonun ölçülen asıl katkısı ayırt etme gücünde değil gürültü bastırmadadır ve bu katkı alarm oranı ölçümünde gözlenmiştir.

#### B.3. Alarm kesinliği

Sistemin ürettiği alarmların ne kadarının haklı olduğu, kaynak videolardan çıkarılan kesitlerin elle değerlendirilmesiyle ölçülmüştür. Kırk alarmın otuz dokuzu etiketlenmiş, biri için karar verilememiş ve analiz dışı bırakılmıştır.

Ham sayı doğrudan raporlanamamaktadır, çünkü kaynak videolar döngüde yayınlanmakta ve aynı olay defalarca alarm üretmektedir. Alarmlar kaynak video içindeki konuma göre tekilleştirilmiştir; birbirine altı saniyeden yakın olan, aynı kameraya ve aynı türe ait alarmlar tek olay sayılmıştır. Sonuçlar Tablo 13'dedir.

*Tablo 13. Alarm kesinliği (Wilson %95 güven aralığı; Wilson, 1927).*

| | n | Doğru | Kesinlik | %95 GA |
|---|---|---|---|---|
| Ham etiketli alarm | 39 | 37 | 0,949 | 0,831 ile 0,986 |
| **Bağımsız olay** | **19** | **17** | **0,895** | **0,686 ile 0,971** |
| Kalabalık | 9 | 9 | 1,00 | 0,70 ile 1,00 |
| Birleşik risk | 5 | 5 | 1,00 | 0,57 ile 1,00 |
| **Düşme** | **5** | **3** | **0,60** | **0,23 ile 0,88** |

Toplu kesinlik değeri 0,895'tir, ancak tür bazında bakıldığında dağılımın düzgün olmadığı görülmektedir. Kalabalık ve birleşik risk türlerinde hata bulunmamaktadır. İki yanlış alarmın ikisi de düşme türündedir ve ikisi de aynı mekanizmadan kaynaklanmaktadır: eğilerek yere uzanan bir kişi düşme olarak sınıflandırılmaktadır. Düşme kuralında gövde eğim değişim hızı için tanımlanmış olan koruma bu hareketi elemeye yetmemektedir.

Bu ayrıştırma, toplu bir sayının bir bulguyu gizleyebileceğini göstermektedir. Yalnızca 0,895 değeri raporlansaydı, sistemin zayıf halkasının belirli bir kural olduğu görülmeyecekti.

Oyalanma türü için ölçüm yapılamamıştır. Bu kural kırk beş saniyelik bir gözlem penceresine dayanmakta, değerlendirme kesitleri ise altı saniyeliktir. Altı saniyelik bir kesit kırk beş saniyelik bir kuralı doğrulayamaz. Bu tür, sıfır örnek olarak raporlanmakta, hatasız olarak raporlanmamaktadır.

Bu yöntem yalnızca kesinlik ölçmektedir, yani sistemin ürettiği alarmların ne kadarının doğru olduğunu. Duyarlılık ölçülmemiştir; sistemin kaçırdığı olayların belirlenmesi için kaynak videoların tamamının etiketlenmesi gerekirdi. Bu sınır sonuçların yorumlanmasında dikkate alınmalıdır.

#### B.4. İfade kademesinin fiili kapsamı

Yüz ifadesi sınıflandırması iki basamaklı bir kapıyla seyreltilmektedir. Birinci basamak, kişi kutusunun yüksekliğinin yüz seksen pikselin üzerinde olmasını aramakta, ikinci basamak yüz tespitinin başarılı olmasını gerektirmektedir. Yirmi bir kamera ve kamera başına yirmi beş kare üzerinde yapılan ölçümde, 2087 kişi tespitinden 171'i (%8,2) birinci basamağı geçmiştir. İkinci basamakta, birinci basamağı geçen sekiz kameranın yedisinde hiç yüz tespit edilememiş, yalnızca yakın plan yüz içeren kamerada yüz bulunabilmiştir.

Bu sonucun iki anlamı vardır. Birincisi, ifade kademesinin hesaplama maliyetinin düşük olması (kare başına 0,46 ms, döngünün yüzde ikisi) bir verimlilik başarısı değil, kapının neredeyse her şeyi elemesinin sonucudur. İkincisi ve daha önemlisi, ifade sinyali pratikte tek bir kamerada üretilmektedir. Füzyon eksik sinyali sıfır değeriyle değerlendirdiğinden, bu durum ifade ağırlığının diğer kameralarda fiilen devre dışı kalması anlamına gelmektedir. Bu sonuç, kullanılan kamera çiftliği ve kapı eşikleri için geçerlidir. Ölçüm, ifade kademesinin genel olarak işlevsiz olduğunu değil, bu kurulumdaki görüntü çözünürlüğünün kapıyı geçecek büyüklükte yüz üretmediğini göstermektedir. Yakın plan yüz içeren kamerada kapının tamamen geçilmesi (25 kırpıntının 25'inde yüz bulunması) bu yorumu desteklemektedir.

### C. Ölçüt ile veri arasındaki uyuşmazlık

Bu bölüm çalışmanın en özgün bulgusunu sunmaktadır. Üç başarı ölçütünde, hedefin tutturulamamasının nedeni sistemin başarımı değil ölçütün kendisidir. Üç durum farklı türdendir ve birlikte genel bir kural vermektedir.

#### C.1. Ölçütün üst sınırı hedefin altındadır

Erken uyarı ölçütü, şiddet başlamadan en az iki saniye önce uyarı üretilmesini gerektirmektedir. Ölçüm sonuçları Tablo 14'te verilmiştir.

*Tablo 14. Erken uyarı avansı (RWF-2000, 20 kavga ve 30 normal klip).*

| Eşik | Yakalanan | Kaçırılan | Geç | Medyan avans | %95 GA | Yanlış alarm |
|---|---|---|---|---|---|---|
| 0,10 | 7 | 13 | 6 | −1,10 sn | −1,87 ile −0,07 | %13 |
| 0,15 | 4 | 16 | 4 | −1,72 sn | −2,13 ile −0,60 | %7 |
| 0,20 | 2 | 18 | 2 | −3,72 sn | −4,30 ile −3,13 | %3 |
| ≥ 0,25 | 0 | 20 | 0 | Ölçülemez | | ≤ %3 |

Negatif değerler, uyarının olaydan sonra üretildiği anlamına gelmektedir. Eşik düşürüldükçe avans iyileşmekte fakat yanlış alarm artmaktadır; bu beklenen bir değiş tokuştur.

Asıl bulgu bu tablonun kendisinde değildir. Ölçütün bu veri setinde ulaşabileceği en yüksek değer hesaplanmıştır. Kliplerde şiddet başlangıcından önceki bağlam süresinin medyanı 0,58 saniye, azamisi 3,07 saniyedir. Yirmi klibin yalnızca ikisinde iki saniyelik bir avans fiziksel olarak mümkündür. Dahası, etiketleri üreten değerlendirici işaretlemenin kendi tepki süresini içerdiğini ve şiddetin fiilen sıfır ile yarım saniye arasında başladığını bildirmiştir. Yani ölçütün gerçek üst sınırı hesaplanan değerden de düşüktür.

Bu koşulda kusursuz çalışan bir dedektör bile ölçütü sağlayamaz. Elde edilen negatif değer sistemin başarısızlığını değil, ölçüt ile veri arasındaki uyuşmazlığı göstermektedir.

Bulgu, farklı özellikte ikinci bir veri setinde de sınanmıştır. Uzun süreli gözetim kayıtlarından oluşan ve olay öncesinde elli sekiz saniyelik bağlam içeren bir klipte, model kavga anını normal davranıştan ayırt edebilmektedir (medyan skor oranı 2,756). Buna karşılık kavgaya giden tırmanma penceresi normal bölümlerden daha düşük skorlanmakta (0,184 ile 0,282), tespit ise olaydan 1,76 saniye sonra gerçekleşmektedir. İki veri seti farklı yollardan aynı sonuca varmaktadır: sistem şiddeti tespit etmekte, fakat şiddet öncesi tırmanmayı ayırt etmemektedir.

#### C.2. Ölçüt eşiği ölçüm çözünürlüğünün altındadır

Arayüz akıcılığı ölçütü, yirmi kamera açıkken çizim hızının saniyede en az otuz kare olmasını gerektirmektedir. Yedi bağımsız koşunun sonuçları Tablo 15'dedir.

*Tablo 15. Arayüz akıcılığı ölçümleri (yedi koşu).*

| Ölçüt | Medyan | Aralık |
|---|---|---|
| Çizim hızı (kare/sn) | 30,00 | 29,43 ile 30,02 |
| Kontrol, kamera açık değilken | Yaklaşık 60 | 59,7 ile 60,2 |
| Video çözme (toplam kare/sn) | 225,0 | 200 ile 300 |
| Düşen kare oranı | %2,3 | %0,0 ile %33,4 |

Çizim hızı ölçümü tarayıcının dikey senkronizasyonuna bağlıdır ve altmış hertzlik bir ekranda pratikte 60, 30, 20, 15 gibi kesikli değerler almaktadır. Yük altında tarayıcı altmıştan otuza inmekte ve orada kilitlenmektedir. Kontrol serisinin her koşuda altmış civarında ölçülmesi bu yorumu desteklemektedir.

Ölçütün eşiği tam olarak otuzdur, yani sistemin oturduğu kesikli basamağın üzerindedir. Ölçülen değerin 29,43 mü yoksa 30,02 mi çıkacağını sistemin başarımı değil, sayım penceresinin kenar etkileri belirlemektedir. Bu koşulda sağlandı veya sağlanmadı kararı ölçüm gürültüsüyle değişmekte ve ölçüt ayırt edici olmamaktadır.

Daha bilgilendirici olan büyüklük düşen kare oranıdır ve bu değer koşular arasında yüzde sıfır ile yüzde otuz üç arasında değişmektedir. Bu değişkenlik makinedeki eşzamanlı yüke bağlıdır. Erken bir ölçümde söz konusu oran sıfır bulunmuş ve beklenenden iyi bir sonuç olarak yorumlanmıştı; yedi koşuluk dağılım bu yorumu geçersiz kılmaktadır. Tek gözleme dayanan bir sonucun, özellikle beklenenden iyi çıktığında, tekrarlanmadan kabul edilmemesi gerekmektedir.

#### C.3. Gözlem birimi bağımsızlık varsayımını karşılamamaktadır

Yanlış alarm ölçütü, kamera başına saatte en fazla üç yanlış alarm öngörmektedir. Bu ölçüt, kaynak videoların döngüde yayınlandığı bir kurulumda sistemin davranışını ölçmemektedir.

Kaynak videoların süreleri beş saniye ile üç yüz kırk beş saniye arasında değişmektedir. En kısa kaynakta bulunan tek bir düşme olayı saatte yaklaşık yedi yüz yirmi kez yeniden oynamakta ve her turda alarm üretmektedir. Aynı sistem, aynı algoritma ve aynı olay, beş saniyelik bir kaynakta saatte yedi yüz yirmi, üç yüz saniyelik bir kaynakta ise on iki alarm üretmektedir. Dolayısıyla ham oran, sistemin yanlış alarm davranışını değil test videolarının uzunluk dağılımını yansıtmaktadır.

Bu nedenle ölçüt, saatlik oran yerine bağımsız olay başına kesinlik olarak yeniden tanımlanmıştır. Otuz dokuz etiketli alarm, döngü içindeki konuma göre tekilleştirildiğinde on dokuz bağımsız olaya karşılık gelmektedir.

Aynı sorun değerlendirme veri setlerinde de bulunmaktadır. Anomali tespiti 1439 kare üzerinden ölçülmektedir, ancak bu kareler yalnızca dokuz klipten gelmektedir ve aynı klibin ardışık kareleri bağımsız gözlem değildir. Kare düzeyinde hesaplanan güven aralığı 0,080 genişliğinde, klip düzeyinde hesaplanan aralık ise 0,123 genişliğindedir. Naif yöntem, sahip olunmayan bir kesinlik iddia etmektedir.

*Tablo 16. Ölçüt ile veri arasındaki üç uyuşmazlık türü.*

| Tür | Belirtisi | Bu çalışmadaki örnek | Sonuç |
|---|---|---|---|
| Ölçütün üst sınırı hedefin altında | Kusursuz sistem bile geçemez | Erken uyarı: tavan 0,58 sn, hedef 2 sn | Ölçüt bu veri setinde ölçülemez |
| Eşik, ölçüm çözünürlüğünün altında | Karar gürültüyle değişir | Arayüz akıcılığı: eşik 30, basamak 30 | Ölçüt ayırt edici değil |
| Gözlem birimi bağımlı | Aralık olduğundan dar, oran şişkin | Alarm oranı ve kare düzeyli AUC | Birim yeniden tanımlanmalı |

Bu üç durum birlikte pratik bir kural vermektedir. Bir ölçüt raporlanmadan önce üç soru sorulmalıdır: Bu ölçütün kullanılan veriyle ulaşabileceği en yüksek değer nedir? Ölçüt eşiği, ölçüm aracının çözünürlüğünün üzerinde midir? Gözlem birimi gerçekten bağımsız mıdır?

### D. Güvenlik bulguları

#### D.1. Korunan yüzey ile korunması gereken yüzeyin ayrışması

Geliştirme sırasında tespit edilen ilk bulgu, uygulama programlama arayüzünün kimlik doğrulamasıyla korunmasına karşın video akışının korunmamış olmasıdır. Görüntüye erişmek için yalnızca adresin bilinmesi yeterliydi. İlk çözüm bir ağ kısıtı olmuş, ilgili port yerel arayüze bağlanmıştır. Bu, açığı kapatmak değil erişimi aynı makineyle sınırlamaktır; makinede çalışan herhangi bir süreç görüntüyü almaya devam edebilmektedir. Kalıcı çözüm, video akışının uygulama ile aynı köken üzerinden sunulması ve vekil sunucunun her video isteği için uygulama arayüzüne yetki sorgusu yapmasıdır.

#### D.2. Tek giriş noktası kurmak yeterli değildir, geçenlerin sayılması gerekir

İkinci bulgu, tek giriş noktası kurulduktan sonra ortaya çıkmıştır. Vekil sunucu yapılandırmasındaki genel yönlendirme kuralı, uygulamanın kimlik doğrulaması bulunmayan uç noktalarını da dışarıya açmaktadır. Yapılan denetimde, gözlemlenebilirlik arayüzünün kimlik doğrulaması olmaksızın ve tek giriş noktası üzerinden erişilebilir olduğu tespit edilmiştir. Bu arayüz kamera adlarını, kamera başına alarm sayılarını, kare hızlarını, gecikme dağılımlarını ve uç nokta envanterini içermektedir. Bir gözetim sisteminde bu bilgiler, sisteme erişim sağlanmadan önce keşif amacıyla kullanılabilecek niteliktedir.

Bulgunun giderilmesi, söz konusu uç noktanın vekil sunucu düzeyinde kapatılmasıyla yapılmıştır. Kimlik doğrulamasının uygulama düzeyinde eklenmesi tercih edilmemiştir, çünkü ölçüm toplama süreci bu arayüzü yerel olarak ve vekil sunucudan geçmeden kullanmaktadır; uygulama düzeyinde koruma gözlemlenebilirliği bozardı. Doğru katman, dışarıya bakan katmandır.

Denetim sırasında ikinci bir gözlem daha yapılmıştır. Denetimin ilk turunda kullanılan araç, uygulama çatısının nesne grafiğini gezerek uç noktaları listelemiş ve on uç bulmuştur. Ancak alt yönlendiricilerle eklenen uç noktalar bu gezinmede görünmemektedir; gerçek sayı on altıdır. Araç yüzeyin bir bölümünü görememekte ve bunu bildirmemektedir. Bu nedenle yöntem değiştirilmiş, arayüz tanımından alınan tüm uç noktalara kimlik doğrulaması olmaksızın gerçek istek gönderilmiş ve dönen durum kodları kaydedilmiştir. Envanteri çıkaran aracın kendisinin de doğrulanması gerekmektedir.

#### D.3. Yapılandırmanın yanlış beyan üretmesi

Üçüncü bulgu, yapılandırma dosyasının kodda karşılığı bulunmayan ayarlar içermesidir. Altmış dokuz ayarın on biri hiçbir kod yolunda okunmamaktaydı. Bunların ikisi doğrudan güvenlik beyanı niteliğindedir: biri imzalı ve süreli klip bağlantılarının yapılandırıldığını, diğeri uygulama arayüzünün tamamında istek hızı sınırlaması bulunduğunu düşündürmektedir. Gerçekte imzalı bağlantı özelliği uygulanmamış, hız sınırlaması ise yalnızca oturum açma uç noktasında bulunmaktadır.

Bu durum bir kod hatası değildir, çünkü hiçbir işlev bozulmamaktadır. Ancak yapılandırma dosyasını inceleyen bir denetçi, sistemde bulunmayan korumaların yapılandırılmış olduğu sonucuna varmaktadır. Bu nedenle söz konusu ayarlar, uygulanmadıkları açıkça belirtilerek işaretlenmiştir.

*Tablo 17. Güvenlik öncelikli listesinin durumu.*

| Durum | Madde sayısı | Kapsam |
|---|---|---|
| Uygulandı | 18 | Parola saklama, belirteç yönetimi, rol tabanlı yetkilendirme, giriş hız sınırı, denetim kaydı, dizin geçişi koruması, taşıma katmanı güvenliği ve tek giriş noktası dâhil |
| Kapsam dışı, gerekçeli | 1 | Kamera bazlı yetkilendirme; tek operatörlü kurulumda karşılığı bulunmamaktadır |
| Yüzeyi oluşmadı | 1 | Sunucu taraflı istek sahteciliği filtresi; kamera ekleme arayüzü bulunmadığından saldırı yüzeyi de bulunmamaktadır |

### E. Geliştirme günlüğünün sınıflandırılması

Bu çalışmada, geliştirme süreci boyunca karşılaşılan her sorun aynı gün bir mühendislik günlüğüne kaydedilmiştir. Günlükte seksen yedi kayıt bulunmaktadır. Bu sayının tamamının yöntemsel bulgu olarak sunulması doğru olmayacaktır; kayıtlar içerik bakımından ayrışmaktadır.

Kayıtlar üç gruba ayrılmıştır. Birinci grup, bir başarım ya da doğruluk iddiasının sonraki bir ölçümle çürütüldüğü kayıtlardan oluşmaktadır ve kırk üç kayıt içermektedir. İkinci grup, ölçümle çürütülen bir iddia içermeyen fakat mimari ya da uygulama düzeyinde bulgu niteliği taşıyan otuz beş kayıttan oluşmaktadır. Üçüncü grup, kurulum ve ortam sorunlarıdır ve dokuz kayıt içermektedir; port çakışması, sürüm yöneticisi yapılandırması ve benzeri konular bu gruptadır. Üçüncü grup bu makalede bulgu olarak sunulmamaktadır.

Bu makalenin yöntemsel katkı ekseni birinci gruba dayanmaktadır. Söz konusu kırk üç kayıtta ortak olan nokta, hatanın modelde ya da sistemde değil ölçüm zincirinde bulunmasıdır. En sık görülen alt türler Tablo 3'te listelenmiştir.

---

## IV. SONUÇ

Bu çalışmada, yirmi eşzamanlı kamera akışının tek bir orta seviye dizüstü grafik işlemcisi üzerinde işlendiği bir gözetim sistemi geliştirilmiş ve sistemin başarımı ile doğruluğu ölçülmüştür. Sistem, tespit, takip, poz kestirimi, yüz ifadesi sınıflandırması, anomali tespiti ve saldırgan davranış kestirimini tek bir kademeli işlem hattında birleştirmektedir.

Başarım tarafında iki sonuç öne çıkmaktadır. Birincisi, uçtan uca gecikmenin hedefin oldukça altında kalmasıdır (p50 378 ms, hedef 1500 ms). İkincisi, analiz edilen kare hızının hedefe ulaşamamasıdır (2,34 kare/saniye, hedef 4). İkinci sonucun nedeni ölçülmüştür ve donanım yetersizliği değildir: grafik işlemci kullanımı medyan yüzde yirmi sekiz, video belleği kullanımı yüzde yedi düzeyinde kalmakta, buna karşılık çıkarım sürecinin seri ana döngüsü tek bir çekirdekte doymaktadır. Sınırlayıcı unsurun mimari olduğu, örnekleme hızının iki katına çıkarıldığı müdahaleli bir deneyle doğrulanmıştır; girdi artırıldığında analiz edilen kare hızı artmamış, yüzde otuz iki düşmüştür.

Doğruluk tarafında, iki bağımsız modelin birleştirilmesi şiddet tespitinde en iyi tek modele göre 0,032 eğri altı alan puanı kazandırmıştır. Bu kazancın kaynağı ayrıca gösterilmiştir: modellerin hata kümeleri yalnızca yüzde on oranında örtüşmektedir. Buna karşılık anomali tespitinde beş sinyalin birleştirilmesinin kazancı, aynı zamansal yumuşatmayı uygulayan tek sinyalli kontrol serisiyle karşılaştırıldığında önceden belirlenmiş anlamlılık eşiğinin altında kalmıştır. Bu iki sonuç birlikte, birleştirmenin kendiliğinden bir kazanç üretmediğini, kazancın birleştirilen bileşenlerin bağımsızlığına bağlı olduğunu göstermektedir.

Ulaşılamayan hedefler ve nedenleri açıkça belirtilmelidir. Analiz kare hızı hedefi, seri çıkarım döngüsü nedeniyle tutturulamamıştır. Erken uyarı hedefi, kullanılan veri setinde ulaşılabilecek en yüksek değerin hedefin altında kalması nedeniyle ölçülememiştir. Arayüz akıcılığı hedefi, ölçüt eşiğinin ölçüm aracının çözünürlük basamağı üzerine düşmesi nedeniyle ayırt edici bulunmamıştır. Bu üç durumun ortak yanı, sonucun sistemin başarımından çok ölçütün tasarımıyla belirlenmiş olmasıdır.

Buradan genellenebilir bir kural çıkmaktadır. Bir başarı ölçütü raporlanmadan önce üç niteliği denetlenmelidir: ölçütün kullanılan veriyle ulaşabileceği en yüksek değer, ölçüt eşiğinin ölçüm aracının çözünürlüğüne göre konumu ve gözlem biriminin bağımsızlığı. Bu denetimler yapılmadığında elde edilen sayı yanlış olmayabilir, ancak yanlış bir soruyu yanıtlıyor olabilir. Bu çalışmada üç ölçütte de durum böyle olmuştur.

Güvenlik tarafında iki bulgu aynı kalıbı göstermektedir. Birinci bulguda uygulama arayüzü korunurken video akışı korunmamış, ikinci bulguda tek giriş noktası kurulmuş fakat bu noktadan geçen uç noktaların envanteri çıkarılmamıştır. Her iki durumda da eksik olan bir güvenlik kontrolü değil, korunması gereken yüzeyin envanteridir. Bu gözlem, kontrol listesi temelli güvenlik yaklaşımlarının yüzey sayımıyla tamamlanması gerektiğine işaret etmektedir.

Gelecek çalışma için üç yön öne çıkmaktadır. Birincisi, erken uyarı ölçütünün anlamlı biçimde değerlendirilebilmesi için olay öncesi bağlam içeren bir veri setinin kullanılmasıdır; bu çalışmada kullanılan iki veri setinin de bu özelliği taşımadığı ölçülerek gösterilmiştir. İkincisi, etiketlemenin birden çok değerlendiriciyle yapılması ve değerlendiriciler arası uyumun raporlanmasıdır. Üçüncüsü, sistemin gerçek ağ koşulları altında ve gerçek kameralarla doğrulanmasıdır.

---

## BEYANLAR

**Teşekkür.** Çalışmanın yürütülmesi sırasındaki yönlendirmesi ve akademik yayına dönüştürülmesi yönündeki önerisi için Düzce Üniversitesi'nden Dr. Öğr. Üyesi Ahmet Albayrak'a teşekkür ederim.

**Yazar katkıları.** Çalışmanın tüm bölümlerini tek başıma gerçekleştirdim.

**Çıkar çatışması.** Herhangi bir çıkar çatışması bulunmadığını beyan ederim.

**Destekleyen kurum.** Bu araştırma için herhangi bir dış finansman almadım.

**Etik onay.** Bu çalışma insan veya hayvan katılımcı içermemektedir. Kullanılan tüm video verileri, araştırma amaçlı erişime açık akademik veri setlerinden elde edilmiş ve ilgili kaynaklar atıfla belirtilmiştir. Veri setleri kendi lisans koşulları çerçevesinde ve yalnızca araştırma amacıyla kullanılmıştır.

**İntihal beyanı.** Bu makale intihal tespit yazılımı ile değerlendirilmiş ve intihal tespit edilmemiştir.

**Yapay zekâ araçlarının kullanımı.** Bu çalışmanın yürütülmesinde ve makalenin hazırlanmasında büyük dil modeli tabanlı bir yapay zekâ aracı (Anthropic Claude) kullanılmıştır. Araç; yazılım geliştirme, ölçüm betiklerinin yazılması, ölçüm sonuçlarının çözümlenmesi ve makale metninin taslaklandırılması aşamalarında kullanılmıştır. Makalede sunulan tüm ölçümleri kendi donanımım üzerinde fiilen çalıştırdım, elde edilen çıktı dosyalarını sakladım ve metindeki her sayısal değeri bu çıktılarla karşılaştırarak doğruladım. Metnin son hâli, bilimsel içeriği ve sonuçları benim sorumluluğumdadır.

**Kod erişilebilirliği.** Çalışmada geliştirilen kaynak kod, ölçüm betikleri ve ölçüm çıktıları bir kod deposunda toplanmıştır: https://github.com/0merf/Staj-Proje

---

---

---

## KAYNAKLAR

Aharon, N., Orfaig, R., & Bobrovsky, B.-Z. (2022). BoT-SORT: Robust associations multi-pedestrian tracking. *arXiv ön baskısı*, arXiv:2206.14651.

Benfold, B., & Reid, I. (2011). Stable multi-target tracking in real-time surveillance video. *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, 3457-3464.

Borodin, K., Kondrashov, K., Vasiliev, N., Gladkova, K., Larina, I., Gorodnichev, M., & Mkrtchian, G. (2025). Benchmarking compact VLMs for clip-level surveillance anomaly detection under weak supervision. *Journal of Imaging*, 11(11), 400.

Cheng, M., Cai, K., & Li, M. (2021). RWF-2000: An open large scale video database for violence detection. *25th International Conference on Pattern Recognition (ICPR)*, 4183-4190.

Degardin, B., & Proença, H. (2020). Human activity analysis: Iterative weak/self-supervised learning frameworks for detecting abnormal events. *IEEE International Joint Conference on Biometrics (IJCB)*.

Efron, B. (1979). Bootstrap methods: Another look at the jackknife. *The Annals of Statistics*, 7(1), 1-26.

Ferryman, J., & Shahrokni, A. (2009). PETS2009: Dataset and challenge. *IEEE International Workshop on Performance Evaluation of Tracking and Surveillance (PETS-Winter)*.

Field, C. A., & Welsh, A. H. (2007). Bootstrapping clustered data. *Journal of the Royal Statistical Society: Series B (Statistical Methodology)*, 69(3), 369-390.

Hu, J., Mathur, L., Liang, P. P., & Morency, L.-P. (2025). OpenFace 3.0: A lightweight multitask system for comprehensive facial behavior analysis. *IEEE International Conference on Automatic Face and Gesture Recognition (FG)*.

Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., & Liu, T.-Y. (2017). LightGBM: A highly efficient gradient boosting decision tree. *Advances in Neural Information Processing Systems (NeurIPS)*, 30, 3146-3154.

Kwolek, B., & Kepski, M. (2014). Human fall detection on embedded platform using depth maps and wireless accelerometer. *Computer Methods and Programs in Biomedicine*, 117(3), 489-501.

Lu, C., Shi, J., & Jia, J. (2013). Abnormal event detection at 150 FPS in MATLAB. *IEEE International Conference on Computer Vision (ICCV)*, 2720-2727.

Mittal, H., Basak, S., & Gautam, A. (2026). DIFEM: Key-points interaction based feature extraction module for violence recognition in videos. *Signal, Image and Video Processing*, 20, Makale 243.

Oh, S., Hoogs, A., Perera, A., Cuntoor, N., Chen, C.-C., Lee, J. T., Mukherjee, S., Aggarwal, J. K., Lee, H., Davis, L., Swears, E., Wang, X., Ji, Q., Reddy, K., Shah, M., Vondrick, C., Pirsiavash, H., Ramanan, D., Yuen, J., … Desai, M. (2011). A large-scale benchmark dataset for event recognition in surveillance video. *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, 3153-3160.

Pathak, G., Kumar, A., Rawat, S., & Gupta, S. (2024). Streamlining video analysis for efficient violence detection. *arXiv ön baskısı*, arXiv:2412.02127.

Senadeera, D. C., Yang, X., Kollias, D., & Slabaugh, G. (2024). CUE-Net: Violence detection video analytics with spatial cropping, enhanced UniformerV2 and modified efficient additive attention. *IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW)*.

Shao, Y., He, H., Li, S., Chen, S., Long, X., Zeng, F., Fan, Y., Zhang, M., Yan, Z., Ma, A., Wang, X., Tang, H., Wang, Y., & Li, S. (2025). EventVAD: Training-free event-aware video anomaly detection. *ACM International Conference on Multimedia (ACM MM)*.

Tran, D., Wang, H., Torresani, L., Ray, J., LeCun, Y., & Paluri, M. (2018). A closer look at spatiotemporal convolutions for action recognition. *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, 6450-6459.

Varma, S., & Simon, R. (2006). Bias in error estimation when using cross-validation for model selection. *BMC Bioinformatics*, 7, 91.

Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association*, 22(158), 209-212.

Wu, W., Peng, H., & Yu, S. (2023). YuNet: A tiny millisecond-level face detector. *Machine Intelligence Research*, 20, 656-665.

Zhang, P., Lei, W., Zhao, X., Dong, L., & Lin, Z. (2023). RTVD-Net: A real-time violence detection method based on pre-training of human skeleton images. *12th International Conference on Networks, Communication and Computing (ICNCC)*, Osaka, Japonya.

Zhang, Y., Wang, X., Ye, X., Zhang, W., Lu, J., Tan, X., Ding, E., Sun, P., & Wang, J. (2023b). ByteTrackV2: 2D and 3D multi-object tracking by associating every detection box. *arXiv ön baskısı*, arXiv:2303.15334.

Zou, S., Tian, X., Wesemann, L., Waschkowski, F., Yang, Z., & Zhang, J. (2025). Unlocking vision-language models for video anomaly detection via fine-grained prompting. *arXiv ön baskısı*, arXiv:2510.02155.
