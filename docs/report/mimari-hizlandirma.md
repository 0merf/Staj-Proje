# Boru Hattı Hızlandırma — ölçülmüş durum ve seçenekler

> **Durum:** karar verilmedi, seçenekler ölçüme dayalı olarak sıralandı.
> Kaynak ölçümler: P-58, P-60, P-61, P-65 (`problems.md`).
> Tarih: 09.09.2026

---

## 1. ÖLÇÜLEN DURUM — spekülasyon yok

```
çıkarım worker CPU      : 0.89 çekirdek  /  20 mantıksal çekirdek   → %4.5
GPU kullanımı           : %25 – %44
VRAM                    : 571 MB / 8192 MB                          → %7
  (PyTorch'un ayırdığı   : 415 MB)
analiz edilen kare hızı : 2.78 FPS/kamera × 20 = 55.6 kare/sn
uçtan uca gecikme       : p50 172–178 ms · p95 322–396 ms
```

**Çıkarım worker'ının tek çekirdeğinin kare başına gittiği yer:**

| aşama | ms/kare | pay |
|---|---|---|
| pose | 2.50 | %16 |
| detect | 1.80 | %12 |
| track | 0.22 | %1 |
| emotion | 0.06 | %0.4 |
| **ölçülen model işi** | **4.58** | **%30** |
| **ÖLÇÜLMEYEN** | **10.6** | **%70** |
| toplam (0.89 çekirdek ÷ 55.6 kare/sn) | 15.2 | %100 |

⚠ **Model çıkarımı, çıkarım worker'ının CPU'sunun yalnızca üçte biri.**
Kalan üçte iki ölçülmüyor: Valkey okuma, paylaşımlı bellek erişimi,
sonuç sözlüğünün kurulması, JSON serileştirme, yayınlama, ACK, slot
iadesi.

---

## 2. ⚠ NEDEN BOŞ ÇEKİRDEKLER KENDİLİĞİNDEN İŞE YARAMIYOR

BLAS düzeltmesi (P-58) boşa dönen ~8 çekirdeği geri kazandı. Ama
çıkarım worker'ı hiçbir zaman çekirdek **kıtlığından** yavaş değildi;
**serilikten** yavaş.

Ana döngü tek iş parçacığında koşuyor:

```
kareyi al → shm'den oku → GPU → sonucu kur → JSON → yayınla → ACK
└──────────────────────── hepsi SIRAYLA ────────────────────────┘
```

Böyle bir döngüye 19 boş çekirdek vermek hiçbir şey değiştirmez —
döngü onları **kullanamaz**. Tavanı bir çekirdektir.

⭐ Deneyle doğrulandı (P-65): örnekleme hızı 4 → 8 FPS yapıldığında
analiz edilen kare hızı **artmadı, 2.78'den 1.88'e düştü** ve çıkarım
worker'ının CPU'su 0.89 çekirdekte **hiç değişmedi**.

> **Boşluk donanımda, darboğaz mimaride.**

---

## 3. ⚠⚠ ÖNCE BİR UYARI: HIZ, DOĞRULUĞU DEĞİŞTİRİYOR

8 FPS koşusunda yalnızca hız değil **model çıktısı da** değişti:

| | normal (4 koşu) | bozuk rejim (8 FPS) |
|---|---|---|
| analiz FPS | 2.78 – 2.84 | 1.88 |
| model skoru medyan | 0.073 – 0.086 | **0.204** (2.5×) |
| model skoru azami | 0.39 – 0.51 | **0.875** |
| alarm türleri | crowd/fall/aggression/loitering/running | **+ `risk` × 27** ⬅ yeni |

Özellikler **5 saniyelik pencerede** hesaplanıyor. Analiz hızı
değişince penceredeki örnek sayısı ve hız/ivme türevleri kayıyor —
P-63'teki eğitim/servis uyuşmazlığının canlı hâli.

