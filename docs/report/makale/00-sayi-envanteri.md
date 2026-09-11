# Makale Sayı Envanteri — her değerin kaynağı

> **Bu dosyanın amacı tek:** makaleye giren hiçbir sayı "hatırladığım
> kadarıyla" olmasın. Her satırın karşısında onu üreten dosya var ve
> o dosya git'te.
>
> Kural: **envanterde olmayan sayı makaleye giremez.**
> Bir sayıyı değiştirmek gerekiyorsa önce ölçüm tekrarlanır, dosya
> güncellenir, sonra buraya yazılır — tersi değil.

**Ortam (tüm ölçümler):** RTX 3070 Laptop GPU (8 GB), 20 mantıksal
çekirdek, Windows 11, Python 3.13.15, torch 2.11.0+cu128, CUDA 12.8,
ultralytics 8.4.118. Altyapı Docker'da, YZ worker'ları native.

---

## 1. Başarı kriterleri

| # | Kriter | Hedef | Ölçülen | Durum | Kaynak dosya |
|---|---|---|---|---|---|
| K1 | Eşzamanlı kamera | ≥20 | **20/20** | ✅ | `frontend/e2e/panel.spec.ts` (canlı sisteme karşı) |
| K2 | Analiz kare hızı | ≥4 FPS/kam | **2.34** (örnekleme 2.84) | 🟡 | `benchmarks/canli_dogrulama_20260910-100331.json` |
| K3 | Uçtan uca gecikme | ≤1500 ms | **p50 378.5 · p95 651.5 ms** | ✅ | aynı dosya |
| K4 | 2 saat çökmesiz | — | **120 dk · 0 kesinti** | ✅ ⚠ eski kod | `benchmarks/k4_dayaniklilik_20260903-173542.json` |
| K5 | Şiddet F1 | ≥0.85 | **0.9369** · yanlılık düzeltilmiş **0.9165** | ✅ | `benchmarks/birlesim_20260909-132516.json` |
| K6 | Anomali AUC | ≥0.75 | **0.8691** · küme GA [0.8057, 0.9286] | ✅ | `benchmarks/k6_20260910-122310.json` |
| K7 | Yanlış alarm | ≤3/kam-saat | **kesinlik 0.895** [0.686, 0.971] · 19 bağımsız olay | 🟡 | `benchmarks/alarm_kesinlik_20260910.json` |
| K8 | Erken uyarı | ≥2 sn | **−1.10 sn** [−1.87, −0.07] · ölçüt tavanı 0.58 sn | ❌ | `benchmarks/k8_20260910-164322.json` |
| K9 | Güvenlik Öncelik-1 | %100 | **18/19** | 🟡 | `PLAN.md §11.1` + kod |
| K10 | UI akıcılığı | ≥30 FPS | çizim medyan **30.00** (29.43–30.02) · düşen kare medyan %2.3 (0–33.4) | 🟡 | `benchmarks/k10_ui_fps_*.json` (7 koşu) |

⚠ **K4 dışındaki tüm ölçümler 09–10.09.2026 tarihli koddan.** K4
03.09'da koşuldu; o tarihten sonra 20'den fazla değişiklik yapıldı ve
dayanıklılık testi tekrarlanmadı. Makalede bu açıkça yazılacak.

---

## 2. Çıkarım döngüsü — aşama kırılımı

**Kaynak:** `benchmarks/asama_kirilimi_20260910-100745.json`
(120 sn pencere · 863 parti · 6.5 kare/parti · 46.8 kare/sn)

| aşama | ms/kare | pay |
|---|---|---|
| pose (KADEME 2a) | **10.96** | %48 |
| detect (KADEME 1) | **7.46** | %33 |
| track (BoT-SORT) | 1.56 | %7 |
| publish | 1.24 | %5 |
| serialize | 0.56 | %2 |
| emotion (KADEME 2b) | 0.46 | %2 |
| slot_release | 0.37 | %2 |
| shm_read | 0.00 | %0 |
| **ölçülen toplam** | **22.62** | |
| **bağımsız ölçülen parti toplamı** | **22.65** | |
| **açıklanamayan** | **0.04** | **%0 — kapanış sağlandı** |

