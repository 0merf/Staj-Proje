# Bağımsız Hakem Denetimi — SENTINEL

> **Bu belge kasten acımasızdır.** Kullanıcının isteği: *"projeye
> bağımsız bir jüri, bir hakem, bu alanda uzman bir mühendismiş gibi
> incele ve eleştir."*
>
> Yazan: projeyi geliştiren asistan. Bu bir çıkar çatışmasıdır ve
> okuyucu bunu bilerek okumalı — kendi işini denetleyen biri, en
> rahatsız edici bulguyu bulmakta en isteksiz olandır. Aşağıdaki her
> madde **kod ya da ölçüm kanıtına** dayandırılmıştır; dayanmayanlar
> "kanıt yok" diye işaretlenmiştir.
>
> Tarih: 08.09.2026 · Denetlenen sürüm: `6cefa65`

---

## 0. Tek cümlelik hüküm

> **Bu proje bir ölçüm metodolojisi çalışması olarak güçlü, bir
> çalışan ürün olarak eksiktir — ve rapor bu ikisini karıştırırsa
> hakem tarafından haklı olarak reddedilir.**

Ölçüm tarafı gerçekten iyi: 56 problem kaydı, sistematik olarak
çürütülmüş varsayımlar, tek değişkenli kontrollü deneyler, bootstrap
güven aralıkları, ayrık tutulmuş doğrulama kümeleri. Bu, staj
seviyesinin belirgin üstünde.

Ürün tarafında ise **projenin adını taşıyan yetenek çalışmıyor.**

---

## 1. 🔴 ÖLÜMCÜL — Manşet yetenek üretimde YOK

### 1.1 Hiçbir öğrenilmiş model canlı boru hattında değil

```bash
$ grep -rln "lightgbm\|Booster\|r3d_18\|saldirganlik_lgbm" backend/src/
(çıktı boş)
```

Raporlanan bütün model sonuçları — K5 F1 **0.889**, R3D-18 **0.911**,
birleşim **0.937** — yalnızca `backend/scripts/` altındaki **çevrim dışı
değerlendirme betiklerinde** var. `src/sentinel/` içinde ne LightGBM ne
PyTorch video modeli çağrılıyor.

Canlı analiz worker'ı yalnızca şunları kullanıyor:

| bileşen | tür |
|---|---|
| `TirmanmaSkorlayici` | elle yazılmış kural |
| `KuralMotoru` (Katman B) | elle yazılmış kural |
| `NormalProfilDeposu` (Katman A) | öğrenilmiş profil (istatistik) |
| `RiskFuzyonu` | elle ağırlıklı toplam |
| `IfadeSinyali` | sınıflandırıcı çıktısı → elle eşleme |

**Hakem yorumu:** *"F1 = 0.889 elde ettik"* cümlesi, o modeli
çalıştırmayan bir sistemin raporunda **yanıltıcıdır.** Doğru ifade:
*"çevrim dışı değerlendirmede F1 = 0.889 ölçüldü; model üretim boru
hattına entegre EDİLMEDİ."* Bu ayrım yapılmazsa makale reddedilir,
staj raporu ise gerçeği yanlış beyan eder.

### 1.2 🔴 Canlı saldırganlık dedektörü SUSUYOR

Füzyondaki en yüksek ağırlık saldırganlıkta:

```python
# fusion.py
A_SALDIRGANLIK = 0.40   # "en spesifik sinyal"
```

K7 koşusunda (20 kamera, 600 sn, 39 alarm) alarm türü kırılımı:

```
crowd 15 · unusual 12 · loitering 6 · fall 6 · aggression 0
```

**Sıfır saldırganlık alarmı.** Kod `"type": "aggression"` üretebiliyor
(`worker.py:582`) ama üretmiyor.

Ve `diagnose_kural.py` sebebini gösterdi (P-52): skorun bileşen
kırılımında **0.60 ağırlık ölü, 0.30 ağırlık doymuş sabit** — yani
skorun %90'ı bilgi taşımıyor. Gerçek kavga videosunda ayırt etme oranı
**1.01** (şans).

**Hakem yorumu:** P-32'de kutlanan *"yanlış alarm 610 → 0"* sonucu,
şimdi başka türlü okunuyor: **dedektör susturularak elde edilmiş.**
Sıfır yanlış alarm, sıfır alarm demekse bu bir başarı değil.

