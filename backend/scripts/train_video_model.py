"""VIDEO MODELİ — literatürün yolunu kendi verimizde ölçer (P-54).

⭐ NEDEN BU BETİK — kullanıcının sorusu
--------------------------------------
> *"Bu LightGBM'i neden kullanıyoruz onu hâlâ tam anlamadım. LightGBM
> tablosal verilerde iyi değil mi? Buradaki veriler görüntü verileri
> değil mi, yani diziler/matrisler/tensörler hâlinde gelmiyor mu?"*

Soru yerinde ve cevabı mimarinin tamamını açıklıyor.

BİZİM BORU HATTIMIZ GÖRÜNTÜYÜ LightGBM'e VERMİYOR
-------------------------------------------------
Görüntüyü işleyen şey zaten derin sinir ağları:

    kare (H×W×3 tensör)
      → YOLO26-s        (CNN)  → kişi kutuları
      → YOLO26-pose     (CNN)  → 17 eklem koordinatı
      → BoT-SORT               → kimlik + zaman serisi
      → özellik çıkarımı       → bilek hızı, duruş genişliği,
                                  gövde eğimi, en-boy oranı, çift
                                  mesafesi… (SKALER, ~99 sütun)
      → LightGBM               → karar

Yani görüntü → tablo dönüşümünü **CNN'ler** yapıyor; LightGBM yalnızca
o tablonun üzerinde karar veriyor. Bu, iskelet tabanlı eylem tanımanın
standart kurgusu ve LightGBM tam da doğru yerde: girdisi gerçekten
tablosal.

⚠ AMA SORUNUN ASIL KISMI HAKLI
------------------------------
Literatürdeki RWF-2000 çalışmalarının çoğu bu yolu izlemiyor: **ham
piksellere doğrudan 3B evrişim** uyguluyorlar (Flow-Gated Network,
two-stream CNN, IDG-ViolenceNet…). Biz o yolu hiç denemedik, yalnızca
onların yayınlanmış sayılarını yazdık.

⭐ Kendi ölçmediğimiz bir sayıyla kıyaslanmak, bu projede defalarca
yanlış çıkan türden bir kıyas (P-17, P-41, P-51). Bu betik o boşluğu
kapatıyor: literatürün yolunu **bizim verimizde, bizim bölünmemizde,
bizim donanımımızda** koşturuyor.

ADİL KARŞILAŞTIRMA KOŞULLARI
----------------------------
1. **AYNI KLİPLER, AYNI BÖLÜNME.** Klip listeleri
   `data/_tmp/rwf_ozellikler.json` içindeki train/val'den okunuyor.
   Farklı bölünme kullanmak, iki modeli iki farklı sınavda ölçmek olurdu.
2. **AYNI DOĞRULAMA KÜMESİ.** Eşik val'de aranıyor — LightGBM'de de
   öyle yapılmıştı; bilinen yanlılık ama İKİ TARAFTA DA aynı.
3. Kinetics-400 ön eğitimli ağırlıklar. Sıfırdan eğitmek 482 klipte
   anlamsız olurdu ve literatürdeki çalışmalar da ön eğitim kullanıyor.

⚠ BEKLENEN SINIRLAMA — ve bu bir bulgu
--------------------------------------
482 eğitim klibi, 33 milyon parametreli bir 3B CNN için **az**.
Literatürdeki sayılar 1600 klip üzerinde eğitilmiş. Bu yüzden betik
iki koşu yapabiliyor:

    --tam-egitim yok  : 482 klip (LightGBM ile AYNI) → adil kıyas
    --tam-egitim      : RWF train'in tamamı (~1600) → videoya en iyi şans

İkisini de raporlamak gerekiyor: birincisi "aynı veriyle hangi yöntem
iyi", ikincisi "yöntemin tavanı ne".

Kullanım:
    uv run python scripts/train_video_model.py --cikar   # kare tensörü
    uv run python scripts/train_video_model.py --egit
    uv run python scripts/train_video_model.py --cikar --egit --tam-egitim
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RWF = PROJECT_ROOT / "data" / "datasets" / "RWF-2000"
OZELLIKLER = PROJECT_ROOT / "data" / "_tmp" / "rwf_ozellikler.json"
TENSOR_DIZINI = PROJECT_ROOT / "data" / "_tmp" / "video_tensor"
BENCHMARKS = PROJECT_ROOT / "benchmarks"
MODEL_DOSYASI = PROJECT_ROOT / "models" / "video_r3d18.pt"

# Kinetics ön işleme — ön eğitimli ağırlıkların beklediği hâl.
# ⚠ Değiştirilirse ön eğitim boşa gider: ağ başka bir dağılım görür.
KARE_SAYISI = 16
BOYUT = 112
KINETICS_ORT = (0.43216, 0.394666, 0.37645)
KINETICS_STD = (0.22803, 0.22145, 0.216989)


def _klip_tensoru(yol: Path) -> Any | None:
    """Bir klipten `KARE_SAYISI` kareyi eşit aralıkla alır (uint8)."""
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(yol))
    if not cap.isOpened():
        return None
    kareler = []
    while True:
        ok, k = cap.read()
        if not ok:
            break
        # 128×171'e küçült, ortadan 112×112 kırp — Kinetics kuralı.
        k = cv2.resize(k, (171, 128))
        y0 = (128 - BOYUT) // 2
        x0 = (171 - BOYUT) // 2
        kareler.append(k[y0:y0 + BOYUT, x0:x0 + BOYUT, ::-1])  # BGR→RGB
    cap.release()
    if len(kareler) < 4:
        return None
    # ⚠ EŞİT ARALIKLI ÖRNEKLEME, ilk N kare DEĞİL: kavga klibin
    # herhangi bir yerinde olabilir ve baştan almak sonu hiç görmez.
    idx = np.linspace(0, len(kareler) - 1, KARE_SAYISI).round().astype(int)
    return np.stack([kareler[i] for i in idx])  # (T, H, W, C) uint8


def _klip_yolu(ad: str, bolum: str) -> Path | None:
    """Klip yolu — BÖLÜM ZORUNLU.

    ⚠⚠ RWF-2000'de val'deki 400 klibin **hepsi** train'de de AYNI ADLA
    var: `train/fight/fight_0001.avi` ve `val/fight/fight_0001.avi`
    ikisi de mevcut ve **farklı videolar** (md5 ve dosya boyutu farklı
    — doğrulandı).

    Yani ada bakarak dosya bulmak, sessizce YANLIŞ bölümden video
    okumaya yol açar: doğrulama kümesi eğitim videolarıyla dolar ve
    sonuç şişer. Hata görünmez — betik çalışır, sayı üretir, yalnızca
    yanlış olur.

    ⚠ `train_aggression.py` bu tuzağa DÜŞMEDİ: o, dizinleri gezerek
    okuyor (`(RWF / bolum / sinif).glob(...)`). Yalnızca sonucu ada
    göre saklıyor. O yüzden LightGBM ölçümlerinde sızıntı yok —
    kontrol edildi.
    """
    kok = ad[:-4] if ad.endswith(".avi") else ad
    for sinif in ("fight", "nonfight"):
        y = RWF / bolum / sinif / f"{kok}.avi"
        if y.is_file():
            return y
    return None


def _cikar(args: argparse.Namespace) -> int:
    import numpy as np

    if not OZELLIKLER.is_file():
        print(f"❌ {OZELLIKLER} yok — önce train_aggression.py --cikar",
              file=sys.stderr)
        return 1
    veri = json.loads(OZELLIKLER.read_text(encoding="utf-8"))

    istenen: list[tuple[str, int, str]] = []
    for bolum in ("train", "val"):
        for k in veri[bolum]:
            istenen.append((str(k["klip"]), int(k["etiket"]), bolum))

    if args.tam_egitim:
        # ⚠ Val kümesi DEĞİŞMİYOR — yalnızca eğitim büyüyor. Val'i de
        # büyütmek iki koşuyu farklı sınavda ölçmek olurdu.
        # ⚠ Val kümesine DOKUNULMUYOR; yalnızca train büyüyor.
        # Ad çakışması burada tehlikeli değil çünkü bölüm sabit ("train").
        mevcut = {a for a, _e, b in istenen if b == "train"}
        for sinif, etiket in (("fight", 1), ("nonfight", 0)):
            for y in sorted((RWF / "train" / sinif).glob("*.avi")):
                if y.name not in mevcut:
                    istenen.append((y.name, etiket, "train"))
        print(f"⚠ --tam-egitim: eğitim kümesi {len(istenen)} klibe çıkarıldı")

    TENSOR_DIZINI.mkdir(parents=True, exist_ok=True)
    ust: dict[str, Any] = {"train": [], "val": []}
    t0 = time.time()
    atlanan = 0
    for i, (ad, etiket, bolum) in enumerate(istenen, 1):
        # ⚠ Dosya adı bölümü İÇERMELİ — train/val'de aynı adlar var.
        kok = ad[:-4] if ad.endswith(".avi") else ad
        anahtar = f"{bolum}_{kok}"
        hedef = TENSOR_DIZINI / f"{anahtar}.npy"
        if not hedef.is_file():
            yol = _klip_yolu(ad, bolum)
            if yol is None:
                atlanan += 1
                continue
            tensor = _klip_tensoru(yol)
            if tensor is None:
                atlanan += 1
                continue
            np.save(hedef, tensor)
        ust[bolum].append({"klip": anahtar, "etiket": etiket})
        if i % 100 == 0:
            print(f"  {i}/{len(istenen)} · {time.time() - t0:.0f} sn")

    (TENSOR_DIZINI / "_ust.json").write_text(
        json.dumps(ust, ensure_ascii=False), encoding="utf-8")
    print(f"\ntrain {len(ust['train'])} · val {len(ust['val'])} klip "
          f"· atlanan {atlanan} · {time.time() - t0:.0f} sn")
    print(f"yazıldı: {TENSOR_DIZINI.relative_to(PROJECT_ROOT)}")
    return 0


def _auc(skorlar: list[float], etiketler: list[int]) -> float:
    ciftler = sorted(zip(skorlar, etiketler, strict=True))
    n_poz = sum(etiketler)
    n_neg = len(etiketler) - n_poz
    if not n_poz or not n_neg:
        return 0.5
    siralar = [0.0] * len(ciftler)
    i = 0
    while i < len(ciftler):
        j = i
        while j + 1 < len(ciftler) and ciftler[j + 1][0] == ciftler[i][0]:
            j += 1
        for k in range(i, j + 1):
            siralar[k] = (i + j) / 2.0 + 1.0
        i = j + 1
    poz = sum(s for s, (_v, e) in zip(siralar, ciftler, strict=True) if e == 1)
    return (poz - n_poz * (n_poz + 1) / 2) / (n_poz * n_neg)


def _f1(skorlar: list[float], etiketler: list[int]) -> dict[str, float]:
    en_iyi = {"f1": 0.0, "esik": 0.5, "kesinlik": 0.0, "duyarlilik": 0.0}
    for i in range(101):
        e = i / 100
        tp = sum(1 for s, y in zip(skorlar, etiketler, strict=True) if s >= e and y == 1)
        fp = sum(1 for s, y in zip(skorlar, etiketler, strict=True) if s >= e and y == 0)
        fn = sum(1 for s, y in zip(skorlar, etiketler, strict=True) if s < e and y == 1)
        if not tp:
            continue
        p, r = tp / (tp + fp), tp / (tp + fn)
        f = 2 * p * r / (p + r)
        if f > en_iyi["f1"]:
            en_iyi = {"f1": f, "esik": e, "kesinlik": p, "duyarlilik": r}
    return en_iyi


def _egit(args: argparse.Namespace) -> int:
    import numpy as np
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, Dataset
    from torchvision.models.video import R3D_18_Weights, r3d_18

    ust_yol = TENSOR_DIZINI / "_ust.json"
    if not ust_yol.is_file():
        print("❌ Tensörler yok — önce --cikar", file=sys.stderr)
        return 1
    ust = json.loads(ust_yol.read_text(encoding="utf-8"))

    ort = torch.tensor(KINETICS_ORT).view(3, 1, 1, 1)
    std = torch.tensor(KINETICS_STD).view(3, 1, 1, 1)

    class Klipler(Dataset):
        def __init__(self, kayitlar: list[dict[str, Any]], *, egitim: bool):
            self.k = kayitlar
            self.egitim = egitim

        def __len__(self) -> int:
            return len(self.k)

        def __getitem__(self, i: int):
            kayit = self.k[i]
            x = np.load(TENSOR_DIZINI / f"{kayit['klip']}.npy")  # (T,H,W,C)
            t = torch.from_numpy(x.copy()).permute(3, 0, 1, 2).float() / 255.0
            if self.egitim and random.random() < 0.5:  # noqa: S311
                # ⚠ TEK ARTIRMA: yatay çevirme. Kavga aynaya göre
                # simetrik bir olay; renk/kırpma artırmaları ise
                # Kinetics ön işlemesini bozar.
                t = torch.flip(t, dims=[3])
            t = (t - ort) / std
            return t, float(kayit["etiket"])

    cihaz = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tr = DataLoader(Klipler(ust["train"], egitim=True), batch_size=args.parti,
                    shuffle=True, num_workers=0, drop_last=True)
    va = DataLoader(Klipler(ust["val"], egitim=False), batch_size=args.parti,
                    shuffle=False, num_workers=0)

    model = r3d_18(weights=R3D_18_Weights.KINETICS400_V1)
    model.fc = nn.Linear(model.fc.in_features, 1)
    model = model.to(cihaz)

    # ⚠ Küçük veri + büyük ağ → düşük öğrenme oranı ve ağırlık sönümü.
    # Gövdeye baştan tam öğrenme oranı vermek ön eğitimi siler.
    opt = torch.optim.AdamW([
        {"params": [p for n, p in model.named_parameters()
                    if not n.startswith("fc")], "lr": args.lr * 0.1},
        {"params": model.fc.parameters(), "lr": args.lr},
    ], weight_decay=1e-4)
    plan = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.devir)
    kayip_f = nn.BCEWithLogitsLoss()
    olcek = torch.amp.GradScaler("cuda", enabled=cihaz.type == "cuda")

    print(f"cihaz {cihaz} · train {len(ust['train'])} · val {len(ust['val'])} "
          f"· parti {args.parti} · {args.devir} devir\n")
    print(f"{'devir':>6} {'kayıp':>9} {'val AUC':>9} {'val F1':>8} {'sn':>6}")

    en_iyi: dict[str, Any] = {"auc": 0.0}
    gecmis: list[dict[str, float]] = []
    for devir in range(1, args.devir + 1):
        t0 = time.time()
        model.train()
        toplam = 0.0
        for x, y in tr:
            x, y = x.to(cihaz, non_blocking=True), y.to(cihaz).float()
            opt.zero_grad(set_to_none=True)
            with torch.autocast("cuda", enabled=cihaz.type == "cuda"):
                cikti = model(x).squeeze(1)
                kayip = kayip_f(cikti, y)
            olcek.scale(kayip).backward()
            olcek.step(opt)
            olcek.update()
            toplam += float(kayip) * x.size(0)
        plan.step()

        model.eval()
        skorlar, etiketler = [], []
        with torch.no_grad():
            for x, y in va:
                x = x.to(cihaz)
                with torch.autocast("cuda", enabled=cihaz.type == "cuda"):
                    p = torch.sigmoid(model(x).squeeze(1))
                skorlar += [float(v) for v in p.float().cpu()]
                etiketler += [int(v) for v in y]
        auc = _auc(skorlar, etiketler)
        d = _f1(skorlar, etiketler)
        sure = time.time() - t0
        print(f"{devir:>6} {toplam / max(len(ust['train']), 1):>9.4f} "
              f"{auc:>9.3f} {d['f1']:>8.3f} {sure:>6.0f}")
        gecmis.append({"devir": devir, "auc": round(auc, 4),
                       "f1": round(d["f1"], 4)})
        if auc > en_iyi["auc"]:
            en_iyi = {"auc": auc, "devir": devir, **d,
                      "skorlar": skorlar, "etiketler": etiketler}
            MODEL_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), MODEL_DOSYASI)

    # ─── Karşılaştırma ───
    kayitlar = sorted(BENCHMARKS.glob("saldirganlik_model_*.json"))
    lgbm = json.loads(kayitlar[-1].read_text(encoding="utf-8"))["model"]

    print("\n═══ KARŞILAŞTIRMA (aynı val kümesi) ═══")
    print(f"{'yöntem':<34} {'AUC':>7} {'F1':>7} {'kesinlik':>9} {'duyarlılık':>11}")
    print(f"{'kural tabanı (elle)':<34} {0.629:>7.3f} {0.712:>7.3f} "
          f"{0.612:>9.3f} {0.867:>11.3f}")
    print(f"{'iskelet + LightGBM (bizim)':<34} {lgbm['auc']:>7.3f} "
          f"{lgbm['f1']:>7.3f} {lgbm['kesinlik']:>9.3f} {lgbm['duyarlilik']:>11.3f}")
    print(f"{'R3D-18 (en iyi devir, val-seçili)':<34} {en_iyi['auc']:>7.3f} "
          f"{en_iyi['f1']:>7.3f} {en_iyi['kesinlik']:>9.3f} "
          f"{en_iyi['duyarlilik']:>11.3f}")
    son = gecmis[-1]
    print(f"{'R3D-18 (SON devir, seçimsiz)':<34} {son['auc']:>7.3f} "
          f"{son['f1']:>7.3f} {'—':>9} {'—':>11}")
    # ⚠⚠ İKİ SATIR DA BASILIYOR VE SEBEBİ ÖNEMLİ.
    #
    # "En iyi devir"i doğrulama kümesindeki AUC'ye bakarak seçmek,
    # RAPORLADIĞIMIZ kümede seçim yapmaktır — 12 devrin maksimumunu
    # almak tek bir eşik seçmekten daha güçlü bir yanlılık.
    #
    # LightGBM tarafında da benzeri var (eşik val'de aranıyor) ama
    # derecesi farklı. Dürüst kıyas için ikisi de yazılıyor:
    # seçimsiz son devir, yanlılığın ALT sınırını verir.
    print("\n⚠ 'En iyi devir' val'de seçildi — raporlanan kümede seçim")
    print("  yapmak yanlılıktır. Seçimsiz son devir alt sınır olarak")
    print("  yukarıda; gerçek başarım ikisinin arasında.")

    print("\n⚠ Literatürün RWF-2000 sayıları (KENDİ bölünmelerinde, bizim")
    print("  ölçmediğimiz — yalnızca bağlam için):")
    print("   Flow-Gated Network 0.8725 · two-stream multidim CNN 0.870")
    print("   IDG-ViolenceNet 0.894 · semi-supervised hard attention 0.895")

    BENCHMARKS.mkdir(exist_ok=True)
    damga = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    hedef = BENCHMARKS / f"video_model_{damga}.json"
    hedef.write_text(json.dumps({
        "olculdu": datetime.now(UTC).isoformat(),
        "mimari": "r3d_18 (Kinetics-400 ön eğitimli)",
        "girdi": f"{KARE_SAYISI} kare × {BOYUT}×{BOYUT}",
        "tam_egitim": bool(args.tam_egitim),
        "train_klip": len(ust["train"]), "val_klip": len(ust["val"]),
        "devir": args.devir, "lr": args.lr, "parti": args.parti,
        "gecmis": gecmis,
        "en_iyi": {k: v for k, v in en_iyi.items()
                   if k not in ("skorlar", "etiketler")},
        "son_devir": gecmis[-1],
        "secim_yanliligi_notu": (
            "en_iyi devir val AUC'sine göre seçildi = raporlanan kümede "
            "seçim. son_devir seçimsizdir ve yanlılığın alt sınırını verir."
        ),
        "karsilastirma": {
            "kural_tabani": {"auc": 0.629, "f1": 0.712},
            "iskelet_lightgbm": lgbm,
            "video_r3d18": {k: v for k, v in en_iyi.items()
                            if k not in ("skorlar", "etiketler")},
        },
        "adil_kiyas_notu": (
            "Aynı klipler, aynı val kümesi. Eşik her iki yöntemde de "
            "val'de arandı — bilinen yanlılık, İKİ TARAFTA DA aynı."
        ),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Video modeli (literatür yolu)")
    ap.add_argument("--cikar", action="store_true", help="kare tensörü çıkar")
    ap.add_argument("--egit", action="store_true", help="modeli eğit")
    ap.add_argument("--tam-egitim", action="store_true",
                    help="RWF train'in tamamını kullan (val aynı kalır)")
    ap.add_argument("--devir", type=int, default=12)
    ap.add_argument("--parti", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()
    if not args.cikar and not args.egit:
        ap.error("--cikar ya da --egit verin")
    if args.cikar and (kod := _cikar(args)):
        return kod
    if args.egit:
        return _egit(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