⭐⭐ **İşletme açısından ciddi bir özellik:** sistem yüklendiğinde
yanlış alarm artıyor. Yük ise tam da olay anında gelir.

> **Bundan sonraki her hızlandırma denemesi, verimin YANINDA doğruluğu
> ve alarm oranını da ölçmek zorunda.** Yalnızca "kaç kare/sn" bakmak,
> sistemi hızlandırıp sessizce bozmak demek olurdu.

---

## 4. SEÇENEKLER — çabaya göre sıralı

### ⭐ A. Ölçülmeyen %70'i ÖNCE ÖLÇMEK (ön koşul)

Kare başına 10.6 ms'nin nereye gittiği bilinmiyor. Bilinmeden yapılacak
her optimizasyon tahmine dayanır — ve bu projede tahminlerin sicili
kötü (66 problem kaydının çoğu bu).

- **Yapılacak:** ana döngünün her adımına histogram (`stage=` etiketiyle
  aynı metriğe): `fetch`, `shm_read`, `postprocess`, `serialize`,
  `publish`, `ack`.
- **Çaba:** ~30 dk + tek ölçüm koşusu
- **Kazanç:** doğrudan yok; ama A'sız B ve C körlemesine olur
- **Risk:** yok (yalnızca gözlem)

### ⭐⭐ B. Kamera bölüştürerek ÇOK ÇIKARIM WORKER'I

**Mimari kural 3'ün dayandığı sayı artık yanlış.** Kural şöyle diyor:

> *"Modeller tek süreçte tek kopya. 4 worker × 4.6 GB = VRAM patlar."*

Ölçülen: **worker başına 571 MB** (PyTorch 415 MB). 4.6 GB varsayımı
**8 kat** fazla. Üç worker ≈ 1.7 GB — 8 GB'lık kartta rahat.

- Kod zaten hazır: `--worker-id` bayrağı var, tüketici grubu
  (`GROUP = "inference"`) kullanılıyor.
