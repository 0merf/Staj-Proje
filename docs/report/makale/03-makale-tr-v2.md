# Kısıtlı Donanımda Yirmi Kameralı Gerçek Zamanlı Gözetim Sistemi: Başarım ve Doğruluk İddialarının Ölçülebilirliği Üzerine Bir Vaka Çalışması

**Ömer Faruk Kanat**¹*

¹ Düzce Üniversitesi, Mühendislik Fakültesi, Bilgisayar Mühendisliği Bölümü (İngilizce), Düzce, Türkiye. `ror.org/04175wc52`

\* Yazışma yazarı: omerfk0121@gmail.com
ORCID: 0009-0006-9229-6217

**Makale Türü:** Araştırma Makalesi

> **v2, 11.09.2026.** v1'e göre değişenler dosyanın sonundaki
> "Sürüm notları" bölümünde listelenmiştir.

---

## ÖZ

Bir nesne tespit modelinin tek başına ölçülen kare başına maliyeti, aynı modelin yirmi kameralı bir işlem hattı içinde ölçülen maliyetinden yaklaşık iki kat düşüktür. Bu çalışma, bileşen düzeyinde ölçülen başarım değerlerinin bütünleşik bir sisteme taşınmadığı gözleminden yola çıkmakta ve yirmi eşzamanlı kamera akışının tek bir orta seviye dizüstü grafik işlemcisi (RTX 3070 Laptop, 8 GB) üzerinde işlendiği bir gözetim sistemini konu almaktadır. Sistemde nesne tespiti, çoklu nesne takibi, poz kestirimi, yüz ifadesi sınıflandırması, anomali tespiti ve saldırgan davranış kestirimi tek bir işlem hattında birleştirilmiştir. Uçtan uca gecikme 378 ms (p50) ve 652 ms (p95) olarak ölçülmüş, kamera başına analiz edilen kare hızı 2,34 kare/saniyede kalmıştır. Şiddet tespitinde iskelet tabanlı bir gradyan artırma modeli ile ham piksel tabanlı üç boyutlu evrişimli bir modelin skor ortalaması alındığında F1 skoru 0,937 (eşik seçim yanlılığı düzeltildiğinde 0,917) elde edilmiş; kazancın kaynağının iki modelin hatalarının yalnızca %10 oranında örtüşmesi olduğu gösterilmiştir. Anomali tespitinde füzyon yaklaşımı 0,869 eğri altı alan değeri vermiş (küme önyükleme %95 güven aralığı 0,806 ile 0,929), ancak aynı zamansal yumuşatmayı tek sinyale uygulayan kontrol serisi 0,860 vermiştir; bu, kazancın sinyal birleştirmeden değil yumuşatmadan geldiğini göstermektedir. Çalışmanın ikinci katkısı ölçüm tarafındadır: geliştirme günlüğündeki 87 kaydın 43'ünde bir başarım ya da doğruluk iddiası sonraki bir ölçümle çürütülmüştür. Bu çürütmeler üç başlıkta toplanmıştır: ölçütün üst sınırının hedefin altında kalması, ölçüt eşiğinin ölçüm çözünürlüğünün altında olması ve gözlem biriminin bağımsızlık varsayımını karşılamaması. Güvenlik tarafında, tek giriş noktası mimarisi kurulmuş olmasına karşın bu noktadan geçen uç noktaların envanteri çıkarılmadığı için gözlemlenebilirlik arayüzünün kimlik doğrulaması olmaksızın dışarıya açık kaldığı tespit edilmiş ve giderilmiştir.

**Anahtar Kelimeler:** Çok kameralı gözetim, Gerçek zamanlı video analizi, Şiddet tespiti, Kaynak kısıtlı çıkarım, Ölçüm geçerliliği

---

## ABSTRACT

`[Türkçe öz kesinleştikten sonra çevrilecek]`

**Keywords:** Multi-camera surveillance, Real-time video analytics, Violence detection, Resource-constrained inference, Measurement validity

