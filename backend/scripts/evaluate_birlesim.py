"""İSKELET + VİDEO BİRLEŞİMİ — "3 YZ birlikte çalışsın" fikrinin ölçümü (P-54).

⭐ FİKİR KİMİN
-------------
Kullanıcı baştan beri şunu söylüyordu:

> *"Bu adamların bana verdiği projede 3 farklı yapay zekânın koşmasını
> istemelerinin sebebi üçünün birlikte çalışmasını istemeleri; üçü de
> birlikte çalışsa daha iyi sonuç vermez mi?"*

İlk cevabım "füzyon zaten var" olmuştu ve eksikti: mevcut füzyon
**aynı özelliklerden** türeyen beş skoru topluyor. Birbirinden bağımsız
bilgi kaynakları değiller; P-41 bunu ölçmüştü (füzyonun K6 kazancının
%91'i yumuşatmadan geliyordu).

⭐⭐ ŞİMDİ GERÇEKTEN BAĞIMSIZ İKİ KAYNAK VAR ve ölçüm ikisinin
**zıt hatalar** yaptığını gösterdi (`train_video_model.py`, aynı
val kümesi — video RWF train'in tamamıyla eğitildi):

    yöntem                        AUC     F1   kesinlik  duyarlılık
    iskelet + LightGBM          0.927  0.889     0.957       0.830
    R3D-18 ham piksel           0.937  0.911     0.864       0.962

İskelet yolu TEMKİNLİ (yanlış alarm az, kaçırıyor); video yolu
AÇGÖZLÜ (neredeyse hiç kaçırmıyor, yanlış alarm çok). Bu tablo
birleştirme için ders kitabı örneği: hatalar bağımsızsa birleşim
ikisinden de iyi olur, bağımlıysa hiçbir şey kazandırmaz.

⚠ VE İKİSİ GERÇEKTEN FARKLI ŞEYE BAKIYOR
----------------------------------------
    iskelet yolu : YOLO-pose'un çıkardığı 17 eklem → geometri
                   (duruş genişliği, gövde eğimi, en-boy oranı)
                   ⚠ Poz bulunamazsa KÖRDÜR.
    video yolu   : ham piksellerde 3B evrişim → doku, hareket bulanıklığı,
                   sahne bağlamı
                   ⚠ Sahne değişince (yeni kamera) genellemesi zayıftır.

Birinin kör olduğu yerde diğeri görüyor olabilir. Bu betik onu ölçüyor.

⚠ NE ÖLÇÜLMÜYOR
---------------
Bu, "üçüncü YZ" (duygu/ifade) dâhil DEĞİL: ifade sinyali uzaktan
güvenilir değil (ölçüldü: füzyon ağırlığı 0.10-0.15) ve RWF kliplerinde
yüz çoğunlukla çözünmüyor. Dürüst kapsam: iki bağımsız kaynak.

⚠ MALİYET DE RAPORLANIYOR: birleşim, video modelini HER KAREDE
çalıştırmayı gerektirir. 20 kameralı gerçek zamanlı kısıt altında bu
bedava değil ve karar ancak maliyetle birlikte verilebilir.

Kullanım:
    uv run python scripts/evaluate_birlesim.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OZELLIKLER = PROJECT_ROOT / "data" / "_tmp" / "rwf_ozellikler.json"
TENSOR_DIZINI = PROJECT_ROOT / "data" / "_tmp" / "video_tensor"
LGBM_DOSYASI = PROJECT_ROOT / "backend" / "models" / "saldirganlik_lgbm.txt"
VIDEO_DOSYASI = PROJECT_ROOT / "backend" / "models" / "video_r3d18.pt"
BENCHMARKS = PROJECT_ROOT / "benchmarks"

KARE_SAYISI = 16
BOYUT = 112
KINETICS_ORT = (0.43216, 0.394666, 0.37645)
KINETICS_STD = (0.22803, 0.22145, 0.216989)
KAMERA_SAYISI = 20
CANLI_FPS = 2.75


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


def main() -> int:
    ap = argparse.ArgumentParser(description="İskelet + video birleşimi")
    ap.parse_args()

    for y in (OZELLIKLER, LGBM_DOSYASI, VIDEO_DOSYASI,
              TENSOR_DIZINI / "_ust.json"):
        if not y.exists():
            print(f"❌ Eksik: {y}", file=sys.stderr)
            return 1

    import lightgbm as lgb
    import numpy as np
    import torch
    from torch import nn
    from torchvision.models.video import r3d_18

    veri = json.loads(OZELLIKLER.read_text(encoding="utf-8"))
    ust = json.loads((TENSOR_DIZINI / "_ust.json").read_text(encoding="utf-8"))

    # ⚠ İKİ MODELİN VAL KÜMESİ AYNI OLMALI — yoksa kıyas geçersiz.
    # Eşleştirme anahtarla yapılıyor ("val_<klip adı>").
    lgbm_val = {f"val_{k['klip'][:-4] if str(k['klip']).endswith('.avi') else k['klip']}": k
                for k in veri["val"]}
    video_val = {k["klip"]: k for k in ust["val"]}
    ortak = sorted(set(lgbm_val) & set(video_val))
    if len(ortak) < len(video_val):
        print(f"⚠ {len(video_val) - len(ortak)} klip eşleşmedi, dışarıda")
    print(f"ortak val kümesi: {len(ortak)} klip\n")

    etiketler = [int(lgbm_val[a]["etiket"]) for a in ortak]

    # ─── İskelet + LightGBM ───
    booster = lgb.Booster(model_file=str(LGBM_DOSYASI))
    kayitlar = sorted(BENCHMARKS.glob("saldirganlik_model_*.json"))
    sutunlar = json.loads(kayitlar[-1].read_text(encoding="utf-8"))["ozellikler"]
    x = np.array([[lgbm_val[a].get(c, float("nan")) for c in sutunlar]
                  for a in ortak])
    s_iskelet = [float(v) for v in booster.predict(x)]

    # ─── Video ───
    cihaz = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = r3d_18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, 1)
    model.load_state_dict(torch.load(VIDEO_DOSYASI, map_location=cihaz))
    model = model.to(cihaz).eval()

    ort = torch.tensor(KINETICS_ORT).view(3, 1, 1, 1)
    std = torch.tensor(KINETICS_STD).view(3, 1, 1, 1)
    s_video: list[float] = []
    sureler: list[float] = []
    with torch.no_grad():
        for a in ortak:
            arr = np.load(TENSOR_DIZINI / f"{a}.npy")
            t = torch.from_numpy(arr).permute(3, 0, 1, 2).float() / 255.0
            t = ((t - ort) / std).unsqueeze(0).to(cihaz)
            if cihaz.type == "cuda":
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            with torch.autocast("cuda", enabled=cihaz.type == "cuda"):
                p = torch.sigmoid(model(t).squeeze())
            if cihaz.type == "cuda":
                torch.cuda.synchronize()
            sureler.append((time.perf_counter() - t0) * 1000.0)
            s_video.append(float(p))
    sureler = sureler[3:]  # ısınma

    # ─── Birleşimler ───
    # ⚠⚠ NORMALİZASYON YOK — VE BU BİLİNÇLİ.
    #
    # İlk sürüm skorları min-max ile ölçekliyordu. Ölçek val kümesinin
    # KENDİ min/max'ından hesaplanıyordu: yani birleşim, doğrulama
    # kümesinin dağılımını görmüş oluyordu. Küçük ama gerçek bir
    # sızıntı — ve tam olarak bu projede defalarca yakalanan türden
    # (P-41: karşılaştırma iki değişkeni birden değiştiriyordu).
    #
    # ⭐ Gerek de yoktu: LightGBM `predict` olasılık döndürüyor,
    # video başı `sigmoid` olasılık döndürüyor. İkisi de zaten [0,1]
    # ve aynı anlamda — "bu klip kavga olma olasılığı". Doğrudan
    # ortalanabilirler.
    ni, nv = s_iskelet, s_video
    birlesimler = {
        "iskelet (LightGBM)": s_iskelet,
        "video (R3D-18)": s_video,
        "ortalama": [(a + b) / 2 for a, b in zip(ni, nv, strict=True)],
        "azami (VEYA)": [max(a, b) for a, b in zip(ni, nv, strict=True)],
        "asgari (VE)": [min(a, b) for a, b in zip(ni, nv, strict=True)],
        "çarpım": [a * b for a, b in zip(ni, nv, strict=True)],
    }

    print("═══ BİRLEŞİM KARŞILAŞTIRMASI (aynı val kümesi) ═══")
    print(f"{'yöntem':<22} {'AUC':>7} {'F1':>7} {'kesinlik':>9} {'duyarlılık':>11}")
    sonuc: dict[str, Any] = {}
    for ad, s in birlesimler.items():
        auc = _auc(s, etiketler)
        d = _f1(s, etiketler)
        print(f"{ad:<22} {auc:>7.3f} {d['f1']:>7.3f} {d['kesinlik']:>9.3f} "
              f"{d['duyarlilik']:>11.3f}")
        sonuc[ad] = {"auc": round(auc, 4), **{k: round(v, 4) for k, v in d.items()}}

    # ─── Hata bağımsızlığı ───
    # ⭐ Birleşim ancak hatalar BAĞIMSIZSA kazandırır. Ölçülmeden
    # varsayılmaz (P-41'in dersi: füzyonun kazandığı sanılıyordu,
    # ölçülünce kazancın %91'i başka yerden geliyordu).
    e_i = _f1(s_iskelet, etiketler)["esik"]
    e_v = _f1(s_video, etiketler)["esik"]
    hata_i = [1 if (s >= e_i) != (y == 1) else 0
              for s, y in zip(s_iskelet, etiketler, strict=True)]
    hata_v = [1 if (s >= e_v) != (y == 1) else 0
              for s, y in zip(s_video, etiketler, strict=True)]
    ikisi = sum(1 for a, b in zip(hata_i, hata_v, strict=True) if a and b)
    yalniz_i = sum(1 for a, b in zip(hata_i, hata_v, strict=True) if a and not b)
    yalniz_v = sum(1 for a, b in zip(hata_i, hata_v, strict=True) if b and not a)
    print("\n═══ HATA BAĞIMSIZLIĞI ═══")
    print(f"  yalnızca iskelet yanıldı : {yalniz_i:>3}")
    print(f"  yalnızca video yanıldı   : {yalniz_v:>3}")
    print(f"  İKİSİ birden yanıldı     : {ikisi:>3}   ⬅ birleşimin kurtaramayacağı")
    print(f"  toplam hata (iskelet)    : {sum(hata_i):>3}")
    print(f"  toplam hata (video)      : {sum(hata_v):>3}")
    ortusme = ikisi / max(min(sum(hata_i), sum(hata_v)), 1)
    print(f"\n  hata örtüşmesi: %{ortusme * 100:.0f} "
          f"(düşük = bağımsız = birleşim kazandırır)")

    # ─── Maliyet ───
    ort_ms = sum(sureler) / len(sureler) if sureler else 0.0
    saniyede = KAMERA_SAYISI * CANLI_FPS
    print("\n═══ MALİYET ═══")
    print(f"  R3D-18 çıkarım: {ort_ms:.1f} ms / 16 karelik pencere")
    print(f"  20 kamera × {CANLI_FPS} FPS = {saniyede:.0f} pencere/sn gerekir")
    print(f"  → {ort_ms * saniyede:.0f} ms/saniye "
          f"= tek GPU'nun %{ort_ms * saniyede / 10:.0f}'i")
    gercek_zamanli = ort_ms * saniyede < 1000.0
    print(f"  {'✅ 20 kamerada yetişir' if gercek_zamanli else '❌ 20 kamerada YETİŞMEZ'}")

    BENCHMARKS.mkdir(exist_ok=True)
    damga = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    hedef = BENCHMARKS / f"birlesim_{damga}.json"
    hedef.write_text(json.dumps({
        "olculdu": datetime.now(UTC).isoformat(),
        "val_klip": len(ortak),
        "sonuclar": sonuc,
        "hata_bagimsizligi": {
            "yalniz_iskelet": yalniz_i, "yalniz_video": yalniz_v,
            "ikisi": ikisi, "ortusme": round(ortusme, 3),
        },
        "maliyet": {
            "r3d18_ms_pencere": round(ort_ms, 2),
            "yirmi_kamera_ms_sn": round(ort_ms * saniyede, 1),
            "gercek_zamanli": gercek_zamanli,
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
