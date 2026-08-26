# UR Fall Detection Dataset — Kaynak, Lisans ve Atıf

> **PLAN.md §7.2 kuralı:** Her veri seti için indirme adresi, lisans ve
> alıntı bilgisi kaydedilir. Veri **git'e girmez**, bu dosya girer.

## Ne için kullanılıyor

**Düşme kuralının gerçek görüntüde doğrulanması** (PLAN.md §6.4 Katman B).

### Neden gerekliydi

Düşme, kural tabanlı anomali katmanının en önemli kuralı — hem güvenlik
açısından en kritik olay, hem de kanıt zinciri mimarisinin vitrini
(en-boy oranı + gövde eğimi + eğim değişim hızı üçü birden aranıyor).

Buna rağmen **26.08.2026'ya kadar gerçek bir düşme görüntüsünde hiç
denenmemişti.** Doğrulaması yalnızca elle kurulmuş sentetik iskeletlerdi
(`tests/unit/test_rules.py`). Sentetik test kuralın kendi mantığını
sınar; kuralın gerçek dünyada ürettiği DEĞERLERİN eşiklere uyup
uymadığını sınamaz. Elimizdeki diğer setlerin hiçbirinde düşme yok:

| Set | İçerdiği anomali | Düşme? |
|---|---|---|
| CUHK Avenue | koşma, nesne fırlatma, oyalanma, ters yön | ❌ |
| RWF-2000 | kavga | ❌ (yerde mücadele var, düşme etiketi yok) |
| VIRAT / PETS / Oxford | etiketsiz normal | ❌ |

Bu boşluk `build_camera_farm.py` içinde 18.08'den beri açıkça
yazılıydı: *"gerçek doğrulama için UR Fall / Le2i gerekiyor."*

### Sonuç (26.08.2026, 10 dakikalık canlı ölçüm)

`benchmarks/fall_20260826.json`

| | |
|---|---|
| cam-16 düşme alarmı | **5** |
| Azami mümkün (60 sn kamera soğuması) | 10 |
| Yakalama | **%50 — sınırlayan soğuma, kural değil** |

Beş alarmın beşinde de kanıt zinciri eksiksiz:
en-boy 1.10–1.79 · gövde eğimi 78–101° · devrilme hızı 42–165°/sn.
(Ayakta duran kişide sırasıyla ~0.4 · ~0-15° · ~0-10°/sn.)

## Kaynak

| | |
|---|---|
| **Ad** | UR Fall Detection Dataset (UR Fall) |
| **Kurum** | Uniwersytet Rzeszowski (Rzeszów Üniversitesi), Polonya |
| **Adres** | http://fenix.ur.edu.pl/~mkepski/ds/uf.html |
| **Kullanılan dizi** | `fall-01-cam0-rgb` — 1 numaralı düşme, kamera 0 (yatay/duvar açısı) |
| **İndirme tarihi** | 26.08.2026 |
| **Boyut** | 160 PNG · 640×480 · ~30 MB |

## İçerik

```
fall-01-cam0-rgb-001.png … fall-01-cam0-rgb-160.png
160 kare @ 30 FPS = 5.33 saniye · RGB · 640×480 · ofis ortamı
```

Özgün set 30 düşme + 40 günlük aktivite dizisi, her biri iki kameradan
(cam0 duvar açısı, cam1 tavan) ve ayrıca derinlik + ivmeölçer verisiyle
birlikte. **Bu projede yalnızca cam0 RGB kullanılıyor** — derinlik ve
ivmeölçer sensörleri sistem mimarimizde yok (IP kamera varsayımı).

## ⚠ Kapsam sınırı — raporda açıkça yazılacak

**Tek dizi, 5.3 saniye.** Bu istatistiksel bir değerlendirme DEĞİL.

Ne kanıtlar: düşme kuralı gerçek bir düşmede, gerçek YOLO26-pose
iskeletiyle, gerçek boru hattı gecikmesi altında ateşliyor ve kanıt
değerleri eşiklerin doğru tarafında.

Ne kanıtlamaz: duyarlılık (kaç düşmeden kaçını yakalar) ve özgüllük
(kaç düşmemede yanlış alarm verir). Bunun için 30 düşme dizisinin
tamamı + 40 günlük aktivite dizisi çevrimdışı işlenmeli. Zaman
bütçesine göre değerlendirilecek (`YOL-HARITASI.md`).

⚠ **Yanlış pozitif zaten görüldü ve düzeltildi:** 175° gövde eğimiyle
(ters dönmüş iskelet — poz modelinin baş/ayak karıştırması) kural
skor 1.00 üretmişti. Üst sınır eklendi (`DUSME_EGIM_AZAMI = 150.0`,
commit `1dfa4ca`). Gerçek görüntü olmasa bu hata bulunamazdı — bu da
tek başına setin değerini gösteriyor.

## Kamera çiftliğindeki yeri

`cam-16` — önceden PETS09'un 8. açısıydı (aynı sahnenin 7 kopya
açısından biri, çiftlikteki en az bilgi taşıyan slot).

MediaMTX videoyu sonsuz döngüde yayınlıyor: düşme her ~5.4 saniyede
tekrarlanıyor, yani kural sürekli sınanıyor.

Yer gerçeği: `data/annotations/cam-16.truth.json`
(3.0–5.4 sn arası düşme; sınırlar kare kare göz incelemesiyle konuldu).

## Mahremiyet

Görüntüde tanımlanabilir bir kişi var (araştırma gönüllüsü, yüzü açık).

- Rapora **bu setten ekran görüntüsü konulmayacak** — Oxford
  TownCentre için alınan kararın aynısı (`data/_sources/SOURCE.md`)
- Sistem çıktısı gösterilecekse yalnızca **iskelet ve kutu** çizimi,
  altındaki görüntü olmadan
- `data/` dizini `.gitignore`'da; hiçbir kare git'e girmiyor

## Lisans ve kullanım kısıtı

Veri seti **akademik araştırma** amacıyla yayımlanmıştır. Yazarlar
kullanım için atıf istiyor.

**Bu projedeki kullanım:**
- Yalnızca yerel değerlendirme
- Teslim paketine dahil edilmez
- Türetilmiş çıktı (iskelet, özellik) da paylaşılmaz

## Atıf (raporda yer alacak)

> Kwolek, B., & Kepski, M. (2014). *Human fall detection on embedded
> platform using depth maps and wireless accelerometer.* Computer
> Methods and Programs in Biomedicine, 117(3), 489–501.
> doi:10.1016/j.cmpb.2014.09.005
