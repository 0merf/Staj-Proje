/**
 * Overlay geometrisi testleri.
 *
 * ⚠⚠ BU DOSYA BİR DENETİM BULGUSUNUN CEVABI
 * Hakem denetimi §4.1: *"215 arka uç testine karşı 1 ön yüz test
 * dosyası. Canvas/overlay çizimi test edilmiyor — oysa P-14 ve P-26
 * tam oradan çıkmıştı."*
 *
 * Testler o iki hatayı ve akrabalarını hedefliyor:
 *   P-14 — iskelet kayması (koordinat uzayı)
 *   P-26 — kutuların kaynak çözünürlükle ölçeksiz çizilmesi
 *   P-39 — arka uçtaki aynı hata sınıfı (letterbox ⟷ kaynak uzayı)
 */

import { describe, expect, it } from 'vitest'

import {
  HAREKET_ESIGI,
  VARSAYILAN_KAYNAK,
  cizgiDeseni,
  hareketli,
  kutuEtiketi,
  kutuRengi,
  kutuyuOlcekle,
  olcek,
} from './overlay'

describe('olcek', () => {
  it('kaynak ve canvas ayni boyuttaysa olcek 1', () => {
    expect(olcek(1280, 720, 1280, 720)).toEqual({ sx: 1, sy: 1 })
  })

  it('⭐ FARKLI cozunurluklu kameralar dogru olcekleniyor (P-26)', () => {
    // 960×720 kaynak, 480×360 canvas → yatayda ve dikeyde 0.5
    expect(olcek(480, 360, 960, 720)).toEqual({ sx: 0.5, sy: 0.5 })
    // 900×720 kaynak — en-boy orani farkli, olcekler AYRI olmali
    const o = olcek(450, 360, 900, 720)
    expect(o.sx).toBeCloseTo(0.5)
    expect(o.sy).toBeCloseTo(0.5)
  })

  it('en-boy orani farkliysa sx ve sy AYRI hesaplaniyor', () => {
    // Tek bir olcek kullanmak P-26'nin ta kendisiydi.
    const o = olcek(640, 360, 1280, 720)
    expect(o.sx).toBeCloseTo(0.5)
    expect(o.sy).toBeCloseTo(0.5)
    const carpik = olcek(640, 720, 1280, 720)
    expect(carpik.sx).toBeCloseTo(0.5)
    expect(carpik.sy).toBeCloseTo(1.0)
    expect(carpik.sx).not.toBeCloseTo(carpik.sy)
  })

  it('⚠ kare boyutu YOKSA varsayilana dusuyor, Infinity uretmiyor', () => {
    const o = olcek(640, 360, undefined, undefined)
    expect(o.sx).toBeCloseTo(640 / VARSAYILAN_KAYNAK.w)
    expect(o.sy).toBeCloseTo(360 / VARSAYILAN_KAYNAK.h)
  })

  it('⚠ SIFIR kare boyutu Infinity uretmiyor', () => {
    const o = olcek(640, 360, 0, 0)
    expect(Number.isFinite(o.sx)).toBe(true)
    expect(Number.isFinite(o.sy)).toBe(true)
  })

  it('⚠ NaN kare boyutu varsayilana dusuyor', () => {
    const o = olcek(640, 360, Number.NaN, Number.NaN)
    expect(Number.isFinite(o.sx)).toBe(true)
    expect(o.sx).toBeCloseTo(640 / VARSAYILAN_KAYNAK.w)
  })
})