---

## I. GİRİŞ

Video gözetim sistemlerinin otomatikleştirilmesi, bilgisayarlı görü alanının en yoğun çalışılan uygulama başlıklarından biridir. Nesne tespiti, çoklu nesne takibi, poz kestirimi ve video tabanlı eylem tanıma alanlarının her birinde son yıllarda hem doğruluk hem hız bakımından belirgin ilerlemeler kaydedilmiştir. Bu bileşenler tek tek değerlendirildiğinde, kare başına maliyetleri ve doğruluk değerleri ayrıntılı biçimde raporlanmaktadır.

Bu çalışmanın çıkış noktası, söz konusu bileşen düzeyindeki değerlerin bütünleşik bir sisteme taşınıp taşınmadığı sorusudur. Soru, geliştirme sırasında yapılan bir ölçümle somutlaşmıştır. Bu çalışmada kullanılan nesne tespit modeli, yalnızca kendisine ayrılmış bir grafik işlemcisi üzerinde ve tam dolu yığınlarla ölçüldüğünde kare başına **3,78 ms** harcamaktadır. Aynı model, yirmi kameralı işlem hattının içinde, diğer kademelerle aynı donanımı paylaşırken ölçüldüğünde kare başına **7,46 ms** harcamaktadır (Tablo 6). Aradaki yaklaşık iki katlık fark modelin kendisinden değil, çalıştığı bağlamdan kaynaklanmaktadır: yığın boyutu üretimde tam dolmamakta, işlemci diğer kademelerle paylaşılmakta ve bellek erişim örüntüsü değişmektedir.

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

**Kademe 1b, çoklu nesne takibi.** Her kamera için ayrı bir takipçi örneği tutulmaktadır.

**Kademe 2a, poz kestirimi (grafik işlemci).** Tespit edilen her kişi kutusuna, yukarıdan aşağı yaklaşımla uygulanmaktadır.

**Kademe 2b, yüz tespiti ve ifade sınıflandırması.** İki basamaklı bir kapıyla seyreltilmektedir (Bölüm III.B.4).

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

⚠ **Mahremiyet notu.** Oxford Town Centre kayıtları, kamu alanında ve kişilerin rızası alınmaksızın elde edilmiş görüntülerdir. Bu nedenle söz konusu kaynaktan alınan hiçbir kare, bu makalede şekil ya da ekran görüntüsü olarak kullanılmamıştır; veri yalnızca yerel değerlendirmede kullanılmıştır.

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

**C.3. Kapanış kontrolü.** Bir işlem hattının bileşenleri tek tek ölçülüp toplandığında, elde edilen toplamın bağımsız olarak ölçülen döngü toplamına eşit olup olmadığı denetlenmektedir. Bu denetim yapılmadığında, ölçülmeyen bileşenlerin maliyeti örtük olarak sıfır kabul edilmiş olmaktadır. Bu çalışmada söz konusu denetimin eksikliği, bir aşamada işlem hattı maliyetinin %70'inin "ölçülmeyen ek yük" olarak yanlış raporlanmasına yol açmış, denetim eklendiğinde açığın sıfıra yakın olduğu görülmüştür.

**C.4. Kontrol serisi kullanılması.** Bir ölçümün, ölçülen sistemin değil ölçüm aracının tavanını yansıtma olasılığına karşı, yük uygulanmadan yapılan bir kontrol ölçümü alınmaktadır. Arayüz akıcılığı ölçümünde tam olarak 30 kare/saniye değerinin elde edilmesi, tarayıcının bu değeri sabitliyor olabileceği şüphesini doğurmuş, kamera açılmadan yapılan kontrol ölçümünün 60 kare/saniye vermesi gözlenen değerin yükün gerçek etkisi olduğunu göstermiştir. Benzer biçimde füzyon değerlendirmesinde, füzyonla aynı zamansal yumuşatmayı uygulayan tek sinyalli bir kontrol serisi tanımlanmıştır.

