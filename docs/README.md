# Yapay Zekâ Destekli Lojistik Anahat (Linehaul) Optimizasyonu

> **TEKNOFEST 2026 — HepsiJET / Akıllı Ulaşım**
> Gelişmiş Çözüm Aşaması — Nihai Rapor
>
> _2. aşama (Temel İşlevli Çözüm / MVP) raporu için: [`experiments/asama2_mvp/ASAMA_2_RAPOR.md`](experiments/asama2_mvp/ASAMA_2_RAPOR.md)._

---

## 0. Yönetici Özeti

Hepsiburada/HepsiJET'in anahat (middle-mile) operasyonunda, **18 transfer merkezi (TM)** arasındaki
**289 hattın** gelecek bir haftalık **desi** talebini önce tahmin ediyor, sonra bu talebi **zorunlu
kiralık filo** ile **sınırsız spot araç havuzu** arasında en düşük maliyetle çizelgeliyor ve konsolide
ediyoruz — elleçleme kotası, tır kotası, SLA kısıtları **ve diğer kısıtlar** altında (donanım ortamı da
dahil: jüri değerlendirmesi **4 çekirdek / 16 GB RAM** ile yapılıyor, §10).

Çalışmayı 2. aşamada olduğu gibi bir **araştırma/tez çalışması disipliniyle** yürüttük: her adımda tek bir
hipotez kurduk, izole bir deneyle ölçtük, sonuca göre karar verdik ve belgeledik. Bu sayede tahmin
tarafında **20**, optimizasyon tarafında **25** olmak üzere toplam **45 versiyonlu deney** ürettik; her
birinin etkisini tek tek ayrıştırdık. Tüm deneyler
`experiments/asama3_gelismis/` altında, her versiyonun kendi kodu, `experiment.md`'si ve çıktı dosyasıyla
saklıdır. Bu aşama 2. aşamadan **tamamen farklı bir problemdir** (gün → gün+saat, 89 → 289 hat, basit
bin-packing → kotalı çizelgeleme); önceki aşamanın modelleri burada iş yapmaz, taşınan tek şey **çalışma
biçimidir**.

**En kritik ilke (2. aşamadan devralınan, burada da geçerli):** Sonucun kalitesi büyük ölçüde **tahmin
doğruluğuna** bağlıdır — az tahmin edersek gerçekte gelen yükün bir kısmı planımızda hiç yer almaz, çok
tahmin edersek boşuna araç çağırırız (fazla maliyet). Ama bu aşamada jüri kuralı bir nüans ekledi:
**optimizasyon başarımız bizim kendi tahminimiz üzerinden**, tahmin doğruluğumuz ise gerçek talep ile
**ayrı ayrı** puanlanıyor. Bu yüzden strateji nettir: tahmini olabildiğince doğru yap (ayrı puanlanıyor),
SLA'yı **çizelgeleme kararlarıyla** yönet (2. aşamadaki P90-tampon mantığı burada geçersiz).

> **Bu raporda "SLA cezası" ne demek — sınırını net çizelim.** Bizim hesapladığımız ve bu raporun her
> yerinde geçen SLA cezası **tek bir şeydir: taşıdığımız yükün geç teslim edilmesi.** Formülü şartnamede
> verilmiştir: `Geciken Desi × ⌈Gecikme Saati⌉ × 0,40 TL` (§1.4). Yani ceza, **plana giren bir talebin,
> araçla taşınıp varış TM'sine hedef saatten sonra ulaşması** hâlinde doğar; muhasebesi araç–desi–saat
> üçlüsü üzerinden yapılır.
>
> **Eksik tahminin cezası bu kalemin içinde DEĞİLDİR** — ve olamaz da: tahmin etmediğimiz bir talebin
> ne desisi ne de gecikme saati bizde vardır, çünkü o talep bizim optimizasyon girdimizde hiç yoktur.
> Şartname de eksik tahmin için ayrı bir katsayı/ceza kalemi vermemiştir. Kavramsal olarak eksik tahmin
> **elbette bir hizmet düzeyi (servis) başarısızlığıdır** — gerçek hayatta o yük ortada kalır ve müşteriye
> geç ulaşır. Ancak yarışmanın puanlama kurgusunda bu başarısızlık, **optimizasyon skorundan değil,
> tahmin doğruluğu skorundan** düşer: jüri bizim tahminimizi gerçek taleple karşılaştırıp ayrıca
> puanlıyor (WAPE/hata cinsinden). Kısacası iki farklı kalem, iki farklı puan:
>
> | Başarısızlık türü | Nerede cezalanır | Bizim hesabımızda var mı |
> |---|---|---|
> | Taşıdığımız yükü geç teslim etmek | **Optimizasyon skoru** — SLA cezası (desi × saat × 0,40 TL) | ✅ evet, tüm rakamlarımıza dahil |
> | Talebi eksik/hiç tahmin etmek | **Tahmin doğruluğu skoru** — jüri gerçek taleple kıyaslar | ❌ hayır (girdimizde o talep yok) |
> | Talebi fazla tahmin etmek | **Optimizasyon skoru** — boşuna araç → fazla araç maliyeti | ✅ evet, dolaylı olarak maliyete yansır |
>
> Bu ayrımı bilerek yaptık ve stratejimizi buna göre kurduk: eksik tahmini "tamponla" gizlemek yerine
> (2. aşamada P90 tamponu böyle çalışıyordu) tahmini **olduğu gibi doğru** kılmaya, gecikmeyi ise
> çizelgelemeyle yönetmeye odaklandık. §8'de anlattığımız P90 kolu da bu yüzden bir *güvence senaryosu*
> olarak durur, teslim ettiğimiz ana plan değildir.

### Nihai sonuç

> **Çekirdek (çalışma ortamı) hakkında bir not.** Yarışma şartnamesi, tüm takımların **eşit koşullarda**
> değerlendirilmesi için değerlendirmenin standart bir bulut konteynerinde — **4 çekirdek CPU / 16 GB
> RAM** — yapılacağını belirtti. Bu bir donanım kısıtıdır ve doğrudan **hem çalışma süresini hem çözüm
> kalitesini** etkiler: bir optimizasyon çözücüsü ne kadar çok çekirdek kullanırsa aynı sürede o kadar
> geniş arama yapar. Bu yüzden çözümü yalnız tek bir donanımda değil, kendi makinemizde (i7-12700H)
> **4, 8 ve 10 çekirdekle ayrı ayrı** ölçtük; çekirdek sayısının süreye ve maliyete etkisini
> deneylerle çıkardık (§10.2). Aşağıdaki "uçtan uca süre" ve nihai maliyet, jüri donanımını (4 çekirdek)
> yansıtır; dashboard/sunum koşuları ise yerel makinede tüm çekirdekleri kullanabilir.
>
> **WAPE'de iki ayrı sayı göreceksiniz — ikisi de doğru, farklı ölçüm kurulumlarıdır.** Tabloda
> **%25,2** yazan değer, modelin **rolling-origin (6 haftalık) çapraz-doğrulama ortalamasıdır** — yani
> "6 farklı hafta üzerinde ortalama performans", en dürüst göstergemiz (§4.3). Rapor içinde yer yer
> **%24,4** gibi değerler geçerse, onlar **tek bir hafta** (22–28 Haziran) üzerinde ölçülen değerlerdir;
> hangisinin hangisi olduğu her yerde belirtilmiştir.