describe('kutuyuOlcekle', () => {
  it('kutu dogru konum ve boyutta olcekleniyor', () => {
    const k = kutuyuOlcekle([100, 200, 300, 500], { sx: 0.5, sy: 0.5 })
    expect(k).toEqual({ x: 50, y: 100, w: 100, h: 150 })
  })

  it('⭐ olcek 1 degilse KONUM da olcekleniyor, sadece boyut degil', () => {
    // P-26'nin sinsi hali: boyut olceklenip konum unutulursa kutular
    // dogru buyuklukte ama YANLIS YERDE cizilir.
    const k = kutuyuOlcekle([100, 100, 200, 200], { sx: 0.25, sy: 0.25 })
    expect(k.x).toBe(25)
    expect(k.y).toBe(25)
    expect(k.w).toBe(25)
    expect(k.h).toBe(25)
  })

  it('⚠ TERS kutu (x2<x1) normallestiriliyor, negatif genislik yok', () => {
    const k = kutuyuOlcekle([300, 500, 100, 200], { sx: 1, sy: 1 })
    expect(k.w).toBe(200)
    expect(k.h).toBe(300)
    expect(k.x).toBe(100)
    expect(k.y).toBe(200)
  })

  it('sifir boyutlu kutu cokmuyor', () => {
    const k = kutuyuOlcekle([10, 10, 10, 10], { sx: 2, sy: 2 })
    expect(k).toEqual({ x: 20, y: 20, w: 0, h: 0 })
  })

  it('⭐ farkli sx/sy kutuyu dogru sekilde carpitiyor', () => {
    const k = kutuyuOlcekle([0, 0, 100, 100], { sx: 0.5, sy: 1.0 })
    expect(k.w).toBe(50)
    expect(k.h).toBe(100)
  })
})

describe('hareketli', () => {
  it('esigin ustunde hareketli', () => {
    expect(hareketli([HAREKET_ESIGI + 1, 0])).toBe(true)
  })

  it('esigin altinda durgun', () => {
    expect(hareketli([HAREKET_ESIGI - 1, 0])).toBe(false)
  })

  it('esikte TAM degeri hareketli SAYMIYOR (kesin esitsizlik)', () => {
    expect(hareketli([HAREKET_ESIGI, 0])).toBe(false)
  })

  it('x ve y MUTLAK degerleri toplaniyor — ters yon iptal etmiyor', () => {
    // [-10, -10] → 20 > 15. Isaretli toplasaydik -20 olurdu ve
    // sola-yukari hizli giden kisi "durgun" gorunurdu.
    expect(hareketli([-10, -10])).toBe(true)
  })

  it('⚠ hiz YOKSA durgun (bilinmiyor ≠ hareketli)', () => {
    expect(hareketli(undefined)).toBe(false)
    expect(hareketli(null)).toBe(false)
    expect(hareketli([])).toBe(false)
    expect(hareketli([5])).toBe(false)
  })

  it('⚠ NaN/Infinity hiz hareketli SAYILMIYOR', () => {
    expect(hareketli([Number.NaN, 0])).toBe(false)
    expect(hareketli([Number.POSITIVE_INFINITY, 0])).toBe(false)
  })
})

describe('kutuEtiketi', () => {
  it('kimlik varsa etikette gosteriliyor', () => {
    expect(kutuEtiketi(7, 0.92)).toBe('#7 92%')
  })

  it('⚠ kimlik YOKSA yalnizca guven — kutu yine de cizilir (P-13)', () => {
    expect(kutuEtiketi(undefined, 0.5)).toBe('50%')
  })

  it('kimlik 0 gecerli bir kimlik, "yok" degil', () => {
    expect(kutuEtiketi(0, 0.8)).toBe('#0 80%')
  })

  it('guven yuvarlaniyor', () => {
    expect(kutuEtiketi(1, 0.876)).toBe('#1 88%')
  })
})

describe('kutuRengi ve cizgiDeseni', () => {
  it('onaysiz kutu gri ve KESIKLI', () => {
    expect(kutuRengi(false, true)).toBe('#8b98ad')
    expect(cizgiDeseni(false)).toEqual([5, 4])
  })

  it('onayli hareketli parlak, onayli durgun koyu', () => {
    expect(kutuRengi(true, true)).toBe('#3fb950')
    expect(kutuRengi(true, false)).toBe('#4d8f5c')
  })

  it('onayli kutu duz cizgi', () => {
    expect(cizgiDeseni(true)).toEqual([])
  })

  it('⚠ onaysizlik hareketten ONCE geliyor — gri, yesil degil', () => {
    // Onaylanmamis bir izin hizi guvenilmez; onu "hareketli yesil"
    // gostermek operatore olmayan bir kesinlik vaat ederdi.
    expect(kutuRengi(false, true)).not.toBe(kutuRengi(true, true))
  })
})