Ayrıca `bekleme_IS_DEGIL` = 1.69 ms/kare (CPU değil, kare bekleme;
toplama katılmaz). Worker zamanının %93'ünü iş yaparak geçiriyor.

⭐ Aynı tablo bir gün önce **farklı bir araçla** ölçülmüştü:
toplam 23.22, parti toplamı 23.26, açık 0.04 (P-66). Bağımsız tekrar.

---

## 3. Kaynak kullanımı (20 kamera, kararlı durum)

**Kaynak:** `benchmarks/canli_dogrulama_20260910-100331.json`

| bileşen | RAM (MB) | CPU (çekirdek) | thread |
|---|---|---|---|
| alım | 1295.0 | 2.42 | 356 |
| çıkarım | 1077.2 | 0.89 | 7 |
| analitik | 133.5 | 0.93 | 2 |
| alarm | 57.9 | 0.00 | 2 |
| API | 74.1 | 0.02 | 3 |
| **toplam** | **2633.9** | **4.27** | |

**GPU (11.09.2026, 60 örnek × 1 sn, panel kapalı)** — `benchmarks/gpu_kullanim_20260911.json`

| ölçüt | değer |
|---|---|
| VRAM | **571 MB / 8192 MB (%7)** — medyan = azami, sabit |
| GPU kullanımı | **medyan %28.5** · ortalama %26.7 · aralık %0–85 |

⚠ Daha önce "%41" yazılmıştı (P-65, 09.09). Bugün tekrar ölçüldü ve
medyan %28.5 çıktı. Makalede bugünkü değer kullanılmaktadır; eski
değer envantere alınmamıştır. VRAM değeri iki ölçümde de aynıdır.

sistem RAM %81

**Arz–talep açığı:** alım 56.8 kare/sn yayınlıyor, çıkarım 46.8
işliyor → 2017 / 11501 kare (%17.5) analiz edilmeden kuyrukta kalıyor.

---

## 4. K5 — şiddet tespiti (RWF-2000 val, 96 klip)

**Kaynak:** `benchmarks/birlesim_20260909-132516.json`

| model | AUC | AUC %95 GA | F1 | kesinlik | duyarlılık |
|---|---|---|---|---|---|
| İskelet + LightGBM | 0.9267 | [0.8676, 0.9722] | 0.8889 | 0.9565 | 0.8302 |
| Video (R3D-18) | 0.9366 | [0.8820, 0.9796] | 0.9107 | 0.8644 | 0.9623 |
| **Birleşim (ortalama)** | **0.9684** | **[0.9352, 0.9917]** | **0.9369** | 0.8966 | 0.9811 |
| Birleşim (azami/VEYA) | 0.9636 | [0.9257, 0.9909] | 0.9358 | 0.9107 | 0.9623 |
| Birleşim (asgari/VE) | 0.9381 | [0.8868, 0.9770] | 0.8889 | 0.8727 | 0.9057 |
| Birleşim (çarpım) | 0.9561 | [0.9168, 0.9850] | 0.9009 | 0.8621 | 0.9434 |

**Eşik seçim yanlılığı** (400 tekrarlı katmanlı yarı-yarıya bölme):
birleşim F1 aynı kümede 0.9369 → ayrı yarıda **0.9165** (iyimserlik
+0.0204). Diğer modellerin iyimserliği +0.018 … +0.033.

**Kazananın laneti:** 4 birleştirme kuralı arasından seçim yapmanın
iyimserliği +0.0014 AUC. ⚠ "ortalama" kuralı **önceden** seçilmişti.

**Hata bağımsızlığı:** yalnız iskeletin yanıldığı 10, yalnız videonun
yanıldığı 9, ikisinin birden yanıldığı **1** klip → örtüşme %10.
Birleşimin neden kazandığının mekanizması bu.

**Maliyet:** R3D-18 penceresi 6.44 ms; 20 kamera için saniyede 354 ms
→ gerçek zamanlı bütçeye sığıyor.

---

