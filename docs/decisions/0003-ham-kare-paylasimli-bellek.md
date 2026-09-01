# ADR-0003 · Ham kare Valkey'den geçmez

**Durum:** kabul edildi
**Tarih:** 12.08.2026

## Bağlam

Alım worker'ı kareyi çözüyor, çıkarım worker'ı işliyor. İkisi ayrı
süreç. Kare nasıl taşınacak?

Aritmetik: 1080p BGR kare = 1920 × 1080 × 3 = **~6 MB.**
20 kamera × 4 FPS = 80 kare/sn × 6 MB = **480 MB/sn.**

## Değerlendirilen seçenekler

**A · Kareyi Valkey mesajına koy**
En basit kod. Ama 480 MB/sn'yi seri hâle getirip TCP'den geçirip geri
çözmek demek — üstelik Valkey RAM'de tutuyor ve kuyruk birikirse RAM
patlıyor.

**B · Diske yaz, yolu gönder**
Disk I/O gecikme ekler ve SSD'yi yorar (14 GB/saat mertebesinde).

**C · Paylaşımlı bellek havuzu + referans**
Kare `multiprocessing.shared_memory` içindeki sabit bir slota yazılıyor;
Valkey'den yalnızca `(slot, boyut, zaman damgası)` geçiyor.

## Karar

**C.** Mimari kural 1: *"Ham kare Valkey'den geçmez."*

Sabit boyutlu bir slot havuzu (48 slot). Alım worker'ı slot alıyor,
yazıyor, referansı yayınlıyor; çıkarım worker'ı okuyor ve slotu iade
ediyor.

## Sonuçlar

**Kazanılan:** Valkey'den geçen veri kare başına ~200 bayt. Kopyalama
yok — çıkarım worker'ı aynı belleği okuyor.

**Kazanılan 2 (sonradan):** Ön işleme alım katmanına taşınınca slot
boyutu 2.76 → **1.23 MB** düştü (640×640 letterbox, 1080p değil).

**Kaybedilen — ve bedeli ağır oldu:** Havuz **paylaşılan bir kaynak**
ve bir tüketici onu ödünç alıp ölürse slot kaybolur. 30.08.2026'da
ölçüldü: çıkarım worker'ı sert kapatıldığında 48 slotun 48'i sızmış,
üretim tamamen durmuştu — ve arıza **sessizdi** (P-38).

Slot muhasebesi eklendi: bir slot ya boş listede, ya işlenmemiş bir
mesajın referansında, ya da tüketicinin elinde olmak zorunda; üçünde
de yoksa sızmıştır.

## Ölçüm

| | |
|---|---|
| Valkey'den geçen | ~200 bayt/kare (6 MB yerine) |
| Slot boyutu | 1.23 MB (ön işleme taşındıktan sonra) |
| Havuz | 48 slot — geri basınç sınırı da bu |
| Sızıntı kurtarma | 0/48 → 36/48, üretim yeniden başladı |
