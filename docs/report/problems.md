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