**C.5. Bağımsızlık biriminin belirlenmesi.** Güven aralıkları hesaplanırken gözlemlerin bağımsız olduğu varsayımı video verisinde çoğunlukla geçerli değildir, çünkü aynı klipten gelen ardışık kareler aynı sahneyi, aynı kişileri ve aynı aydınlatmayı içermektedir. Bu çalışmada kare düzeyinde ve klip düzeyinde önyükleme aralıklarının ikisi de hesaplanmış ve raporlanmıştır. Aradaki fark, bağımsızlık varsayımının sonuç üzerindeki etkisinin niceliksel ölçüsüdür.

**C.6. Eşik seçim yanlılığının ölçülmesi.** F1 gibi eşiğe bağlı ölçütlerde, en iyi eşiğin ölçütün hesaplandığı kümede aranması iyimser bir sonuç üretmektedir. Bu yanlılık, veri kümesinin tekrarlı ve katmanlı biçimde yarıya bölünmesi, eşiğin bir yarıda seçilip diğerinde uygulanmasıyla ölçülmüştür (400 tekrar).

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

Mimarinin güvenlik açısından belirleyici bileşeni, ters vekil sunucu üzerinden kurulan tek giriş noktasıdır. Bu bileşenin gerekçesi, geliştirme sırasında tespit edilen bir açıktan doğmuştur: uygulama programlama arayüzü kimlik doğrulaması gerektirirken, video akışını sunan medya sunucusu hiçbir doğrulama yapmamaktaydı. Video akışının uygulama ile aynı köken üzerinden sunulması, tarayıcının kimlik çerezini bu isteklere de eklemesini ve dolayısıyla video isteklerinin de doğrulanabilmesini sağlamaktadır. Vekil sunucu, video isteğini medya sunucusuna iletmeden önce uygulama arayüzüne yönlendirerek yetki sorgusu yapmaktadır (Şekil 3).

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

#### A.4. Çıkarım motoru hızlandırma denemesi

Aşama kırılımı, hızlandırılabilir grafik işlemci işinin döngü bütçesinin yüzde seksen birini oluşturduğunu göstermektedir (poz %48, tespit %33). Bu nedenle TensorRT ile hızlandırma ölçülmüştür (Tablo 7).

*Tablo 7. PyTorch ile TensorRT karşılaştırması (izole ölçüm).*

| | Yığın (ms) | Kare (ms) | p90 (ms) |
|---|---|---|---|
| PyTorch FP16 | 30,233 | 3,779 | 31,324 |
| TensorRT FP16 | 18,741 | 2,343 | 20,310 |
| Hızlanma | 1,61 kat | | |

Hızlanmanın doğruluğu bozmadan elde edildiği ayrıca denetlenmiştir. Her iki motor da aynı görüntüde yirmi tespit üretmiş, eşleşme tam olmuş, ortalama kesişim oranı 0,9915 bulunmuştur. Bu denetim zorunludur, çünkü hızlanma sonucu bozarak da elde edilebilir.

Buna karşılık motor üretime alınamamıştır. Kullanılan tespit mimarisinin dikkat blokları dinamik girdi şekilleriyle TensorRT çekirdeği bulamadığından motor sabit yığın boyutuyla ihraç edilmek zorunda kalmış, bu da yalnızca tam sekiz karelik yığınların kabul edilmesi anlamına gelmiştir. Üretimde ölçülen yığın medyanı 6,67 karedir ve kısmi yığınlar hata üretmektedir. Eksik yerleri kare tekrarıyla doldurmak mümkündür; bu durumda etkin kazanç 1,61 kattan yaklaşık 1,34 kata, verim kazancı ise yaklaşık yüzde dokuza inmektedir. Dolgu yapılan karelerin sonuçlarının ayıklanması gerekmekte, yanlış yapıldığında sistem var olmayan tespitler üretmektedir. Kalan süre içinde yüzde dokuz verim için bu risk alınmamış ve karar gerekçesiyle kaydedilmiştir.

