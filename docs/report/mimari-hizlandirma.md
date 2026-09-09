# Boru Hattı Hızlandırma — ölçülmüş durum ve seçenekler

> ⚠⚠ **09.09 AKŞAMI DÜZELTİLDİ (P-66).** Bu belgenin ilk sürümü
> "kare başına 15.2 ms'nin %70'i ölçülmeyen tutkal" diyordu. **Yanlıştı**
> — aynı metrikte iki farklı birim (kare başına / parti başına)
> toplanmıştı. Ölçülünce döngünün **%91'i model işi**, tutkal **%9**
> çıktı. Aşağıdaki §1 ve §4 buna göre güncellendi; C ve D seçenekleri
> düştü, TensorRT (E) yükseldi.

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

⚠⚠ **YUKARIDAKİ TABLO YANLIŞTIR — P-66'da çürütüldü.** Bilerek
bırakıldı: raporda "ölçüm aracı hatası" örneği olarak kullanılacak.
Doğrusu aşağıda.

### ✅ DÜZELTİLMİŞ KIRILIM (tek pencere, fark alarak, tek birim)

150 sn · 6941 kare · 1040 parti · 46.3 kare/sn

| aşama | ms/kare | pay |
|---|---|---|
| **pose** | **11.64** | **%50** |
| **detect** | **7.43** | **%32** |
| track | 1.56 | %7 |
| publish | 1.19 | %5 |
| serialize | 0.59 | %3 |
| emotion | 0.47 | %2 |
| slot_release | 0.33 | %1 |
| shm_read | 0.00 | %0 |
| **ölçülen toplam** | **23.22** | **%100** |
| PARTİ TOPLAMI (kapanış kontrolü) | 23.26 | — |
| açıklanmayan | **0.04** | **%0** ✅ |

⭐ **Döngünün %91'i model işi, %9'u tutkal.** Kaldıraç sırası:
`pose > detect >> diğer her şey`. Poz tek başına bütçenin yarısı.

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

### ❌ C. Ana döngüyü BORU HATTINA çevirmek — P-66 SONRASI DÜŞTÜ

⚠ Bu seçeneğin tüm gerekçesi "tutkal %70" idi. Tutkal **%9** ölçüldü;
tamamen örtüşse bile tavan kazanç %9. Emek/kazanç oranı kötü.
Aşağıdaki değerlendirme tarihsel kayıt için bırakıldı.

<details><summary>eski değerlendirme</summary>

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

</details>

### ❌ D. Tutkalın kendisini ucuzlatmak — P-66 SONRASI DÜŞTÜ

A'nın sonucuna göre hedefli müdahaleler: JSON yerine msgpack,
Valkey çağrılarını pipeline'lamak, gereksiz kopyaları kaldırmak.

- **Çaba:** A'nın bulgusuna bağlı, muhtemelen 1-2 saat
- **Avantaj:** hem B hem C'ye yarar (serileştirilen iş küçülür)

### ⭐ E. TensorRT — P-66 SONRASI YÜKSELDİ

⚠ İlk değerlendirmem *"kaldıraç değil, %3"* diyordu ve **yanlış
tablodan türemişti**: `detect`in bütçenin %3'ü olduğu sanılıyordu,
ölçülen **%32**. Poz da eklenince hızlandırılabilir GPU işi **%82**.

1.40× hızlanma ölçülmüştü (`detect`, tespitler birebir aynı). Aynı
oran poza da uygularsa: 19.07 → 13.6 ms/kare, yani **kare başına
~%23 kazanç**. ADR-0006 yeniden değerlendirilmeli.

⚠ Poz için TensorRT ölçülmedi — varsayım değil, ölçüm gerekiyor.

---

## 5. ÖNERİLEN SIRA

```
A (ölç) ✅ YAPILDI → B (kamera bölüştürme, 1 sa) → E (TensorRT, poz dâhil)
```

⭐ A yapıldı ve **öneri sırasını değiştirdi** (P-66): C ve D düştü,
E yükseldi. Bu, "önce ölç" ilkesinin bu projedeki en somut
karşılığı — ölçmeden gidilseydi bir gün yanlış seçeneğe (C)
harcanacaktı.

B hâlâ birinci: iş GPU model işi ve süreçler arasında gerçekten
paralelleşir; GPU %25-44'te, VRAM %7'de.

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
