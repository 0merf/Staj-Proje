# ADR-0009 · Kimlik doğrulama: JWT + `httpOnly` çerez, `localStorage` DEĞİL

**Durum:** kabul edildi
**Tarih:** 30.08.2026 · **Güncellendi:** 03.09.2026 (G14, G19 eklendi)

## Bağlam

⚠ **API, Gün 16'ya kadar TAMAMEN AÇIKTI.** Kamera listesi, olay
geçmişi, webcam açma/kapatma — hiçbiri kimlik doğrulaması istemiyordu.
`config.py` JWT ayarlarını Gün 1'den beri taşıyordu ama tek satır kod
yoktu.

Tek hafifletici koşul her şeyin `127.0.0.1`'e bağlı olmasıydı ve bu
**bir savunma değil bir tesadüf**: Caddy ters vekili devreye girdiği
an API dış ağa açılıyor.

Bu sistem bir **gözetim altyapısı.** Ele geçirilmesi durumunda saldırgan
yalnızca veri çalmaz — **binanın içini canlı izler.**

## Değerlendirilen seçenekler

### Parola saklama

| Seçenek | Değerlendirme |
|---|---|
| SHA-256 / MD5 | ❌ **Hızlı olmak için tasarlandılar.** Parola hash'inde hız saldırganın işine yarar |
| bcrypt | 🟡 Yaygın ve iyi; ama yalnızca CPU maliyeti dayatıyor |
| **Argon2id** | ✅ Hem CPU **hem BELLEK** maliyeti → GPU'yla paralel kırma avantajı da siliniyor. 2015 Password Hashing Competition kazananı, OWASP'ın 1. önerisi |

Ölçülen doğrulama süresi bu makinede **~50 ms** — kullanıcı için
görünmez, saldırgan için deneme başına 50 ms.

### Token saklama — projenin en önemli güvenlik kararı

| Seçenek | Değerlendirme |
|---|---|
| `localStorage` | ❌ **JavaScript okuyabiliyor.** Sayfaya sızan herhangi bir XSS, tokenı doğrudan çalar. Yaygın kalıp olması güvenli olduğu anlamına gelmiyor |
| Bellekte (React state) | 🟡 XSS'e karşı biraz daha iyi ama sayfa yenilenince oturum düşüyor; ayrıca `<video>` ve WebSocket'e taşınamıyor |
| **`httpOnly` çerez** | ✅ JavaScript **okuyamıyor.** Ayrıca WebSocket el sıkışmasında ve `<video>` isteğinde **kendiliğinden** gidiyor |

⚠ **Çerez seçimi teknik bir zorunluluk da:** tarayıcının WebSocket
API'si özel başlık eklemeye izin vermiyor. `Authorization: Bearer`
başlığı WS'e taşınamıyor; çerez taşınıyor.

Bedeli: panel *"girişli miyim"* sorusunu tokena bakarak
cevaplayamıyor, **sunucuya sormak** zorunda (`GET /auth/ben`). Ucuz
bir bedel.

## Karar

```
Parola  : Argon2id (kütüphane varsayılanının üstünde parametreler)
Token   : JWT · erişim 15 dk · yenileme 7 gün
Taşıma  : httpOnly + SameSite=lax + Secure(yalnızca production) çerez
          (+ Authorization başlığı da kabul ediliyor — API istemcileri için)
Roller  : viewer < operator < admin (hiyerarşik)
```

### ⚠ PLAN'DAN SAPMA: `SameSite=Strict` değil `lax`

PLAN §11.1/G03 `SameSite=Strict` diyor. Kod `lax` kullanıyor.

**Gerekçe:** `Strict`, kullanıcı panele **başka bir sayfadan gelen bir
bağlantıyla** girdiğinde çerezi göndermiyor ve kullanıcı girişli
olduğu hâlde giriş ekranıyla karşılaşıyor. `lax`, CSRF'in asıl hedefi
olan **durum değiştiren çapraz site istekleri**ni (POST) yine
engelliyor.

⚠ Sapmanın kendisi sorun değil; **gerekçesiz sapma** sorun (mimari
kural 0). Bu satır o gerekçe.

### ⚠ JWT İPTAL EDİLEMEZ — bilinen kısıt

