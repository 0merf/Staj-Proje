# ADR-0001 · Arka uç dili: Python + FastAPI

**Durum:** kabul edildi
**Tarih:** 12.08.2026

## Bağlam

Şartname teknik detayları geliştiriciye bırakıyor. Sistem hem **web
uygulaması** hem **gerçek zamanlı YZ çıkarım hattı**. İki iş yükünün
gereksinimleri farklı ve tek bir dilde birleştirilecekler.

Kurumsal alışkanlık ASP.NET Core yönünde; teknik gereksinim başka yöne
işaret ediyor.

## Değerlendirilen seçenekler

**A · ASP.NET Core (C#)**
Web tarafında olgun, tip güvenli, yüksek başarımlı. Ama YZ tarafında
ONNX Runtime dışında seçenek yok: Ultralytics, PyAV, EmotiEffLib,
BoT-SORT — hiçbirinin C# karşılığı yok. Her model için ONNX'e ihraç +
ön/son işlemeyi elle yeniden yazmak gerekir.

**B · İkisi birden** — C# API + Python YZ servisi
Her iki ekosistemin gücü. Ama iki dil, iki dağıtım, iki test altyapısı,
ve aralarında bir sınır. 25 iş günlük bir projede bu sınırın bakımı
tek başına bir kalem.

**C · Python + FastAPI**
YZ ekosisteminin tamamı yerli. FastAPI async, OpenAPI'yi kendiliğinden
üretiyor, Pydantic ile girdi doğrulaması geliyor (G10).

## Karar

**C.** Ana kısıt YZ ekosistemi; web tarafı zaten çözülmüş bir problem.

## Sonuçlar

**Kazanılan:** Model değiştirmek bir satırlık iş. `Detector`,
`PoseEstimator`, `Tracker` protokolleri sayesinde Ultralytics'in
AGPL-3.0 lisansından çıkış kapısı da açık kaldı.

**Kaybedilen — ve bedeli ödendi:** GIL. Tek süreçte gerçek CPU
paralelliği yok. Mimari bunu telafi etmek zorunda kaldı:

- Alım katmanı kamera başına **thread** kullanıyor ve bu ancak
  `cv2.resize`/PyAV GIL'i **bıraktığı** için işe yarıyor
- Çıkarım tek süreç (VRAM zorunluluğu) ve orada paralellik yok
- Ön işlemenin alım katmanına taşınması (P-18) doğrudan bu kısıtın
  sonucu: iş, GIL'i bırakan tarafa taşındı

## Ölçüm

Ön işleme alım katmanına taşındığında kare başına maliyet
**6.78 → 3.87 ms** (%43 kazanç), tespitler birebir aynı.
`benchmarks/` · P-18.

Bu sayı kararın kendisini doğrulamıyor — GIL'in gerçek bir kısıt
olduğunu ve mimarinin onu **başarıyla dolandığını** gösteriyor.
