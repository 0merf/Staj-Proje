# ADR-0010 · Olay kalıcılığı: TimescaleDB, düz PostgreSQL değil

**Durum:** kabul edildi
**Tarih:** 30.08.2026

## Bağlam

⚠ **30.08.2026'ya kadar alarmlar HİÇBİR YERE kaydedilmiyordu.**

Analytics worker bir olay üretiyor, Valkey akışına yazıyor, panel
açıksa gösteriyor — **panel kapalıysa olay hiç olmamış gibi
kayboluyordu.**

Bir gözetim sisteminde bu kabul edilemez, çünkü operatörün asıl
sorusu *"şu an ne oluyor"* değil:

> **"Dün gece 03:00'te ne oldu?"**

Canlı akış **dikkat**, geçmiş **kanıt** üretir. Kanıtı olmayan bir
gözetim sistemi, kendisi de denetlenemez hâle gelir.

Bu tablonun üç özelliği var ve üçü de zaman serisi:

1. **Yalnızca ekleme yapılıyor.** Olaylar sonradan değişmez.
2. **Sorgular hep zaman aralıklı.** *"Son 24 saatte cam-09'da neler
   oldu"* — hiçbir zaman "tüm tarihte" sorulmuyor.
3. **Eski veri değerini yitiriyor ama ÖZETİ yitirmiyor.** Üç ay önceki
   tek bir alarmın ayrıntısı gereksiz; *"üç ay önce günde kaç alarm
   vardı"* değerli.

## Değerlendirilen seçenekler

**A · Düz PostgreSQL, tek tablo**
Basit. Ama üç özelliğin hiçbiri için makine yok: eski satırları elle
silmek gerekir, saatlik özet her sorguda baştan hesaplanır, tablo
büyüdükçe zaman aralıklı sorgular yavaşlar.

**B · Valkey akışında bırakmak (`maxlen` ile)**
Zaten oradalar. Ama Valkey bellekte çalışıyor: 30 günlük geçmiş RAM'e
sığmaz ve yeniden başlatmada kaybolur. Bir *kuyruk*, bir *arşiv*
değil.

**C · Ayrı bir zaman serisi veritabanı (InfluxDB / Prometheus)**
Prometheus zaten kurulu. Ama Prometheus **metrik** deposu: olayın
`kanit` JSONB'sini, `track_id`'sini, `klip_anahtar`'ını taşıyamaz ve
tasarımı gereği yüksek kardinaliteli etiketlerden kaçınır. Olay kaydı
metrik değil, **kayıt**.

**D · PostgreSQL + TimescaleDB eklentisi**

## Karar

**D.** TimescaleDB üç özelliğin üçü için de hazır makine veriyor:

```
hypertable            → zaman dilimlerine (chunk) otomatik bölme;
                        eski dilimler sorguda hiç AÇILMIYOR
sürekli toplulaştırma → saatlik özet arka planda güncelleniyor
saklama politikası    → eski ham satırlar otomatik siliniyor,
                        özet KALIYOR
```

⚠ **Sürekli toplulaştırma K7'nin ta kendisi.** K7 kriteri
*"kamera-saat başına yanlış alarm ≤3"* diyor ve bugüne kadar her
ölçümde elle bir betik yazılıp Valkey akışı dinlenmişti.
`olay_saatlik` görünümü tam olarak bu sayıyı **sürekli** üretiyor:
kriter artık bir ölçüm koşusunun değil, **sistemin normal
çıktısının** parçası (`GET /api/v1/events/ozet`).

### ⚠ Neden ayrı bir `kanit` JSONB sütunu

Her anomali türünün kanıtı farklı: düşmede en-boy oranı ve eğim,
saldırganlıkta bileşen skorları, Katman A'da sigma sapması. Bunları
ayrı sütunlara açmak, **her yeni kural için şema değişikliği** demekti.
JSONB, alarmın NEDEN verildiğini kaybetmeden şemayı sabit tutuyor — ve
operatöre gösterilen açıklama da buradan geliyor.