⚠ Bu üç bulgu birlikte şu anlama geliyor: **şartnamenin üç YZ
görevinden biri — "saldırgan davranışın erken tespiti" — üretimde
işlevsel değil.**

---

## 2. 🔴 Başarı kriterleri — dürüst tablo

| # | Kriter | Durum | Hakem notu |
|---|---|---|---|
| K1 | ≥20 kamera | ✅ 20/20 | Ama **dosyadan** besleniyor, gerçek IP kamera yok |
| K2 | ≥4 FPS/kam | 🟡 2.75 | Hedefin %69'u |
| K3 | ≤1500 ms | ✅ p95 463 ms | Sağlam |
| K4 | 2 sa çökmesiz | ✅ | ⚠ Gün 18 düzeltmelerinin ÇOĞUNU içermiyor |
| K5 | F1 ≥0.85 | ✅ 0.889 | ⚠ **Üretimde değil** (§1.1) |
| K6 | AUC ≥0.75 | ✅ 0.867 | ⚠ Kazancın %91'i EMA'dan (P-41) |
| K7 | ≤3 yanlış alarm | 🟡 | **Yanlış alarm oranı DEĞİL** — yer gerçeği yok |
| K8 | ≥2 sn avans | ❌ | Tespit olaydan **+2.2 sn SONRA**; n=1 video |
| K9 | Güvenlik %100 | 🟡 17/19 | TLS yok, kamera bazlı yetki yok |
| K10 | ≥30 FPS UI | ⬜ | **Hiç ölçülmedi** |

**Hakem yorumu:** 10 kriterin **3'ü tam geçiyor** (K1 kısmen, K3, K4).
K5 ve K6 kâğıt üstünde geçiyor ama şartlı. K8 açıkça başarısız. K10
ölçülmemiş. Bir hakem bu tabloya bakıp *"sistem çalışıyor"* demez;
*"sistem ayakta duruyor, kararları zayıf"* der.

---

## 3. 🟠 METODOLOJİK ZAYIFLIKLAR

### 3.1 K8 tek videoya dayanıyor (n = 1)

Erken uyarı — projenin iddia ettiği **özgün katkı** — tek bir
UBI-Fights videosunda, tek bir temiz olay başlangıcında ölçüldü.
İstatistiksel bir sonuç değil, **vaka çalışması**. Üstelik yer
gerçeği bizim kendi gözle etiketlememiz; ikinci bir etiketleyici yok,
etiketleyiciler arası uyum (inter-annotator agreement) ölçülmedi.

### 3.2 Doğrulama kümesinde seçim yapılıyor — iki modelde de

- LightGBM: `en_iyi_esik` val'de aranıyor (belgelenmiş yanlılık)
- R3D-18: **en iyi devir** val AUC'sine göre seçiliyor — 12 devrin
  maksimumunu almak, tek eşik seçmekten güçlü bir yanlılık

Seçimsiz son devir 0.918/0.874; seçilmiş 0.937/0.911. Aradaki fark
(**+0.019 AUC**) tamamen seçim yanlılığı olabilir.

### 3.3 Doğrulama kümesi çok küçük (96 klip)

RWF-2000'in 400 kliplik val bölümünün yalnızca 96'sı kullanıldı
(`--klip 300` → sınıf başına 60 val). Bir hakem soracak: **neden
tamamı değil?** 96 klipte %95 güven aralıkları geniş; nitekim Mod A/B
farkı (+0.030) için aralık **[−0.001, +0.067]** çıktı — sıfırı kıl
payı içeriyor.

⚠ Ve **birleşim sonucu (0.968) hiç bootstrap'lenmedi.** Mod A/B için
yapılan istatistiksel titizlik, projenin en güçlü iddiasına
uygulanmadı. Bu tutarsızlık.

### 3.4 Çapraz doğrulama yok

Tek bir train/val bölünmesi. k-katlı çapraz doğrulama, bu boyuttaki
bir veri kümesinde standarttır ve yapılmadı.

### 3.5 Literatür karşılaştırması aynı zeminde değil

```
bizim (kendi bölünmemizde)      : 0.937 AUC / 0.911 F1
Flow-Gated Network (kendi böl.) : 0.8725 doğruluk
IDG-ViolenceNet   (kendi böl.)  : 0.894 doğruluk
```