## 5. K6 — anomali tespiti (Avenue, 9 klip / 1439 kare)

**Kaynak:** `benchmarks/k6_20260910-122310.json`

| sinyal | AUC | kare GA (naif) | **küme GA (doğru)** |
|---|---|---|---|
| **füzyon (5 sinyal + EMA)** | **0.8691** | [0.8257, 0.9060] | **[0.8057, 0.9286]** |
| katman_a (ham) | 0.7891 | [0.7476, 0.8250] | [0.7494, 0.8275] |
| katman_a + EMA (kontrol) | 0.8602 | [0.8128, 0.9019] | [0.8142, 0.9004] |
| kural (Katman B) | 0.500 | — | [0.499, 0.500] |
| saldırganlık | 0.457 | — | [0.444, 0.486] |

**Füzyon sınavı:** füzyon (0.8691) − katman_a+EMA (0.8602) = **+0.0089**
Anlamlılık eşiği 0.02 olarak **önceden** belirlenmişti (9 klip / 69
anomali karesinde AUC belirsizliği bu mertebede).
→ **Sonuç: kazandıran birleştirme değil, yumuşatma.**

⚠ Küme (klip) bootstrap'ı kare bootstrap'ından %54 daha geniş aralık
veriyor. Naif yöntemle raporlansaydı sahip olmadığımız bir kesinlik
iddia edilmiş olurdu.

---

## 6. K7 — alarm kesinliği

**Kaynak:** `benchmarks/alarm_kesinlik_20260910.json`
**Yer gerçeği:** `data/annotations/alarm_etiketleri_20260910.csv`

| | n | doğru | kesinlik | %95 GA (Wilson) |
|---|---|---|---|---|
| ham etiketli alarm | 39 | 37 | 0.949 | [0.831, 0.986] |
| **bağımsız olay** | **19** | **17** | **0.895** | **[0.686, 0.971]** |
| — crowd | 9 | 9 | 1.00 | [0.70, 1.00] |
| — risk | 5 | 5 | 1.00 | [0.57, 1.00] |
| — **fall** | **5** | **3** | **0.60** | **[0.23, 0.88]** |
| — loitering | 0 | — | ölçülemez | 6 sn klip 45 sn kuralı doğrulayamaz |

40 alarmın 39'u etiketlendi, 1'i "karar veremedim" → analiz dışı.
Her iki yanlış alarm da `fall`, ikisi de aynı mekanizma: **eğilen /
çömelen kişiyi düşme sanmak.**

---

## 7. K8 — erken uyarı (RWF-2000 val, 20 kavga + 30 normal klip)

**Kaynak:** `benchmarks/k8_20260910-164322.json`
**Yer gerçeği:** `data/annotations/rwf_k8.json`

| eşik | yakala | kaçır | geç | medyan avans | %95 GA | y. alarm |
|---|---|---|---|---|---|---|
| 0.10 | 7 | 13 | 6 | **−1.10 sn** | [−1.87, −0.07] | %13 |
| 0.15 | 4 | 16 | 4 | −1.72 sn | [−2.13, −0.60] | %7 |
| 0.20 | 2 | 18 | 2 | −3.72 sn | [−4.30, −3.13] | %3 |
| ≥0.25 | 0 | 20 | 0 | — | — | ≤%3 |

**⚠ ÖLÇÜTÜN TAVANI:**

| | değer |
|---|---|
| kavga öncesi bağlam, medyan (etiketten) | **0.58 sn** |
| aynı, azami | 3.07 sn |
| etiketleyici beyanı (gerçek başlangıç) | **0–0.5 sn** |
| K8 hedefi | **2.00 sn** |
| hedefin fiziksel olarak mümkün olduğu klip | **2/20** |

**Bağımsız ikinci ölçüm** (cam-15h, UBI-Fights, 58 sn olay öncesi
bağlam — `benchmarks/k8_video_20260907-170644.json`):
model kavgayı normalden ayırıyor (oran 2.756) ama tırmanma penceresi
normalden **düşük** skorluyor (0.184 ⟷ 0.282); tespit **+1.76 sn geç**.

