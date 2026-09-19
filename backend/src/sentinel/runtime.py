"""Çalışma zamanı ön ayarları — NumPy/BLAS import edilmeden önce (P-58).

Bu modül `numpy` IMPORT edilmeden önce çağrılmak zorunda
--------------------------------------------------------------
NumPy'ın BLAS arka ucu (OpenBLAS/MKL) iş parçacığı havuzunu **import
anında** kuruyor ve havuz boyutu o anki ortam değişkenlerinden
okunuyor. Sonradan değiştirmek işe yaramıyor.

Neden gerekli — ölçülmüş hikâye
----------------------------------
Öğrenilmiş model üretime alındıktan sonra (P-56) gecikme 2.2 kat
arttı ve analiz hızı %39 düştü. Üç hipotez sırayla çürütüldü:

  1. Kopya süreçler   → temizlendi, gecikme aynı kaldı
  2. Modelin kendi işi → üretimde ölçüldü: kare başına 0.86 ms
                         (bir çekirdeğin %2.6'sı) — masum
  3. LightGBM OpenMP  → `num_threads=1` yapıldı, değişmedi

Sonra süreç başına CPU ölçüldü ve suçlu göründü:

    rol         CPU %    çekirdek   thread
    analitik    795.5      7.96        59     ← 8 çekirdek

Analitik worker'ın kendi işi 0.86 ms/kare iken 8 çekirdek yiyordu.
Sebep: modelin `np.array(...)` çağrısı NumPy'ın BLAS havuzunu
uyandırıyor; havuz **çekirdek sayısı kadar** (bu makinede 20) iş
parçacığı açıyor ve işler arasında **meşgul bekliyor** (busy-wait).
Saniyede ~27 tahminle havuz hiç uykuya geçmiyor.

Ortam değişkenleri sınırlandığında:

    Analitik   795.5% → 38.3%   (7.96 → 0.38 çekirdek, 21 kat)
    thread        59  → 3
    sistem CPU  %94.1 → %33.8

Ve bu iş parçacıkları hiçbir şey kazandırmıyordu: tahmin girdimiz
**tek satır × 99 özellik**. Böyle bir işlemi 20 çekirdeğe yaymanın
faydası yok, yalnızca zararı var.

Ders: duvar saati ≠ CPU zamanı
----------------------------------
Modelin içine koyduğum histogram `predict`i 0.307 ms ölçüyordu ve bu
**doğruydu** — iş 20 iş parçacığına yayıldığı için duvar saati
gerçekten küçüktü. Ama CPU zamanı 20 katıydı ve asıl darboğaz
havuzun beklerken dönmesiydi.

> Bir işlemin maliyetini "ne kadar sürdü" diye ölçmek, paralel
> çalışan bir şey için yanlış sorudur. Doğru soru: "ne kadar
> çekirdek-saniye harcadı".

Bu, projedeki ölçüm aracı hatalarının bir başka türü: araç doğru
çalışıyordu, **yanlış büyüklüğü** ölçüyordu.

Neden `.env` değil de kod
---------------------------
`.env` ya da başlatma betiğine yazmak çalışırdı ama kırılgan: worker
elle başlatılırsa (geliştirme, hata ayıklama, testler) ayar kaybolur
ve sorun sessizce geri gelir. Kod garanti ediyor.

Kullanıcı yine de üzerine yazabilir: ortam değişkeni zaten
tanımlıysa dokunulmuyor.
"""

from __future__ import annotations

import os

# BLAS/OpenMP arka uçlarının iş parçacığı sayısını okuduğu değişkenler.
# Hepsi gerekiyor: hangi arka ucun derlendiği platforma göre değişir
# (OpenBLAS, MKL, ya da NumPy'ın kendi havuzu).
_THREAD_DEGISKENLERI = (
    "OMP_NUM_THREADS",       # OpenMP (LightGBM, OpenBLAS, sklearn)
    "OPENBLAS_NUM_THREADS",  # OpenBLAS
    "MKL_NUM_THREADS",       # Intel MKL
    "NUMEXPR_NUM_THREADS",   # numexpr (pandas zinciri)
    "VECLIB_MAXIMUM_THREADS",  # macOS Accelerate
)


def tek_thread_blas(*, zorla: bool = False) -> dict[str, str]:
    """BLAS/OpenMP havuzlarını tek iş parçacığına sabitler.

    `numpy` import edilmeden önce çağrılmalı — havuz import anında
    kuruluyor.

    Args:
        zorla: `True` ise mevcut ortam değişkenlerinin üzerine yazar.
            Varsayılan `False`: kullanıcı bilinçli bir değer verdiyse
            ona dokunulmaz.

    Returns:
        Bu çağrının ayarladığı değişkenler (tanı için).
    """
    ayarlanan: dict[str, str] = {}
    for ad in _THREAD_DEGISKENLERI:
        if not zorla and os.environ.get(ad):
            continue
        os.environ[ad] = "1"
        ayarlanan[ad] = "1"
    return ayarlanan


__all__ = ["tek_thread_blas"]
