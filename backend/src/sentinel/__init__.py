"""SENTINEL — çok kameralı akıllı gözetim sistemi.

⚠⚠⚠ BU DOSYA `numpy` IMPORT EDİLMEDEN ÖNCE ÇALIŞIR — VE BU KRİTİK
------------------------------------------------------------------
Python bir alt modülü (`sentinel.analytics.worker`) import ederken
ÖNCE paketin `__init__.py`'ını çalıştırıyor. Yani buraya konan ayar,
hiçbir alt modül `numpy`i import etmeden önce yürürlüğe giriyor.

NumPy'ın BLAS arka ucu (OpenBLAS/MKL) iş parçacığı havuzunu **import
anında** kuruyor ve boyutunu ortam değişkenlerinden okuyor; sonradan
değiştirmek işe yaramıyor. Bu yüzden ayar başka hiçbir yere
konulamazdı.

⭐ Ölçülen etki (P-58): analitik worker 795.5% → 38.3% CPU
(7.96 → 0.38 çekirdek), iş parçacığı 59 → 3, sistem CPU %94 → %34.
Tam gerekçe ve ölçüm zinciri: `sentinel/runtime.py` modül başlığı.
"""

from sentinel.runtime import tek_thread_blas

# ⚠ Kullanıcı ortamda değer verdiyse DOKUNULMUYOR (zorla=False).
tek_thread_blas()

__all__ = ["tek_thread_blas"]