#### A.5. Paylaşımlı bellek havuzunun boyutu bir kuyruk kararıdır

Paylaşımlı bellek havuzu doksan altı yuvadan oluşmakta ve 265 MB yer kaplamaktadır. Sistem belleğinin 16 GB olduğu düşünüldüğünde bu değer düşük görünmektedir. Havuzun işlevi depolama değil tamponlamadır: yuvalar yalnızca alım ile çıkarım arasında yolda olan kareleri tutmaktadır. Çıkarım süreci yetişebildiği sürece aynı anda kullanılan yuva sayısı azdır.

Havuzun büyütülmesi belirli bir noktadan sonra fayda sağlamamaktadır. Tüketici doymuş durumdaysa daha büyük bir tampon verimi artırmak yerine yalnızca kuyrukta bekleyen karelerin daha eski olmasına, dolayısıyla gecikmenin artmasına yol açmaktadır. Bu davranış kuyruk kuramında bilinen bir sonuçtur ve sistemde de gözlenmiştir (Bölüm III.A.3).

Geliştirme sırasında havuz boyutu kırk sekiz yuvadan doksan altı yuvaya çıkarıldığında belirgin bir iyileşme gözlenmiştir. Bunun nedeni kırk sekiz değerinin fazla küçük olması ve üreticinin yuva bulamadığı için kare düşürmesidir. Ancak burada bir dürüstlük notu gereklidir: söz konusu karşılaştırmaya ait ölçüm çıktısı dosyaya kaydedilmemiş, yalnızca geliştirme günlüğüne yazılmıştır. Ertesi gün aynı yapılandırmayla yapılan ölçümler o değerleri tekrar üretmemiştir. Bu nedenle bu makalede tekrar üretilebilen ve çıktısı saklanan ölçümler esas alınmış, tekrar üretilemeyen değerler kullanılmamıştır.

### B. Doğruluk

#### B.1. Şiddet tespiti ve iki modelin birleşimi

Şiddet tespiti için iki bağımsız yaklaşım değerlendirilmiştir. Birincisi, poz kestiriminden türetilen iskelet özniteliklerini bir gradyan artırma modeline veren yaklaşımdır. İkincisi, kısa video kesitlerini doğrudan ham piksel olarak işleyen üç boyutlu bir evrişimli ağdır. Sonuçlar Tablo 8'de verilmiştir.

*Tablo 8. Şiddet tespiti sonuçları (RWF-2000 doğrulama, 96 klip).*

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

Füzyonun katkısının ölçülebilmesi için bir kontrol serisi tanımlanmıştır: tek bir sinyale, füzyonla aynı zamansal yumuşatma uygulanmaktadır. Böylece iki değişken ayrıştırılmaktadır; birleştirme ile yumuşatma. Sonuçlar Tablo 9'dadır.

*Tablo 9. Anomali tespiti sonuçları (CUHK Avenue, 9 klip ve 1439 kare).*

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

Ham sayı doğrudan raporlanamamaktadır, çünkü kaynak videolar döngüde yayınlanmakta ve aynı olay defalarca alarm üretmektedir. Alarmlar kaynak video içindeki konuma göre tekilleştirilmiştir; birbirine altı saniyeden yakın olan, aynı kameraya ve aynı türe ait alarmlar tek olay sayılmıştır. Sonuçlar Tablo 10'dadır.

*Tablo 10. Alarm kesinliği (Wilson %95 güven aralığı).*

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

Bu sonucun iki anlamı vardır. Birincisi, ifade kademesinin hesaplama maliyetinin düşük olması (kare başına 0,46 ms, döngünün yüzde ikisi) bir verimlilik başarısı değil, kapının neredeyse her şeyi elemesinin sonucudur. İkincisi ve daha önemlisi, ifade sinyali pratikte tek bir kamerada üretilmektedir. Füzyon eksik sinyali sıfır değeriyle değerlendirdiğinden, bu durum ifade ağırlığının diğer kameralarda fiilen devre dışı kalması anlamına gelmektedir. Gözetim kameralarında yüz çözünürlüğünün ifade sınıflandırması için yetersiz kalması bilinen bir kısıttır ve bu ölçüm onu niceliksel olarak doğrulamaktadır.

