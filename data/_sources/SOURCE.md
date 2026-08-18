# Kamera Çiftliği Kaynak Videoları — Kaynak, Lisans ve Atıf

> **PLAN.md §7.2 kuralı:** Her veri seti için indirme adresi, lisans ve
> alıntı bilgisi kaydedilir. Veri **git'e girmez**, bu dosya girer.

## Ne için kullanılıyor

20 gerçek IP kamera yok. Bu videolar MediaMTX ile **20 bağımsız RTSP
akışına** dönüştürülüyor; sistem açısından gerçek kameralardan ayırt
edilemezler (PLAN.md §7.1).

```
_sources/<set>/*.mp4
   ↓ scripts/prepare_videos.py  (720p / H.264 / 25 FPS normalize)
data/videos/cam-01..20.mp4  +  manifest.json
   ↓ MediaMTX runOnDemand + stream_loop -1
rtsp://127.0.0.1:8554/cam-NN
```

Kamera → kaynak eşlemesi **`data/videos/manifest.json`** dosyasındadır
(her kamera için `label`, `kind`, `source`, `duration_s`).

---

## VIRAT Video Dataset  ·  `_sources/virat/`  ·  ~7.3 GB

| | |
|---|---|
| **Ad** | VIRAT Video Dataset (Ground, Release 2.0) |
| **Erişim** | https://viratdata.org/ · https://data.kitware.com/ |
| **İçerik** | Sabit gözetim kamerasından otopark, kampüs, bina girişi |
| **Kullanım** | cam-01…cam-08 — **normal sahne** |

**Neden bu set:** Anomali modülünün "normal"i öğrenmesi için uzun,
olaysız, sabit kamera görüntüsü gerekiyor (PLAN.md §6.4 Katman A).
VIRAT tam olarak bunu sağlıyor — gerçek gözetim açısı, gerçek yaya
trafiği, dakikalarca hiçbir şey olmayan bölümler.

**Lisans:** Araştırma amaçlı serbest kullanım. Ticari kullanım için
sahiplerine başvuru gerekir.

**Atıf:**
> Oh, S., Hoogs, A., Perera, A., et al. (2011). *A Large-scale Benchmark
> Dataset for Event Recognition in Surveillance Video.* CVPR 2011.

---

## PETS 2009  ·  `_sources/pets/`  ·  ~803 MB

| | |
|---|---|
| **Ad** | PETS 2009 Benchmark Data — Crowd_PETS09 |
| **Erişim** | http://cs.binghamton.edu/~mrldata/pets2009 |
| **İçerik** | Çoklu kamera, kalabalık akışı, yürüyüş/koşu/dağılma senaryoları |
| **Kullanım** | Kalabalık ve **ani dağılma** senaryoları |

**Neden bu set:** PLAN.md §6.4 Katman B'de "ani dağılma (panik
göstergesi)" ve "aşırı kalabalık" kuralları var. PETS 2009 bu
davranışları **sahnelenmiş ama gerçekçi** biçimde içeriyor ve kare
seviyesinde belgeli.

**Lisans:** Akademik kullanım için serbest.

**Atıf:**
> Ferryman, J., & Shahrokni, A. (2009). *PETS2009: Dataset and Challenge.*
> IEEE International Workshop on Performance Evaluation of Tracking and
> Surveillance (PETS-Winter).

---

## Oxford Town Centre  ·  `_sources/oxford/`  ·  ~86 MB

| | |
|---|---|
| **Ad** | Oxford Town Centre Dataset |
| **İçerik** | `TownCentreXVID.mp4` + kalibrasyon + yer gerçeği (`.top`) |
| **Kullanım** | Yoğun yaya trafiği · **takip doğruluğu** referansı |

**Neden bu set:** Yanında **yer gerçeği (ground truth)** geliyor —
`TownCentre-groundtruth.top`. Gün 23'teki takip değerlendirmesinde
(PLAN.md §14.2 · HOTA/IDF1) MOT17 dışında ikinci bir referans olarak
kullanılabilir.

⚠ **Mahremiyet notu:** Bu video gerçek kişilerin rızası alınmadan
kaydedilmiş bir kamu alanı görüntüsüdür ve bazı kurumlar kullanımını
kısıtlamıştır. **Yalnızca yerel değerlendirmede** kullanılıyor;
ekran görüntüsü ya da klip teslim paketine/rapora **konulmayacak**.

**Lisans:** Araştırma amaçlı; kısıtlar için yukarıdaki nota bakınız.

**Atıf:**
> Benfold, B., & Reid, I. (2011). *Stable Multi-Target Tracking in
> Real-Time Surveillance Video.* CVPR 2011, 3457-3464.

---

## Pexels  ·  `_sources/pexels/`  ·  ~151 MB

| | |
|---|---|
| **Erişim** | https://www.pexels.com/ |
| **İçerik** | Yakın plan yüz içeren sahneler, yürüyen insanlar |
| **Kullanım** | cam-19, cam-20 — **duygu modülü testi** |

**Neden bu set:** Gözetim setlerinde yüzler 15 piksel civarında ve
KADEME 2b'yi besleyemiyor (ölçüldü:
`benchmarks/expression_20260818-gun14.json`). Pexels klipleri yakın plan
yüz içerdiği için ifade sınıflandırmanın **çalıştığı koşulda çalıştığını**
gösterebiliyor.

**Lisans:** **Pexels License** — ücretsiz kullanım, atıf zorunlu değil,
ticari kullanım serbest. Bu projedeki tek kısıtsız kaynak.
https://www.pexels.com/license/

⚠ Dosya adları Pexels'in özgün kimliklerini koruyor
(`14720058_1920_1080_25fps.mp4`), böylece kaynak klip her zaman geri
bulunabilir.

---

## Ortak kurallar

| Kural | Uygulama |
|---|---|
| Veri git'e girmez | `data/_sources/*` ve `data/videos/*` `.gitignore`'da |
| Teslim paketi | Hiçbir kaynak video dahil edilmez |
| Rapor görselleri | Yalnızca **Pexels** ve **VIRAT** kaynaklı kareler kullanılır; Oxford Town Centre kullanılmaz (mahremiyet notu) |
| Normalize etme | `scripts/prepare_videos.py` — 720p / H.264 / 25 FPS |
| Kamera eşlemesi | `data/videos/manifest.json` |

## Kamera dağılımı (PLAN.md §7.1)

| Kamera | İçerik | Amaç |
|---|---|---|
| 01-08 | Normal sahne (otopark, kampüs, giriş) | Anomali modülünün "normal"i öğrenmesi |
| 09-13 | Kavga / saldırganlık | Saldırganlık modülü testi |
| 14-16 | Anomali (düşme, koşma, ters yön) | Anomali modülü testi |
| 17-18 | Boş sahne | Kademe 0 filtresinin yük düşürdüğünü ispatlamak |
| 19-20 | Yakın plan yüz | Duygu modülü testi |
| **21** | **Laptop webcam — canlı** | **Canlı demo** |
