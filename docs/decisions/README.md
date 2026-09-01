# Mimari Karar Kayıtları (ADR)

> Rapor bölümü **§3.4 "Teknoloji seçimleri ve gerekçeleri"** buradan
> yazılacak. `CLAUDE.md` §9: *"Her mimari karar → `docs/decisions/`"*.

## ⚠ Bu dizin 30.08.2026'ya kadar BOŞTU

39 problem kaydı vardı, **0 karar kaydı**. Fark önemli:

| | Neyi anlatır |
|---|---|
| `problems.md` | **Ne bozuldu, nasıl düzeltildi** — hata günlüğü |
| `decisions/` | **Neden X, neden Y değil** — seçim gerekçesi |

Şartnamenin asıl sınavı ikincisi: *"Teknik detaylar geliştiriciye
bırakılmıştır"* denen bir projede, her seçimin savunulabilir olması
gerekiyor. Gerekçeler kod yorumlarına dağılmış durumdaydı; kod yorumu
bir dosyayı okuyana konuşur, karar kaydı raporu okuyana.

## Biçim

Her kayıt `NNNN-kisa-baslik.md`, şu iskeletle:

```markdown
# ADR-NNNN · Başlık
**Durum:** kabul edildi | reddedildi | değiştirildi (ADR-XXXX ile)
**Tarih:** GG.AA.YYYY

## Bağlam        — hangi kısıt bu kararı zorunlu kıldı
## Değerlendirilen seçenekler
## Karar
## Sonuçlar      — neyi kazandık, neyi kaybettik
## Ölçüm         — kararı destekleyen ya da çürüten sayı
```

⚠ **"Ölçüm" bölümü boş bırakılmaz.** Ölçülmemiş bir karar bir tercihtir;
ölçülmüş bir karar bir bulgudur. Ölçüm yapılamadıysa *neden
yapılamadığı* yazılır.

⚠ **Çürüyen kararlar SİLİNMEZ**, durumu "değiştirildi" olur ve yeni
karara işaret eder. Bir kararın nasıl çürüdüğü, kararın kendisinden
öğreticidir (ADR-0005 ve ADR-0006 tam bu çifti oluşturuyor).

## Kayıtlar

| # | Karar | Durum |
|---|---|---|
| [0001](0001-python-vs-aspnet.md) | Arka uç dili: Python + FastAPI | kabul |
| [0002](0002-kademeli-isleme.md) | Kademeli işleme — 20 kamerayı mümkün kılan mimari | kabul |
| [0003](0003-ham-kare-paylasimli-bellek.md) | Ham kare Valkey'den geçmez | kabul |
| [0004](0004-sunucu-videoya-cizmez.md) | Video ve üst katman ayrı yollardan gider | kabul |
| [0005](0005-nvdec-kullanilmiyor.md) | NVDEC kullanılmıyor | kabul |
| [0006](0006-tensorrt.md) | TensorRT ölçüldü, üretime alınmadı | kabul |
| [0007](0007-kural-once-model-sonra.md) | Önce kural tabanlı skor, sonra model | kabul |
