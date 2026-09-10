# Makale İskeleti — CDEJ

**Dergi:** Siber Güvenlik ve Dijital Ekonomi Dergisi (CDEJ), Düzce Üniversitesi
**Şablon:** `templateCDEJ_ENG.docx` · Cambria · APA atıf · sayfa numarası yok
**Tür:** Research Article · **Dil:** Türkçe (Öz + İngilizce Abstract)
**Yazar:** tek

---

## Makalenin tezi — tek cümlede

> Orta seviye tek bir GPU'ya sıkıştırılmış çok kameralı bir gözetim
> sisteminde, başarım ve doğruluk iddialarının çoğu **sistemin
> kendisinden değil, ölçüm aracının doğrulanmamasından** kaynaklanan
> hatalar taşır; bu çalışma tek bir sistemin geliştirilmesi boyunca
> ortaya çıkan bu hataları belgelemekte ve her biri için düzeltme
> yöntemini göstermektedir.

**Neden bu tez:** "20 kamera izleyen sistem yaptık" tek başına yeni
değil. Bizim elimizde olan farklı: **kısıtlı bir donanımda** çalışan
bir sistem ve onun ölçülmesi sırasında biriken, **87 kayıtlık
belgelenmiş hata günlüğü**. Klasik "sistem + değerlendirme"
kurgusunda K2/K8/K10 sonuçlarımız "zayıf" görünür; ölçüm-yöntemi
kurgusunda ise **bulgu** olurlar.

**İkinci eksen — dergi siber güvenlik dergisi:** güvenlik tarafında
aynı kalıp iki kez çıktı (P-37, P-86) ve ikisi de aynı şeyi söylüyor:
*"korunuyor" demek "her uç korunuyor" demek değildir.*

---

## Başlık adayları

1. **Kısıtlı Donanımda Yirmi Kameralı Gerçek Zamanlı Gözetim Sistemi: Başarım ve Doğruluk İddialarının Ölçülebilirliği Üzerine Bir Vaka Çalışması**
2. Tek GPU Üzerinde Çok Kameralı Anomali ve Saldırganlık Tespiti: Ölçüm Tasarımının Sonuçlar Üzerindeki Etkisi
3. Gözetim Sistemlerinde Ölçülemeyen Ölçütler: Yirmi Kameralı Bir Uygulamada Kriter–Veri Uyuşmazlıkları

→ **1 numaralı öneriliyor.** Hem sistemi hem tezi taşıyor.

**Anahtar kelimeler (3–5):** Video gözetim, Anomali tespiti, Kenar
hesaplama, Ölçüm geçerliliği, Sistem güvenliği

---

## I. GİRİŞ  (~900 kelime)

1. **Bağlam.** Çok kameralı akıllı gözetim; kurumların elindeki
   gerçek kısıt: sınırsız bulut değil, tek makine.
2. **Problem.** Literatürde bildirilen doğruluk ve gecikme değerleri
   çoğunlukla *tek modelin, tek akışın, izole* ölçümüdür. 20 akışın
   tek GPU'da paylaştığı bir sistemde bu sayılar taşınmaz.
3. **Bu çalışmanın kapsamı ve KISITLARI — baştan.**
   - Gerçek IP kamera yok; 20 kamera **döngüdeki video dosyalarından**
     simüle edildi (Tablo: kamera–kaynak eşlemesi)
   - Donanım: tek RTX 3070 Laptop (8 GB), 20 mantıksal çekirdek
   - Süre: 25 iş günü, tek geliştirici
   - ⚠ Bu kısıtlar bir mazeret değil, **araştırma ortamının tanımı**;
     sonuçların hangi koşulda geçerli olduğunu belirliyorlar.
4. **Katkılar (madde madde).**
   - (a) Kısıtlı donanımda çalışan, uçtan uca ölçülmüş bir mimari
   - (b) İki bağımsız modelin birleşiminin ölçülmüş kazancı ve
     **mekanizmasının** gösterilmesi (hata örtüşmesi %10)
   - (c) **Ölçüt–veri uyuşmazlığı** kavramının üç somut örneği
     (K7, K8, K10)
   - (d) Tek giriş noktalı bir mimaride **envanter eksikliğinden**
     doğan güvenlik açığı ve kapatılması
5. **Makalenin planı.**

