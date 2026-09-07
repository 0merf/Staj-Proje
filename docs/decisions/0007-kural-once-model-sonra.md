# ADR-0007 · Önce kural tabanlı skor, sonra model

**Durum:** kabul edildi
**Tarih:** 26.08.2026

## Bağlam

Saldırgan davranışın erken tespiti projenin özgün katkısı. Literatürde
RWF-2000 üzerinde %90+ doğruluk veren onlarca eğitilmiş model var.
Neden doğrudan model eğitmiyoruz?

## Değerlendirilen seçenekler

**A · Doğrudan eğitilmiş model** (ST-GCN / LightGBM / GRU)
Literatür doğruluğuna en hızlı yol. Ama: eğitim verisi işlenene kadar
sistemde saldırganlık modülü **hiç yok**; hata ayıklama zor (model
neden bu skoru verdi?); ve modelin iyi olup olmadığını söyleyecek bir
kıyas noktası yok.

**B · Kural tabanlı, açıklanabilir skor**
İlk günden çalışır, her bileşeni okunabilir, ama doğruluk tavanı
düşük.

**C · Önce B, sonra A — ve B taban çizgisi olarak KALIR**

## Karar

**C.** Üç gerekçe:

1. **İlk günden çalışır.** Eğitim verisi işlenmeyi beklerken sistem
   ayakta.
2. **Açıklanabilir.** *"Skor 0.72 çünkü bilek hızı 3.1, mesafe 0.4
   gövde, karşılıklı bakıyorlar."* Operatör sebebi görmezse alarmı
   kapatır — ve K7'nin asıl riski yanlış alarm sayısı değil,
   operatörün sistemi umursamamaya başlamasıdır.
3. **Model için TABAN ÇİZGİSİ.** Eğitilecek modelin bu skoru geçip
   geçmediği ölçülebilir. Geçmiyorsa modelin kendisi sorgulanır —
   *"model kullandık"* demek başarı değildir.

## Sonuçlar

**Kazanılan:** Taban çizgisi sayısı elde edildi.

**Kaybedilen — ve dürüstçe raporlanacak:** K5 hedefi (F1 ≥ 0.85)
kural tabanlı skorla **tutmuyor.** Bu bir başarısızlık değil, planın
kendisi: modülün rolü zaten taban çizgisi olmaktı.

## Ölçüm

RWF-2000 `val` bölümü, 60 kavga + 60 normal klip, canlı boru hattının
aynısından geçirildi (`benchmarks/rwf_eval_20260826-181902.json`):

| Ayar | kavga p50 | normal p50 | AUC | F1 |
|---|---|---|---|---|
| ESKI | 0.368 | 0.219 | 0.665 | 0.704 |
| IKISI | 0.089 | 0.063 | 0.629 | **0.712** |

⚠ `val` seçildi çünkü `train` bölümü sahte kamera cam-17'yi besliyor.
Eşiği aynı kliplerle hem ayarlayıp hem değerlendirmek, ezberi başarı
sanmaktır.

**En iyi F1 = 0.712. Eğitilecek modelin geçmesi gereken sayı bu.**

AUC ≈ 0.63 skorun kendi sınırını gösteriyor: eşik nereye konursa
konsun, kavganın %20'sini yakalamak normalin %20'sini yakmak demek —
yani şans seviyesi.

---

## ⚠ DÜZELTME (03.09.2026) — bu ADR kendi ilkesini ihlal ediyordu

Yukarıdaki paragraf şunu yazıyor:

> *"Eşiği aynı kliplerle hem ayarlayıp hem değerlendirmek, ezberi
> başarı sanmaktır."*

İlke doğru. Ama **ölçüm tam olarak bunu yapıyor.**

`evaluate_rwf.py`, F1'i hesapladığı **aynı 120 klip üzerinde**
`en_iyi_esik`'i arıyor ve o eşikteki F1'i raporluyor. `train`/`val`
ayrımı yapılmış olması bunu çözmüyor: ayrım *modelin eğitimi* için
doğru yerdeydi, ama burada eğitilen bir model yok — **eşiğin kendisi
öğrenilen parametre** ve o parametre test kümesinde seçiliyor.

**Etkisi:** Bildirilen **F1 = 0.712 optimistik.** Gerçek, görülmemiş
veri üzerindeki F1 bundan düşük. Ne kadar düşük olduğu ölçülmedi.

**Neden şimdi düzeltilmiyor:** İki seçenek vardı ve ikisi de bu
noktada zarar/fayda sınavını geçmiyor:

- `val`'ı ikiye bölmek → her yarıda 30+30 klip kalır; F1 tahmininin
  gürültüsü, düzeltmeye çalıştığımız yanlılıktan büyük olur
- `train`'den eşik seçmek → `train` sahte kamera cam-17'yi besliyor,
  yani sistemin canlı davranışıyla iç içe geçmiş bir veri

**Bunun yerine yapılan:** Yanlılık **açıkça raporlanıyor.** K5 zaten
tutmuyor (0.712 < 0.85); yanlılığı bildirmek sayıyı daha da aleyhimize
çeviriyor ve doğrusu bu.

⚠ **Kaydedilmeye değer ders:** Bir belgede ilkeyi doğru yazmak, onu
uyguladığını göstermez. Bu ADR ilkeyi savunuyor ve ihlal ediyordu —
üstelik ihlal, ilkenin yazıldığı paragrafın **iki satır altındaydı.**
Aynı sınıf: ADR-0006'nın dersi (*"bir kararın gerekçesi belgeye
girdikten sonra veri gibi davranmaya başlıyor"*).
