# 5 Dakikalık Ara Sunum — Konuşma Notları

> **Durum:** Gün 5 / 25 · KİLOMETRE TAŞI 1 tamamlandı
> **Hazırlık tarihi:** 13 Ağustos 2026
> Bu notlar ezberlenmek için değil, **akışı hatırlatmak** için. Sayılar
> gerçek ölçümlerdir; hepsi `benchmarks/` altında JSON olarak duruyor.

---

## ⏱️ Zaman planı

| Bölüm | Süre | Ekranda ne var |
|---|---|---|
| 1. Problem ve zorluk | 0:00-0:50 | Slayt ya da sadece sen |
| 2. Mimari fikri | 0:50-2:00 | Mimari diyagramı |
| 3. Canlı demo | 2:00-3:40 | Panel → kamera → Grafana |
| 4. Ölçümler | 3:40-4:20 | Benchmark tablosu |
| 5. Sırada ne var | 4:20-5:00 | Yol haritası |

---

## 1️⃣ Problem ve neden zor (0:00 – 0:50)

**Görev:** En az 20 kameranın izlendiği, üç yapay zekâ yeteneği çalıştıran
web tabanlı bir uygulama — anomali tespiti, duygu analizi ve saldırgan
davranışın **erken** tespiti.

**Söylenecek kilit cümle:**

> "Bu projenin zor kısmı yapay zekâ değil. Modeller hazır, indirip
> çalıştırıyorsunuz. Zor kısmı, 20 eşzamanlı video akışını tek bir orta
> seviye GPU'da gerçek zamanlı işleyebilen mimariyi kurmak."

**Neden zor — somut sayı ver:**

```
20 kamera × 25 kare/saniye × 3 model = saniyede 1500 model çağrısı
```

Bu hiçbir tek makinede dönmez. Bu yüzden mesele "hangi modeli seçeyim"
değil, "işi nasıl azaltırım" oluyor.

---

## 2️⃣ Mimari fikri — kademeli işleme (0:50 – 2:00)

**Ana fikir:** Gerçek bir güvenlik kamerasında karelerin büyük bölümünde
hiçbir şey olmuyor. Pahalı modelleri **sadece gerektiğinde** çalıştır.

| Kademe | Ne yapar | Ne zaman | Maliyet |
|---|---|---|---|
| **0** | Hareket var mı? | Her karede | 1.6 ms, CPU |
| **1** | İnsan tespiti (YOLO26) | Hareket varsa | 6.8 ms, GPU |
| **2** | İskelet + yüz ifadesi | İnsan varsa | orta |
| **3** | Video aksiyon doğrulaması | Risk yüksekse | pahalı ama nadir |

**Ölçülmüş sonuç:** Durgun bir otopark kamerasında Kademe 0 karelerin
**%96.7'sini** eliyor. Yani pahalı model o kameraya neredeyse hiç bakmıyor.

**İkinci kilit karar — söylemeye değer:**

> "Sunucu videonun üstüne kutu çizmiyor. Video ayrı bir kanaldan
> WebRTC ile gidiyor, kutular ayrı bir kanaldan JSON olarak gidiyor,
> çizimi tarayıcı yapıyor."

Neden: 20 videoyu sunucuda yeniden kodlamak ekran kartının encoder
oturum limitine takılır ve GPU'yu tüketir. Bu ayrım sayesinde kutu
verisi saniyede sadece **17 kilobayt** yer kaplıyor.

**Üçüncü karar:** Ham kareler mesaj kuyruğundan geçmiyor. Bir 720p kare
2.6 MB; saniyede 80 kare 200 MB/sn eder. Kareler **paylaşımlı bellekte**
duruyor, kuyruktan sadece "şu slotta, şu boyutta bir kare var" referansı
geçiyor — 200 bayt.

---

## 3️⃣ Canlı demo (2:00 – 3:40)

### Önce sistemi ayağa kaldır (kayıttan önce yap!)

```powershell
pwsh backend/scripts/start_all.ps1
```

### Demo akışı

**a) Panel — http://127.0.0.1:8001**

Göster ve söyle:
- Beş altyapı servisi: Valkey, PostgreSQL+TimescaleDB, MediaMTX,
  Prometheus, Grafana — hepsi Docker'da, sağlık durumları canlı
- **24 kamera tanımlı** — 20'si video dosyalarından simüle edilmiş
  gerçek gözetim kaydı, 3'ü sentetik test deseni, 1'i laptop webcam'i

> "Gerçek IP kameram olmadığı için 20 kamerayı video dosyalarından
> simüle ettim. Sistem açısından bunlar gerçek IP kameradan ayırt
> edilemiyor — RTSP protokolüyle bağlanıyorlar."

**b) Bir kameraya "İzle" de** — `cam-09` (kalabalık cadde) iyi seçim

Göster:
- Video akıyor
- Üstünde **yeşil kutular** ve güven yüzdeleri
- Sol üstte kaç kişi tespit edildiği

> "Bu kutular sunucuda çizilmedi. Model sonucu JSON olarak geldi,
> tarayıcı canvas üzerine çizdi."

**c) Kamera 21 — canlı webcam** (etkileyici kısım)

Panelden "Kamerayı aç" de, kendini göster, kutunun seni takip ettiğini
göster, sonra kapat.

> "Kamera kendiliğinden açılmıyor. Mahremiyet gereği yalnızca açık bir
> istekle başlıyor ve her açma/kapama loglanıyor."

**d) Grafana — http://127.0.0.1:3000**