---

## 8. K10 — arayüz akıcılığı (7 koşu)

**Kaynak:** `benchmarks/k10_ui_fps_*.json`

| ölçüldü | çizim FPS | kontrol (0 kamera) | video/sn | düşen % |
|---|---|---|---|---|
| 08:05 | 29.96 | — | 275.0 | 1.8 |
| 08:06 | 30.00 | — | 275.0 | 2.3 |
| 08:09 | 30.02 | 60.19 | 275.0 | 0.0 |
| 14:46 | 29.43 | 59.68 | 225.0 | 16.1 |
| 14:48 | 30.00 | 59.92 | 225.0 | 11.4 |
| 14:50 | 30.02 | 59.99 | 300.0 | 33.4 |
| 14:51 | 29.90 | 60.05 | 200.0 | 1.6 |
| **medyan** | **30.00** | **~60** | 225.0 | **2.3** |
| **aralık** | 29.43–30.02 | 59.7–60.2 | 200–300 | 0.0–33.4 |

---

## 9. KADEME 2b — ifade kapısının eleme oranı

**Kaynak:** `benchmarks/ifade_kapi_20260910-070202.json`
(21 kamera × 25 kare)

| basamak | ölçüm |
|---|---|
| 1. kişi kutusu ≥180 px | 2087 kişiden **171'i geçti (%8.2)** |
| 2. YuNet yüz buluyor mu | kapıyı geçen 8 kameranın 7'sinde **0 yüz**; yalnız cam-20 (25/25) |

→ İfade sinyali pratikte **tek kamerada** üretiliyor. Maliyetinin
düşük olmasının (0.46 ms/kare) sebebi bu.

---

## 10. Kaynak videolar — döngü etkisi

**Kaynak:** `benchmarks/kamera_video_sureleri.json`

| kamera | süre | saatte tekrar |
|---|---|---|
| cam-16 | **5 sn** | **720** |
| cam-08 | 42 sn | 86 |
| cam-07 / cam-20 | 70 / 65 sn | 51 / 55 |
| cam-10…14 | 114 sn | 32 |
| cam-15 | 128 sn | 28 |
| cam-01…06, 09, 17 | 300 sn | 12 |
| cam-18 / cam-19 | 328 / 345 sn | 11 / 10 |

→ Ham "alarm/kamera-saat" oranı sistemin davranışını değil, **test
videolarının uzunluk dağılımını** ölçüyor.

---

## 11. TensorRT (üretime alınmadı)

**Kaynak:** `benchmarks/tensorrt_20260909-200411.json`

| | parti ms | kare ms | p90 |
|---|---|---|---|
| PyTorch FP16 | 30.233 | 3.779 | 31.324 |
| TensorRT | 18.741 | 2.343 | 20.310 |
| **hızlanma** | **1.61×** | | |

Tespit eşdeğerliği: 20/20 eşleşme, ortalama IoU 0.9915, kayıp/fazla 0.
**Üretimde çalışmadı:** motor `dynamic=False` ile ihraç edilmek
zorunda (YOLO26 dikkat bloğu), sabit parti yalnız 8 kare kabul ediyor;
üretim parti medyanı 6.67. Dolgu ile net kazanç ~1.34× → %9 verim;
hayalet tespit riski nedeniyle uygulanmadı.

---

## 12. Makalede KULLANILMAYACAK sayılar (ve nedeni)

| sayı | neden kullanılmıyor |
|---|---|
| "gecikme p50 147 ms" (P-69) | **tekrar üretilemedi**, yapıtı kaydedilmemiş (P-82) |
| "düşen kare 0" (P-75) | tek koşuydu; 7 koşuda aralık %0–33 (P-87) |
| "alarm 11.69/kamera-saat" | döngü şişkinliği; sistemin davranışını ölçmüyor (P-79) |
| "tutkal %70" (P-65 §4) | birim karışıklığı; kapanış kontrolüyle çürütüldü (P-66) |
| "kesinlik 0.917" (P-77) | n=12'lik ara ölçüm; n=19 ile güncellendi (P-85) |