Farklı bölünme, farklı ölçüt (AUC ⟷ doğruluk). **Bu tablo bir
karşılaştırma değildir.** Belgede uyarı var ama tablo yine de yan yana
basılıyor; hakem bunu "yanıltıcı sunum" sayabilir.

### 3.6 Kamera çiftliği gerçek değil

20 kamera, dosyadan sonsuz döngüyle beslenen sahte RTSP akışları.
Gerçek dağıtımda olan hiçbir şey yok: ağ gecikmesi ve dalgalanması,
paket kaybı, kamera yeniden bağlanması, farklı kodek/çözünürlük
karışımı, saat kayması. **K1 ve K4'ün dış geçerliliği sınırlı.**

### 3.7 Katman A profilleri sentetik veriden öğrenildi

"Her kameranın normali ayrı öğrenilir" mimari kuralı, döngüde
tekrarlanan aynı videodan öğreniyor. Gerçek bir kameranın normali
gün/gece, hafta içi/sonu, mevsim değişir. **Bu hiç sınanmadı.**

---

## 4. 🟠 MÜHENDİSLİK BORÇLARI

| # | Borç | Kanıt |
|---|---|---|
| 4.1 | **Ön yüz pratikte test edilmiyor** | 215 arka uç testine karşı **1 ön yüz test dosyası** (`sync.test.ts`), yalnızca zaman ekseni matematiği. Canvas/overlay çizimi test edilmiyor — oysa P-14 ve P-26 tam oradan çıkmıştı |
| 4.2 | **Uçtan uca test yok** | Playwright PLAN §14.1'de var, hiç kurulmadı. Sistemin "çalıştığı" elle doğrulanıyor |
| 4.3 | **ESLint kurulu değil** | Kalite kapısı yok; `npm run lint` kaldırıldı |
| 4.4 | **Klip zinciri gerçek kayıtla denenmedi** | `data/clips/` boş. Kod + 12 test var, **hiç gerçek video kesilmedi** |
| 4.5 | **TLS yok** | G18 hiç kurulmadı. Video akışı IP kısıtıyla korunuyor, kimlik doğrulamayla değil |
| 4.6 | **Kamera bazlı yetki yok** | G05: her kullanıcı tüm kameraları görüyor |
| 4.7 | **Rapor malzemesi eksik** | `screenshots/` → **1 dosya**. Mimari diyagram yok |

---

## 5. 🟡 TUTARSIZLIKLAR VE YARIM KALMIŞLAR

### 5.1 Uyarlanabilir taban eklendi ama işe yaramadı — yine de duruyor

P-52'de kamera başına uyarlanabilir ölü bölge tabanı eklendi. Ölçüldü:
etkin taban 1.529 → 1.438, cam-15 ayrımı **1.01 → 1.01**, RWF'de
**değişim yok**. Yani **hiçbir ölçülebilir fayda sağlamadı** ama kod
karmaşıklığı olarak kaldı.

**Hakem yorumu:** Gerekçe *"mimari kural 7'yi uyguluyor"* — savunulabilir
ama zayıf. Faydası ölçülemeyen bir soyutlama, bakım borcudur.

### 5.2 Kural yolu bilinçli olarak bozuk bırakıldı

P-52 sorunu teşhis etti, çözmedi. Ağırlık araması dejenere çıktı
(durus 1.00), F1 düştü, uygulanmadı. Sonuç: **projenin en yüksek
ağırlıklı sinyali bilinerek çalışmaz hâlde bırakıldı.**

Bu dürüst bir karar ama raporda **açıkça** yazılmalı, yoksa okuyucu
"füzyon 5 sinyali birleştiriyor" cümlesini okuyup bunların çalıştığını
sanar.

### 5.3 Duygu analizi kararda var ama etkisi ölçülmedi

İfade sinyali füzyona bağlandı (P-43) ve ağırlığı 0.10-0.15. Ama
**bağlandıktan sonra hiçbir kriter yeniden ölçülmedi** — K6 da K7 de
ifade bağlanmadan önceki koşulardan. Yani "duygu analizi karara
katkı sağlıyor" iddiasının **hiçbir ölçüm dayanağı yok.**

### 5.4 Ölçümler farklı kod sürümlerinden

K4 (dayanıklılık) Gün 18 düzeltmelerinden önce koşuldu — belgede
yazılı. K6 ve K7 ifade bağlanmadan önce. K5/K8 bugünkü kodla. **Hiçbir
kriter aynı sürümde ölçülmedi**; rapor bir "sistem" tablosu sunacaksa
bu tablo hiçbir zaman var olmamış bir sürümü tarif ediyor.

