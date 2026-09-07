# ADR-0008 · Füzyon katmanı: gözlem doğrudan konuşur, ipucu ancak toplulukta

**Durum:** kabul edildi — ⚠ **GEREKÇESİ DEĞİŞTİ** (05.09.2026)
**Tarih:** 01.09.2026 · **Güncellendi:** 05.09.2026

> ⭐ **ÖZET:** Karar ayakta, ama dayanağı K6'dan K7'ye taşındı.
> Füzyonun gerekçesi **ayırt etme gücü (AUC) değil, gürültü
> bastırma.** Ölçüm aşağıda; tam anlatım `problems.md` · P-41.

## Bağlam

Beş modül birbirinden bağımsız çalışıyor ve **her biri kendi eşiğine
göre alarm üretiyordu.** İki sorun doğurdu:

**1 · Zayıf sinyaller tek başına alarm veriyordu.** Katman A'nın
söylediği şey *"bu kişi bu bölge için 3σ hızlı"* — istatistiksel bir
sapma, fiziksel bir olay değil. Canlı ölçümde eşik 0.5 iken 63 alarmın
**49'u (%78)** buradan geliyordu ve kontrol kamerasında **saatte 90
alarm** çıkıyordu (K7 hedefi ≤3).

Geçici çözüm eşiği 0.85'e çekmekti ve kodda açıkça *"geçici bir
kısıtlama, kalıcı çözüm füzyon"* diye yazılmıştı.

**2 · Birlikte anlam kazanan sinyaller birleşmiyordu.** *"3σ hızlı"*
tek başına gürültü. *"3σ hızlı **ve** yanındakine hızla yaklaşıyor
**ve** bileği sarsılıyor"* bir olay. Ayrı ayrı hiçbiri eşiği aşmıyordu;
birlikte aşmalıydı.

## Değerlendirilen seçenekler

**A · Her modül kendi eşiğiyle alarm versin (mevcut durum)**
Basit ve modüller bağımsız kalıyor. Ama yukarıdaki iki sorun bunun
doğrudan sonucu. Eşikleri yükselterek çözmek, zayıf sinyalleri
**tamamen** susturmak demek — birlikte anlam kazanma imkânı da gidiyor.

**B · Tek bir sınıflandırıcı (hepsini birden öğrensin)**
En yüksek doğruluk potansiyeli. Ama: etiketli veri yok (anomali tanımı
gereği "daha önce görülmemiş"), açıklanabilirlik kayboluyor ve
operatöre *"model öyle dedi"* demek zorunda kalıyoruz — K7'nin asıl
riski tam da operatörün sisteme güvenini kaybetmesi.

**C · Ağırlıklı toplam + histerezis, AMA fiziksel gözlemler muaf**

## Karar

**C.** Sinyaller ikiye ayrılıyor:

```
DOĞRUDAN ALARM (fiziksel gözlem, kanıt zinciri var)
  düşme · koşma · kalabalık · saldırganlık(alarm seviyesi)

FÜZYONA GİREN (istatistiksel ipucu, tek başına yetersiz)
  Katman A olağandışılık · oyalanma · saldırganlık(uyarı) · ifade
```

> ⭐ **Kural: gözlem doğrudan konuşur, ipucu ancak toplulukta konuşur.**

⚠ **Füzyon her sinyali YUTMAZ ve bu ayrım hayati.** Bir düşme, başka
hiçbir sinyal olmasa bile alarmdır. Onu ağırlıklı toplamın içinde
eritmek, tıbbi acil olabilecek bir olayı *"diğer göstergeler sakin"*
diye bastırmak olurdu.

Ağırlıklar PLAN §6.6'dan aynen alındı (toplam 1.00):

```
saldırganlık 0.40   ← en spesifik sinyal
anomali      0.25
kural        0.20
ifade        0.10   ← bilimsel belirsizlik nedeniyle düşük (Barrett vd. 2019)
kalabalık    0.05
```

**Ek kural — en az iki sinyal.** Füzyon riski, yalnızca bir sinyal
katkı verdiyse (≥0.15) **yayınlanmıyor.** Gerekçe: tek sinyalin
yükselttiği bir risk skoru, o sinyalin kendi alarmının kopyasıdır ve
operatöre aynı olayı iki kez göstermek K7'nin asıl riskini besler.

## Sonuçlar

**Kazanılan:** Katman A artık alarm değil **skor** üretiyor. Yanlış
alarm 26.4 → kontrol kamerasında **0.00**/kamera-saat.

**Kaybedilen:** Bir modül kapalıysa (ör. poz çalışmıyorsa) risk skoru
**sistematik olarak düşük** çıkıyor. Eksik sinyali "bilinmiyor" sayıp
kalanları yeniden ölçeklendirmek, az sinyalli anları yapay olarak
yükseltirdi; bilinçli takas.

## Ölçüm

CUHK Avenue, 9 etiketli test klibi, 1439 kare
(`benchmarks/k6_20260901-132604.json`):