### C. Ölçüt ile veri arasındaki uyuşmazlık

Bu bölüm çalışmanın en özgün bulgusunu sunmaktadır. Üç başarı ölçütünde, hedefin tutturulamamasının nedeni sistemin başarımı değil ölçütün kendisidir. Üç durum farklı türdendir ve birlikte genel bir kural vermektedir.

#### C.1. Ölçütün üst sınırı hedefin altındadır

Erken uyarı ölçütü, şiddet başlamadan en az iki saniye önce uyarı üretilmesini gerektirmektedir. Ölçüm sonuçları Tablo 11'de verilmiştir.

*Tablo 11. Erken uyarı avansı (RWF-2000, 20 kavga ve 30 normal klip).*

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

Arayüz akıcılığı ölçütü, yirmi kamera açıkken çizim hızının saniyede en az otuz kare olmasını gerektirmektedir. Yedi bağımsız koşunun sonuçları Tablo 12'dedir.

*Tablo 12. Arayüz akıcılığı ölçümleri (yedi koşu).*

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

*Tablo 13. Ölçüt ile veri arasındaki üç uyuşmazlık türü.*

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

*Tablo 14. Güvenlik öncelikli listesinin durumu.*

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

Gelecek çalışma için dört yön öne çıkmaktadır. Birincisi, çıkarım döngüsünün paralelleştirilmesidir; ölçülen kaynak kullanımı bunun için belirgin bir alan bulunduğunu göstermektedir. İkincisi, erken uyarı ölçütünün anlamlı biçimde değerlendirilebilmesi için olay öncesi bağlam içeren bir veri setinin kullanılmasıdır; bu çalışmada kullanılan iki veri setinin de bu özelliği taşımadığı ölçülerek gösterilmiştir. Üçüncüsü, etiketlemenin birden çok değerlendiriciyle yapılması ve değerlendiriciler arası uyumun raporlanmasıdır. Dördüncüsü, sistemin gerçek ağ koşulları altında, gerçek kameralarla doğrulanmasıdır.

---

## BEYANLAR

**Teşekkür.** Yazar, çalışmanın yürütülmesi sırasındaki yönlendirmesi ve akademik yayına dönüştürülmesi yönündeki önerisi için Düzce Üniversitesi'nden Dr. Öğr. Üyesi Ahmet Albayrak'a teşekkür eder.

**Yazar katkıları.** Çalışmanın tüm bölümleri yazar tarafından gerçekleştirilmiştir.

**Çıkar çatışması.** Yazar herhangi bir çıkar çatışması bulunmadığını beyan eder.

**Destekleyen kurum.** Bu araştırma herhangi bir dış finansman almamıştır.

**Etik onay.** Bu çalışma insan veya hayvan katılımcı içermemektedir. Kullanılan tüm video verileri kamuya açık akademik veri setlerinden elde edilmiştir ve ilgili kaynaklar atıfla belirtilmiştir. Kişilerin rızası alınmaksızın kamu alanında kaydedilmiş olan bir veri setinden (Oxford Town Centre) alınan hiçbir kare, bu makalede şekil olarak kullanılmamıştır.

**İntihal beyanı.** Bu makale intihal açısından değerlendirilmiş ve intihal tespit edilmemiştir. `[TARAMA YAPILDIKTAN SONRA KESİNLEŞTİRİLECEK]`

