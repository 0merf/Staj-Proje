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
