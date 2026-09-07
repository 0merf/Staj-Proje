# UBI-Fights — kaynak ve lisans

**İndirme:** http://socia-lab.di.ubi.pt/EventDetection/
**Atıf:** Degardin, B. & Proença, H., *"Human activity analysis:
Iterative weak/self-supervised learning frameworks for detecting
abnormal events"*, IJCB 2020.

**Lisans:** Akademik kullanım. **Yeniden dağıtım hakkı yok** — bu
yüzden ne videolar ne de `annotation/` altındaki etiket CSV'leri
git'e giriyor (`.gitignore`).

## Neden bu veri seti kullanıldı

RWF-2000 klipleri olayın etrafından **kırpılmış**: kavga başlangıcı
medyan 0.58 saniyede. Erken uyarı (K8) o veri setinde **tanımsız** —
sistem 3 saniyelik özellik penceresini dolduramadan olay bitiyor.

UBI-Fights **kesilmemiş** gözetim videoları veriyor: olay öncesi
bağlam var, dolayısıyla "kaç saniye önce" sorusu sorulabiliyor.

## ⚠ Bu veri setiyle ilgili ÖLÇÜLEN sınırlar

Bkz. `docs/report/problems.md` · P-50 ve P-51.

1. **Etiketler olayın BAŞLANGICINI vermiyor.** Veri seti "şiddet
   pencereleri" işaretliyor. `F_74_1_2_0_0`'da ilk etiket 57.97 sn,
   fiziksel çatışma ~32.8 sn'de başlıyor — **25 saniye sapma**.
   Erken uyarı ölçümü bu farkı doğrudan avans sanır.
2. **Videoların çoğu elde çekim.** 60 aday taranınca 45'i sabit
   çıktı ama `F_74` kayma medyanı %0.197 (p90 %1.023) — boru
   hattımızın sabit kamera varsayımının dışında.
3. **Bazı videolar çok kameradan kurgulanmış.** `F_0_1_0_0_0`
   ortasında hastane koridorundan otoparka kesiyor.
4. **Bazıları kurgu/eğitim videosu.** `F_202_0_0_0_0` üzerinde
   "Active Self Protection" filigranı var.

Seçim aracı: `backend/scripts/bul_sabit_kamera.py`
Kullanılan video: **`F_45_0_0_0_0`** (gerçek CCTV, sabit, tek sahne).
Yer gerçeği: `data/annotations/cam-15.gorsel.json` (elle görsel doğrulama).
