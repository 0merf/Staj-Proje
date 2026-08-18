# RWF-2000 — Kaynak, Lisans ve Atıf

> **PLAN.md §7.2 kuralı:** Her veri seti için indirme adresi, lisans ve
> alıntı bilgisi kaydedilir. Veri **git'e girmez**, bu dosya girer.

## Ne için kullanılıyor

**Saldırgan davranışın erken tespiti** modülünün eğitim ve
değerlendirme seti (PLAN.md §6.5.5).

| Aşama | İş | Gün |
|---|---|---|
| 1 | Klipleri YOLO26-pose'dan geçirip iskelet dizileri çıkar | 14 |
| 2 | Özellik vektörleri üret (`.npz`) | 17 |
| 3 | LightGBM taban modeli eğit, F1 ölç | 17 |
| 4 | GRU tırmanma modeli, taban modeli geçiyor mu | 18 |
| 5 | **Erken uyarı avansı** — elle etiketli alt küme | 17-18 |

Başarı kriteri **K5: F1 ≥ 0.85** (PLAN.md §1.4).

## Kaynak

| | |
|---|---|
| **Ad** | RWF-2000: A Large Scale Video Database for Real World Violence Detection |
| **Erişim** | Kaggle — `vulamnguyen/rwf2000` |
| **İndirme** | `kagglehub.dataset_download("vulamnguyen/rwf2000")` |
| **Özgün depo** | https://github.com/mchengny/RWF2000-Video-Database-for-Violence-Detection |
| **Boyut** | ~12 GB (bu makinede, çıkarılmış hâl) |
| **İndirme tarihi** | 13.08.2026 |

## İçerik

```
train/fight      800 klip
train/nonfight   800 klip
val/fight        200 klip
val/nonfight     200 klip
─────────────────────────
TOPLAM          2000 klip
```

Klipler ~5 saniyelik, 30 FPS. Kaynak **gerçek gözetim kameraları** —
literatürde bu setin tercih edilme sebebi bu (Hockey Fight gibi
setler spor yayınından derlenmiştir ve sahne dağılımı gerçekçi değildir).

## ⚠ Dosya adları DEĞİŞTİRİLDİ

Özgün arşivdeki bazı dosya adları 240 karaktere kadar çıkıyor ve bozuk
kodlamalı (mojibake). Windows'un `MAX_PATH` sınırı 260 karakter olduğu
için normal çıkarma "Yol çok uzun" hatası veriyor ve dosyaları sessizce
atlıyordu.

`backend/scripts/extract_rwf2000.py` dosyaları kısa, sıralı adlarla
çıkarıyor:

```
RWF-2000/train/Fight/-1l5631l3fg_0.avi   →   train/fight/fight_0001.avi
```

Etiket bilgisi zaten **klasör adında**; dosya adının analitik değeri yok.

**İzlenebilirlik:** özgün adlar `manifest.csv` dosyasında saklanıyor
(`split, label, new_name, size_bytes, original_name`). Tekrarlanabilirlik
ve rapor için bu eşleme gerekli.

## Lisans ve kullanım kısıtı

Veri seti **akademik araştırma** amaçlıdır. Özgün depo, kullanım için
yazarların şartlarına uyulmasını istiyor.

**Bu projedeki kullanım:**
- Yalnızca **yerel değerlendirme** ve model eğitimi için
- Veri seti **teslim paketine dahil edilmez**
- `data/` dizini `.gitignore`'dadır — hiçbir klip git'e girmez
- Türetilmiş çıktılar (iskelet dizileri, `.npz` özellik dosyaları) da
  ham görüntü içermediği hâlde teslim paketine dahil edilmez

## Atıf (raporda yer alacak)

> Cheng, M., Cai, K., & Li, M. (2021). *RWF-2000: An Open Large Scale
> Video Database for Violence Detection.* 25th International Conference
> on Pattern Recognition (ICPR), 4183-4190. arXiv:1911.05913

## Karşılaştırma bağlamı (LITERATUR.md §6.5.1)

Literatürde bu set üzerinde raporlanan sonuçlar:

| Yöntem | Doğruluk | Not |
|---|---|---|
| RTVD-Net | %93.28 | YOLO-Pose iskeleti üzerinde ön eğitim |
| 60 bin parametreli iskelet modeli | %90.25 | Çok hafif |

⚠ Bizim katkımız doğruluk yarışı değil, **erken uyarı avansı**:
literatürdeki çalışmalar "şiddet var/yok" doğruluğu raporluyor, "kaç
saniye önce" sorusunu ölçmüyor (PLAN.md §6.5.5 adım 5).
