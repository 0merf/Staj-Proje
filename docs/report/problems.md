# Karşılaşılan Problemler ve Çözümleri

> **Bu dosya staj raporunun en değerli bölümüdür.**
> Sonradan hatırlanmaz — her problemi **yaşadığın gün** yaz.
> Rapor bölümü: 4.6 "Karşılaşılan problemler ve çözümleri"

**Yazım formatı:** Her kayıt aşağıdaki şablonu kullanır. Kısa tutmaktan çekinme,
ama **belirti / sebep / çözüm** üçlüsü mutlaka olsun.

---

## Şablon

```markdown
### P-XX · [Kısa başlık]

**Tarih:** GG.AA.YYYY · **Faz:** X · **Kaybedilen süre:** ~X saat

**Belirti:** Ne oldu, hata mesajı neydi, nasıl fark ettim?

**Araştırma:** Neyi denedim, hangi kaynaklara baktım, hangi hipotezler yanlış çıktı?

**Kök sebep:** Asıl sebep neydi?

**Çözüm:** Ne yaptım? (kod parçası / komut / konfigürasyon)

**Öğrenilen ders:** Bir dahaki sefere neyi farklı yaparım?
```

---

## Kayıtlar

<!-- Yeni kayıtlar buraya, en yenisi en üstte -->

### P-05 · `.gitignore` satır içi yorum desteklemiyor — 5565 JPEG commit'e girdi

**Tarih:** 13.08.2026 · **Faz:** 0 · **Kaybedilen süre:** ~10 dk

**Belirti:** Veri setleri `data/_sources/` altına taşındıktan sonra
`git add -A` çalıştırıldığında 5565 PETS2009 JPEG dosyası stage'e girdi.
`.gitignore`'a kural eklenmişti ama işe yaramıyordu.

**Araştırma:** İlk hipotez "kural yanlış yazılmış" idi. `git check-ignore -v`
ile bakınca kuralın **hiçbir dosyayla eşleşmediği** görüldü.

**Kök sebep:** Kural şöyle yazılmıştı:

```gitignore
data/_sources/*      # ham indirilen veri setleri
```

**`.gitignore` satır içi yorum desteklemez.** `#` yalnızca satırın
**başındayken** yorum başlatır. Ortadaki `#` desenin bir parçası sayılır;
git `data/_sources/*      # ham indirilen veri setleri` diye tuhaf bir
desen arar ve hiçbir şey eşleşmez. Sessizce başarısız olur — hata vermez.

**Çözüm:** Yorumlar kendi satırlarına alındı:

```gitignore
# ham indirilen veri setleri (VIRAT, Oxford, PETS…)
data/_sources/*
```

**Öğrenilen ders:** Yeni bir `.gitignore` kuralı yazınca **her zaman
`git check-ignore -v <dosya>` ile doğrula.** Sessizce çalışmayan kural,
hata veren kuraldan çok daha tehlikelidir — bu vakada 800 MB'lık veri
seti fark edilmeden depoya gidebilirdi. Commit öncesi
`git diff --cached --name-only` kontrolü de rutin hâline getirildi.

---

### P-04 · Ruff, Türkçe harfleri "belirsiz unicode" sayıp 108 yanlış pozitif üretti

**Tarih:** 13.08.2026 · **Faz:** 0 · **Kaybedilen süre:** ~5 dk

**Belirti:** `ruff check src` 110 hata döndürdü. Kod yeni yazılmıştı ve
çalışıyordu.

**Kök sebep:** RUF001/RUF002/RUF003 kuralları, görsel olarak ASCII'ye
benzeyen unicode karakterleri "homoglif saldırısı" riski olarak işaretler.
Türkçe `ı` (noktasız i), `ş`, `ğ`, `İ` harfleri bu kapsama giriyor.
108 hatanın tamamı Türkçe docstring ve yorumlardan kaynaklanıyordu.

**Çözüm:** Bu üç kural `pyproject.toml`'da gerekçesiyle birlikte kapatıldı.
Kalan 2 gerçek hata (`RUF100` kullanılmayan `noqa`, import sıralaması)
`--fix` ile düzeltildi.

**Öğrenilen ders:** Lint kuralları dil-agnostik değildir. Yanlış pozitifleri
tek tek `noqa` ile susturmak yerine kuralın **neden** yanlış olduğunu anlayıp
merkezi olarak, gerekçe yazarak kapatmak doğru yaklaşım. Aksi halde 108 tane
`# noqa` satırı kodu okunamaz hale getirirdi.

---

### P-03 · Sağlık kontrolü, sağlıklı servisleri "ölü" raporladı (Windows IPv6 tuzağı)

**Tarih:** 13.08.2026 · **Faz:** 0 · **Kaybedilen süre:** ~20 dk

**Belirti:** `/api/v1/system/health` uç noktası 503 döndürüyor; Valkey ve
PostgreSQL "erişilemiyor" görünüyordu. Ancak `docker compose ps` her ikisini
de `healthy` gösteriyor, `valkey-cli PING` ve `psql` elle çalışıyordu.

**Araştırma:** Aynı bağlantıları uygulama dışında bir Python betiğiyle
denedim — **çalıştılar**, ama Valkey PING'i **2491 ms** sürdü. Sağlık
kontrolündeki zaman aşımı 3 sn'ydi; yani kontrol kıl payı düşüyordu.
Asıl soru "neden bağlanamıyor" değil, "neden 2.5 saniye sürüyor" oldu.

