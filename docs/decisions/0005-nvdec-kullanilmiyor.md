# ADR-0005 · NVDEC kullanılmıyor

**Durum:** kabul edildi
**Tarih:** 13.08.2026 (ilk teşhis 12.08, **düzeltildi**)

## Bağlam

20 RTSP akışının H.264 çözümü CPU'da mı yapılacak, GPU'nun donanım
çözücüsünde (NVDEC) mi?

Gün 2'de ilk ölçüm *"1 kamera ≈ 1 çekirdek, NVDEC şart"* dedi ve bu
karar bir gün boyunca doğru sanıldı.

## ⚠ İlk ölçüm YANLIŞTI

Ölçüm **RTSP akışından** yapılmıştı. Akış zaten gerçek zamanlı 25 FPS
veriyor — ölçülen şey çözme kapasitesi değil, **akışın kendi hızıydı.**
Bir hız sınırı kapasite tavanı sanıldı (P-07).

Yerel dosyadan doğru ölçüm (13.08.2026):

| | Sadece çözme | Çözme + BGR dönüşümü |
|---|---|---|
| CPU tek çekirdek | 1072 FPS | **249 FPS** |
| NVDEC | 1142 FPS | **172 FPS** ⬅ daha yavaş |

## Karar

**NVDEC kullanılmıyor.**

Sebep ikinci sütunda: NVDEC kareyi GPU belleğinde çözüyor, ama boru
hattının geri kalanı (BGR dönüşümü, hareket filtresi) o kareyi
**CPU'da** istiyor. GPU→CPU kopyası, kazanılan çözme süresinden
pahalıya geliyor.

## Sonuçlar

**Kazanılan:** GPU tamamen YZ'ye kalıyor. 20 kamera için ~2.0 çekirdek
yetiyor (14 çekirdeğin %14'ü).

**Kaybedilen:** Yok — ölçüm NVDEC'in bu boru hattında zararlı olduğunu
gösteriyor.

## ⚠ Bu karar KOŞULLU

Ölçüm, **kare CPU'ya inecek** varsayımıyla yapıldı. Zincir baştan sona
GPU'da kalırsa (NVDEC → GPU resize → GPU hareket filtresi → doğrudan
model tensörü) sonuç **tersine dönebilir**: GPU→CPU kopyası hiç
olmayacağı için NVDEC'in avantajı ortaya çıkar.

Bu, açık bir iş olarak duruyor. Kararın *hangi varsayımla* alındığını
yazmak, kararın kendisi kadar önemli — varsayım değişirse karar da
değişmeli.

## Ölçüm

`docs/report/problems.md` · P-07 (hatalı teşhis) + P-09 (düzeltme).