Metrikleri göster: kamera başına FPS, kuyruk derinliği, GPU kullanımı.

> "Ölçmediğin şeyi iyileştiremezsin. Her bileşen Prometheus'a metrik
> yazıyor."

---

## 4️⃣ Ölçümler (3:40 – 4:20)

Bu tabloyu ekrana koy ya da oku:

| Ölçüm | Sonuç |
|---|---|
| Eşzamanlı kamera | **20** |
| Tespit hızı (YOLO26-s, FP16) | **6.8 ms/kare** (p50) |
| Uçtan uca gecikme | **770 ms** (hedef ≤1500 ms) ✅ |
| Hareket filtresi eleme oranı | %0 – %96.7 (sahneye göre) |
| Tarayıcıya akış | 57 FPS · 17.7 KB/sn |
| Video çözme yükü | 14 çekirdeğin **%14'ü** |

**Anlatmaya değer bir hata — dürüstlük puan kazandırır:**

> "İlk ölçümümde video çözmenin darboğaz olduğunu, GPU'nun donanımsal
> çözücüsüne geçmem gerektiğini düşünmüştüm. Sonra fark ettim ki ölçümü
> canlı akıştan yapmışım — akış zaten saniyede 25 kare veriyor, ben bu
> hız sınırını kapasite tavanı sanmışım. Yerel dosyadan doğru ölçünce
> CPU'nun saniyede 1000 kare çözdüğünü gördüm. Üstelik GPU çözücüsünü
> denediğimde **daha yavaş** çıktı, çünkü her kareyi GPU'dan geri
> indirmek gerekiyor. Bu sayede bir günlük gereksiz işten kurtuldum."

Bu hikâye iki şey gösterir: ölçmenin değeri ve varsayımların tehlikesi.

---

## 5️⃣ Sırada ne var (4:20 – 5:00)

**Yapılanlar (Gün 5/25):**
- Altyapı, 20 kameralık çiftlik, kademeli işleme boru hattı
- GPU tespiti, WebSocket kanalı, tarayıcıda canlı kutular
- **Kilometre Taşı 1 tamamlandı**

**Sırada:**

| Hafta | İş |
|---|---|
| 2 | İskelet (poz) çıkarımı + kişi takibi |
| 3 | Anomali tespiti — her kamera **kendi normalini** öğrenecek |
| 4 | Saldırganlık erken uyarısı + alarm sistemi |
| 5 | Güvenlik sertleştirme, ölçüm, rapor |

**Saldırganlık modülünü anlat — projenin en özgün kısmı:**

> "Yumruk atıldıktan sonra tespit etmek kolay ama işe yaramaz. Ben
> **tırmanma evresini** yakalamaya çalışıyorum: iki kişi arasındaki
> mesafenin daralması, bileklerin ani hızlanması, gövdenin öne yatması,
> etrafta halka oluşması. Bunları iskelet verisinden bir 'tırmanma
> skoruna' çeviriyorum."

> "Literatürdeki çalışmalar 'şiddet var mı yok mu' sorusunu ölçüyor.
> Ben ek olarak **'kaç saniye önce uyardık'** sorusunu ölçeceğim. Bunun
> için test videolarını hazırlarken kavganın hangi saniyede başladığını
> kaydettim — hazır etiketli veri var."

**Anomali için:**

> "Anomalinin tanımı 'daha önce görmediğim şey' olduğu için etiketli
> veri toplanamaz. Bu yüzden her kamera kendi normalini öğreniyor:
> insanlar nerede yürüyor, hangi hızda, ne kadar duruyor. Koridorda
> koşmak anomalidir, spor salonunda değildir."

**Duygu analizi için — dürüst ol:**

> "Duygu analizinde bilimsel bir tartışma var: yüz ifadesiyle içsel
> duygu arasında güvenilir bir eşleme olmadığı savunuluyor. Üstelik
> gözetim kamerasında yüzler 10-20 piksel, çoğu zaman kullanılamaz.
> Bu yüzden modül 'yüz yeterince net değil' diyebiliyor ve tek başına
> alarm üretmiyor — sadece diğer sinyallere düşük ağırlıkla katkı
> veriyor."

---

## 🎯 Kapanış cümlesi

> "Şu an sistemin iskeleti uçtan uca çalışıyor: kameradan görüntü
> geliyor, GPU'da işleniyor, tarayıcıda görünüyor — ölçülebilir bir
> gecikmeyle. Geri kalan haftalarda bu iskeletin üstüne yapay zekâ
> modüllerini ekleyeceğim."

---

## 📝 Kayıt öncesi kontrol listesi

- [ ] `pwsh backend/scripts/start_all.ps1` çalıştır, 30 saniye bekle
- [ ] Paneli aç, kutuların geldiğini doğrula
- [ ] 2-3 kamerayı önceden aç (video başlaması birkaç saniye sürüyor)
- [ ] Grafana'yı ayrı sekmede aç
- [ ] Bildirimleri kapat, gereksiz sekmeleri kapat
- [ ] Ekran çözünürlüğünü 1080p yap (yazılar okunabilsin)

## ⚠️ Söylememen gerekenler

- "Yapay zekâyı ben yazdım" — modeller hazır, sen **sistemi** kurdun.
  Asıl değerli olan da bu, olduğu gibi anlat.
- Tutturamadığın hedefleri gizleme. "Şu an kamera başına 3.6 FPS'te,
  hedefim 4" demek, hiç bahsetmemekten iyidir.