|                                                                            | Değer                                                                                                                               |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **Talep tahmini** (şampiyon f_v13 = EWMA + takvim düzeltmesi)      | RMSSE **0,59** · MASE **0,65** · WAPE **%25,2** · Bias **−%1,2** _(rolling-origin, 6 fold ortalaması)_ |
| **Optimizasyon** (şampiyon o_v13 = pickup'lı, 4 çekirdek / 60 sn) | **10.381.178 TL** (araç 10,13M + SLA 0,25M), 0 kısıt ihlali                                                                 |
| **Uçtan uca süre** (jüri donanımı: 4 çekirdek / 16 GB)         | tahmin ~15 sn + optimizasyon ~370 sn ≈ **6,4 dk**                                                                              |
| **P90 güvence kolu** (talebin üst bandına kapasite ayırma)       | 15.573.519 TL (raporlanır, teslim edilmez)                                                                                          |

**Optimizasyonun bilimsel izi (maliyet, milyon TL):** 47,81 (naïve, geçersiz) → 21,65 (greedy) →
13,10 (Clarke-Wright multi-drop) → 12,43 (tır multi-drop + column-generation) → 12,11 (aktarma/hub) →
11,43 (09:00→17:00 bekletme) → **9,96** (ara durakta yükleme / pickup, 8 çekirdek). Yani her versiyon bir
öncekinin bıraktığı israfı hedef aldı; son büyük sıçrama, jürinin bir soru-cevabından doğdu (§B.9).

**Üretim kodu `core/` altında dataset-değiştirilebilir kurulmuştur:** dosyalar desenle bulunur,
anomaliler veriden tespit edilir, backtest penceresi otomatik seçilir. Final aşamasında yeni veri
klasöre atılıp betikler çalıştırıldığında sistem kendini yeni tarih aralığına uyarlar — kod değişmez.

### Takım

| Üye             | Rol                                                                                                |
| ---------------- | -------------------------------------------------------------------------------------------------- |
| **Ömer**  | Takım Kaptanı — Talep Tahmini (ML), Optimizasyon, Sistem Entegrasyonu, API                      |
| **Zeynep** | Backend & Dashboard — PostgreSQL şeması, ASP.NET MVC arayüz, harita/Gantt/KPI görselleştirme |

Bu rapor üç bölümden oluşur: **A. Talep Tahmini**, **B. Optimizasyon**, **C. Sistem & Dashboard**.

---

## 1. Problem ve Veri Seti

**Amaç:** 6 aylık geçmiş veriyle **29 Haziran – 5 Temmuz 2026** haftasının talebini, her (hat, gün, saat)
için tahmin etmek ve bu talebi araçlara en düşük maliyetle atamak.

### 1.1 Bu aşama 2. aşamadan ne kadar farklı

|              | 2. aşama (MVP)          | **3. aşama (Gelişmiş)**                                  |
| ------------ | ------------------------ | ----------------------------------------------------------------- |
| Granülerlik | gün                     | **gün + saat** (09:00 / 17:00)                             |
| Hat sayısı | 89                       | **289**                                                     |
| Mesafe       | haversine (kuş uçuşu) | **gerçek km + araç-tipi seyir süreleri**                 |
| Kısıt      | basit bin-packing        | **elleçleme kotası + tır kotası + SLA + konsolidasyon** |
| Zaman        | —                       | **dakika çözünürlüğü**, TM'ler 24 saat açık        |

### 1.2 Veri dosyaları

| Dosya                                | İçerik                                                                          |
| ------------------------------------ | --------------------------------------------------------------------------------- |
| `teknofest26_gelismis.xlsx`        | Talep: 66.024 kayıt, 179 gün (01 Oca → 28 Haz), 18 TM, 289 hat                 |
| `sehirler_arasi_lojistik.xlsx`     | TM çiftleri arası mesafe (km) + araç-tipi seyir süresi + SLA günü (24/48 s) |
| `Araç_Kapasite_Maliyet_Saat.xlsx` | 4 araç tipi: kapasite + saatlik kira + km maliyeti (spot/kiralık ayrı)         |
| `Kiralık_Araclar.xlsx`            | Sabit kiralık filo (14 araç/gün, tanımlı hatlar)                             |
| `Ellecleme-kapasite.xlsx`          | TM başına günlük elleçleme (desi) kotası                                    |
| `tir_kapasiteleri v2.xlsx`         | TM başına günlük tır yanaşma kotası (jüri 10 Tem'de güncelledi)          |

**Dosyaları "desenle" bulmak — neden ve nasıl.** `core/config.py`, bu dosyaları tam adıyla değil,
**isim kalıbıyla** arar. Yani `Araç_Kapasite_Maliyet_Saat.xlsx` dosyasını açarken "tam olarak bu adı
bul" demiyoruz; "içinde _kapasite_ ve _maliyet_ geçen bir Excel bul" diyoruz. Kod açısından fark şu:

```
İsimle (kırılgan) :  pd.read_excel("Araç_Kapasite_Maliyet_Saat.xlsx")   → ad değişirse PATLAR
Desenle (dayanıklı):  desen "*apasite*aliyet*.xlsx" ile eşleşeni bul     → ad değişse de BULUR
```

Bunu neden yaptık: **final aşamasında jüri yeni bir veri seti verecek** ve dosya adları farklı olabilir
(`arac_maliyet_2026.xlsx` gibi). Desenle arama sayesinde kod bir satır bile değişmeden yeni veriyle
çalışır. Aynı dayanıklılık ilkesini **anomali/tatil tespitinde** de uyguladık: tatilleri kodun içine
tarih olarak yazmak yerine (`if tarih == '2026-05-26'`), **veriden ampirik** buluyoruz — bir gün, o
haftanın-gününün normal medyanının %35'inin altına düşüyorsa "anomali" (tatil/kapanış) sayılıyor. Böylece
sürpriz veri setinde, o dönemin tatilleri hangi tarihlerse, model onları **kendiliğinden** tespit eder.
Özetle sistemin tasarım hedefi: **"yeni veriyi klasöre at, betiği çalıştır, gerisini kod halletsin."**

### 1.3 Araç tipleri ve maliyet formülü

Şartnamenin verdiği **araç maliyeti** formülü şudur:

```
Araç maliyeti = Saatlik Kira × Kullanım Süresi + Mesafe × km maliyeti
Kullanım Süresi = elleçleme + bekleme + seyir   (üçü ayrı toplanır)
```

| Tip          | Kapasite (desi) | Kiralık TL/s | Spot TL/s |
| ------------ | --------------- | ------------- | --------- |
| Tır         | 22.400          | 291,67        | 487,50    |
| Kamyon       | 12.000          | 208,33        | 318,25    |
| Hafif Kamyon | 7.200           | 208,33        | 364,58    |
| Kamyonet     | 5.600           | 156,25        | 197,92    |

> **Değerler neden ondalıklı?** Saatlik kiralar günlük ücretin 24'e bölünmüş halidir (ör. kiralık Tır
> 7.000 TL/gün ÷ 24 = **291,6667** TL/saat). Excel bu hücreleri sütun genişliği yüzünden yuvarlayıp
> "292" gösterebilir, ama dosyadaki gerçek değer ondalıklıdır ve kod her zaman gerçek değeri okur.

**Değerlendirme skoru = araç maliyeti + SLA cezası.** Yukarıdaki formül yalnız **araç maliyetidir**; buna
ayrı bir kalem olarak SLA cezası (`Geciken Desi × ⌈Gecikme Saati⌉ × 0,40 TL`, §1.4) eklenir. Rapordaki
"toplam maliyet" rakamları hep bu ikisinin toplamıdır (ör. 10,13M araç + 0,25M SLA = 10,38M).

**Bir gözlem — israfın kaynağı.** Bu formülde "aracı kullandığın için" düz bir sabit ücret yoktur; yalnız
kullandığın süre ve gittiğin km için ödersin. Bunun pratik sonucu şu: bir sefer çıktığında km + seyir
"tabanını" **yük ne olursa olsun** ödersin (İstanbul→Mardin 1.548 km ≈ 27.864 TL sadece km — içinde 1 desi
de olsa 20.000 desi de olsa aynı). Optimizasyon bölümündeki (§B) kazançların çoğu, bu tabanı gereksiz yere
tekrar tekrar ödemeyi önlemekten gelir: yükleri tek sefere toplamak (konsolidasyon), bir aracı yol üstünde
doldurmak (multi-drop/pickup) hep aynı tabanı bir kez ödeme fikridir.

### 1.4 Kritik kurallar (resmî soru-cevap oturumlarından netleşen)

- **Talep:** her gün 2 sabit saat (09:00, 17:00). Her (hat, gün, saat) için ayrı tahmin + **Talep ID**
  (D00001). Bölünürse D00001-1, tekrar bölünürse D00001-1-1. **ID'leri biz üretiyoruz**, tahmin ve plan
  dosyalarında birebir eşleşmeli. 0,5 desi altı tahmin bile satır olarak sunulmalı.
- **Elleçleme:** 0,01 dk/desi, çıkış + varış ayrı. TM başına günlük desi kotası (00:00 sıfırlanır); her
  indirme + her yükleme ayrı düşer. **Gece yarısını aşan işlem oransal bölünür** (23:30'da 10.000 desilik
  işlem → o gün 3.000, ertesi gün 7.000).
- **Tır kotası:** TM başına günlük yanaşma sayısı; yalnız "Tır" tipini kapsar (7 TM'de kota 0 → tır
  giremez). **Merkezden ayrılmadan tekrar yükleme = tek yanaşma** (bu cevap §B.9'un temelidir).
- **SLA:** başlangıç = orijinal çıkış TM'de talep tamamlanma anı; bitiş = orijinal varış TM'de elleçleme
  bitişi. **Ceza = Geciken Desi × ⌈Gecikme Saati⌉ × 0,40 TL.** Gecikme saati **yukarı yuvarlanır** —
  yani **1 dakika gecikme bile 1 saatlik ceza** yazdırır (⌈⌉ tavan işlemi). Bilinçli geciktirme serbest
  (ucuzsa beklet).
- **Kiralık:** sabit hat, uğrama/dönüş yok, talep olmasa da her gün çıkmak zorunlu. **Spot:** dönüş var,
  multi-drop var, gün içi sınırsız sefer.
- **Ufuk:** 29 Haz 09:00 – 5 Tem 17:00. Teslimat pencere dışına taşabilir (5 Tem talebi 7 Tem'de teslim
  edilebilir; SLA ona göre). Optimizasyon zaman sınırı yok — **runtime puanlamaya girer** (§B.10).
- **Süre/çıktı formatı (soru-cevaptan):** Çıkış/Varış saati **SS:DD** yeterli; süre sütunları **dakika ve
  en yakın büyük tam sayıya yuvarlanmış** (0,92 saat = 55,2 dk → 56).

---

## 2. Metodoloji — Bir Araştırma/Tez Çalışması Disipliniyle

2. aşamada olduğu gibi bu aşamada da her adımı, bir araştırma/tez çalışmasının döngüsüyle kurduk:
**hipotez → izole deney → ölç → karar → raporla**. Yani "şunu denesek daha iyi olur mu?" diye bir
hipotez kurduk, onu diğer her şeyi sabit tutarak izole bir deneyle ölçtük, sonuca göre karar verdik ve
her adımı (kodu + `experiment.md`'siyle) belgeledik. Bir sonraki versiyon hep bir öncekinin bıraktığı
soruya cevaptır. Bu aşamanın farkı, **iki ayrı zincirin** (tahmin ve optimizasyon) aynı disiplinle,
paralel ilerlemesidir. Genel akış:

```
[6 aylık geçmiş talep]
      │
      ▼
[① TALEP TAHMİNİ]   f_v1..f_v7 (nokta) → f_v8 (rolling-origin CV) → f_v9..f_v14 (yeni bilgi)
      │                → f_v13 şampiyon (EWMA+takvim) · f_v15 (P90 conformal)
      ▼
[Talep ID üretimi]  deterministik D00001… (tahmin ve plan dosyalarında birebir aynı)
      │
      ▼
[② OPTİMİZASYON]    o_v1 (greedy) → o_v3 (aynı-lane) → o_v4 (Clarke-Wright) → o_v5/6/7b (CP-SAT+colgen)
      │                → o_v8 (tır MD) → o_v9 (aktarma) → o_v11 (bekletme) → o_v13 (pickup) şampiyon
      │                → o_v12 (de-pandas) / o_v14 (determinizm) hız & sağlamlık
      ▼
[③ ÇIKTI]           Talep-tahmini.xlsx + Tasima-plani.xlsx (jüri formatı, pandera ile denetimli)
      │
      ▼
[④ SİSTEM]          PostgreSQL + FastAPI + ASP.NET dashboard (plan-vs-gerçek karşılaştırma dahil)
```

---

# A. TALEP TAHMİNİ

> Bu aşamada sonucun doğruluğunu belirleyen ilk faktör tahmindir. Ama 2. aşamadan farklı olarak talep
> **aralıklı** (olası slotların %36'sı sıfır) ve **çok çarpık** (birkaç dev hat + uzun kuyruk). Bu, iki
> şeyi baştan değiştirdi: hangi metriğe bakacağımızı ve hangi modelin kazanacağını.

## 3. Metrik Felsefesi — Neden RMSSE + MASE + WAPE

2. aşamada MAE/RMSE/MAPE'ye bakıyorduk (talep büyük ve düzgündü). Bu aşamada talep **aralıklı** (olası
   slotların %36'sı sıfır) ve **çarpık** (birkaç dev hat + uzun kuyruk) olunca bu metrikler yanıltmaya başladı.
   Örneğin MAPE her noktada `|hata| / gerçek` hesaplar; gerçek 0'a yakınsa bölme patlar, tek bir küçük hat tüm
   skoru bozar. Bu yüzden tek metriğe güvenmedik; **10 hata metriği** motoru kurduk (`metrikler.py`) ve tüm
   modelleri **aynı zeminde** kıyasladık. Önce metriklerin ne ölçtüğünü kısaca tanımlayalım:

| Metrik          | Açılım / ne ölçer                                                                                                                                         | Bu veride durumu                                                                                                                         |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **RMSSE** | Root Mean Squared Scaled Error — hatanın karesini, mevsimsel-naïve tahmincinin hatasına **bölerek ölçekler**. M5 yarışmasının resmî metriği. | ⭐ **birincil.** Ölçek-bağımsız, sıfıra dayanıklı; **RMSSE < 1 = mevsimsel-naïve'den iyi**, mutlak bir eşik verir. |
| **MASE**  | Mean Absolute Scaled Error — RMSSE'nin mutlak-hata (kare değil) hali; yine naïve'e ölçeklenir.                                                            | ⭐ **ikinci altın.** RMSSE'yi bağımsız doğrular (kareye değil mutlağa duyarlı).                                             |
| **WAPE**  | Weighted Absolute Percentage Error = Σ\|hata\| ÷ Σgerçek. "Toplam kaç desi yanıldık ÷ toplam gerçek desi."                                            | ✅ **iş standardı.** Operasyonel yorumu net, hacim-ağırlıklı (büyük hattaki hata daha önemli sayılır).                   |
| **Bias**  | Σ(tahmin − gerçek) ÷ Σgerçek — hatanın **işareti/yönü**.                                                                                       | ✅ **yön teşhisi.** `−` = az tahmin (yükün bir kısmı plana hiç girmez → tahmin puanı kaybı), `+` = fazla tahmin (boş araç).                                            |
| RMSE / MAE      | Root Mean Squared Error / Mean Absolute Error — klasik mutlak hata ölçüleri (ölçekleme yok).                                                             | ℹ️ Referans olarak tutuldu; ölçek-bağımlı oldukları için sıralamada birincil değil.                                           |
| MAPE / sMAPE    | (symmetric) Mean Absolute Percentage Error — noktasal yüzde hata.                                                                                            | ❌ **kullanılmadı.** Sıfıra yakın değerlerde matematiksel olarak patlıyor; aralıklı talepte güvenilmez.                   |
| RGRMSE / PBt    | Relatif geometrik RMSE / "kaç noktada naïve'den iyiyiz" oranı — tamamlayıcı çapraz-kontroller.                                                          | ℹ️ Panelde hesaplanıp tutarlılık kontrolü için bakıldı; sıralamaya alınmadı.                                                 |

**Neden bu dördünü (RMSSE + MASE + WAPE + Bias) seçtik:** Aralıklı, çarpık, sıfır-dolu bir talepte
güvenilir olanlar **ölçeklenmiş** (RMSSE/MASE — sıfıra dayanıklı) ve **hacim-ağırlıklı** (WAPE) metriklerdir;
Bias ise "ne kadar" değil "hangi yöne" yanıldığımızı söyler (SLA açısından hayati). MAPE/sMAPE'yi bilinçli
olarak dışarıda bıraktık çünkü %36 sıfırlı bir gridde tanımsızlaşıyorlar.

Bu seçim keyfî değil, **literatürdeki yerleşik öneriyle uyumludur.** Ölçeklenmiş hata ölçüleri (MASE) tam
da "sıfır içeren ve farklı ölçekli serileri karşılaştırma" problemi için önerilmiştir [1]; kare-tabanlı
kardeşi RMSSE ise M5 yarışmasının resmî doğruluk metriğidir. Buna karşılık aralıklı talepte MAE/MAPE
tabanlı ölçülerin yanıltıcı olduğu — hatta "hiç tahmin etme, sıfır de" gibi dejenere çözümleri
ödüllendirebildiği — açıkça uyarılan bir konudur [2]. Rolling-origin (kayan-başlangıç) değerlendirme
yaklaşımı da zaman serisi tahmininde standart doğrulama yöntemidir [3]. Tüm literatür taramamız ve
kaynak listesi: [`experiments/asama3_gelismis/LITERATUR.md`](experiments/asama3_gelismis/LITERATUR.md).

**Kritik bulgu:** RMSSE, MASE ve WAPE **aynı şampiyonu** işaret etti → sonuç tek bir metriğe overfit değil,
metriğe dayanıklı. Ham-hedef üzerine kurulan ML denemeleri **RMSSE > 1** (yani mevsimsel-naïve'den bile kötü)
çıkarak elendi — bunun nedenini §4.1'de teşhis ediyoruz.

## 4. Tahmin Versiyonları (f_v1 → f_v15 · 20 deney)

Konum: `experiments/asama3_gelismis/forecasting/`. Her versiyon kendi klasöründe, tek bir hipotezi test
edip ölçüyor; her satırın hikâyesi kendi `experiment.md`'sinde.

### Nasıl adil kıyasladık — rolling-origin çapraz doğrulama

Bir modelin gerçekte ne kadar iyi olduğunu ölçmenin tek dürüst yolu **backtesttir**: bilinen bir haftayı
gizleyip, yalnız öncesindeki veriyle tahmin yapmak, sonra gerçekle kıyaslamak. Ama tek bir haftaya bakmak
tehlikelidir — o hafta şanslı ya da şanssız olabilir. Bu yüzden **rolling-origin** (kayan-başlangıç) yöntemi
kullandık: aynı sınavı **6 farklı hafta** için, başlangıç noktasını geri geri kaydırarak tekrarladık:

```
Fold 1:  [ ── eğitim ── ]│ hafta-1 tahmin → gerçekle kıyasla
Fold 2:  [ ── eğitim ─── ]│ hafta-2 tahmin → kıyasla
   ⋮                          ⋮
Fold 6:  [ ── eğitim ────── ]│ 22–28 Haz tahmin → kıyasla
                                 → 6 sonucun ORTALAMASI = modelin gerçek performansı
```

Bir ince nokta: bu 6 haftadan biri **Kurban Bayramı**na (26–30 Mayıs) denk geliyordu ve talep o hafta
alışılmadık biçimde çöküyor. Bir bayram haftası tüm modelleri aynı anda "kötü" gösterip sıralamayı
bozacağı için, **Kurban fold'unu ayrı işaretledik** ve birincil ortalamayı 5 temiz fold üzerinden aldık
(bayram davranışını ayrıca takvim düzeltmesinde ele aldık, §4.4). Bu altyapı `_rolling.py`'de kuruldu ve
**tüm versiyonlar aynı zeminde** (rolling-origin, 6 fold, temiz ortalama) yeniden ölçüldü.

> ⚠️ **İki farklı WAPE sayısı — karıştırmayın.** Aşağıdaki tablodaki değerler **rolling-origin ortalamasıdır**
> (6 hafta; dürüst gösterge). Rapor içinde bazı yerlerde bir modelin **tek pencere** (yalnız 22–28 Haz)
> değeri de anılır — örneğin f_v5 için "%24,4" tek pencere, "%25,2" rolling ortalamadır. Nerede hangisini
> kullandığımızı her seferinde belirtiyoruz. Karar her zaman **rolling** değere göre verilmiştir.

**Sıralama RMSSE'ye göre (aralıklı talebin altın standardı).** Bias sütunu işaretlidir: **negatif = model
ortalamada az tahmin ediyor** (gerçek yükün bir kısmı plana hiç girmez), **pozitif = fazla tahmin
ediyor** (boş araç maliyeti); 0'a
yakın = dengeli. Tüm yaptığımız testler aşağıda:

| #   | Ver             | Yöntem (test edilen hipotez)                       | RMSSE⭐        | MASE⭐         | WAPE            | Bias   |
| --- | --------------- | --------------------------------------------------- | -------------- | -------------- | --------------- | ------ |
| 🏆  | **f_v13** | **EWMA + takvim düzeltmesi (tatil/ay-sonu)** | **0,59** | **0,65** | **%25,2** | −1,2  |
| 🏆= | f_v5            | EWMA (recency-mevsimsel taban)                      | 0,59           | 0,65           | %25,2           | −1,2  |
| 3   | f_v6            | EWMA + LightGBM ham artık (residual)               | 0,60           | 0,71           | %27,1           | −5,2  |
| 4   | f_v7            | Momentum + 3-GBM ensemble                           | 0,62           | 0,68           | %26,1           | −6,7  |
| 5   | f_v12           | Segment/havuz (EWMA + segment-LGBM)                 | 0,62           | 0,70           | %27,1           | −9,0  |
| 6   | f_v9a           | Croston (aralıklı talep, α=0,15)                 | 0,63           | 0,70           | %26,8           | −10,8 |
| 7   | f_v9d           | TSB (aralıklı talep, α=0,2)                      | 0,65           | 0,72           | %27,6           | −12,6 |
| 8   | f_v10a/b        | ADIDA / IMAPA (zaman-toplulaştırma)               | 0,65           | 0,71           | %27,3           | −12,8 |
| 9   | f_v14           | Holt (çift-EWMA, trend eğimli)                    | 0,66           | 0,74           | %28,7           | +3,6   |
| 10  | f_v9b           | SBA (Croston-düzeltmeli)                           | 0,71           | 0,76           | %29,3           | −15,9 |
| 10  | f_v9c           | SBJ (Croston-düzeltmeli)                           | 0,71           | 0,76           | %29,4           | −16,1 |
| 11  | f_v1            | Naïve baseline (lane×dow×saat ort.)              | 0,73           | 0,77           | %29,8           | −15,2 |
| 12  | f_v4            | LightGBM ham hedef + base-rate feature              | 1,09           | 1,31           | %45,4           | −10,2 |
| 13  | f_v2            | LightGBM ham hedef (L2 kayıp)                      | 1,10           | 1,35           | %50,9           | −22,7 |
| 14  | f_v3            | LightGBM ham hedef + anomali maskesi                | 1,15           | 1,42           | %50,1           | −6,1  |
| 15  | f_v11a          | Tweedie-LightGBM (sıfır-farkındalıklı kayıp)  | 1,26           | 1,36           | %53,9           | −35,7 |
| 16  | f_v11b          | Hurdle (2-aşamalı LightGBM)                       | 1,43           | 1,51           | %59,0           | −52,7 |

_Tabloda iki versiyon **puanla değil rolle** yer alır: **f_v8** bir model değil, yukarıda anlatılan
rolling-origin **metodoloji altyapısıdır** (§4.3); **f_v15** ise nokta tahmini değil, belirsizlik bandıdır
(P90 conformal, §4.4) — ikisi de bu sıralamaya girmez._

### 4.1 "Ham hedef" ML neden çalışmadı (f_v1 → f_v4)

Önce bir terim: raporda **"ham-ML"** dediğimizde, ML modelini doğrudan **ham hedef** (`desi` sayısının
kendisi) üzerine eğitmeyi kastediyoruz — f_v2, f_v3, f_v4. Bu, "ML'i hiç geliştirmedik" demek değildir;
tam tersine bu yaklaşımın **neden yetersiz olduğunu ölçüp teşhis ettik**, sonra ML'i doğru yerde (§4.2'de
artık üzerinde) yeniden kurduk.

**f_v1 (naïve baseline):** EDA'daki en güçlü sinyaller (haftalık mevsimsellik + saat ayrımı) ile basit,
düşük-varyanslı bir tahminci. Sürpriz derecede güçlü çıktı.

**f_v2 (ham hedef LightGBM):** "ML kazanır" varsayımını test ettik — **yanlış çıktı** (RMSSE 1,10, WAPE
%50,9). Teşhis: `lag_28` gibi trailing feature'lar, backtest haftası için Kurban Bayramı çukuruna
(26–30 May) denk gelip ortalamayı aşağı çekiyor → sistematik az tahmin.

**f_v3 (anomali maskesi):** Tatili **veriden ampirik** tespit edip (tarih hardcode yok → sürpriz veride
de çalışır, §1.2'deki anomali tespiti) lag'lerden maskeledik. Biraz düzeldi, yetmedi.

**f_v4 (base-rate feature):** f_v1'in bilgisini feature olarak verdik. Yine yenemedi. **Asıl sebep şu iki
yapısal sınır:** (1) LightGBM 63 yaprakla 289×2×7 farklı (hat, saat, haftanın-günü) seviyesini temsil
edemiyor — hacimli hatları bucket'layıp ortalamaya çekiyor; (2) ağaçlar eğitim verisindeki en yüksek
seviyenin üstüne **ekstrapole edemiyor**, dolayısıyla +%59'luk trendi geriden takip ediyor.

> **Ders 1:** ML'i "ham hedef" olarak kullanmak bu problemde yanlış. Doğru yol: güçlü bir istatistik
> tabanı kur, ML'i onun **artığı (residual)** üzerinde çalıştır (§4.2). Not: bu, 2. aşamadan farklı bir
> tablodur — orada talep büyük ve düzgündü, LightGBM (ml_v5) tahminde kazanan modeldi. Bu aşamada talebin
> **aralıklı ve çarpık** yapısı ham-ML'i zora soktu; yani "basit hep kazanır" gibi bir kural yok — problem
> değişince kazanan da değişiyor.

### 4.2 Kazanan reçete — kararlı taban + recency (f_v5 → f_v7)

> Bu bölümdeki %24,4 / %22,6 / %22,4 değerleri **tek pencere** (22–28 Haz) ölçümleridir; bunlar f_v1–f_v7'nin
> ilk kıyaslandığı zemindi. §4.3'te göreceğiniz gibi rolling-origin CV bu tabloyu değiştirdi — o yüzden
> nihai sıralama (§4 tablosu) rolling değerleriyledir.

**f_v5 (EWMA):** Baseline'ın kendisini iyileştirdik. Aynı (hat, haftanın-günü, saat) serisinde son haftaları
**üstel ağırlıkla** öne çıkaran EWMA (üstel ağırlıklı hareketli ortalama, span=8) kurduk — düz ortalamanın
aksine eski günlere az, yeni günlere çok ağırlık verir. f_v1'in −%9,8 trend bias'ı kapandı, tek pencere WAPE
%28 → **%24,4**. Ağaç olmadığı için ekstrapolasyon derdi de yok; veride +%59 trend olduğundan recency
(yakın geçmişe ağırlık) belirleyici oldu.

**f_v6 (EWMA + artık ML):** Ders 1'i uyguladık — ML'i ham hedef yerine tabanın **artığı** (`desi − base`)
üzerine eğittik. (Önce log-artık denendi → sıfırlarda çöktü, %63; ham toplamsal artığa geçince düzeldi.)
LightGBM artık trend/seviyeyi değil, tabanın kaçırdığı ince yapıyı (momentum, hat-gün etkileşimi) öğreniyor
→ tek pencere **%22,6**. ML ilk kez anlamlı katkı verdi — yani ML'i attık değil, **doğru yere koyduk**.

**f_v7 (3-GBM ensemble):** ML'i daha da geliştirdik: momentum feature'ları + üç ayrı gradient-boosting
modelinin (LightGBM / XGBoost / CatBoost) ortalaması. Tek pencere **%22,4**. Üç bağımsız model %22,5–23,2
gibi dar bir bantta toplandı — "en iyi" gibi göründü. Ama f_v8 bunu çürüttü.

> **Not — ML'i geliştirdik mi?** Evet. Bu üç versiyon (residual framing, momentum, 3-model ensemble) ML'in
> **geliştirilmiş** halleridir; ayrıca ileride aralıklı-talebe özel ML yaklaşımlarını da denedik (f_v11
> Tweedie/Hurdle, f_v9 Croston ailesi). Yani "EWMA iyi çıktı diye ML'i geliştirmeden kabullendik" değil —
> ML'i birçok biçimde geliştirdik; sadece bu **özel veride** (%36 sıfır, 289×2 çözünürlük) EWMA'nın recency
> avantajını hiçbiri geçemedi. Bunu rolling CV ile kanıtladık.

### 4.3 Metodoloji kırılması — rolling-origin CV (f_v8)

f_v1–f_v7'yi hep **tek pencerede** (22–28 Haz) ölçmüştük ve f_v7 orada "en iyi" görünüyordu. Ama modeli
tek bir haftaya göre seçmek, tek soruluk bir sınavla öğrenci seçmeye benzer. Bu yüzden §4 başındaki
rolling-origin altyapısını kurup **tüm modelleri 6 hafta üzerinde yeniden ölçtük.** Sonuç çarpıcıydı:
**ML'in tek penceredeki üstünlüğü o haftaya özgü bir şanstı.** 5 temiz fold ortalamasında saf EWMA (f_v5)
**%25,2** ile kazanıyor; ML artık-modeli (f_v6) rolling'de **%27,1**'e geriliyor — yani tek pencerede
"%22,6 ile daha iyi" görünen model, gerçekte ortalama **2 puan daha kötü** ve fold'lar arası varyansı
daha yüksek. Aynı olgu f_v7 için de geçerli (tek pencere %22,4 → rolling %26,1).

> **Ders 2:** Tek haftaya güvenmek yanıltır. Tek pencerede parlayan bir model rolling CV'de sönebilir. Bu
> yüzden tüm model seçimini ve karşılaştırmayı rolling-origin ortalaması üzerinden yaptık — nihai tablodaki
> (§4) her sayı budur.

### 4.4 Yeni bilgi arayışı ve şampiyon (f_v9 → f_v15)

Rolling-temiz zemin kurulunca "EWMA'yı gerçekten geçebilir miyiz?" diye yeni bilgi kaynaklarını sistematik
olarak taradık — hepsi rolling CV'de ölçüldü:

- **Aralıklı-talebe özel klasik yöntemler** (f_v9, f_v10): Croston [4], onun yanlılığını düzelten SBA [5],
  SBJ, talep olasılığını her periyotta güncelleyen TSB [6], ve zaman-toplulaştırma yaklaşımları ADIDA /
  IMAPA. Bunlar tam da "çok sıfırlı, seyrek" talep için literatürde önerilen standart yöntemlerdir; kendi
  implementasyonumuz hazır kütüphane StatsForecast'i açık ara yendi (Croston %27,7 vs %36,5) — ama yine de
  **EWMA'yı geçemedi**.
- **Aralıklı-talebe özel ML** (f_v11): Tweedie (sıfır-farkındalıklı kayıp fonksiyonu) ve Hurdle (önce
  "yük var mı", sonra "ne kadar" diye iki aşamalı model). İkisi de bu gridde çöktü (RMSSE > 1).
- **Segment/havuz modelleri** (f_v12) ve **çift-EWMA/Holt** (f_v14, trend eğimini açıkça modelleyen).

Hiçbiri EWMA'yı geçemedi. Bu bir başarısızlık değil, **sağlam bir negatif sonuçtur**: bu özel veride
recency-mevsimsel EWMA yapısal olarak en iyisi.

**Şampiyon f_v13 (EWMA + takvim düzeltmesi).** Tabloya bakan biri haklı olarak sorar: "f_v5 ve f_v13
rolling'de birebir aynı (ikisi de %25,2, RMSSE 0,59) — neden f_v5 değil de f_v13'ü teslim ettiniz?"
Cevap teslim haftasının takvimindedir. Rolling ortalamayı aldığımız 5 temiz fold'da **özel gün yok**, bu
yüzden orada takvim düzeltmesinin devreye gireceği bir şey olmuyor → f_v13, f_v5'e eşit çıkıyor. Ama
**teslim ufkumuz (29 Haz – 5 Tem) 30 Haziran ay-sonunu içeriyor** ve verideki güçlü bir kurala göre ay
sonları talep neredeyse sıfıra düşüyor (bir tür kapanış/sayım günü; 5 ayın 5'inde gözlendi). Saf EWMA bunu
bilmez, geçmiş haftaların ortalamasını yazıp o günü **fazla tahmin eder**; f_v13'ün takvim düzeltmesi ise
ay-sonu/tatil günlerinde bu fazla-tahmini kırar. Etkisi özel günlerde çok büyük: izole bir Kurban fold'unda
WAPE %467 → %108, ay-sonu haftasında +22,6 puan iyileşme. Yani **f_v13 = "f_v5 + özel gün sigortası"**;
temiz haftalarda f_v5'le aynı, özel gün içeren teslim haftasında daha güvenli. Anomali tespiti veriden
ampirik olduğu için (§1.2) sürpriz veri setinde de çalışır.

**f_v15 (P90 belirsizlik bandı).** Eksik tahmin riskini (yani gerçekte gelip de planımıza girmeyen yükü)
yönetmek için ayrı bir kol — SLA gecikme cezasını değil, **kapsama**yı hedefler. Nokta tahmini (tek sayı) yerine
talebin **olası aralığını** verir: split-conformal yöntemiyle, geçmişte ölçülen tahmin hatalarına bakarak
"talep büyük olasılıkla bunun altında kalır" üst sınırını (P90) hesaplar; kalibrasyon yalnız `tarih < hedef`
verisiyle yapıldığı için sızıntı yok. Teslim ettiğimiz iki tahmin: **P50** (medyan senaryo, ana plan,
5,46M desi) ve **P90** (üst-bant güvence, 8,03M desi). _Not: conformal yöntem alt bandı (P10) da hesaplar
ama biz teslimde ve optimizasyonda yalnız P50 ile P90'ı kullanıyoruz; P10 raporlanmaz._

> **Ders 3:** En büyük kaldıraç recency (EWMA) oldu; ML'i doğru uzayda (artık) kurunca küçük katkı verdi
> ama rolling CV'de eridi. Aralıklı-talebe özel yöntemler (Croston ailesi, Tweedie, Hurdle) bile EWMA'yı
> geçemedi. Şampiyon üç altın metrikte de (RMSSE/MASE/WAPE) aynı çıktı → sonuç metriğe dayanıklı ve sağlam.

**Bu bulgu literatürle de tutarlı.** "Basit istatistik yöntemler aralıklı talepte modern ML'i
yenebiliyor" sonucu bize özgü bir tuhaflık değil: aralıklı talep tahmininde makine öğrenmesini derleyen
güncel bir inceleme, LSTM gibi derin modellerin en iyi klasik yönteme (Croston) **çok yakın** kaldığını,
yani basit yöntemlerin hâlâ güçlü bir referans olduğunu raporluyor [7]. Dolayısıyla "ML'i denedik,
kazanamadı" ifademiz bir eksiklik itirafı değil, **beklenen ve literatürde belgelenmiş** bir sonucun
kendi verimizde doğrulanmasıdır.

### 4.5 ⭐ Bulgu: tahmin talebi "yayıyor" — ve bu optimizasyon maliyetini şişiriyor

Bu, tahmin ile optimizasyonu birbirine bağlayan ince ama önemli bir bulgu. Hikâye şöyle başladı:
optimizasyon çıktısını incelerken, planın çok sayıda **minik yük** için ayrı sevkiyat yaptığını fark ettik
— birkaç desilik yükler için araç çıkıyordu. "Bu yükler gerçek mi?" diye tahmini gerçek talebe karşı
kontrol ettik ve şunu bulduk.

**Gözlem.** Gerçek talep, elimizdeki 6 ay boyunca (66.024 dolu slot) **hiçbir zaman 17 desinin altına
inmiyor** (minimum 17, 1. yüzdelik dilim 21). Yani gerçek dünyada bir hat ya hiç yük göndermiyor (0), ya da
en az ~17 desi gönderiyor — ikisinin arası boş. Ama tahmin modelimiz, talebin aralıklı (çok sıfırlı)
yapısını yumuşatma eğiliminde olduğu için, gerçekte sıfır olan slotlara **küçük ama sıfır-olmayan** değerler
yazıyor: teslim haftasında **814 slota** 17 desiden az tahmin koyuyor. Bunlar "hayalet mikro-yükler" —
gerçekte var olmayan, ama tahmin dosyasında görünen minicik talepler.

**Neden önemli.** Jüri, optimizasyon başarımızı **bizim kendi tahminimiz üzerinden** ölçüyor. Yani tahmin
bir hayalet yük içeriyorsa, optimizasyon o hayalet yük için de araç çıkarmak zorunda kalıyor ve maliyet
şişiyor. Somut ölçüm (22–28 Haz, elimizde gerçek talep de var): tahmin bazlı plan **4.618 bacak**, aynı
haftanın gerçek talebiyle kurulan plan **3.174 bacak**. Aradaki farkın önemli kısmı bu hayalet yüklerden.

**Ne yaptık — eşik deneyi.** "17 desinin altındaki tahminleri sıfırla" diye bir müdahale denedik ve **iki
tarafı da ölçtük**: (a) tahmin doğruluğu tarafında bedel **sıfır** — WAPE %24,4'te sabit kaldı, çünkü
silinen yükler tüm tahminin yalnız %0,09'u; (b) optimizasyon tarafında **−%0,8 kazanç**. İyi bir takas gibi
duruyor. Ama daha derin baktığımızda, bu müdahale planı SLA cezasına daha çok yaslanan bir yapıya kaydırıyor
(hayalet yükler kalkınca çözücü farklı bir denge buluyor). **Karar:** bulgu değerli ve rapora giriyor, ama
teslim planına **uygulanmadı** — teslime az kala, %0,55'lik bir kazanç için doğrulanmış ve kararlı bir planı
SLA-ağırlıklı bir yapıya çevirmek iyi bir risk/getiri dengesi değil. Bu, "her ölçülen kazancı körü körüne
almak yerine, takasını tartıp karar vermek" ilkemizin bir örneği.

---

# B. OPTİMİZASYON

> Problem: talebi taşıyacak araç filosunu **en düşük maliyetle çizelgele + konsolide et** — elleçleme
> kotası, tır kotası ve SLA kısıtları altında. Bu, raporun asıl algoritmik ağırlığıdır: 25 deneyden oluşan
> bir yolculukla, geçerli maliyeti **48,00M'den 9,96M'e** indirdik. Her versiyon bir öncekinin bıraktığı
> israfı hedef aldı ve her sıçramanın **kaynağını önce ölçtük, sonra kurduk**.

## 5. Temel Taş — Değerlendirici ve Kısıt Sistemi

Bir çözücü yazmadan önce cevaplanması gereken bir soru var: "bir planın **ne kadara mal olduğunu** ve
**kurallara uyup uymadığını** doğru ölçebiliyor muyuz?" Çünkü değerlendirici yanlışsa, onun üstüne kurulan
tüm optimizasyon — ne kadar zeki olursa olsun — yanlış bir hedefi kovalar. Bu yüzden ilk ve en dikkatli
işimiz bu çekirdeği kurmak oldu.

### 5.1 Route-aware (sefer-farkında) değerlendirici

`core/evaluation/rota.py`, bir **rotayı** (bir aracın bir kalkışta yaptığı tüm iş) alıp maliyetini ve SLA
cezasını hesaplar. "Sefer-farkında" olmasının anlamı şu: bir araç tek bir seferde birçok Talep ID
taşıyabilir, ve bu durumda maliyet ile SLA **farklı seviyelerde** sayılmalıdır:

- **Maliyet, km ve seyir → sefer başına.** Bir araç 5 farklı talebi tek seferde taşıyorsa, o seferin
  km + seyir + yükleme maliyeti **bir kez** hesaplanır; her talebe ayrı araç maliyeti yazılmaz. (İlk
  denemelerde bunu kaçırırsak tüm maliyetler şişerdi.)
- **SLA cezası → talep başına.** Aynı seferde taşınan her talebin kendi teslim süresi (deadline'ı) vardır;
  ceza her talep için ayrı hesaplanır.

Değerlendiricinin doğru kurması gereken ince bir nokta, multi-drop rotalarında yükün ara duraklarda nasıl
işlendiğidir. Bir tır İstanbul'dan çıkıp **İstanbul → Yalova → Eskişehir** rotasını izliyor ve üstünde iki
yük var: biri Yalova'ya, biri Eskişehir'e. Araç Yalova'ya vardığında **yalnızca Yalova'nın yükü indirilir**
(elleçlenir); Eskişehir'e giden yük ise araçtan **hiç inmez** — aracın içinde kalır, Yalova'da elleçlenmez,
sadece yol üstünde geçip Eskişehir'de indirilir. Yani bir yük, bir ara duraktan **inmeden geçiyorsa** o
duraktaki elleçleme işlemine (ve elleçleme kotasına) hiç dokunmaz; her yük yalnız gerçekten indiği ya da
yüklendiği yerde elleçlenir. Bu ayrım kritik: yanlış modelleseydik, ara duraktan geçen her yükü sanki orada
indirilip yeniden yüklenmiş gibi iki kez sayar, hem maliyeti hem kota kullanımını şişirirdik.

Değerlendirici, elle doğrulanan test vakalarıyla sabitlendi (İst→Yalova 10.000 desi = **3573,5 TL**;
İst→Yalova→Eskişehir 5.000+5.000 = **9553,1 TL**). Bu dosya sistemin **kanonik referansıdır** ve hız için
asla değiştirilmez; hızlandırma gerektiğinde (§10) onun **doğrulanmış bir hızlı kopyası** kullanılır, ama
nihai skor her zaman bu kanonik değerlendiriciyle üretilir.

Zaman tarafında `core/evaluation/zaman.py` tek bir zaman modeli tutar: SLA'nın teslim anı çıkış
elleçlemesini (yüklemeyi) de içerir, ve elleçleme kotası gece yarısını aşan işlemleri jüri kuralına göre
**oransal** böler (§1.4).

### 5.2 Genişletilebilir kısıt sistemi (K1–K8)

Kurallara uyumu tek bir yerde, `core/optimization/kisitlar.py`'de topladık. Tasarım ilkesi şu: **her kısıt
bağımsız bir sınıftır**; yeni bir kural eklemek, çözücüye hiç dokunmadan tek bir sınıf yazıp listeye
eklemek demektir. Bir planın geçerli sayılması için sekiz kısıtın **hepsini** geçmesi gerekir:

| Kısıt                                | Ne denetler                                                                                                                                              | Neden var / nasıl                                                                                                                                                                                     |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **K1 — Araç kapasitesi**       | Bir seferde taşınan toplam desi, aracın kapasitesini aşamaz (Tır 22.400, Kamyon 12.000 …).                                                         | Fiziksel sınır. Pickup'lı rotalarda (§9) yük yolda değiştiği için **anlık yük** (aracın en dolu olduğu an) denetlenir — toplam desi değil.                                         |
| **K2 — Elleçleme kotası**     | Bir TM'de bir günde yapılan toplam elleçleme (indirme + yükleme), o TM'nin günlük desi kotasını aşamaz.                                         | TM'lerin işleme kapasitesi sınırlı. Her indirme + her yükleme ayrı sayılır; konsolidasyon 2× (x indir + y yükle). Gece yarısını aşan işlem **oransal** bölünür (jüri kuralı). |
| **K3 — Tır kotası**           | Bir TM'de bir günde **yanaşan tır sayısı**, o TM'nin tır kotasını aşamaz (7 TM'de kota 0).                                                 | Yalnız "Tır" tipini kapsar; Kamyon/Kamyonet kotasız. Yanaşma **varış gününe** göre sayılır — bu, kiralık tırla gece yarısı etkileşimini doğurur (§7).                          |
| **K4 — Kiralık sabit hat**     | Kiralık araç (tır **ve** kamyon) yalnız tanımlı hattında gider; uğrama/dönüş yapamaz, talep olmasa da her gün çıkar.                                            | Sözleşme kuralı. Kiralık, spot'tan farklı olarak rotadan sapamaz. Filo günde 14 araç (10 kiralık tır + 4 kiralık kamyon), 7 günde 98 zorunlu çıkış.                                                                                                                                 |
| **K5 — Zaman tutarlılığı**  | Bir seferin durakları zamanda tutarlı olmalı (yükle → seyir → indir sırası, negatif süre yok).                                                  | Fiziksel zaman akışı; değerlendiricinin ürettiği zaman çizgisi kendi içinde çelişemez.                                                                                                       |
| **K6 — Eşzamanlı elleçleme** | Bir araçtaki tüm yük aynı anda elleçlenir (ayrı ayrı değil).                                                                                     | Jüri kuralı: "bir araçtaki tüm yük aynı anda elleçlenir" — süre`0,01 × toplam desi`, parça parça değil.                                                                                 |
| **K7 — Talep bütünlüğü**   | Her tahmin edilen talep planda **tam olarak** taşınmalı; eksik/fazla/uydurma talep olamaz. Bölünen talep parçaları toplamı orijinale eşit. | Çıktının tahmin dosyasıyla birebir tutması şart (jüri Talep ID eşleşmesi).                                                                                                                   |
| **K8 — Tır-yasağı TM**       | Tır kotası 0 olan 7 TM'ye (Bilecik, Denizli, Isparta, Karaman, Zonguldak, Sivas, Kütahya) tır giremez.                                               | K3'ün özel hâli; bu merkezlere yalnız Kamyon/Kamyonet ile ulaşılır.                                                                                                                             |

Bu ayrık tasarımın pratik faydası şu oldu: yarışma boyunca kurallar netleştikçe (ör. tır kotası dosyası
güncellendiğinde) ya da yeni bir kural belirdiğinde, çözücüyü hiç bozmadan ilgili kısıt sınıfını
güncelledik. Sonraki bölümlerde göreceğiniz her versiyon, bu sekiz kısıdı geçen — yani **geçerli** — bir
plan üretir; "geçersiz ama ucuz" bir plan bizim için hiç var olmadı (o_v1 dışında, o da bilinçli bir
naïve referanstı).

## 6. Versiyon İzi (o_v1 → o_v14 · 25 deney)

Aşağıdaki tabloda 25 deneyin hepsi var. Hepsi **aynı P50 ufuk tahmini** üzerinde, aynı sefer-farkında
değerlendiriciyle skorlanır — yani rakamlar birebir kıyaslanabilir (adil kıyas).

**Neden "8 worker" — bir metodoloji notu.** Aksi belirtilmedikçe bu tablodaki koşular **8 worker /
CPSAT 180 sn** ile alındı. Sebebi pratik: 25 deneyin her birini defalarca koştururken, her koşunun mümkün
olduğunca hızlı bitmesi gerekiyordu ki bir sonraki hipotezi hızla deneyebilelim. 8 worker, geliştirme
makinemizde (i7-12700H, 14 fiziksel çekirdek) hem hızlı hem kararlı sonuç veriyordu. Bu, "araştırma
zeminidir" — versiyonları birbiriyle **aynı koşullarda** kıyaslamamızı sağlar. Ama **teslim edeceğimiz
nihai modeli ayrıca jüri donanımında (4 çekirdek / 16 GB) ölçtük ve orada hızlandırdık** (§10); çünkü
runtime puanı o ortamdan geliyor. Yani iki farklı amaç var: (1) versiyonları adil kıyaslamak → 8 worker
sabit zemin; (2) teslim modelini gerçek ortamda optimize etmek → 4 çekirdek ölçüm + hızlandırma.

**Ana algoritmik yolculuk (maliyeti düşüren versiyonlar):**

| Ver             | Ne test etti (hipotez)                                         | TOPLAM           | Geçerli? | Bulgu                                                                          |
| --------------- | -------------------------------------------------------------- | ---------------- | --------- | ------------------------------------------------------------------------------ |
| o_v1            | En basit çözüm ne verir? (naïve referans)                  | 47,81M           | ❌        | Her minik yüke ayrı araç; tır kotasını deliyor → **geçersiz**     |
| o_v2            | Kurallara tam uyan en yalın plan?                             | 48,00M           | ✅        | İlk **geçerli** plan; geçerliliğin bedeli yalnız +0,25M              |
| o_v3            | Aynı hattın yüklerini tek sefere toplasak?                  | **21,74M** | ✅        | 🚀 En büyük sıçrama: **−26M**; "sefer tabanı" asıl israfmış      |
| o_v3b           | Greedy'nin son damarı: araç tipi karışımı                | 21,65M           | ✅        | Greedy tavanı; saf greedy doygun (−0,09M)                                    |
| o_v4            | Aynı çıkıştan farklı varışlara tek araç (multi-drop)? | **13,10M** | ✅        | 🚀 Detour tabanı seyir tabanının yerini aldı; **−%40**               |
| o_v5            | CP-SAT ile matematiksel optimum? (CW warm-start)               | 12,96M           | ✅        | Aday havuzunda kanıtlı optimal; CW'yi −0,14M cilaladı                      |
| o_v6            | Havuzu ALNS boz-onar ile zenginleştirsek?                     | 12,80M           | ✅        | Havuz 10.810 → 15.722 aday; +NN durak sırası (aşağıda açıklanır)             |
| o_v7            | Son çözücü ALNS mi CP-SAT mı? (kıyas)                    | 12,78M           | ✅        | ALNS ≈ CP-SAT (fark ~0,02M) → CP-SAT seçildi (§6.2)                        |
| **o_v7b** | CP-SAT'ı ALNS ile besleyip döngüye alsak?                   | 12,77M           | ✅        | 🎯 Kolon-üretimi tarzı matheuristic — mimari çekirdek + optimallik kanıtı        |
| o_v8            | Spot tırlar da multi-drop yapsa? (tır kota kısıtı)        | 12,43M           | ✅        | 🚀 Tırlar da yol-üstü doldurur (K8 yasaklı TM'lere girmeden); −0,37M       |
| o_v8b           | Keşif döngüsü **tır-dışı** ailede (Kamyon/Kamyonet)      | 12,386M          | ✅        | Colgen tır-dışı multi-drop rotalarını keşfediyor; −0,04M                |
| o_v8c           | Keşif döngüsü **tırları da** keşfetse?                  | 12,381M          | ✅        | Tam mimari; iki aile (tır + tır-dışı) de colgen'de                          |
| o_v9            | Aktarma/hub potansiyeli var mı? (ölçüm)                    | *(ölçüm)*   | —        | Multi-drop'un kör noktası: uzak varış + çok çıkış (~2,76M potansiyel) |
| o_v9b           | Aktarmayı CW havuzuna eklesek?                                | 12,114M          | ✅        | Cross-origin hub konsolidasyon; −0,27M                                        |
| o_v9c           | Aktarmayı column-gen de keşfetse?                            | **11,80M** | ✅        | Colgen'e 3. keşif pass'i (aktarma); v9b'den −0,31M, SLA de düştü          |
| **o_v11** | 09:00 yükünü 17:00'ye bekletsek?                            | **11,43M** | ✅        | 🏆 Yarı-boş 09:00 seferleri 17:00'de doluyor; −0,37M                        |
| o_v12           | Hızlandırma A: pandas'ı kaldır                             | 11,43M           | ✅        | Skor aynı, süre 150→88 sn (§10.1)                                          |
| o_v12b          | Hızlandırma B: +Numba kernel                                 | 11,43M           | ✅        | Skor aynı, süre →76 sn                                                      |
| **o_v13** | Araç ara durakta yük de alsa? (pickup)                       | **9,96M**  | ✅        | 🏆🏆 Jüri cevabından doğdu; −1,47M (§9)                                   |

**Ölçüm ve varyant versiyonları (şampiyonu düşürmez; belirli bir soruyu yanıtlar):**

| Ver    | Amaç                                                         | Sonuç                                                                  |
| ------ | ------------------------------------------------------------- | ----------------------------------------------------------------------- |
| o_v9d  | Şampiyon v11'i jüri 4-core ortamında ölç                 | Skor aynı (11,43M), süre ~5× uzun → worker = hız lever'ı (§10.2) |
| o_v13b | Şampiyon v13'ü 4 çekirdekte ölç = **teslim ayarı** | **10,38M / 6,2 dk** (jüri donanımı)                            |
| o_v13c | Pickup'lı P90 güvence kolu                                  | 15,57M (eski P90 16,26M'den −0,69M)                                    |
| o_v10  | P90 güvence (v9c tabanı)                                    | 16,24M — P50→P90 +%38; ertelemesiz infeasible'dı                     |
| o_v10b | P90 güvence optimize (v11 + erteleme daraltma)               | 16,26M, doluluk %72                                                     |
| o_v14  | Aynı girdi → aynı çıktı sağlanabilir mi?               | Sağlanabilir ama +%5,6 maliyet → açılmadı (§10.3)                 |

### 6.1 Kilit dersler (detaylı)

**1. Asıl kaldıraç "sefer tabanı", araç sayısı değil (o_v3 — en büyük sıçrama).** §1.3'te anlattığımız gibi
sabit araç ücreti yok; ama her seferin km + seyir "tabanı" yüksek ve **yükten bağımsız**. o_v2'ye kadar
plan, her minik yükü ayrı bir sefere atıyor ve o tabanı tekrar tekrar ödüyordu. Aynı hattın (ör.
İstanbul→Yalova) bir gün içindeki yüklerini **tek sefere toplayıp** tabanı yalnız bir kez ödeyince maliyet
**48M'den 21,74M'e**, yani yarıdan fazla düştü. Bu, tüm optimizasyonun en büyük tek sıçramasıdır — ve
tipik bir "önce ölç, sonra kur" örneğidir: aynı-lane konsolidasyon potansiyelini kodlamadan önce ölçtük
(~23M), değerini görünce kurduk.

**2. Multi-drop, seyir tabanını "detour" maliyetiyle değiştirir (o_v4).** Önce bir terim: **detour**,
"sapma" demektir. Bir araç doğrudan İstanbul→Eskişehir gitmek yerine yolda Yalova'ya uğrarsa, Yalova
döngüsünün eklediği fazladan mesafe o seferin **detourudur**. Bulgu şu: slotların %98'i bir Kamyon'u bile
dolduramayacak kadar küçük. Aynı çıkıştan farklı varışlara giden bu küçük yükleri ayrı ayrı (her biri
yarı-boş bir araçla) göndermek yerine **tek araca doldurup sırayla uğratmak**, her varışın koca seyir
tabanını ucuz bir detour ile değiştirir. Örnek: İstanbul→Yalova ve İstanbul→Eskişehir'i ayrı iki araçla
değil, İstanbul→Yalova→Eskişehir tek aracıyla taşımak (Yalova zaten yol üstünde). Tek adımda **−%40**.

**3. Durak sırası tek başına ~2M değerinde (o_v6/o_v7).** Bir multi-drop rotasında araç, duraklara **hangi
sırayla** uğradığına göre farklı toplam mesafe kat eder — İstanbul→Yalova→Eskişehir ile
İstanbul→Eskişehir→Yalova aynı üç şehir ama farklı km. o_v7'de bunu ölçtük: durakları rastgele sırayla
tutan ilk sürüm **14,8M** verdi; durakları "nearest-neighbor" (her adımda en yakın durağa git) sırasına
sokunca **12,78M**'e düştü — yani yalnızca **durak sırasını düzeltmek ~2M** kazandırdı. Bu yüzden tüm
üreticiler artık durakları NN ile sıralıyor. (Bu ~2M, v5→v6 kazancı değil; ayrı ve şaşırtıcı derecede
büyük bir kaldıraçtır.)

**4. Kısıtsız ölçüm yanıltır (o_v3b bağlamı).** Bir kaldıracın potansiyelini ölçerken kotaları
modellemezsen, ulaşılamaz bir sayı görürsün. Örneği somutlaştıralım. o_v3'te bir hattın konsolide yükünü
**tek tip** araçla taşıyorduk: 25.000 desilik bir yük → 2 Tır (ikincisi neredeyse yarı boş, ama tabanını
tam ödüyor). o_v3b'nin fikri şuydu: ikinci aracı Tır yerine **Kamyonet** yapalım (1 Tır + 1 Kamyonet) —
Kamyonet'in tabanı çok daha ucuz, artan küçük yükü ona koyarsak tasarruf ederiz. Bu fikrin potansiyelini
**kotasız** (her yerde istediğimiz tipi kullanabiliyormuşuz gibi) ölçtüğümüzde **0,73M** kazanç göründü.
Ama gerçekte bir engel var: bazı hatlarda Kamyonet'e geçmek istediğimiz durak, tır kotası dolu olan bir
TM olabilir ya da tam tersi Kamyonet uygun olmayabilir — yani "yarı-boş Tır'ı Kamyonet'e çevirme"yi **her
yerde** yapamıyoruz. Kotaları modele kattığımızda gerçek, ulaşılabilir kazanç **0,15M**'e indi. Ders:
bir kaldıracın parlak potansiyelini görmek yetmez; kısıtları modellemeden ölçersen ulaşamayacağın bir
sayının peşine düşer, hayal kırıklığına uğrarsın. Biz bu yüzden her potansiyeli **kısıtlarla birlikte**
ölçtük.

### 6.2 ALNS mi, CP-SAT mı? — Bir mimari kararın hikâyesi

Bu karar, projenin en çok düşündüğümüz mühendislik tercihidir, o yüzden hikâyesini ayrıca anlatmak istiyoruz.

**Başlangıç planımız.** Yarışmanın önceki aşamasında kurduğumuz mimaride, **son seçici olarak ALNS**
(Adaptive Large Neighborhood Search — "boz-onar" tipi bir sezgisel arama) kullanmayı planlamıştık. ALNS,
bir çözümü alıp bir kısmını rastgele "bozar" (destroy), sonra daha iyi biçimde "onarır" (repair), ve bu
döngüyü tekrarlayarak iyileştirir. Güçlü ama **sezgiseldir**: bulduğu çözümün gerçekten en iyi olduğunu
kanıtlayamaz.

**Alternatif: CP-SAT.** CP-SAT bir **kesin çözücüdür** (constraint programming / SAT tabanlı). Problemi
"set partitioning" olarak kurarız — "şu aday rotalardan, her talebi tam bir kez kapsayan, kotalara uyan,
en ucuz alt kümeyi seç" — ve CP-SAT bunun **kanıtlanmış en iyisini** verir (optimallik aralığı ≈ 0). Ama
iki önemli sınırı var. Birincisi: yalnız **kendisine verilen aday havuzunu** görür — havuz dışındaki bir
rotayı üretemez. İkincisi: havuz büyüdükçe **arama süresi** uzar; biz CP-SAT'a bir zaman tavanı veriyoruz
(§10) ve zengin havuzlarda çözücü çoğu zaman bu **tavana çarparak** durur (yani "kanıtlı optimum bulundu"
değil, "süre doldu, elimdeki en iyi bu" ile biter). Bu ikinci sınır, sonraki hız çalışmalarımızın (§10)
ana motivasyonudur: aynı havuzu daha hızlı tarayabilmek, tavana çarpmadan optimumu kanıtlayabilmek.

**Ölçtük (o_v7).** Hangisinin son seçici olması gerektiğini kıyaslamak için iki kurulumu **her şeyi sabit
tutarak** karşılaştırdık — kiralık atama, parti oluşturma, multi-drop üretimi ikisinde de birebir aynı;
tek fark son adım:

- **o_v6 (CP-SAT son seçici):** ALNS aday havuzunu zenginleştirir, **son kararı CP-SAT verir** (set
  partitioning, kanıtlı optimal). → **12,80M**
- **o_v7 (ALNS son seçici):** **CP-SAT hiç kullanılmaz**; Clarke-Wright ile başlanır, sonra ALNS'in
  destroy/repair + simulated-annealing döngüsü çözümü doğrudan iyileştirir. → **12,78M**

Sonuç neredeyse eşit (fark ~0,02M, yani binde iki). Yani ALNS'in son seçici olarak tek başına anlamlı bir
üstünlüğü yoktu — ama CP-SAT'ın elinde bir avantaj vardı: bulduğu çözümün o havuz için **en iyi olduğunu
kanıtlayabiliyordu**.

**Kararımız: ikisini birleştirmek (o_v7b).** ALNS ile CP-SAT'ı **rakip değil, ortak** yaptık. Döngü şöyle
işler: **CP-SAT** mevcut havuzun kanıtlı optimalini bulur → **ALNS** o çözümün etrafını keşfedip havuzda
**olmayan** yeni rotalar üretir → bunlar havuza eklenir → CP-SAT tekrar çözer. Havuz doyana kadar tekrarlar.
Böylece ALNS'in keşif gücü ile CP-SAT'ın kanıtlı optimalliği **birleşir**: ALNS "nereye bakılacağını"
bulur, CP-SAT "en iyisini kanıtlı seçer". Bu yaklaşım, yöneylem literatüründeki **column generation**
fikrinden esinlenir (kesin bir çözücüyü, dışarıdan üretilen yeni "kolonlarla" besleyip döngüye almak).
Terimi dürüst kullanalım: klasik column generation, kolonları bir LP-gevşemesinin indirgenmiş-maliyet
(dual pricing) hesabıyla üretir; bizde ise kolonları üreten bir **sezgiseldir (ALNS)** ve seçici bir LP
değil bir **SAT çözücüsüdür (CP-SAT)**. Yani teknik olarak bu, klasik column generation'ın kendisi değil,
ondan esinlenen bir **"kolon-üretimi tarzı matheuristic"tir** (sezgisel + kesin çözücü melezi). Sonuç:
hem o_v6'yı hem o_v7'yi geçtik **ve** optimallik kanıtını koruduk — ve bu mimari, sonraki tüm versiyonların
(tır multi-drop, aktarma, pickup) üstüne kurulduğu çekirdek oldu.

## 7. Kaldıraçlar — Kiralık, Multi-drop, Aktarma, Bekletme

### 7.1 Kiralık zorunlu çıkış ve gece yarısı inceliği

Kiralık araçların özel bir kuralı var: talep olsun olmasın **her gün çıkmak zorundalar** (sözleşme). Boş
çıksalar bile km + seyir maliyetleri sayılır. Bu, tüm versiyonlarda ortak bir tabandır.

**Sen de haklı olarak sorabilirsin: "kiralık her gün çıkar, seferi ertesi güne sürse bile gider, ertesi
gün yeni kiralık yine çıkar — burada ne kısıtı var?"** İncelik, kiralık çıkışında değil, **tır kotasının
varış gününe göre sayılmasında**. Bunu bir örnekle açalım:

- Bir kiralık **Tır**, 4 Temmuz akşamı 17:00'de tam dolu (22.400 desi) yüklenir. Yükleme 224 dakika sürer,
  üstüne seyir eklenir → araç **gece yarısını aşıp 5 Temmuz'da** varış TM'sine ulaşır.
- Tır kotası (K3) **varış gününe** göre sayılır. Yani bu tırın yanaşması **5 Temmuz**'un kotasına yazılır.
- Ama 5 Temmuz'un zorunlu kiralık çıkışı da aynı TM'ye o gün varıyorsa → o TM'de **5 Temmuz'da 2 tır
  yanaşması** olur. Kotası 1 olan bir TM'de bu bir **kota ihlalidir**.

Yani ortada icat ettiğimiz bir kural yok; sadece **mevcut K3 kısıtını gece yarısı geçişinde doğru
uyguladık**. Çözücü, kiralık tırı **aynı gün varacak kadar** yükler (yükleme + seyir gece yarısını aşmasın),
taşan yükü ise tır kotası olmayan **Kamyon**'a devreder. Bu ayrımı yapmayan bir model, kâğıt üzerinde daha
ucuz görünen ama aslında **geçersiz** (K3'ü delen) planlar üretirdi — ve jüri değerlendirmede bunu görürdü.
Biz baştan geçerli tarafta kaldık.

### 7.2 Multi-drop — aynı çıkıştan çok varışa (o_v4)

§6.1'de anlattığımız kaldıraç. Bir araç tek çıkıştan yola çıkıp **sırayla birçok varışa** uğrar; her varışta
o varışın yükünü indirir (ötekiler araçta kalır — §5.1'deki "elleçlenmeden geçme"). Değeri, her varış için
ayrı bir aracın koca seyir tabanını, tek aracın küçük detour maliyetiyle değiştirmesinden gelir. Bu veride
tek adımda 21,65M → 13,10M (**−%40**), çünkü slotların %98'i tek başına bir aracı bile dolduramayacak kadar
küçük.

### 7.3 Aktarma / hub — farklı çıkışlardan ortak varışa (o_v9)

Multi-drop'un bir **kör noktası** var: yalnız **aynı çıkıştan** gelen yükleri birleştirebiliyor. Ama
bazen bir uzak varışa (ör. Şanlıurfa) **14 farklı çıkıştan** küçük yükler gidiyor — bunlar farklı
çıkışlardan olduğu için multi-drop birleştiremiyor, her biri ayrı yarı-boş araçla gidiyordu. Çözüm:
bu yükleri bir **hub'da (ara merkez) buluşturmak**. Yük önce çıkışından hub'a gider (leg1: O→H), orada
diğer yüklerle birleşip **tek dolu araçla** nihai varışa taşınır (leg2: H→D). Bedeli bedava değil: yük
hub'da iki kez elleçlenir (indir + yeniden yükle) ve bir süre bekler. Ölçtük: net **−0,31M** kazanç.
İlginç bir denge de gözlemledik — hub üzerinden geçmek yolu uzattığı için SLA cezası **bilinçli olarak
arttı**, ama araç maliyetindeki düşüş bunu fazlasıyla karşıladı. (o_v9c'de aktarmayı sadece greedy havuza
değil **column-gen keşif turlarına** da taşıyınca SLA yeniden düştü — her iki kalem birden iyileşti.)

### 7.4 09:00 → 17:00 bekletme (o_v11)

EDA'da net bir desen bulmuştuk: talebin **%91'i 17:00**'de, yalnız %9'u 09:00'da geliyor. Bu yüzden 09:00
yükleri seyrek ve çıkışta **yarı-boş** araçlar doğuruyordu. Fikir basit ama etkili: her 09:00 partisini,
**aynı gün aynı çıkıştaki 17:00 grubuna da** aday olarak ekledik. Böylece üreticiler, o 09:00 yükünü 17:00
yüküyle **birleştiren** dolu araç adayları da üretti (09:00 yükü 8 saat bekler, bu bekleme SLA'ya sayılır).
Sonra **CP-SAT seçer**: "bu yükü 09:00'da yarı-boş mu çıkarayım, yoksa 17:00'de doluyla mı birleştireyim?"
— hangisi ucuzsa. Aday havuza yalnız **eklendiği** için (var olan seçenekler durur) maliyet ancak düşebilir.
Sonuç: −0,37M, doluluk +1,9 puan. Bu, "erteleme makinesinin" gün-içi (+8 saat) hâlidir.

## 8. Erteleme (Feasibility Güvencesi) ve P90 Kolu

### 8.1 Erteleme — algoritmanın "patlamamasını" garanti etmek

Bir teknik gerçek: CP-SAT'ın kota kısıtları **katıdır** (hard constraint). Yani bir (TM, gün) hücresinde
talep, elleçleme kotasını aşıyorsa, CP-SAT o problemi **çözülemez (infeasible)** ilan eder ve hiçbir plan
üretmez — program çöker. P50 talebinde bu nadiren olur, ama **P90'da veya yoğun bir sürpriz veri setinde**
gerçekleşebilir.

Jüri kuralı bu duruma zaten bir çıkış veriyor: "kota aşılırsa yük ertesi güne bekletilir." Biz de tam bunu
modelledik. Bir (TM, gün) hücresi kotayı aşıyorsa, o TM'nin partilerine **sonraki güne kaymış** tekil
aday rotalar ekledik; CP-SAT kotayı bağladığında bu ertelenmiş adayı seçebilir → çözülemez durum ortadan
kalkar.

Bu yaklaşımın bir güzelliği şu: elleçleme kullanımı **rotadan bağımsızdır** — bir günde bir TM'de kalkan
ve varan toplam desi, hangi rotalar seçilirse seçilsin aynıdır. Bu yüzden "hangi (TM, gün) hücrelerinin
gerçekten kotayı aştığını", plandan **bağımsız olarak ve kesin** biliriz; erteleme adaylarını yalnız
gerçekten aşan hücreler için üretiriz, gereksiz aday şişmesi olmaz. Bunun anlamı, bu güvencenin
**kanıtlanabilir biçimde sağlam** olmasıdır — teknik terimiyle *provably robust*. Yani hangi veri gelirse
gelsin (P90, sürpriz veri, yoğun bir hafta), algoritma çözülemez duruma düşüp çökmez; her zaman geçerli
bir plan üretir, çünkü aşan her hücre için önceden bir kaçış yolu (erteleme adayı) hazırlanmıştır. P50'de
bu mekanizma nötrdür (maliyeti değiştirmez), ama **final aşamasının sürpriz/yoğun verisi için bir
sigortadır** — teslim ettiğimiz çözümün sadece bu veri setinde değil, gelecek veride de ayakta kalacağının
güvencesi.

### 8.2 P90 güvence kolu — belirsizliğe karşı kapasite ayırma

İki kollu stratejimizin ikinci kolu. **P50** ana plandır (medyan senaryo, maliyet-optimal). **P90** ise
bir güvence: gerçek talep, tahminimizin medyanını aşarsa taşıma kapasitesi önceden ayrılmış olsun diye
talebi üst bandına (P90) göre çözeriz. Pickup'lı P90 sonucu: **15.573.519 TL** (pickup öncesi 16,26M'den
−0,69M). P50 → P90 geçişi maliyeti +%55,7 artırıyor — bu, "belirsizliğe karşı sigortanın fiyatıdır".

İlginç bir gözlem: pickup, P90'da P50'ye göre **daha az** kazandırıyor (−%4,2 vs −%12,9). Sebep mantıklı:
P90'da yükler zaten büyük ve araçlar **dolu** (doluluk %76), dolayısıyla pickup'ın doldurabileceği boş
kapasite az. Pickup'ın değeri **boş giden kapasiteyle orantılıdır**; talep arttıkça o boşluk kapanır.

**Neden P90'ı teslim etmiyoruz?** Çünkü jüri optimizasyon başarımızı **bizim kendi tahminimiz üzerinden**
ölçüyor. P90'a göre plan yaparsak, olmayan talep için de araç çıkarmış oluruz ve optimizasyon skorumuz
**kötüleşir**. Doğru strateji: teslim planı P50 (maliyet-optimal), belirsizlik yönetimi ise tahmin
tarafında (conformal band) ve çizelgeleme kararlarında yapılır. P90 kolu **rapor ve savunma için** üretilir.

## 9. ⭐ o_v13 — Ara Durakta Yükleme (Pickup): Geç-Aşama En Büyük Atılım

Optimizasyonun mutlak en büyük tek sıçraması o_v3 konsolidasyonuydu (−26M). Pickup ise **geç aşamanın en
büyük atılımıdır**: 11,43M gibi olgun bir noktadan bir hamlede **−1,47M** kazandırdı ve ilk kez 10 milyonun
altına indirdi. Bizim için ayrıca özeldir, çünkü **jürinin bir soru-cevabından** doğdu — yani yeni bir
bilgi kaynağını dinleyip değerlendirmenin somut karşılığı.

**Nasıl başladı.** Jüri, tır kapasitesi sorulduğunda şunu yazdı: *"Tır kapasitesi bir gün içinde
yanaşabilecek toplam tırı ifade eder. **Merkezden ayrılmadan tekrar yükleme yaparsanız tek tır olarak
sayılır**, merkezden ayrılıp yeniden geldiği durumda 2 tır olarak sayılır."* Bu cevap iki kapıyı açtı:
(1) bir araç ara durakta yükünü indirip **oradan yeni yük alabilir** (bunu o güne kadar hiç yapmıyorduk —
tüm rotalarımız "çıkışta yükle → duraklara dağıt" biçimindeydi); (2) bu yeniden yükleme **ek tır kotası
harcamıyor** (aynı yanaşma sayılıyor). o_v1..o_v12'nin hiçbirinde bu rota tipi yoktu; pickup **doğrudan bu
cevabın ardından** kuruldu.

**Kazancın kaynağı.** §1.3'teki "sabit araç ücreti yok" gerçeğinin en güçlü sonucu burada. Bir araç zaten
D₁→D₂ yolunu kat ediyorsa, D₁'den D₂'ye giden bir yükü almanın ek maliyeti **yalnız elleçleme süresidir**;
o yük için ayrı bir aracın km + seyir tabanı **tamamen** kurtulur. Elle doğrulanmış örnek (Kamyon):

| Senaryo                                                               | Maliyet              |
| --------------------------------------------------------------------- | -------------------- |
| (a) araç İst→Yalova(5.000)→Eskişehir(4.000), pickup yok          | 7.189,4 TL           |
| (b) **aynı araç Yalova'da +3.000 desi alıyor** (Eskişehir'e) | **7.507,7 TL** |
| (c) o 3.000 desi için ayrı araç (Yalova→Eskişehir)               | 5.019,2 TL           |

Pickup ile toplam **7.507,7 TL**, ayrı araçla **12.208,7 TL** → **%38,5 tasarruf**. Ek maliyet yalnız
elleçleme (+318 TL), kurtulan ise koca bir seferin tabanı (5.019 TL).

**Kritik ayrım (ilk testte yanlış kurup gördük).** Pickup, "yeni bir sefer yerine pickup" demek değildir.
Araç o yolu **zaten kat etmiyorsa** kazanç sıfırdır — çünkü km ve süre yine ödenir. Değer tamamen **boşta
giden kapasiteyi yol üstünde doldurmaktan** gelir. Bu ayrımı ilk denememizde yanlış kurup ölçerek gördük;
doğru çerçeve budur.

**Uygulama.** Değerlendiriciye geriye-uyumlu bir `alimlar` alanı eklendi (i. durakta araca alınan yükler);
elleçleme kotasında indirme ve yeniden yükleme **ayrı olay** sayılır, ama tır kotasında ara durak **tek
yanaşmadır** (jüri kuralı). Kapasite artık **anlık yüke** bakar (`maks_yuk`) — çünkü pickup'lı rotada yük
yolda değişir; toplam desi kapasiteyi aşabilir ama araç hiçbir an aşırı yüklü olmayabilir. Aday üretimine,
column-generation döngüsünün **4. keşif pass'i** eklendi: her turda CP-SAT'ın seçtiği çok-duraklı rotaların
ara duraklarında, ileri bir durağa giden ve o an **hazır olan** (talep tamamlanmış) yükler aranır.

**Sonuç (P50):**

|                                            | v12b (eski şampiyon) | **v13 (pickup)**         | Δ                              |
| ------------------------------------------ | --------------------- | ------------------------------ | ------------------------------- |
| **TOPLAM (8 çekirdek)**             | 11.428.510            | **9.959.850**            | **−1.468.660 (−%12,9)** |
| Fiziksel araç                             | 488                   | 377                            | −111                           |
| Ortalama doluluk                           | %55,5                 | %67,1                          | +11,6 puan                      |
| Toplam km                                  | 466.261               | 390.557                        | −%16                           |
| **Çalışma süresi (8 çekirdek)** | 76 sn                 | 76 sn*(→ 698 sn tam tavan)* | ~aynı¹                        |

_¹ Süre karşılaştırması ince bir konu (§10.2): v12b 60 sn tavanla 76 sn'de biterken, v13'ün zengin havuzu
CP-SAT'a daha çok iş verir ve tavana çarpar. Teslim ayarında (4 çekirdek / 60 sn) v13 ~6,2 dakikadır —
v12b ile aynı zarfta ama %10 daha ucuz plan._

**Doğrulama.** 0 kısıt ihlali, 0 eksik talep, elleçleme/tır kotası 0 aşım; 560 pickup satırının tamamında
yük yüklendiğinde hazırdı (zamanlama teyidi). Kazanç şans değil: aynı ayarın 3 bağımsız koşusu %0,1 bandında
(9,9599 / 9,9689 / 9,9696M). Ve farklı bir haftada (22-28 Haz) da doğrulandı — tahminle −%8,8, gerçek
taleple −%8,5. Yani pickup tek bir şanslı haftaya değil, problemin yapısına dayanan gerçek bir kaldıraç.

## 10. Runtime Mühendisliği — Hız da Puandır

Şartname, gelişmiş çözüm aşaması değerlendirmesi için bir puanlama formülü verdi:
`Toplam Skor = 0,60 × Maliyet + 0,20 × Kısıt + 0,20 × Hız`, ve değerlendirmenin standart bir bulut
konteynerinde (**4 çekirdek / 16 GB RAM**) yapılacağını belirtti. (Bu formülün kesin katsayılarının ve
referans değerinin nihai değerlendirmede aynen mi kalacağı bize net bildirilmedi; formülü şartnamede
verilen haliyle esas alıyoruz.) Hızın da puanlandığını bilmek, onu **ayrı bir mühendislik hedefi** olarak
ele almamızı gerektirdi — sadece ucuz değil, aynı zamanda hızlı bir çözüm.

### 10.1 De-pandas + Numba — kodu neyin yavaşlattığını bulup gidermek (o_v12 / o_v12b)

Hızı iyileştirmenin ilk adımı, zamanın **nerede** harcandığını ölçmektir (profilleme). Profil çıkardığımızda
darboğaz netti: sürenin çoğu, maliyet/SLA/elleçleme hesaplayan üç fonksiyonda (`rota_hesapla`, `_rota_sla`,
`gun_bol`) geçiyordu — çünkü bunlar optimizasyon boyunca **2,6 milyon kez** çağrılıyor. Peki bu üç fonksiyon
neden yavaştı? Cevap **pandas**tı. Pandas, veri analizi için mükemmel bir kütüphanedir, ama bu kadar çok
sayıda **minik** çağrıda, her `Timestamp`/`Timedelta` nesnesi oluşturmanın ve saklamanın bir maliyeti var;
bu küçük maliyet 2,6 milyonla çarpılınca devasa bir yavaşlığa dönüşüyordu.

**Çözüm A — de-pandas (o_v12).** "Pandas'ı sıcak yoldan kaldır" demek. Zaman değerlerini pandas Timestamp
nesneleri yerine **düz tamsayılar** (gün başından itibaren geçen dakika) olarak tuttuk ve tüm hesabı bu
tamsayılarla yaptık (`R2` fonksiyonu). Kritik nokta: `R2`, kanonik `rota.py`'ın **doğrulanmış hızlı
kopyasıdır** — ikisinin sonucu birbirinden farkı **0,000000000** olacak şekilde birebir aynı (yani hız
için doğruluktan hiç ödün vermedik). Nihai skor her zaman yavaş ama güvenilir kanonik değerlendiriciyle
üretilir; hızlı `R2` yalnız optimizasyon içindeki milyonlarca ara-hesap için kullanılır.

**Çözüm B — Numba (o_v12b).** Numba, Python fonksiyonlarını çalışma anında **makine koduna derleyen**
(JIT — just-in-time compilation) bir kütüphanedir; en çok çağrılan maliyet hesabını (`@njit` işaretiyle)
derlenmiş bir "kernel"e taşıdık. Numba **opsiyoneldir**: kurulu değilse kod otomatik olarak saf-Python
sürümüne düşer (jüri ortamında Numba yoksa program **patlamaz**, sadece biraz yavaşlar).

**Sonuç.** İki çözüm birlikte, skoru **hiç değiştirmeden** süreyi 8 çekirdekte 150 sn'den 76 sn'ye indirdi.
İlginç bir bulgu: asıl kazanç **de-pandas'tandı**; Numba yalnız %14 ekledi. Sebep, Numba'nın minik-çok-çağrı
senaryosunda parlamaması — her çağrıda veriyi Python'dan derlenmiş koda taşımanın (marshalling) küçük bir
maliyeti var ve bizim çağrılar zaten çok küçük olduğu için bu maliyet kazancın çoğunu yiyor. Numba, büyük
sayısal dizilerde çok daha etkilidir; bizim iş yükümüz milyonlarca minik rotadan oluştuğu için katkısı
mütevazı kaldı. Yine de kodda tutuyoruz — ücretsiz gelen her hız iyidir.

### 10.2 ⭐ Çekirdek × CP-SAT tavanı matrisi — hız/maliyet takasının kanıtı

o_v13'ün hem 4 hem 8 çekirdekte, farklı CP-SAT tavanlarıyla ölçümü. Hepsi geçerli (0 ihlal):

| Çekirdek   | Tavan           | Skor (TL)                            | Süre                 |
| ----------- | --------------- | ------------------------------------ | --------------------- |
| 8           | 180 sn          | 9.959.850                            | 698 sn (11,6 dk)      |
| 8           | 60 sn           | 10.004.433                           | 300 sn (5,0 dk)       |
| 4           | 180 sn          | 10.154.196                           | 948 sn (15,8 dk)      |
| 4           | 90 sn           | 10.278.975                           | 499 sn (8,3 dk)       |
| **4** | **60 sn** | **10.303.665 → 10.381.178¹** | **6,0–6,2 dk** |

_¹ teslim koşusu, şablon formatlı; aynı ayar._

Bu matristen üç bulgu çıktı:

**1. CP-SAT'a daha çok süre vermek maliyeti gerçekten düşürüyor — ama azalan verimle.** Havuz artık zengin
olduğu için (pickup, aktarma, multi-drop hepsi aday üretiyor), CP-SAT'a verilen ek süre işe yarıyor: 4
çekirdekte tavanı 60'tan 180 sn'ye çıkarmak maliyeti %1,46 düşürüyor. Ama bunun bedeli süreyi **%164**
artırmak. Yani ilk saniyeler çok değerli, sonrakiler giderek daha az kazandırıyor.

**2. Worker (çekirdek) sayısı süreyi değil, çözüm kalitesini belirliyor.** Bu, önceki modelden büyük bir
fark. Eski modelde (v12b) 8 worker'dan 4'e inmek çalışma süresini **4,4 katına** çıkarıyordu. v13'te ise
aynı geçiş süreyi yalnız **%20** uzatıyor. Sebep: v13'te runtime CP-SAT'ın **zaman tavanına** bağlı —
tavan sabit olduğu için süre de sabit kalıyor; değişen tek şey, o sabit sürede kaç çekirdeğin ne kadar
geniş arama yaptığı, yani **çözümün kalitesi** (4 çekirdek aynı sürede biraz daha kötü çözüm buluyor:
10,30M vs 10,00M). Pratik faydası: jüri donanımındaki davranış **öngörülebilir** — süre hedefimizi
tutarız, yalnız kalite bir tık düşer.

**3. Süreyi düşürmenin doğru yeri "havuz" değil, "tavan"dır.** Pickup aday sayısını kısarak hızlanmayı
denedik (durak başına en fazla 3 pickup adayı): sonuç maliyeti +0,50M kötüleştirdi **ve süreyi bile
düşürmedi**. Yani darboğaz aday sayısı değil, CP-SAT'ın tavana çarpmasıydı. Bu yüzden hızlanmak için havuzu
budamak yerine CP-SAT tavanını ayarlamak doğru yoldur.

**Teslim kararı: 4 çekirdek / 60 sn / tam havuz + dedup.** Gerekçesini açalım, çünkü bu bir maliyet-hız
takasıdır. Jüri donanımı 4 çekirdek; orada 60 sn tavan **10,38M / 6,2 dakika** veriyor, 180 sn tavan ise
**10,15M / 15,8 dakika**. Yani 180 sn, maliyette yalnız %1,46 kazanmak için süreyi **2,6 katına** çıkarıyor.
Puanlama `0,60×Maliyet + 0,20×Hız` olduğu ve hız puanı takımlar arası kıyaslanacağı için, 16 dakikalık bir
koşu bu %1,5'lik maliyet avantajını fazlasıyla götürür. 60 sn seçimi hem **düşük maliyeti** (10,38M, eski
şampiyona göre −%9,8) hem **hızlı süreyi** (6,2 dk) birlikte tutar — ikisinin en dengeli noktası. Ayrıca 60
sn, yoğun bir hafta ya da final aşamasının sürpriz verisinde süre patlamasına karşı bir **güvenlik payı**
da bırakır. Son bir ayrıntı: worker sayısı donanıma otomatik uyarlanır (`min(10, os.cpu_count())`) — 4
çekirdekli jüri kutusunda otomatik 4 olur, aşırı abonelik olmaz, ve hiçbir donanımda patlamaz.

### 10.3 Determinizm — neden aynı sonucu vermiyor, ve sabitlemenin bedeli (o_v14)

Bir gözlem: aynı kodu, aynı veriyle, aynı ayarla iki kez çalıştırdığımızda **birebir aynı planı**
vermiyorduk. Skor %0,1 bandında oynuyordu (9,9599 / 9,9689 / 9,9696M) — maliyet neredeyse aynı ama **hangi
aracın hangi yükü taşıdığı** değişiyordu. Bu, "farklı makinelerde farklı plan çıkar mı?" endişesini doğurur,
o yüzden hem sebebini hem çözümünün bedelini ölçtük.

**Neden oynuyor?** İki kaynak var. **Birincisi CP-SAT'ın çok-işçili modu:** 8-10 worker'ı paralel
çalıştırıp süre dolunca kesiyoruz; süre bittiğinde elde hangi çözümün olduğu, o an hangi worker'ın nereye
vardığına — yani makinenin anlık yüküne — bağlı. **İkincisi bizim Python kodumuz:** aday rota kümelerini
`set`/`frozenset` ile tutuyoruz, ve Python'da metin (string) hash'i her süreçte **rastgele tohumlanır**;
bu, kümelerin gezilme sırasını, dolayısıyla aday üretim sırasını her koşuda değiştiriyor.

**Sabitlenebilir mi? Evet — ama iki katman birden gerekiyor.** Yalnız CP-SAT'ı sabitlemek (`random_seed` +
`interleave_search` + iş-birimi bazlı süre limiti) yetmedi, %0,19 fark kaldı. `PYTHONHASHSEED=0` ekleyip
Python tarafını da sabitleyince iki koşu **ondalık basamağına kadar aynı** çıktı (10.563.252,4981 ×2) ve
üretilen taşıma planı CSV'leri **bit-bit özdeş** oldu (MD5 ile doğrulandı). Yani tam tekrarlanabilirlik
teknik olarak elimizde.

**Bedeli neden var — sebep-sonuç.** Deterministik modda CP-SAT'a `interleave_search` diyoruz; bu, paralel
worker'ları rastgele yarıştırmak yerine **deterministik bir sırayla** çalıştırır. Ama tam da bu sıralı
çalışma, paralel aramanın gücünü büyük ölçüde söndürür: worker'lar birbirini bekler, aynı süre bütçesinde
**daha az düğüm** taranır, dolayısıyla biraz **daha kötü (daha pahalı)** bir çözümde durulur. Bir başka
deyişle, aramayı tümüyle sabitlemek, keşfedilebilecek daha ucuz rotaların bir kısmının ortaya çıkmasını
engelliyor. Adil kıyasta (benzer duvar saati) bedel **+%5,6 maliyet** (10,00M → 10,56M). Üstelik iş-birimi
bazlı limit, duvar saatini de öngörülemez yapıyor (aynı 60 birim, bir koşuda 248 sn, başka koşuda 590 sn
sürdü). Ölçüm tablosu:

| Mod | Hash tohumu | Skor (TL) | Süre | Birebir tekrar? |
|---|---|---|---|---|
| **Non-det (teslim modeli)** | serbest | **10.004.433** | 300 sn | ❌ %0,1 bandında oynuyor |
| Deterministik (yalnız CP-SAT) | serbest | 10,33M / 10,35M | 590 sn | ❌ hâlâ %0,19 fark |
| Deterministik (CP-SAT + Python) | **0** (sabit) | **10.563.252,4981** *(×2)* | 248 sn | ✅ **bit-bit özdeş plan** |

_Son satır iki kez koşuldu ve hem skor (ondalık basamağına kadar) hem üretilen taşıma planı CSV'si (MD5)
birebir aynı çıktı._

**Kararımız: teslim modeli non-deterministik kalır** (`DETERMINISTIK = False`). Gerekçeler:

1. Maliyet, puanlamada %60 ağırlıklı — %5,6'lık bir artışı karşılayacak bir kazanç yok.
2. Mevcut varyans zaten %0,1 bandında; plan **kararlarını** değiştirmiyor, sadece eşdeğer maliyetli
   alternatif rotalar arasında geziniyor.
3. **Asıl çözüm mimari.** "Herkes kendi makinesinde yeniden hesaplasın da aynı çıksın" bir gereklilik
   değil. Sistemimizde plan **bir kez** üretilip `kosu_id` ile PostgreSQL'e yazılıyor, tüm taraflar
   (dashboard, API) onu **okuyor** (§C). Yani üretimde plan **tek merkezde** üretilip dağıtılır; herkes
   aynı koşuyu gördüğü için "farklı makine, farklı plan" sorunu **doğmaz**. Şu an bileşenler her
   geliştiricinin makinesinde ayrı çalışıyor; tek ortak sunucuya almak bir **dağıtım adımıdır**, kod
   değişikliği gerektirmez.

Determinizm bayrağı kodda duruyor — istenirse `DETERMINISTIK=True` + `PYTHONHASHSEED=0` ile birebir
tekrarlanabilir mod açılır. Yani bu bir eksiklik değil, **ölçülmüş ve bilinçli bir tasarım tercihidir.**

## 11. Jüri Kurallarına Uyum ve Teslim Denetimi

Jürinin net bir kuralı var: "format dışı dosya değerlendirilmez." Yani dünyanın en iyi planı bile, çıktı
biçimi yanlışsa **hiç puan almaz**. Bu yüzden teslim tarafını da bir mühendislik problemi gibi ele aldık
ve hiçbir şeyi göze/tesadüfe bırakmadık.

**Multi-drop'u jüri şablonuyla aynı biçimde — zincir olarak — yazmak.** Bu, teslime yakın yakaladığımız
kritik bir sorundu. Bir multi-drop seferi (İstanbul→Yalova→Eskişehir) iç modelimizde doğru, ama çıktıya
yazarken her durağı **seferin ilk çıkış TM'sinden** ("İstanbul'dan") ayrı bir satırmış gibi yazıyorduk —
bir tür "yıldız" gösterimi. Oysa jürinin kendi şablonu **zincir** bekliyor: V0001 önce İstanbul→Yalova,
sonra **Yalova→Eskişehir**; ve bir yük geçtiği her bacakta bir satır alıyor. Bu yanlış gösterimin iki kötü
sonucu vardı: (1) planın **%28'i** (multi-drop seferleri) yanlış biçimdeydi; (2) tek bir tırın tek
yanaşması, çıktıda iki ayrı "çıkış" gibi görünüp **sahte tır kotası ihlali** doğuruyordu. Çıktıyı zincir
olarak yeniden yazınca hem şablona uyduk hem sahte ihlaller kayboldu (skor değişmedi — sadece gösterim
düzeldi).

**Süre formatı — jüri cevabına birebir.** Jüri, süre sütunlarının **dakika cinsinden ve en yakın büyük tam
sayıya yuvarlanmış** olmasını istedi (0,92 saat = 55,2 dk → **56**; elleçleme için desi × 0,01 → yukarı
yuvarla). Çıktımızı bu kurala uydurduk ve jürinin **kendi örneğiyle** doğruladık. Önemli: yuvarlama yalnız
çıktı biçimindedir — iç maliyet/SLA hesabı tam çözünürlükte (ondalık dakika) kalır, yoksa küçük yuvarlamalar
birikip skoru bozardı.

**Şablon biçimi.** Tarih `29.06.2026` (gg.aa.yyyy), saat `09:00:00` — jüri şablonundaki örnek satırlardan
birebir alındı.

**İki katmanlı otomatik denetim.** Elle göz kontrolüne güvenmedik; teslim dosyalarını makine ile denetleyen
iki katman kurduk:

- **Şema doğrulama (`core/io/semalar.py`, pandera kütüphanesi):** iki teslim dosyasının şeması
  makine-okunur biçimde tanımlı — sütun adı **ve sırası**, veri tipi, biçim deseni (Talep ID `D#####`,
  Araç ID `V####`, tarih/saat kalıpları) ve değer aralıkları. Bir sütun kayar ya da biçim bozulursa
  **anlaşılır bir hata** verir. Bu özellikle final aşaması için bir sigortadır: sürpriz veride biçim
  değişirse, sessizce yanlış sonuç üretmek yerine bize açıkça haber verir.
- **Çapraz-tutarlılık denetimi (`core/io/teslim_denetimi.py`):** gönderimden önce çalıştırdığımız tek
  komut. Şemaya ek olarak iki dosyanın **birbirini tutup tutmadığını** ve planın jüri kurallarına uyduğunu
  kontrol eder: Talep ID eşleşmesi (plandaki her kök ID tahmin dosyasında var mı), talep bütünlüğü (eksik/
  fazla taşınan yük), elleçleme kotası (gece-yarısı oransal), tır kotası (yanaşma sayımı), tır-yasağı
  merkezler. Bu denetimi yazarken bile iki ince tuzak yakaladık (elleçleme desisini süreden geri türetmenin
  küçük yükleri şişirmesi; tır sayımının sefer kimliği gerektirmesi) — ikisini de doğru kurduk. **Nihai
  teslim dosyalarında tüm kontroller temiz geçiyor.**

---

# C. SİSTEM & DASHBOARD

> Optimizasyon ve tahmin, yarışma anında çalışacak üretim kodudur (`core/`). Ama bir karar destek sistemi,
> sonucu **görünür ve sorgulanabilir** kılmalı. Bu bölüm, üç bağımsız servisin (PostgreSQL + FastAPI +
> ASP.NET dashboard) nasıl birlikte çalıştığını ve "tek doğruluk kaynağı" ilkesini nasıl uyguladığımızı
> anlatır. Dashboard/backend Zeynep'in alanıdır; algoritma çekirdeği Ömer'in.

## 12. Mimari — Üç Servis, Tek Doğruluk Kaynağı

Bir optimizasyon algoritması ne kadar iyi olursa olsun, çıktısı bir Excel dosyasında kalırsa kimse ona
bakıp karar veremez. Bu yüzden çözümün etrafına, sonucu **görünür, gezilebilir ve sorgulanabilir** kılan
bir karar destek sistemi kurduk. Sistem üç bağımsız servisten oluşur ve her biri diğerine yalnız iyi
tanımlı arayüzler (HTTP ve SQL) üzerinden bakar — yani biri değişince öteki yeniden yazılmaz:

```
┌──────────────┐   HTTP / JSON  ┌──────────────┐   SQL (psycopg2)  ┌──────────────┐
│  Dashboard   │ ──────────────▶│     API      │ ─────────────────▶│  PostgreSQL  │
│ ASP.NET MVC  │◀────────────── │   FastAPI    │◀───────────────── │  (postgres)  │
│   (.NET 8)   │  :5000         │  (Python)    │                   │   :5432      │
└──────────────┘                └──── :8000 ───┘                   └──────────────┘
      Zeynep                    Ömer (core köprüsü)                  ortak veri
```

- **`core/`** — algoritma (tahmin + optimizasyon); yarışma anında fiilen çalışacak üretim kodu.
- **`services/api`** (FastAPI, Python) — `core/`'un ürettiği planı PostgreSQL'e yazan ve dashboard'a sunan
  köprü. Aynı zamanda "canlı koşu" (yeni senaryo üret) isteklerini karşılar.
- **`services/dashboard`** (ASP.NET MVC, .NET 8) — kullanıcının gördüğü arayüz. İlke olarak **yalnız çizer**,
  hesap yapmaz.

### Neden bu üçe bölme?

İki kişilik bir takımda paralel çalışabilmek için işleri temiz sınırlarla ayırmak gerekiyordu. Ömer
`core/` ve `services/api`'de (algoritma + veri köprüsü), Zeynep `services/dashboard` ve `db/`'de
(arayüz + şema) çalıştı. Buluşma noktaları yalnızca **API sözleşmesi** (hangi uç hangi JSON'u döndürür)
ve **veritabanı şeması** oldu. Bu sayede biri algoritmayı geliştirirken öteki arayüzü, birbirini
beklemeden ilerletebildi.

### Tek doğruluk kaynağı ilkesi

Bir metriği (ör. "günün toplam maliyeti") **iki farklı yerde** hesaplarsanız — bir kez algoritmada, bir
kez tarayıcıda — er ya da geç iki sonuç birbirini tutmaz ve hangisinin doğru olduğunu kimse bilemez. Bunu
projede **bizzat yaşadık**: bir noktada ekranda "%22,5 doluluk" görünürken gerçek değer %65'ti. Sebep
inceydi — plan artık zincir yazıyor (bir yük geçtiği her bacakta bir satır alır, §11), dolayısıyla ham
satır sayısı "bacak" değil "taşıma kaydı"dır; tarayıcı bunu karıştırıp doluluğu yanlış hesaplıyordu.

Dersimiz şu oldu: **hesap tek bir yerde, arka uçta yapılır; arayüz yalnız hazır sonucu gösterir.** Gün
bazlı KPI'ları da veritabanı üzerinde (SQL sorgusuyla) hesaplayan bir uç ekledik (`GET /kosu/{id}/
kpi-gunluk`); doğru seviye ayrımı (bacak = sefer+sıra tekil, taşınan desi = yalnız nihai varışta sayılır,
aktarmalı yük hub'da iki kez sayılmasın diye) bu sorgunun içinde bir kez tanımlıdır. Böylece ekrandaki
her rakam, raporumuzdaki rakamla birebir aynıdır.

Bu ilkeyi tek bir uçla bırakmadık, **ekrandaki tüm sayısal panelleri** arka uca taşıdık: filo doluluk
barları (`GET /kosu/{id}/filo-doluluk` — sefer bazında, aracın çıkıştaki yükü ÷ kapasitesi), en yoğun
hatlar tablosu (`/en-yogun-hatlar` — bacak bazında toplanmış, gün başına ilk N) ve SLA cezası listesi
(`/sla-cezalari`). Arayüzde artık yalnızca **çizim** kodu var; hesap yapan tek satır bile kalmadı — eski
istemci hesapları API'nin ulaşılamadığı durum için *yedek* olarak duruyor (uç boş dönerse ekran boş
kalmasın diye). Doğruluğu iki bağımsız sorguyu çaprazlayarak denetledik: `/filo-doluluk` satırlarının
sefer sayısıyla ağırlıklı ortalaması, `/kpi-gunluk`'ün günlük doluluk değerine **dört ondalık basamağa
kadar** eşit çıkıyor; `/sla-cezalari` toplamları da günlük SLA cezasıyla kuruşuna kadar tutuyor.

## 13. Veritabanı Tasarımı ve API Katmanı

### 13.1 PostgreSQL şeması

Veritabanı, bir optimizasyon çalıştırmasının ("koşu") tüm çıktısını hiyerarşik bir zincir olarak saklar ve
her koşuyu kendi kimliği altında **izole** tutar (üzerine yazma yok — eski koşular durur, yeni koşu ayrı
kaydedilir):

```
kosu  (senaryo: P50 / P90 / GERÇEK, tarih aralığı, çalışma süresi, ana_plan bayrağı)
 ├─ arac      (fiziksel araç: tür, tip, sefer sayısı, maliyet)
 ├─ sefer     (bir aracın bir kalkışta yaptığı iş: çıkış + durak zinciri)
 │   └─ plan_legs  (tek bacak: iki durak arası; sefer_id + sira_no ile sıralı)
 ├─ forecast  (talep tahmini: tahmin_desi, p50, p90, gercek_desi)
 └─ kpi_ozet  (koşu özeti: toplam maliyet, SLA, doluluk, araç sayıları …)
```

Şema, yarışma boyunca **migration'larla** (sıralı SQL dosyaları) evrildi: `001` temel şema → `002` koşu/
sefer/gerçek zincirine geçiş → `003` eğitim verisi tabloları (`ham_talep`/`bos_slot`) → `004` P90 alanı →
`005` ana plan bayrağı → `900` hazır koşu tohumu (yeni bir makinede `docker compose up` yapıldığında
dashboard'un boş değil, dolu açılması için nihai planı SQL olarak gömer). Tüm yabancı anahtarlar
`ON DELETE CASCADE`: bir koşu silinince ona bağlı tüm sefer/bacak/tahmin/KPI otomatik temizlenir.

### 13.2 API uçları

API iki iş yapar. **Okuma** (dashboard'un veri kaynağı): `/kosular` (koşu listesi), `/kosu/{id}/forecast`,
`/plan_legs`, `/kpi`, `/kpi-gunluk`, `/seferler`, `/tm_kapasite`, `/tm_koordinat`, `/filo-doluluk`,
`/en-yogun-hatlar`, `/sla-cezalari` (son üçü §12'de anlatılan "hesap arka uçta" ilkesinin gereği).
**Çalıştırma** (canlı
senaryo üretme): `POST /run` bir tarih aralığı + senaryo alıp tahmin+optimizasyonu **ayrı bir süreçte**
başlatır ve hemen bir iş kimliği döner (istek bloklamaz); `GET /run/{id}` ilerlemeyi bildirir;
`DELETE /run/{id}` çalışan koşuyu **anında** iptal eder. İptal güvenliği kritik bir tasarım detayıdır:
koşu veritabanına yalnız **en son adımda** yazılır, ortada durdurulursa DB'ye hiçbir şey yazılmamış olur,
yani **yarım/bozuk koşu asla oluşmaz**. Bir de plan-vs-gerçek karşılaştırma uçları var (`POST /gercek-talep`,
`POST /kosu/{id}/gercek-eslestir`, `GET /karsilastir`) — bunları §14.3'te anlatıyoruz.

## 14. Dashboard — Ne Gösterir, Neden Kurduk

Dashboard, planı bir tablo yığını olmaktan çıkarıp **anlaşılır bir operasyon resmine** çevirir. Aşağıda
her bileşenin ne işe yaradığını ve neden koyduğumuzu anlatıyoruz — çünkü bu raporu okuyan birinin
dashboard'u fiilen çalıştırmadan da neler yapabildiğimizi görmesini istiyoruz.

### 14.1 Ana ekran: harita, KPI'lar ve koşu künyesi

**Harita (Leaflet).** 18 gerçek transfer merkezi koordinatı üzerinde, o günün tüm seferleri çizgilerle
gösterilir — çizgi rengi araç türünü (Tır/Kamyon/…), stili araç tipini (kiralık düz, spot kesikli) belli
eder. TM'ler, o günkü elleçleme doluluğuna göre açıktan koyuya renklenir (kota dolan/aşan merkezler ayrı
vurgulanır), böylece hangi merkezlerin darboğaz olduğu bir bakışta görülür. Bir TM'ye tıklanınca o
merkezin elleçleme ve tır kotası doluluğu açılır. Harita, o gün kalkan seferlerin yanı sıra **önceki
günden kalkıp o güne sarkan** (gece yarısını aşan) seferleri de soluk çizgiyle gösterir — çünkü
bacakların yarısından fazlası gece yarısını aşıyor ve araç o sabah hâlâ yolda.

**KPI kartları ve koşu künyesi.** Üstteki beş kart (günlük maliyet, SLA cezası, doluluk, kiralık/spot
araç, konsolidasyon) **seçili güne** aittir; hemen üstündeki "koşu künyesi" şeridi ise koşunun **tamamına**
ait toplamı gösterir (10,38M · 394 araç · %65,5 doluluk · ⏱ 6 dk 10 sn / 4 çekirdek). Bu ikisini bilinçli
olarak ayırdık — çünkü "günün maliyeti" ile "koşunun toplam maliyeti" farklı sayılardır ve karıştırılırsa
"ekranda 1,1M yazıyor ama raporda 10,4M" gibi bir kafa karışıklığı doğar. Künyede çalışma süresini de
gösteriyoruz, çünkü runtime da puanlanıyor (§10) ve sunumda bunu görünür kılmak istedik.

### 14.2 Sağ panel, Gantt ve senaryo üretme

**Sağ panel — araçlar, doluluk, en yoğun hatlar.** Sağ tarafta araç-bazlı bir liste (her aracın seferleri,
bacakları, taşıdığı desi; tıklanınca detay açılır) ve bir **araç ID arama** kutusu var — yüzlerce araç
arasında birini bulmak için. Altında filo doluluk oranları (araç türü × tip kırılımında), en yüksek hacimli
hatlar tablosu ve SLA cezası alan araçların listesi (ceza formülüyle birlikte: geciken desi × saat × 0,40).

**Gantt görünümü (araç × zaman).** Üst çubuktaki butonla açılan tam ekran zaman çizelgesi. Her araç bir
satır; o aracın gün boyunca yaptığı seferler, otobüs tarifesi gibi peş peşe bloklar olarak dizilir
(yükleme → seyir → her durakta boşaltma, saatleriyle). Multi-drop bir sefer, ardışık durakları tek zincir
olarak gösterir. Gece yarısını aşan seferler doğru yansıtılır (önceki günden sarkan araç, bu günün
Gantt'ında hâlâ meşgul görünür). Araç havuzu ataması sayesinde bir araç gün boyu izlenebilir.

**"Senaryo Üret" (Otomasyon) paneli — neden koyduk.** Dashboard yalnız hazır bir planı göstermekle
kalmıyor; sol paneldeki bu bölümden kullanıcı bir **tarih aralığı + senaryo** (P50 / P90 / GERÇEK) seçip
**canlı olarak yeni bir koşu üretebiliyor** — sistem o tarihe kadarki tüm veriyle tahmin yapar,
optimizasyonu çalıştırır ve sonucu yeni bir koşu olarak kaydeder. İlerleme çubuğu, tahmini süre ve bir
DURDUR butonu vardır. Bunu koymamızın iki nedeni var: (1) **final aşaması** — jüri sürpriz bir tarih
aralığı verdiğinde, arayüzden tek tıkla o dönemi çözebilmek; (2) **esneklik** — sabit bir çıktıya
mahkûm olmadan, istenen herhangi bir hafta için planı canlı üretebilmek.

> **Panelden üretilen koşu hangi ayarla çalışır?** Teslim ettiğimiz ana plan, jüri donanımını birebir
> taklit etmek için **4 çekirdeğe kısıtlanarak** üretilmiştir (§10). Dashboard'dan başlatılan canlı
> koşular ise bunun aksine **çalıştığı makinenin çekirdeklerini kullanır** (çözücü tavanı 10 çekirdek);
> CP-SAT tur başına zaman tavanı her iki durumda da aynıdır: **60 saniye**. Bu bilinçli bir ayrımdır —
> teslim rakamı en kötü (kısıtlı) donanımda dürüstçe ölçülsün, arayüzdeki keşif/demo koşuları ise
> gereksiz yere yavaşlamasın diye. Karışıklık olmaması için her koşunun **kullandığı çekirdek sayısı ve
> süresi koşu künyesine yazılır** ve ekranda "⏱ süre (N çekirdek)" olarak görünür; yani bir koşuya
> bakan kişi hangi donanım koşulunda üretildiğini her zaman görebilir.

### 14.3 Koşu seçici, arşiv ve plan-vs-gerçek karşılaştırma

**Koşu seçici ve arşiv.** Üstteki açılır menüden farklı koşular arasında geçilebilir (ana teslim planı,
P90 güvence koşusu, geçmiş demo koşuları…). Her koşu `kosu_id` ile arşivlenir ve istendiğinde geri
çağrılır; ana plan kazara silinmeye karşı korumalıdır. Böylece "şu senaryoyu bir daha göster" demek, koşuyu
yeniden çalıştırmadan mümkün.

Aşağıda anlatacağımız karşılaştırma paneli iki koşu gerektirdiği için, sistemi ilk açan kişinin boş bir
ekranla karşılaşmaması adına **kendi ölçtüğümüz örnek koşuyu da hazır kaydettik**: veritabanı, teslim
planının (koşu 1) yanında 22–28 Haziran haftasının **tahminle** (koşu 2) ve **gerçek taleple** (koşu 3)
çözülmüş iki planını da içerir. Yani panel ilk açılışta doludur ve aşağıdaki rakamlar ekranda birebir
görülebilir. Bu üç koşu bir kısıt değil, bir başlangıç noktasıdır — kullanıcı istediği iki koşuyu seçip
kıyaslayabilir ve "Senaryo Üret" ile kendi koşularını ekleyebilir (numaralar 4'ten devam eder).

**Karşılaştırma ("⇄ Karşılaştır") — amacı.** Bu, sistemin en güçlü karar-destek özelliğidir. İki koşuyu
**yan yana** koyar; asıl kullanım senaryosu şu: bir haftayı hem **bizim tahminimizle** hem o haftanın
**gerçekleşen talebiyle** çözüp ikisini kıyaslamak. Böylece "tahmin hatamızın operasyonel bedeli ne kadar?"
sorusunu sayıyla cevaplarız. Panel, ham maliyet farkının yanı sıra **desi başına maliyeti** de gösterir —
çünkü iki plan farklı miktarda yük taşıyorsa ham fark yanıltıcıdır (fark = hacim etkisi + verimlilik etkisi;
karşılaştırılabilir tek gösterge birim maliyettir, ve bu ayrıştırmayı panel rakamla gösterir). Ölçülen demo
(22–28 Haz): tahminle plan **11.765.268 TL**, gerçek taleple **10.733.840 TL** (−%8,77); taşınan yük
6,68M → 6,34M desi; **desi başına maliyet 1,761 → 1,694 TL (−%3,79)**. Panel bu farkı ayrıştırarak da
gösterir: toplam −1.031.428 TL farkın −608.767 TL'si **hacim etkisidir** (B planı 345.753 desi daha az
yük taşıyor × A'nın birim maliyeti), geriye kalan **−422.661 TL ise verimlilik farkıdır**. Yani "tahmin
hatasının operasyonel bedeli" **%3,79**'dur — tahminimiz kusursuz olsaydı aynı işi bu kadar daha ucuza
yapardık. Aynı ekranda A koşusunun tahmin doğruluğu da görünür: model 6.682.093 desi talep öngörmüş,
gerçekte 6.336.332 desi oluşmuş → **WAPE %24,4** (modelin bilinen seviyesi).

### 14.4 Öğrenme döngüsü — sistem neden kendi kendini besliyor

Bir tahmin modeli, yalnız kurulduğu günün verisiyle sınırlı kalırsa zamanla körelir: talep desenleri
değişir (yeni hatlar açılır, hacimler kayar, mevsimsellik döner) ama model hâlâ eski dünyayı bilir.
Gerçek bir karar destek sisteminin bunu çözmesi gerekir. Bu yüzden sistemi bir **kapalı döngü** olarak
tasarladık:

```
   [tahmin]  →  [optimizasyon]  →  [plan]  →  [operasyon gerçekleşir]
       ▲                                              │
       └──────────  gerçekleşen talep geri beslenir  ◀┘
```

**Nasıl çalışıyor.** Operasyon gerçekleştikçe, o gün fiilen oluşan talep `POST /gercek-talep` ucuyla
sisteme bildirilir ve eğitim verisine `kaynak='gercek'` etiketiyle **eklenir** (aynı slot yeniden
gönderilirse üzerine yazar, yani düzeltme kabul eder). Bundan sonra yapılan **her tahmin**, kesim
tarihine kadarki tüm veriyi — hem tarihsel hem yeni gerçekleşen kayıtları — kullanarak üretilir. Yani
sistem her hafta biraz daha çok şey bilerek tahmin yapar; kimsenin modeli elle yeniden eğitmesi gerekmez.
Bunu uçtan uca test ettik: sahte bir operasyon kaydı gönderdik, modelin onu eğitim kümesinde gördüğünü
ve cutoff'lu tahminin sızıntısız çalıştığını doğruladık.

**Neden bu kadar önemsedik.** Çünkü bir planın "iyi" olup olmadığı ancak gerçekle karşılaştırılınca
anlaşılır. Sistem hem tahmini hem gerçekleşeni sakladığı için (`forecast.gercek_desi`), "geçen hafta ne
kadar yanıldık, bu bize kaça mal oldu?" sorusunu **sayıyla** cevaplayabiliyor (§14.3'teki karşılaştırma
paneli). Bu, yalnız optimize eden bir araç ile **kendini ölçen** bir sistem arasındaki farktır.

**"Senaryo Üret" bu döngünün kullanıcı arayüzüdür.** Sol paneldeki bu bölüm, yukarıdaki döngüyü tek
tıkla çalıştırmanın yoludur: kullanıcı bir tarih aralığı ve senaryo seçer (P50 = model tahmini,
P90 = güvence bandı, GERÇEK = o dönemin fiili talebi), sistem o tarihe kadarki **tüm veriyle** tahmin
üretir, optimizasyonu koşturur ve sonucu yeni bir koşu olarak kaydeder. İlerleme çubuğu, geçen süre ve
tahmini bitiş gösterilir; istenirse DURDUR ile iptal edilir. Üç pratik faydası var: **(1) Final aşaması
hazırlığı** — jüri sürpriz bir tarih aralığı verdiğinde arayüzden tek tıkla o dönemi çözebiliriz;
**(2) senaryo karşılaştırma** — aynı haftayı hem tahminle hem gerçekle koşup farkı ölçebiliriz;
**(3) canlı gösterim** — sunumda "işte şu an, önünüzde plan üretiyoruz" diyebilmek.

> **Dürüst sınırlama.** Gerçek operasyon verisi (araçların GPS'i, şoför/teslimat sistemi kayıtları)
> HepsiJET'in kendi sistemlerindedir; bizim elimizde yok. Dolayısıyla döngüyü, geçmiş **gerçek talebi**
> "gerçekleşmiş operasyon" gibi kullanarak demo ediyoruz. Kurduğumuz şey, gerçek veri bağlandığı anda
> çalışmaya hazır **altyapıdır**: veritabanı şeması hem plan hem gerçek alanlarını (talep, sefer ve bacak
> düzeyinde) tutar, giriş ve eşleştirme uçları hazırdır. Ayrıca bileşenler şu an her geliştiricinin kendi
> makinesinde ayrı çalışıyor; tek ortak sunucuya almak bir **dağıtım adımıdır**, kod değişikliği
> gerektirmez.

## 15. Kurulum, Repo Yapısı ve Çalıştırma

### 15.1 Kurulum — iki yol

> Ayrıntılı adım adım rehber, sorun giderme ve gereksinimler: **[`KURULUM.md`](KURULUM.md)**

**Önce:** Yarışma verisi (gizli olduğu için) depoya dâhil değildir — 6 Excel dosyasını
`data/Gelismis_cozum/` klasörüne koyun.

**Yol A — Docker (önerilen, tek komut).** Bilgisayarda yalnız **Docker Desktop** olması yeterlidir;
Python/kütüphane kurulumu gerekmez. Arayüz, API ve veritabanı birlikte ayağa kalkar:

```bash
cd deploy && docker compose up -d --build     # → http://localhost:5000
```

Dashboard **ilk açılışta doludur**: teslim ettiğimiz nihai plan (10.381.178 TL) ve karşılaştırma
panelini besleyen iki örnek koşu (22–28 Haz, tahminle ve gerçek taleple) veritabanına önceden
gömülüdür — kimsenin önce optimizasyon çalıştırmasına gerek yoktur. Arayüzden planı inceleyebilir,
koşuları karşılaştırabilir ve "Senaryo Üret" ile canlı yeni plan ürettirebilirsiniz. Canlı koşunun
ihtiyaç duyduğu eğitim tablosu (66 bin satırlık geçmiş talep, repoya konamayacak kadar büyük ve
yarışmaya ait) ilk ihtiyaç anında veri dosyalarından **kendiliğinden** yüklenir; kullanıcının ek bir
komut çalıştırması gerekmez.

**Yol B — Python (algoritmayı doğrudan çalıştırmak için).** **Python 3.9+** gerekir. Depo kökündeki
kurulum betiği sanal ortamı kurar ve bağımlılıkları yükler:

```bash
kurulum.bat            # Windows (çift tıklanabilir)
./kurulum.sh           # macOS / Linux
```

### 15.2 Repo yapısı

```
core/                         # ÜRETİM: config, forecasting, optimization, evaluation, io
  forecasting/tahmin.py       #   → talep_tahmini_P50.csv + _P90.csv (+ Talep ID)
  optimization/planlayici.py  #   şampiyon v13 (pickup); planla(cpu, cpsat_saniye)
  evaluation/rota.py          #   kanonik route-aware değerlendirici (değiştirilmez)
  io/{submission,semalar,teslim_denetimi,db_export}.py
  calistir.py                 #   uçtan uca (opt + export)
experiments/asama3_gelismis/  # deney izi: eda/ + forecasting (20) + optimization (25)
                              #   + 05_BULGULAR.md (ölçülmüş bulgular defteri)
experiments/asama2_mvp/       # 2. aşama arşivi (ASAMA_2_RAPOR.md dahil)
services/{api,dashboard,otomasyon}/   # FastAPI + ASP.NET + canlı koşu
db/                           # PostgreSQL şema (migrations) + ER diyagramı + seed
submission/                   # Talep-tahmini.xlsx + Tasima-plani.xlsx (teslim)
```

**Çalıştırma:**

```bash
# Talep tahmini (P50/P90 CSV + Talep ID)
venv/Scripts/python.exe core/forecasting/tahmin.py

# Uçtan uca optimizasyon + submission (jüri 4-core)
venv/Scripts/python.exe core/calistir.py --cpu 4

# Teslim dosyalarını denetle
venv/Scripts/python.exe core/io/teslim_denetimi.py

# Dashboard + API + DB (tek komut)
cd deploy && docker compose up -d --build
```

**Dataset değiştirme (final sürpriz veri):** `LOJIX_DATA_DIR` env var veya `get_config(dir)`; dosyalar
desenle bulunur, anomaliler veriden tespit edilir, backtest penceresi otomatik seçilir → **kod değişmeden
yeni veriyle çalışır.**

---

## 16. Kaynaklar

Metrik seçimi, doğrulama yöntemi ve aralıklı talep algoritmalarına ilişkin kararlarımızı bir literatür
taramasına dayandırdık. Aşağıdakiler raporda doğrudan atıf yapılan kaynaklardır; taramanın tamamı
(değerlendirme notlarımız ve neyi neden almadığımız dâhil)
[`experiments/asama3_gelismis/LITERATUR.md`](experiments/asama3_gelismis/LITERATUR.md) dosyasındadır.

1. **Hyndman, R. J. & Koehler, A. B. (2006).** *Another look at measures of forecast accuracy.*
   International Journal of Forecasting, 22(4), 679–688. — Ölçeklenmiş hata (MASE) önerisi; sıfır içeren
   ve farklı ölçekli serilerin karşılaştırılması. [PDF](https://robjhyndman.com/papers/mase.pdf)
2. **Svetunkov, I. (2025).** *Don't use MAE-based error measures for intermittent demand.* openforecast.org
   — Aralıklı talepte MAE/MAPE tabanlı ölçülerin neden yanıltıcı olduğu.
   [Yazı](https://openforecast.org/2025/01/21/don-t-use-mae-based-error-measures-for-intermittent-demand/)
3. **Hyndman, R. J. & Athanasopoulos, G.** *Forecasting: Principles and Practice (3rd ed.),* §5.10
   Time series cross-validation. — Rolling-origin değerlendirme. [Bölüm](https://otexts.com/fpp3/tscv.html)
4. **Croston, J. D. (1972).** *Forecasting and stock control for intermittent demands.* Operational
   Research Quarterly, 23(3), 289–303. — Aralıklı talebin "aralık + boyut" ayrıştırması.
5. **Syntetos, A. A. & Boylan, J. E. (2005).** *The accuracy of intermittent demand estimates.*
   International Journal of Forecasting, 21(2), 303–314. — Croston'un yanlılık düzeltmesi (SBA).
   [Kayıt](https://www.sciencedirect.com/science/article/abs/pii/S0169207004000792)
6. **Teunter, R. H., Syntetos, A. A. & Babai, M. Z. (2011).** *Intermittent demand: Linking forecasting
   to inventory obsolescence.* European Journal of Operational Research, 214(3), 606–615. — TSB yöntemi.
7. **Machine learning for intermittent demand forecasting: a review (2025).** International Journal of
   Production Research. — Derin modellerin klasik yöntemlere (Croston) yakın kaldığı bulgusu.
   [Kayıt](https://www.tandfonline.com/doi/full/10.1080/00207543.2025.2578701)

Ek olarak kullanılan/incelenen araçlar: **Nixtla StatsForecast** (aralıklı talep referans uygulamaları,
kendi implementasyonumuzla karşılaştırma), **pyInterDemand** (Croston ailesi referansı) ve **Google
OR-Tools CP-SAT** (set-partitioning çözücüsü).