| Skor | AUC |
|---|---|
| füzyon | **0.867** ✅ (K6 hedefi ≥0.75) |
| katman_a (ham) | 0.789 |
| saldırganlık | 0.465 |
| kural | 0.4996 |

⚠ **Dürüstlük notu — `kural` bileşeni Avenue'da hiç ateşlemiyor.**
Avenue'nun anomalileri çanta fırlatma, bisiklet, ters yön; bizim boru
hattımız yalnızca **insan** tespit ediyor. K6'yı taşıyan neredeyse
tümüyle Katman A. Kapsamın dürüst sınırı budur.

---

## ⚠⚠ AÇIK SORU (03.09.2026) — bu ADR'nin merkezî iddiası HENÜZ KANITLANMADI

Yukarıdaki tablo şu çıkarıma dayanak yapılmıştı:

> *"Füzyon (0.867), en iyi tek bileşeninden (0.789) daha iyi — demek ki
> birleştirme kazandırıyor ve katman karmaşıklığı karşılığını verdi."*

**Bu çıkarım desteklenmiyor.** Karşılaştırılan iki sayı aynı işlemden
geçmemiş:

```
katman_a = HAM, kare başına skor
füzyon   = EMA(α=0.4) ile ZAMANSAL YUMUŞATILMIŞ ağırlıklı toplam
```

Füzyona **iki şey birden** eklenmişti — sinyal birleştirme *ve*
zamansal yumuşatma — ve ölçüm hangisinin kazandırdığını ayırmıyordu.
Deneysel yöntemin en temel kuralı: iki grubu karşılaştırırken aralarında
**yalnızca bir fark** olmalı.

Eldeki sayılar yumuşatmayı işaret ediyor:

1. Diğer bileşenler **şans seviyesinde** (0.465 ve 0.4996). Şans
   seviyesindeki iki sinyali eklemek AUC'yi 0.789'dan 0.867'ye
   çıkaramaz.
2. Katman A karelerinin **%42'si tam 0.0**. AUC hesabı eşitlikleri 0.5
   sayıyor ve bu kadar eşitlik AUC'ye **tavan** koyuyor. EMA geçmişten
   sızdırıp sıfırları dolduruyor → eşitlik azalıyor → AUC **mekanik
   olarak** yükseliyor.

**Yapılan:** `evaluate_k6.py`'a `katman_a_ema` **kontrol serisi**
eklendi — Katman A'nın tek başına, füzyonla aynı EMA'dan geçmiş hâli.

```
füzyon > katman_a_ema  → birleştirme gerçekten kazandırıyor
füzyon ≈ katman_a_ema  → kazandıran YUMUŞATMA; bu veri setinde
                          füzyon katmanı karşılığını vermiyor
```

## ⭐ ÖLÇÜM SONUCU (05.09.2026) — ikinci şık çıktı

`benchmarks/k6_20260905-112405.json`:

```
katman_a (ham)          : 0.789
katman_a + EMA (kontrol): 0.860   ⬅ tek sinyal, füzyonla aynı yumuşatma
füzyon (5 sinyal + EMA) : 0.867
fark (füzyon − kontrol) : +0.007   ⬅ gürültü içinde
```

**Kazancın %91'i yumuşatmadan, %9'u birleştirmeden.** "Birleştirme
kazandırıyor" iddiası bu veri setinde **desteklenmiyor.**

### Karar neden yine de AYAKTA

**1 · Bu veri setinde birleştirilecek bir şey yoktu.** Beş sinyalden
dördü ölü: `kural` AUC tam 0.500 (Avenue'nun anomalileri çanta
fırlatma/bisiklet, biz yalnızca insan tespit ediyoruz),
`saldırganlık` 0.465, `ifade` ve `kalabalık` sıfır. **Tek sinyali
birleştirmek tanım gereği bir şey kazandıramaz.** Ölçüm *"füzyon bu
veri setinde kazandırmıyor"* diyor, *"füzyon kazandırmaz"* demiyor.

**2 · Füzyonun asıl kazancı zaten ölçülmüştü — K7'de.** "En az iki
sinyal" kuralı yanlış alarmı **26.4 → 0.00/kamera-saat** düşürdü.
Yani füzyonun işi ayırt etme gücünü artırmak değil, **zayıf
sinyallerin tek başına alarm üretmesini engellemek** — ve bu, bu
belgenin "Bağlam" bölümünde zaten böyle yazılıydı. Yanlış olan karar
değil, kararı savunmak için seçilen ÖLÇÜTTÜ.

### ⚠ Ders

Bu ADR bir kararı doğru gerekçeyle aldı, sonra **yanlış bir sayıyla
savundu.** K6 (ayırt etme gücü) füzyonun çözdüğü problemi ölçmüyor;
K7 (yanlış alarm oranı) ölçüyor. Bir kararı destekleyen sayı,
kararın çözdüğü problemi ölçmelidir — yoksa doğru karar yanlış
kanıtla savunulmuş olur ve kanıt çürüdüğünde karar da haksız yere
şüpheli hâle gelir.

Tam anlatım: `docs/report/problems.md` · **P-41**