**Kaynaklar:** LITERATUR.md'den 25–35 atıf (YOLO, BoT-SORT, RWF-2000,
Avenue, UR Fall, UBI-Fights, WebRTC/WHEP, TimescaleDB, ölçüm
geçerliliği literatürü).

---

## II. MATERYAL VE YÖNTEM  (~2200 kelime)

### A. Sistem mimarisi
- **Şekil 1:** Veri akışı (`01-veri-akisi.svg`) — üzerinde ölçülmüş
  sayılarla
- Beş süreç: alım → çıkarım → analitik → alarm → API/panel
- **Tasarım kuralları ve gerekçeleri** (her biri bir kısıttan doğdu):
  - Ham kare mesaj kuyruğundan geçmez (1080p ≈ 6 MB) → paylaşımlı
    bellek + referans
  - Sunucu videoya kutu çizmez → WHEP video ayrı, kutular WebSocket
  - Modeller tek süreçte tek kopya (VRAM)
  - Her kuyruk sınırlı

### A.1. Kademeli işleme
- **Şekil 2:** Kademe hunisi + maliyet dağılımı (`02-kademeli-isleme.svg`)
- KADEME 0 hareket kapısı → 1 tespit → 1b takip → 2a poz → 2b yüz/ifade
- **Tablo 1:** Aşama kırılımı (§2 envanter) + **kapanış kontrolü**
- ⚠ KADEME 3 planlandı, kodlanmadı — açıkça belirtilecek

### B. Veri setleri ve yer gerçeği
- **Tablo 2:** RWF-2000, Avenue, UR Fall, UBI-Fights + kamera çiftliği
- Her biri hangi kriteri besliyor
- ⚠ Elle üretilen etiketler: 20 klip (K8), 40 alarm (K7); tek
  değerlendirici; değerlendirici beyanı (tepki gecikmesi)

### C. Ölçüm yöntemi  ⬅ **makalenin ayırt edici bölümü**
- **C.1. Kümülatif histogramdan pencere farkı** — neden zorunlu
- **C.2. Duvar saati ≠ CPU zamanı** — `thread_time`, BLAS thread havuzu
- **C.3. Kapanış kontrolü** — parçaların toplamı bağımsız ölçülen
  toplama eşit mi
- **C.4. Kontrol serisi** — K10'da 0 kamera, K6'da katman_a+EMA
- **C.5. Bağımsızlık birimi** — kare mi klip mi; küme bootstrap'ı
- **C.6. Eşik seçim yanlılığı** — tekrarlı yarı-yarıya bölme
- **C.7. Kazananın laneti** — N kural arasından seçim
- **Tablo 3:** Ölçüm hatası türleri ve düzeltme yöntemi (özet)

### D. Güvenlik yaklaşımı
- Öncelik-1 listesi (G01–G20), tek giriş noktası (Caddy + forward_auth)
- **Şekil 3:** Kimlik doğrulama akışı (video dâhil)

---

## III. BULGULAR VE TARTIŞMA  (~3000 kelime)

### A. Başarım
- **Tablo 4:** Kriterler ve ölçülen değerler (§1 envanter)
- **A.1. Darboğaz nerede:** GPU %41, VRAM %7, 19 çekirdek boşta →
  sınır **mimari** (seri döngü), donanım değil
- **A.2. Arz–talep açığı:** 56.8 yayın / 46.8 işleme → %17.5
- **A.3. Girdiyi artırmak çıktıyı DÜŞÜRDÜ** (4→8 FPS: 2.78→1.88)
  → müdahaleli deneyin gözlemsel veriye üstünlüğü
- **A.4. TensorRT:** 1.61× izole, üretimde parti boyutunda kırılıyor
- **A.5. Tek satırlık ayarın etkisi** (slot havuzu) ve
  **tekrar üretilememesi** (P-82) — dürüstçe

### B. Doğruluk
- **B.1. Şiddet tespiti (K5):** Tablo 5 — tek modeller vs birleşim,
  güven aralıkları, eşik yanlılığı, kazananın laneti
  - ⭐ **Mekanizma:** hata örtüşmesi %10 → birleşim neden kazanıyor
- **B.2. Anomali (K6):** Tablo 6 — füzyon vs kontrol serisi
  - ⭐ **Çürütülen iddia:** kazandıran birleştirme değil yumuşatma
  - Küme GA vs kare GA farkı (%54 daha geniş)
