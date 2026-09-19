# Mimari Karar Kayıtları (ADR)

Projede verdiğim mimari kararları ve gerekçelerini burada topladım.
Raporun "Teknoloji seçimleri ve gerekçeleri" bölümünü bu kayıtlardan
yazdım.

## Bu dizin 30.08.2026'ya kadar boştu

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

**"Ölçüm" bölümü boş bırakılmaz.** Ölçülmemiş bir karar bir tercihtir;
ölçülmüş bir karar bir bulgudur. Ölçüm yapılamadıysa *neden
yapılamadığı* yazılır.

**Çürüyen kararlar silinmez**, durumu "değiştirildi" olur ve yeni
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
| [0007](0007-kural-once-model-sonra.md) | Önce kural tabanlı skor, sonra model | kabul düzeltme notu (03.09) |
| [0008](0008-fuzyon-katmani.md) | Füzyon: gözlem doğrudan, ipucu toplulukta | kabul **gerekçesi eksik** |
| [0009](0009-kimlik-dogrulama.md) | JWT + `httpOnly` çerez, `localStorage` değil | kabul |
| [0010](0010-timescaledb-olay-kaliciligi.md) | Olay kalıcılığı: TimescaleDB | kabul |

## İki kaydın durumu "kabul" ama tam değil — ve bu bilinçli

**ADR-0007** ilkeyi doğru yazıp kendisi ihlal ediyordu: *"eşiği aynı
kliplerle hem ayarlayıp hem değerlendirmek ezberi başarı sanmaktır"*
diyor, ama `en_iyi_esik` tam olarak öyle seçiliyor. 03.09'da bir
düzeltme notu eklendi. Karar değişmedi; değişen, **bildirilen sayının
yanlılığının açıkça yazılması.** Yanlılığı sonradan ölçtüm: +0.020 F1
(P-64).

**ADR-0008**'in merkezî iddiası (*"birleştirme kazandırıyor"*) K6'da
kanıtlanamadı: kontrol serisiyle ölçünce kazancın %91'i yumuşatmadan,
%9'u birleştirmeden geliyordu (P-41). Füzyonun asıl kazancı gürültü
bastırma olduğu için gerekçeyi K7'ye taşıdım.

> Bu iki kayıt, ADR'lerin **canlı belge** olduğunun kanıtı. Bir
> kararı yazmak onu doğrulamaz; ADR-0006'nın dersi burada da geçerli:
> *"bir kararın gerekçesi belgeye girdikten sonra veri gibi davranmaya
> başlıyor."*