**Yapay zekâ araçlarının kullanımı.** Bu çalışmanın yürütülmesinde ve makalenin hazırlanmasında büyük dil modeli tabanlı bir yapay zekâ aracı (Anthropic Claude) kullanılmıştır. Araç; yazılım geliştirme, ölçüm betiklerinin yazılması, ölçüm sonuçlarının çözümlenmesi ve makale metninin taslaklandırılması aşamalarında kullanılmıştır. Makalede sunulan tüm ölçümler yazarın donanımı üzerinde fiilen çalıştırılmış, elde edilen çıktı dosyaları saklanmış ve metindeki her sayısal değer bu çıktılarla karşılaştırılarak doğrulanmıştır. Metnin son hâli, bilimsel içeriği ve sonuçları yazarın sorumluluğundadır.

**Veri ve kod erişilebilirliği.** `[YAZAR KARARI: depo bağlantısı eklenecek mi]`

---

## KAYNAKLAR

> ⚠ **DOĞRULAMA NOTU.** Aşağıdaki kaynaklardan künyesi tam verilenler, proje boyunca tutulan veri seti kayıt dosyalarında (`data/_sources/SOURCE.md`) ve literatür dosyasında belgelenmiş olanlardır. `[KÜNYE DOĞRULANMALI]` işaretli satırlarda yazar adı, yıl ve sayfa bilgisi ilgili yayının kendisinden alınarak tamamlanmalıdır. Bu makalede hiçbir kaynak künyesi tahminle yazılmamıştır.

### Veri setleri

Benfold, B., & Reid, I. (2011). Stable multi-target tracking in real-time surveillance video. *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, 3457-3464.

Cheng, M., Cai, K., & Li, M. (2021). RWF-2000: An open large scale video database for violence detection. *25th International Conference on Pattern Recognition (ICPR)*, 4183-4190.

Degardin, B., & Proença, H. (2020). Human activity analysis: Iterative weak/self-supervised learning frameworks for detecting abnormal events. *IEEE International Joint Conference on Biometrics (IJCB)*.

Ferryman, J., & Shahrokni, A. (2009). PETS2009: Dataset and challenge. *IEEE International Workshop on Performance Evaluation of Tracking and Surveillance (PETS-Winter)*.

Kwolek, B., & Kepski, M. (2014). Human fall detection on embedded platform using depth maps and wireless accelerometer. *Computer Methods and Programs in Biomedicine*, 117(3), 489-501.

Lu, C., Shi, J., & Jia, J. (2013). Abnormal event detection at 150 FPS in MATLAB. *IEEE International Conference on Computer Vision (ICCV)*, 2720-2727.

Oh, S., Hoogs, A., Perera, A., et al. (2011). A large-scale benchmark dataset for event recognition in surveillance video. *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*.

### Yöntemler ve modeller

Aharon, N., Orfaig, R., & Bobrovsky, B.-Z. (2022). BoT-SORT: Robust associations multi-pedestrian tracking. *arXiv:2206.14651*.

Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., & Liu, T.-Y. (2017). LightGBM: A highly efficient gradient boosting decision tree. *Advances in Neural Information Processing Systems (NeurIPS)*, 30.

Tran, D., Wang, H., Torresani, L., Ray, J., LeCun, Y., & Paluri, M. (2018). A closer look at spatiotemporal convolutions for action recognition. *IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, 6450-6459.

Wu, W., Peng, H., & Yu, S. (2023). YuNet: A tiny millisecond-level face detector. *Machine Intelligence Research*, 20, 656-665.

`[KÜNYE DOĞRULANMALI]` Ultralytics YOLO26 dokümantasyonu ve ilgili teknik rapor. https://docs.ultralytics.com/models/yolo26

`[KÜNYE DOĞRULANMALI]` EmotiEffLib yüz ifadesi tanıma kütüphanesi. https://github.com/sb-ai-lab/EmotiEffLib

### İstatistiksel yöntemler

Efron, B. (1979). Bootstrap methods: Another look at the jackknife. *The Annals of Statistics*, 7(1), 1-26.

Field, C. A., & Welsh, A. H. (2007). Bootstrapping clustered data. *Journal of the Royal Statistical Society: Series B*, 69(3), 369-390.

Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of the American Statistical Association*, 22(158), 209-212.

