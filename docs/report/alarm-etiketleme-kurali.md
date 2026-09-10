# Alarm Doğrulama — ETİKETLEME ÖLÇÜTÜ

> ⚠⚠ **BU DOSYA KLİPLER İZLENMEDEN ÖNCE YAZILDI.** (10.09.2026)
>
> Sebep P-49: *"ölçütün TANIMI olayın tanımını yanlış çizebiliyor."*
> Etiketleme kuralını gördükten sonra yazmak, gördüğünü haklı
> çıkaracak tanımı seçmek olur. Kural önce yazılır, sonra bakılır.

## Yöntem

`scripts/alarm_klipleri.py` her alarmın **±3 saniyesini** kaynak
videodan kesiyor (`kanit.video_pts` sayesinde). Klipler görsel olarak
değerlendirilip `dogru` sütunu dolduruluyor:

- **1** = alarm haklı (aşağıdaki ölçüt sağlanıyor)
- **0** = alarm yanlış (ölçüt sağlanmıyor)
- **boş** = karar veremedim → **analiz dışı** bırakılır

⚠ "Emin değilim"i 0 saymak, sistemi haksız yere cezalandırmak olurdu;
1 saymak ise kayırmak. Üçüncü seçenek şart.

## Tür bazlı ölçüt — sistemin KENDİ iddiasına göre

Her ölçüt, kuralın kodda ne iddia ettiğinden türetildi
(`analytics/anomaly/rules.py`). "Bana anormal göründü" bir ölçüt değil.

| tür | sistemin iddiası (koddaki eşik) | DOĞRU sayılma ölçütü |
|---|---|---|
| `crowd` | kişi sayısı, kameranın öğrenilmiş tabanının **2.5 katını** aşıyor **ve** en az **4** kişi | Karede **≥4 kişi** açıkça görünüyor ve sahne o kamera için olağandışı yoğun |
| `fall` | en-boy oranı >0.9, gövde eğimi 55°–150°, eğim değişim hızı >40°/sn | Bir kişi **yere düşüyor ya da yerde yatıyor** |
| `running` | hız >1.5 gövde/sn, iz tamlığı ≥0.5 | Bir kişi **belirgin biçimde koşuyor** (yürüyüş değil) |
| `loitering` | 45 sn boyunca 0.6 yarıçapında kalıyor | ⚠ **6 saniyelik klipten ÖLÇÜLEMEZ** → kural gereği **boş** |
| `aggression` | öğrenilmiş model + kural payı | **Fiziksel çatışma/boğuşma** görünüyor |
| `risk` | füzyon (5 sinyal) eşiği aştı | Yukarıdakilerden **en az biri** görünüyor |

## ⚠ Bu yöntemin ölçemedikleri — önceden

1. **Duyarlılık (recall) ÖLÇÜLMÜYOR.** Yalnızca sistemin ürettiği
   alarmlara bakılıyor. "Kaçırdığı olay var mı" sorusu için videoların
   TAMAMI etiketlenmeliydi. Bu ölçüm bir **kesinlik (precision)**
   ölçümüdür ve raporda böyle adlandırılacak.

2. **Tek değerlendirici.** İkinci bir gözle uyum (inter-rater
   agreement) ölçülmedi.

3. **`loitering` ölçülemiyor** — 6 saniyelik pencere 45 saniyelik bir
   kuralı doğrulayamaz. Bu türün kesinliği bu yöntemle **bilinemez**
   ve "0 örnek" olarak raporlanacak, "%100" ya da "%0" olarak değil.

4. **Klip anahtar kareye hizalanıyor**, kesim 1-2 sn kayabilir. Olayın
   tam anı klibin ortasında değil kenarında olabilir.
