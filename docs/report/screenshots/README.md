# Ekran Görüntüleri — çekilecekler listesi

> Rapor eki. **Bu dizin 01.09.2026 itibarıyla BOŞ.**
> `YOL-HARITASI.md` §4.1

## ⚠ MAHREMİYET KURALI — önce bunu oku

Bu sistem **gerçek insanları** içeren görüntüler işliyor. İki veri
setinde tanımlanabilir kişiler var ve `SOURCE.md` dosyalarında açık
kural yazılı:

| Set | Kamera | Kural |
|---|---|---|
| Oxford TownCentre | cam-09 | Rapora **görüntü konulmayacak** |
| UR Fall | cam-16 | Yüzü açık araştırma gönüllüsü — **görüntü konulmayacak** |

**Gösterilebilecek olan:** iskelet ve kutu çizimleri, altındaki
görüntü olmadan. Panelin "görünüm modu" düğmesi bunu zaten
destekliyor (kapalı / kutular / iskelet).

⚠ Bir gözetim sistemi raporunda mahremiyet ihlali yapmak, raporun
kendi tezini çürütür.

## Çekilecekler

| # | Ne | Neden | Nasıl |
|---|---|---|---|
| 1 | **Panel — 20 kamera** | K1'in görsel kanıtı | `/app`, hepsini aç · ⚠ cam-09 ve cam-16 kutucuklarını kapat ya da iskelet moduna al |
| 2 | **Alarm paneli — kanıt satırları açık** | ⭐ Açıklanabilirliğin vitrini. "Anomali var" demek yetmez; hangi ölçümün eşiği neden aştığı görünmeli | Bir düşme alarmı bekle (cam-16 her ~5.4 sn) |
| 3 | **Füzyon alarmı** | Beş sinyalin birleşimi. `birleşen sinyal sayısı ≥2` görünmeli | Alarm türü `RİSK (birleşik)` |
| 4 | **Grafana — boru hattı sağlığı** | K2/K3/K7 + boş slot | `:3000` → `sentinel-boru-hatti` |
| 5 | **Giriş ekranı** | Güvenlik bölümü (§5) | Çıkış yapıp `/app` |
| 6 | **Kimlik doğrulama reddi** | 401/403 davranışı | DevTools ağ sekmesi, tokensiz istek |
| 7 | **Denetim izi** | G19 — "kim ne zaman izledi" | `/api/v1/auth/denetim` (admin) |
| 8 | **K6 ROC sonucu** | Terminal çıktısı yeterli | `evaluate_k6.py` çıktısı |

## Adlandırma

```
NN-kisa-aciklama.png     → 01-panel-20-kamera.png
```

⚠ Ekran görüntüsünde **parola, token ya da `.env` içeriği görünmesin.**
Tarayıcı DevTools açıkken çekiyorsan `Authorization` başlığını kırp.