- **Çaba:** ~1 saat (kamera bölüştürme + ayrı metrik portları) + ölçüm
- **Beklenen:** GPU (%25-44) ve Valkey doyana kadar neredeyse doğrusal;
  2 worker ile ~110 kare/sn (K2'yi geçer)

⚠⚠ **KRİTİK KISIT — naif paylaşım BOZAR:** BoT-SORT takipçisinin
durumu **worker'ın içinde, kamera başına** tutuluyor
(`takipci.update(kamera, ...)`). Tüketici grubu kareleri gelişigüzel
dağıtır; aynı kameranın kareleri iki worker'a bölünürse **her ikisinde
de yarım iz** oluşur, kimlikler kopar ve zamansal özelliklerin tamamı
bozulur (P-14/P-26 ile aynı sınıf hata).

→ **Zorunlu tasarım:** kameralar worker'lara **ayrık kümeler** hâlinde
bölüştürülmeli (sharding). Her kamera tam olarak bir worker'a ait olur.
En basit uygulama: worker'a `--cameras` filtresi; kendisine ait olmayan
kareyi işlemeden ACK'ler. (İsraflı ama tek satır; temizi ayrı akış.)

### C. Ana döngüyü BORU HATTINA çevirmek (tek süreç, çok iş parçacığı)

Döngüyü üç aşamaya bölmek: `getir/çöz` → `GPU` → `sonuç kur/yayınla`,
aralarında sınırlı kuyruklar. GPU işi yine sırayla akar ama 10.6 ms'lik
tutkal onunla **örtüşür**.

- **Çaba:** yarım – bir gün
- **Beklenen:** teorik olarak 15.2 → ~6 ms/kare
- ⚠ **RİSK: GIL.** Tutkalın ne kadarının saf Python (sözlük kurma,
  JSON) olduğu bilinmiyor. Saf Python ise iş parçacıkları **hiçbir şey
  kazandırmaz** — GIL serileştirir. Valkey I/O ve numpy GIL bırakır,
  sözlük kurma bırakmaz.
- → **A yapılmadan bu seçenek kumar.** A, tutkalın dağılımını verince
  bu seçeneğin işe yarayıp yaramayacağı belli olur.

### D. Tutkalın kendisini ucuzlatmak

A'nın sonucuna göre hedefli müdahaleler: JSON yerine msgpack,
Valkey çağrılarını pipeline'lamak, gereksiz kopyaları kaldırmak.

- **Çaba:** A'nın bulgusuna bağlı, muhtemelen 1-2 saat
- **Avantaj:** hem B hem C'ye yarar (serileştirilen iş küçülür)

### E. TensorRT — ⚠ bu kaldıraç DEĞİL

1.40× ölçüldü ama yalnızca `detect` üzerinde ve `detect` 15.2 ms'nin
**1.80'i**. En iyi ihtimalle kare başına 0.5 ms kazandırır — %3.
Darboğaz orada değil. (ADR-0006 zaten üretime almamıştı; bu ölçüm o
kararı **güçlendiriyor**.)

---

## 5. ÖNERİLEN SIRA

```
A (ölç, 30 dk)  →  B (kamera bölüştürme, 1 sa)  →  A'ya göre C ya da D
```

Gerekçe: B en ucuz **ve** en büyük beklenen kazanç, çünkü kod zaten
destekliyor ve engel sanılan VRAM kısıtı ölçümle çürüdü. A, B'den önce
yapılırsa B'nin sonucunu da açıklayabilir.

---

## 6. ⭐ RAPOR İÇİN NEDEN DEĞERLİ

Makalenin katkısı "bir sistem yaptık" değil, **"aynı donanımda, aynı
veriyle, aynı ölçüm aracıyla dört yapılandırmayı kıyasladık"** olur.
Kıyas tablosu şu sütunları taşımalı:

| yapılandırma | analiz FPS/kam | gecikme p50/p95 | çıkarım CPU | GPU % | VRAM | model skoru medyan | alarm oranı |
|---|---|---|---|---|---|---|---|
| taban (tek worker) | 2.78 | 172/322 | 0.89 çek. | %25-44 | 571 MB | 0.078 | ölçülecek |
| 2 worker (bölüştürülmüş) | ? | ? | ? | ? | ? | ? | ? |
| boru hattı (thread) | ? | ? | ? | ? | ? | ? | ? |
| taban + 8 FPS (karşı örnek) | 1.88 | 433/711 | 0.89 çek. | ? | ? | **0.204** | `risk` ×27 |

⚠ **Son satır bilerek tabloda:** başarısız bir yapılandırma, başarılı
olanlar kadar öğretici. "Daha çok kare vermek analizi yavaşlattı ve
yanlış alarmı artırdı" cümlesi, ölçülmüş bir karşı-sezgidir.

⚠ Ve doğruluk sütunları **zorunlu**: bu sistemde hız ile doğruluk
bağımsız değil (bkz. §3). Yalnızca verim raporlayan bir kıyas,
sistemi hızlandırıp sessizce bozan bir kararı destekleyebilirdi.

---

## 7. AÇIK RİSKLER

| # | Risk | Not |
|---|---|---|
| R-A | Kamera bölüştürme yapılmazsa takip kimlikleri kopar | §4-B'deki kritik kısıt; naif çoklu worker **sessizce** bozar |
| R-B | Çok worker VRAM'i ×N yapar | 571 MB × 3 = 1.7 GB, 8 GB'da güvenli; ama ölçülerek doğrulanmalı |
| R-C | GIL, C seçeneğini etkisiz kılabilir | A yapılmadan bilinemez |
| R-D | Her hızlanma model skorlarını kaydırabilir | §3 — her yapılandırmada doğruluk yeniden ölçülmeli |
| R-E | Kalan süre 6 iş günü ve rapor yazılmadı | B ve A yapılabilir; C bir günlük iş, kapsam kararı gerektirir |