- **B.3. Alarm kesinliği (K7):** Tablo 7 — tür bazında
  - ⭐ Zayıf halka `fall` 3/5; her iki hata da aynı mekanizma
  - Toplu sayının bulguyu gizlemesi

### C. Ölçüt–veri uyuşmazlığı  ⬅ **makalenin en özgün bölümü**
- **C.1. K8:** ölçütün **tavanı** hedefin altında (0.58 < 2.00 sn)
  - Kusursuz bir dedektör bile geçemez
  - İki bağımsız veri setinde aynı sonuç
- **C.2. K10:** ölçütün **eşiği** kuantalama basamağında
  - vsync 60/30/20/15 → "≥30" ayırt edici değil
- **C.3. K7:** ham oran **video uzunluğunu** ölçüyor
  - 39 alarm → 19 bağımsız olay
- **Tablo 8:** Üç uyuşmazlık türü ve genel kural

### D. Güvenlik bulguları
- **D.1. P-37:** API korunuyordu, video korunmuyordu
- **D.2. P-86:** tek giriş noktası kuruldu, envanter çıkarılmadı →
  `/metrics` dışarıya açık
  - ⚠ Denetim aracının kendisi eksik ölçtü
- **D.3. Ölü ayarların güvenlik beyanı olarak yanlışlığı**
- **Tablo 9:** G01–G20 durumu, kapsam dışı bırakılanlar gerekçesiyle

### E. Sınırlar — ayrı ve açık bir alt bölüm
1. Gerçek IP kamera yok; döngüdeki dosyalar
2. Tek değerlendirici; uyum katsayısı yok
3. Duyarlılık (recall) ölçülmedi — yalnız kesinlik
4. K4 eski kod sürümünde
5. Kaynak videoların bir kısmı **derleme** (sahne kesikli) → "kamera
   normali" varsayımını zorluyor
6. Tek donanım; taşınabilirlik ölçülmedi

---

## IV. SONUÇ  (~700 kelime)

- Ne yapıldı, hangi kısıtla, hangi sonuçla (tekrar etmeden)
- **Ulaşılamayan hedefler ve nedenleri** — K2, K8, K10
- **Genellenebilir kural:** bir ölçütü raporlamadan önce
  (a) tavanını, (b) çözünürlüğünü, (c) bağımsızlık birimini kontrol et
- Gelecek çalışma: çıkarım döngüsünün paralelleştirilmesi, tırmanma
  için uygun veri seti, çok değerlendiricili etiketleme, gerçek IP
  kamera ile doğrulama

---

## BEYANLAR
- Teşekkür · Yazar katkısı (tek yazar) · Çıkar çatışması (yok)
- Destekleyen kurum (yok) · Etik onay (insan/hayvan katılımcı yok)
- İntihal beyanı
- **⚠ Yapay zekâ araçları beyanı** — açık ve ayrıntılı yazılacak

## KAYNAKLAR
APA · `LITERATUR.md`'den

---

## Şekil ve tablo listesi

| # | İçerik | Kaynak |
|---|---|---|
| Şekil 1 | Veri akışı + ölçülmüş maliyetler | `diagrams/01-veri-akisi.svg` |
| Şekil 2 | Kademeli işleme + maliyet dağılımı | `diagrams/02-kademeli-isleme.svg` |
| Şekil 3 | Kimlik doğrulama akışı (video dâhil) | **yeni çizilecek** |
| Şekil 4 | Panel ekran görüntüsü (canlı kutular) | `screenshots/03-canli-kutular.png` |
| Şekil 5 | Klip zinciri doğrulaması (düşme dizisi) | `screenshots/07-klip-zinciri-dogrulama.png` |
| Şekil 6 | K8 ölçüt tavanı grafiği | **yeni çizilecek** |
| Tablo 1 | Aşama kırılımı + kapanış kontrolü | envanter §2 |
| Tablo 2 | Veri setleri ve yer gerçeği | — |
| Tablo 3 | Ölçüm hatası türleri | problems.md sentezi |
| Tablo 4 | Kriterler ve sonuçlar | envanter §1 |
| Tablo 5 | K5 modeller + GA + yanlılık | envanter §4 |
| Tablo 6 | K6 füzyon vs kontrol | envanter §5 |
| Tablo 7 | K7 tür bazında kesinlik | envanter §6 |
| Tablo 8 | Ölçüt–veri uyuşmazlığı türleri | §C sentezi |
| Tablo 9 | Güvenlik durumu G01–G20 | PLAN §11.1 |
