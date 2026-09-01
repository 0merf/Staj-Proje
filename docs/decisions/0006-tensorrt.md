# ADR-0006 · TensorRT ölçüldü, üretime alınmadı

**Durum:** kabul edildi (koşullu)
**Tarih:** 26.08.2026

## Bağlam

Çıkarım PyTorch FP16 ile yapılıyor. TensorRT genellikle 2-5× hızlanma
vaat ediyor.

## ⚠ On gün boyunca YANLIŞ bir gerekçeyle ertelendi

Gün 8'den beri proje hafızasında şu yazıyordu:

> *"TensorRT planlandı ama kullanılmıyor: GPU %0-5'te boş oturuyor
> (`GpuIdle`), yani modeli hızlandırmak kazanç getirmezdi."*

Cümle mantıklı görünüyor. **Yanlış.** İki farklı büyüklük
karıştırılmış:

| Ölçülen | Sanılan |
|---|---|
| **Görev döngüsü** — GPU zamanın yüzde kaçında meşgul | **Çağrı maliyeti** — bir ileri geçiş kaç ms |

GPU'nun %5 kullanımda görünmesi, ileri geçişin ucuz olduğunu değil,
**partiler arasında beklediğini** söyler.

## Ölçüm — önce kazanç tavanı

⚠ CUDA olayıyla ölçüldü, duvar saatiyle değil: CUDA çağrıları
eşzamansız, `perf_counter` işin bitişini değil kuyruğa atılışını ölçer.

```
AŞAMA      kare ms    pay
TENSOR       0.960    15%
FORWARD      3.372    53%   ⬅ TensorRT'nin dokunabildiği tek yer
ARTIK        1.970    31%   NMS + Results nesnesi kurma
CONVERT      0.004     0%
TOPLAM       6.305
```

İleri geçiş bütçenin **yarısından fazlası.** Amdahl'a göre 3×
hızlanma → toplam %35.6 kazanç. Yani denemeye değer.

## Ölçüm — sonra gerçek

Motor derlendi (⚠ iki engel: TensorRT 11/cu13 torch cu128 ile uyumsuz
→ 10.13/cu12; `dynamic=True` YOLO26'nın dikkat bloğunda kırılıyor →
sabit parti).

Dönüşümlü A/B, 25 tur:

```
PyTorch    5.144 ms/kare
TensorRT   3.662 ms/kare      1.40×  (−28.8% süre)

TESPİT EŞDEĞERLİĞİ: 20/20 eşleşme · 0 kayıp · ortalama IoU 0.9989
```

⚠ İkinci satır olmadan birincisi anlamsız. "Hızlandı" diye raporlanan
bir kazanç, modelin daha az insan bulmasıysa kazanç değil kayıptır —
ve bu **sessiz** bir hatadır, hız grafiğinde görünmez.

## Karar

**Üretime ALINMADI.** Sebep hızda değil, parti dağılımında:

```
parti   PyTorch   TRT(8'e dolgu)   kazanç
    2     12.30          17.65    -43.4%
    4     19.57          24.74    -26.4%
    6     38.04          29.58    +22.2%
    8     39.25          27.13    +30.9%
```

Motor **sabit parti** istiyor; eksik kareler tekrarla dolduruluyor ve
maliyet tam parti kadar oluyor. Canlı ölçüm (5 dk, 1424 parti):

```
ortalama 5.52 kare/parti · partilerin yalnızca %47'si 7-8 aralığında
```

Yani partilerin **yarısından fazlasında TensorRT kaybettirirdi.**

## Sonuçlar

**Kazanılan:** On günlük yanlış bir gerekçe düzeltildi. İhraç reçetesi
(`scripts/export_tensorrt.py`) ve A/B ölçüm aracı hazır.

**Açık iş:** `--batch-fill-ms` özelliği yazıldı (partiyi doldurmak için
kısa süre bekle) ve mekanizmanın çalıştığı ölçüldü — dolu parti oranı
%46 → %78. Ama **verim etkisi ölçülemedi**: bloklar arası yayılım
etkiden büyük çıktı (P-36). Varsayılan KAPALI.

TensorRT ancak parti doldurma kanıtlanınca anlamlı.

## ⚠ Kaydedilmeye değer ders

Bir kararın gerekçesi belgeye girdikten sonra **veri gibi davranmaya
başlıyor.** "TensorRT'ye gerek yok" on gün boyunca bir bulgu olarak
alıntılandı; oysa bir çıkarımdı ve yanlıştı.