> ⭐ Bu sütun boşsa alarm bir **iddia**, doluysa bir **gözlem**.

### ⚠ Neden Alembic değil, düz SQL

Alembic bağımlılığı kurulu ama kullanılmıyor. Tek tablolu bir şema için
otomatik revizyon üretimi kazandırdığından fazla makine getiriyor.
Daha önemlisi: `create_hypertable` ve sürekli toplulaştırma Alembic'in
bilmediği TimescaleDB çağrıları; hepsi elle SQL yazılacaktı zaten.

Şema her açılışta **idempotent** olarak kuruluyor — elle migration
gerektiren bir sistem, bir bileşen yeniden başladığında sessizce
çalışmaz duruma gelir.

## Sonuçlar

**Kazanılan:** Alarm geçmişi kalıcı. Panel açıldığında son 24 saat
yükleniyor. K7 sürekli ölçülüyor. 30 gün sonra ham satırlar otomatik
siliniyor (KVKK: *"gerektiğinden uzun saklamamak"* bir yükümlülük,
tercih değil).

**Kaybedilen:** Bir eklenti bağımlılığı. ⚠ Azaltma: eklenti yoksa
tablo **yine kuruluyor**, yalnızca zaman serisi özellikleri atlanıyor
ve WARNING loglanıyor. Sistem düz PostgreSQL'de de ayakta kalıyor —
eklenti bir **optimizasyon**, bir ön koşul değil.

**Ayrı süreç kararı:** Alarm worker'ı analytics'in İÇİNDE değil.
Veritabanına yazmak ağ turu + disk fsync demek; bunu analiz döngüsüne
koymak iki şeyi birden bozardı: gecikme (K3) doğrudan artar, **ve
veritabanı yavaşlarsa ANALİZ yavaşlar.** Yardımcı bir bileşenin
arızası ana boru hattını durduramaz (PLAN §4.2).

## Ölçüm

01.09.2026 canlı koşusu, 20 kamera: **204 olay** TimescaleDB'ye
yazıldı, `GET /api/v1/events/ozet` saatlik kırılımı döndürüyor.

Üretilen ve **yazılan** alarm sayısı ayrı metrikler
(`sentinel_anomalies_total` vs `sentinel_olaylar_yazildi_total`) ve
Grafana'da yan yana çiziliyor. ⚠ İkisi ayrışırsa veritabanı yolu
tıkanmış demektir — **ve bu, sistem dışarıdan sağlıklı görünürken
sessizce olur:** panel canlı alarmları göstermeye devam eder, yalnızca
geçmiş birikmez.

### ⚠ Kurulumda çıkan üç tuzak (P-34)

1. **Şema tek metin + `split(";")` ile bölünüyordu** ve
   `syntax error at end of input` veriyordu. Sebep: **SQL yorumunun
   içinde noktalı virgül vardı.** Ders: SQL'i ayırıcıya bakarak
   bölmek, dizeleri ve yorumları tanımayan bir ayrıştırıcı yazmaktır.

2. **`.format()` yerine `.replace()`** gerekti: SQL metni
   `'{}'::jsonb` içeriyor ve `format` onu yer tutucu sanıp
   `IndexError` fırlatıyordu.

3. ⭐ **`materialized_only = false` — en öğretici olanı.**
   `GET /events/ozet?saat=1` **boş dönüyordu.** Sebep sessizdi:
   yenileme politikası `end_offset => 1 hour` kullanıyor, yani en son
   saat kasten özetlenmiyor (yarım saatlik veriyi tam saat gibi
   göstermemek için). Materyalize edilmemiş bölge sorguya hiç
   girmediğinden operatör *"son 1 saatte hiçbir şey olmadı"* cevabı
   alıyordu — **oysa alarmlar tabloya yazılmıştı.**

   > ⭐ Bir gözetim sisteminde en tehlikeli cevap budur: **"hiçbir şey
   > yok" ile "bakmadım" aynı görünüyorsa, sistem sessizce yanıltıyor
   > demektir.**