Kendi kendini doğrulayan bir token, süresi dolana kadar geçerlidir;
*"çıkış yap"* gerçek bir iptal değildir. Doğru çözüm bir `jti` kara
listesi (Valkey'de) ve bu, erişim tokenının 15 dakikalık ömrüyle
sınırlı bir risk karşılığında **bilinçli olarak** yapılmadı.

**Yenileme tokenı için iptal VAR:** veritabanındaki `token_surumu`
artırılınca o kullanıcının tüm yenileme tokenları geçersizleşiyor.
Yani "tüm oturumları kapat" gerçekten çalışıyor.

## Sonuçlar

**Kazanılan:** API kapandı. XSS ile token çalma yolu kapandı.
Kullanıcı numaralandırma (user enumeration) kapandı — hem tek hata
mesajı hem de var olmayan kullanıcı için sahte hash doğrulaması
(zamanlama saldırısı).

**Kaybedilen:** Panel her açılışta sunucuya bir istek daha atıyor.

**Bilinen eksik (G05):** Kamera bazlı yetki YOK. Doğrulanmış her
kullanıcı **tüm** kameralara abone olabiliyor. `user_camera_access`
tablosu yazılmadı ve bu, raporda "yapıldı" diye değil **eksik** diye
yazılacak.

## Ölçüm

Kimlik doğrulama bir hız ölçümü değil, bir kapsam ölçümü. Kontrol
listesi (PLAN §11.1, Öncelik-1):

| | Madde | Durum |
|---|---|---|
| G01 | Argon2id | ✅ |
| G02 | Kısa ömürlü access + refresh | ✅ |
| G03 | httpOnly çerez | ✅ (`lax`, gerekçesi yukarıda) |
| G04 | RBAC | ✅ |
| G05 | Kamera bazlı yetki | ❌ |
| G06 | WS Origin doğrulaması | ✅ (şema dâhil — P-21) |
| G07 | WS abonelikte yeniden yetkilendirme | ✅ beyaz liste |
| G14 | Bağlantı limitleri | ✅ 03.09 |
| G19 | Denetim kaydı | ✅ 03.09 (sadece-ekleme trigger dâhil) |
| G20 | Giriş hız sınırı + kilitleme | ✅ |

**K9: 17/19.** Kalan: G05 (kamera yetkisi), G18 (TLS/Caddy).

### ⚠ 03.09.2026'da çıkan iki bulgu

**1 · G14 bir ölü ayardı.** `MAX_WS_CONNECTIONS_PER_USER=4` hem
`.env`'de hem `config.py`'de vardı ve **hiçbir yerde okunmuyordu.**
Güvenlik kontrol listesinde bir madde, kodda bir ölü değişken olarak
yaşıyordu — ve ayarın varlığı korumanın var olduğu izlenimini
veriyordu.

> ⭐ Olmayan korumadan kötüsü, **var sanılan korumadır.**

**2 · G19 sandığından eksikti.** Denetim izi yalnızca giriş/çıkış/
yenileme yazıyordu. Webcam açma — **sistemdeki en mahremiyet-hassas
eylem, çünkü tek "yeni kamera açan" uç** — denetime hiç girmiyordu.
Üstelik kodda *"Faz 1'de rol ve denetim kaydı zorunlu olacak"* notu
duruyordu: rol gelmişti, denetim gelmemişti, ve **not bayat olduğu
için eksik görünmez hâle gelmişti.**

Ayrıca PLAN §12.1'in söz verdiği *"denetim kaydı sadece-ekleme, DB
trigger ile UPDATE/DELETE engellenir"* maddesi de kodda yoktu.
03.09'da eklendi (UPDATE, DELETE **ve** TRUNCATE — sonuncusu ifade
bazlı çalıştığı için ayrı bir tetikleyici istiyor ve kolayca atlanır).

⚠ **Dürüst sınır:** veritabanının sahibi bu trigger'ı düşürebilir.
Gerçek değişmezlik ayrı bir sunucu ya da WORM depolama ister; bu
kurulumda yok. Trigger kazayı ve sıradan kötüye kullanımı engelliyor,
kararlı bir saldırganı değil.

Tam anlatım: `docs/report/problems.md` · **P-42**