Varma, S., & Simon, R. (2006). Bias in error estimation when using cross-validation for model selection. *BMC Bioinformatics*, 7, 91.

### Alan literatürü

`[KÜNYE DOĞRULANMALI]` Şiddet tespiti alanındaki güncel yaklaşımlar (iskelet tabanlı gerçek zamanlı yöntemler). Bkz. `LITERATUR.md` §C.

`[KÜNYE DOĞRULANMALI]` Video anomali tespiti alanındaki güncel yaklaşımlar. Bkz. `LITERATUR.md` §D.

`[KÜNYE DOĞRULANMALI]` Yüz ifadesi tanıma alanındaki güncel yaklaşımlar. Bkz. `LITERATUR.md` §E.

---

## SÜRÜM NOTLARI

### v2 (11.09.2026), v1'e göre değişenler

| # | Değişiklik | Gerekçe |
|---|---|---|
| 1 | Öz'ün açılış cümlesi somutlaştırıldı | v1'deki cümle soyut ve anlaşılması güçtü; yerine ölçülmüş bir gözlem konuldu (3,78 ms ile 7,46 ms karşılaştırması) |
| 2 | Anahtar kelimeler değiştirildi | Önceki küme çalışmanın konusunu yeterince tanımlamıyordu. Yeni küme: çok kameralı gözetim, gerçek zamanlı video analizi, şiddet tespiti, kaynak kısıtlı çıkarım, ölçüm geçerliliği |
| 3 | "87 problem kaydı" ifadesi kaldırıldı | Kayıtların tamamı yöntemsel bulgu değildir. Sınıflandırma yapıldı: 43 çürütme, 35 mühendislik bulgusu, 9 kurulum sorunu. Makalede 43 sayısı kullanılmaktadır (Bölüm III.E) |
| 4 | Grafik işlemci kullanımı düzeltildi | v1'de %41 yazıyordu (09.09 ölçümü). 11.09'da 60 örnekle yeniden ölçüldü: medyan %28,5 |
| 5 | Veri seti tablosu tamamlandı | VIRAT, PETS 2009, Oxford Town Centre ve Pexels kaynakları eklendi; kamera eşlemesi ve atıflar verildi |
| 6 | Mahremiyet notu eklendi | Oxford Town Centre verisinden alınan kareler makalede kullanılmamaktadır |
| 7 | "Ölçüt" terimi tanımlandı | Bölüm I.B'de terimin anlamı örnekle açıklandı |
| 8 | Zamansal yumuşatma açıklandı | Bölüm III.B.2'de füzyonun çalışma biçimi ve yumuşatmanın ne olduğu ayrıntılandırıldı |
| 9 | Paylaşımlı bellek havuzunun boyutu gerekçelendirildi | Yeni alt bölüm III.A.5: havuzun bir depolama değil kuyruk kararı olduğu, büyütmenin gecikmeyi artırdığı |
| 10 | Kademe 3 açıklandı | Bölüm II.A.1 ve III.E'de bileşenin ne olduğu ve neden gerçekleştirilmediği yazıldı |
| 11 | Uzun tire kullanımı kaldırıldı | Metin boyunca noktalama sadeleştirildi |
| 12 | Denetim aracının eksik ölçümü eklendi | Bölüm III.D.2'ye, uç nokta envanterini çıkaran aracın yüzeyin bir bölümünü görememesi eklendi |

### Açık kalemler

| Kalem | Durum |
|---|---|
| İngilizce öz | Türkçe öz kesinleştikten sonra çevrilecek |
| Kaynak künyeleri | `[KÜNYE DOĞRULANMALI]` işaretli satırlar tamamlanacak |
| Şekil 3 | Kimlik doğrulama akış diyagramı çizilecek |
| Şekil biçimi | Renkli kutu yerine tek renk kullanımı değerlendirilecek |
| İntihal taraması | Yapılacak ve beyan güncellenecek |
| Depo bağlantısı | Yazar kararı |