**Kök sebep:** İki karar birleşince ortaya çıkan bir etkileşim:
1. `docker-compose.yml` portları güvenlik gereği **yalnızca IPv4**'e
   bağlıyor (`127.0.0.1:6379:6379`).
2. `.env` dosyasında adres `localhost` yazıyordu.

Windows'ta `localhost` **önce `::1` (IPv6)** olarak çözülür. Servis IPv6
dinlemediği için bağlantı zaman aşımına uğrar, ardından IPv4'e düşülür.
Bu geri düşüş ~2 saniye sürüyor — her istekte.

**Çözüm:** İki yönlü:
- `.env` ve `config.py` içindeki tüm **servis adresleri** `localhost` yerine
  `127.0.0.1` yapıldı. (`ALLOWED_ORIGINS` bilerek `localhost` kaldı —
  tarayıcı Origin başlığını öyle gönderiyor.)
- Sağlık kontrolü zaman aşımı 3 sn → 5 sn (soğuk başlangıç payı).

**Sonuç:** Valkey gecikmesi **2491 ms → 525 ms**. Tüm servisler sağlıklı.

**Öğrenilen ders:** "Bağlanamıyor" ile "yavaş bağlanıyor" farklı problemlerdir
ve zaman aşımı ikisini aynı hataya dönüştürür. Zaman aşımını büyütmek
semptomu gizlerdi; asıl kazanç kök sebebi bulmaktı. Ayrıca bu, güvenlik
kararının (portları IPv4-localhost'a kısıtlamak) beklenmedik bir performans
yan etkisi yaratmasının güzel bir örneği — **rapora bu şekilde yazılacak.**

---

### P-02 · MediaMTX yönetim API'si 401 döndürüyor

**Tarih:** 13.08.2026 · **Faz:** 0 · **Kaybedilen süre:** ~10 dk

**Belirti:** Konteynerler sağlıklı (`healthy`) görünmesine rağmen host'tan
`http://127.0.0.1:9997/v3/config/paths/list` çağrısı
`{"status":"error","error":"authentication error"}` döndürüyordu.

**Araştırma:** İlk hipotez "port yanlış" idi — değildi. İkinci hipotez
"konteyner içinden çalışıyor, dışarıdan çalışmıyor" — doğru çıktı.
Docker sağlık kontrolü konteyner *içinden* `localhost` ile bağlandığı için
geçiyordu; host'tan gelen istek ise Docker köprü ağının IP'sinden (172.x)
geliyordu.

**Kök sebep:** MediaMTX v1.x, varsayılan iç kullanıcı tanımında yalnızca
`publish` / `read` / `playback` izinlerini veriyor. `api` ve `metrics`
eylemleri **varsayılan olarak kapalı** — bu aslında iyi bir güvenlik
varsayılanı, hata değil.

**Çözüm:** `infra/mediamtx/mediamtx.yml` içine `authInternalUsers` bloğu
eklendi. Yayın/izleme iç ağdan serbest bırakıldı; `api` ve `metrics`
izinleri **yalnızca localhost ve özel ağ aralıklarıyla** sınırlandı
(`127.0.0.1/32`, `::1/128`, `10/8`, `172.16/12`, `192.168/16`).

**Öğrenilen ders:** "Konteyner healthy" ile "host'tan erişilebilir" aynı şey
değil. Ayrıca güvenli varsayılanlar ilk denemede hata gibi görünür — konfigürasyonu
gevşetmeden önce *neden* kapalı olduğunu anlamak gerekir. Burada izinleri
tamamen açmak yerine IP kısıtlı açtık (PLAN.md §11 ilkesi).

---

### P-01 · Aynı makinede çalışan başka bir projeyle port çakışması

**Tarih:** 13.08.2026 · **Faz:** 0 · **Kaybedilen süre:** ~15 dk

**Belirti:** `docker compose up` çalıştırılmadan önce yapılan kontrolde,
makinede halihazırda çalışan başka bir Docker Compose projesi (`deploy`)
olduğu görüldü. Konteynerleri: `teknofest_postgres` (5432),
`teknofest_api` (8000), `teknofest_dashboard` (5000).

**Araştırma:** `docker ps -a`, `docker compose ls -a` ve `docker volume ls`
ile mevcut durum çıkarıldı. İki gerçek çakışma tespit edildi: PostgreSQL
(5432) ve planlanan FastAPI portu (8000).

**Kök sebep:** Standart varsayılan portlar kullanılmıştı. Aynı host üzerinde
iki proje aynı portu dinleyemez.

**Çözüm:** SENTINEL'in portları kaydırıldı — **PostgreSQL 5433**, **API 8001**.
Diğer servisler (Valkey 6379, MediaMTX 8554/8889, Prometheus 9090,
Grafana 3000) boştu, standart bırakıldı. Ayrıca `prometheus.yml` içindeki
`sentinel-api` hedefi de 8001'e çekildi — aksi halde Prometheus yanlışlıkla
**diğer projenin** API'sini kazıyacaktı (sessiz ve fark edilmesi zor bir hata).

**Öğrenilen ders:** Altyapıyı ayağa kaldırmadan **önce** `docker ps` ile
mevcut durumu incele. Ayrıca Docker'ın port çakışmasında yeni konteyneri
başlatmayı reddettiğini, çalışan konteynere zarar vermediğini bilmek
gereksiz endişeyi önler. İzolasyon garantileri: proje adı (`name: sentinel`),
açık konteyner adları (`sentinel-*`), ayrı ağ (`sentinel-net`) ve
ad-alanlı volume'lar (`sentinel_*`).

---