---

## 6. 🟢 GERÇEKTEN İYİ OLANLAR

Dürüst bir hakem güçlü yanları da yazar:

1. **56 problem kaydı ve çürütülmüş varsayımlar.** Bu, staj
   projelerinde neredeyse hiç görülmez ve makalenin asıl katkısı.
2. **Ölçüm aracı hatalarının sistematik dökümü.** On kez ölçüm
   aracının kendisi suçlu çıktı; bunların taksonomisi (girdi hatası →
   tasarım hatası → ölçütün tanımı → yer gerçeğinin tanımı) özgün.
3. **Tek değişken disiplini.** `--haric-onek` bayrağı, ortak klip
   kümesine indirgeme, alt süreçte eğitim — hepsi kontrollü
   karşılaştırma için eklenmiş.
4. **Bootstrap güven aralıkları.** Staj seviyesinde nadir.
5. **Negatif sonuçların raporlanması.** K8 tutmuyor, kaskad
   kazandırmıyor, kural yolu çökük — hepsi yazılmış.
6. **Mimari kararların gerekçelendirilmesi.** 11 ADR.
7. **Birleşim bulgusu (§P-54)** gerçekten değerli: hata örtüşmesi %10,
   birleşim +0.031 F1.

---

## 7. HAKEMİN SORACAĞI SORULAR (rapordan önce cevaplanmalı)

1. *"F1 = 0.889 diyorsunuz; bu modeli çalıştıran kod nerede?"*
2. *"Saldırganlık füzyonda 0.40 ağırlıkta ama K7'de sıfır alarm
   üretmiş. Bu sinyal çalışıyor mu?"*
3. *"K8 tek videoda ölçülmüş. Neden 400 kliplik val kümesinin
   tamamında değil?"*
4. *"Birleşim +0.031 F1 veriyor; güven aralığı nedir?"*
5. *"Literatürle karşılaştırma farklı bölünmelerde. Neden kendi
   verinizde onların yöntemini koşturup karşılaştırmadınız?"* (→
   R3D-18 için yapıldı, Flow-Gated için yapılmadı)
6. *"20 kamera gerçek IP kamera mı?"*
7. *"K10 neden ölçülmedi?"*

---

## 8. RAPORA GİRMEDEN ÖNCE YAPILMASI GEREKENLER

### Zorunlu (yapılmazsa rapor yanlış beyan olur)

- [ ] **§1.1 ve §1.2 raporda açıkça yazılacak.** "Model çevrim dışı
      değerlendirildi, üretime entegre edilmedi." "Saldırganlık kural
      yolu gerçek görüntüde ayırt etmiyor."
- [ ] Her ölçümün **hangi kod sürümünde** yapıldığı tabloya eklenecek
- [ ] Literatür tablosu "aynı zeminde değil" uyarısıyla ayrılacak

### Yüksek değerli (yapılabilirse yapılmalı)

- [ ] **Birleşim için bootstrap GA** — en güçlü iddia, en zayıf
      istatistik
- [ ] **LightGBM'i üretime entegre etmek** — 0.0004 ms maliyet, K5'i
      gerçek yapar
- [ ] **K10 ölçümü** — 30 dakikalık iş
- [ ] Val kümesini 400 klibe çıkarmak
- [ ] İfade bağlandıktan sonra K6/K7'yi yeniden ölçmek

### İsteğe bağlı

- [ ] Çapraz doğrulama · Playwright · ESLint · TLS · ekran görüntüleri

---

## 9. Hakemin kapanış cümlesi

> Bu proje, **kendi ölçümlerini denetlemeyi öğrenmiş** bir mühendislik
> çalışması. Bulduğu şeylerin çoğu, aradığı şeyler değildi — ve bunu
> gizlemek yerine kayda geçirmiş olması, sonuçlarından daha değerli.
>
> Ama aynı titizlik **entegrasyona** uygulanmamış. Ölçülen model
> koşmuyor, koşan model ölçülmüyor. Rapor bu boşluğu kapatmazsa,
> okuyucu var olmayan bir sistemi okumuş olur.
>
> **Öneri:** makale, ölçüm metodolojisi ve birleşim bulgusu üzerine
> kurulsun; "çalışan 20 kameralı sistem" iddiası ikincil ve şartlı
> sunulsun.
