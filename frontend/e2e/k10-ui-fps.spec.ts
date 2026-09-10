import { test } from '@playwright/test'
import { writeFileSync, mkdirSync } from 'node:fs'

/**
 * K10 — UI AKICILIĞI (hedef ≥30 FPS, 20 kutucuk açıkken)
 *
 * ⭐ NEDEN BU ÖLÇÜM ZOR VE NEDEN BÖYLE YAPILIYOR
 * ----------------------------------------------
 * PLAN §1.4 "20 kutucukta ≥30 FPS" diyor ama **hangi FPS** olduğunu
 * söylemiyor. Üç ayrı şey var ve karıştırmak ölçümü anlamsız kılar:
 *
 *   1. **Çizim (paint) hızı** — tarayıcı arayüzü saniyede kaç kez
 *      tazeliyor. `requestAnimationFrame` sayılarak ölçülür. Ekran
 *      60 Hz ise tavanı 60'tır.
 *   2. **Video çözme hızı** — 20 H.264 akışı saniyede kaç kare
 *      çözülüyor. `getVideoPlaybackQuality().totalVideoFrames` farkı.
 *   3. **Düşen kare** — çözülüp EKRANA BASILAMAYAN kareler.
 *      `droppedVideoFrames`. Asıl "akıcı mı" göstergesi bu.
 *
 * ⚠ Yalnızca (1)'e bakmak yanıltıcı olurdu: arayüz 60 FPS çizerken
 * videolar 5 FPS'te takılıyor olabilir ve kullanıcı "akmıyor" der.
 * Üçü birden raporlanıyor.
 *
 * ⚠ BEKLENEN SONUÇ KÖTÜ VE BU BİR KOD HATASI DEĞİL
 * Tarayıcı 20 H.264 akışını **CPU'da** çözüyor (P-24: panel açıkken
 * boru hattı verimi yarıya düşüyor). Bu bir donanım/tarayıcı sınırı.
 * Sonuç ne çıkarsa çıksın olduğu gibi raporlanacak.
 *
 * Kullanım:
 *   npx playwright test e2e/k10-ui-fps.spec.ts
 */

const KULLANICI = process.env.E2E_USER ?? 'e2e-test'
const PAROLA = process.env.E2E_PASSWORD ?? ''
const OLCUM_SN = 30
const ISINMA_SN = 10

interface Olcum {
  paintFps: number
  videoKareToplam: number
  videoKareDusen: number
  videoFpsToplam: number
  acikKamera: number
  gorunenKamera: number
}

test('K10 — 20 kutucuk açıkken UI akıcılığı', async ({ page }) => {
  test.setTimeout(300_000)

  await page.goto('/app')
  await page.locator('input[autocomplete="username"]').fill(KULLANICI)
  await page.locator('input[type="password"]').fill(PAROLA)
  await page.getByRole('button', { name: /giriş/i }).click()
  await page.getByTestId('kamera-izgarasi').waitFor()

  const hazirlar = page.locator('[data-testid="kamera-kutucugu"][data-hazir="1"]')
  for (let i = 0; i < 30 && (await hazirlar.count()) < 20; i++) {
    await page.waitForTimeout(1000)
  }

  // ─── ⭐ KONTROL SERİSİ: HİÇ kamera açmadan çizim hızı ───
  //
  // ⚠ BU OLMADAN ÖLÇÜM ANLAMSIZ. Başsız (headless) tarayıcı
  // `requestAnimationFrame` hızını sabitleyebiliyor. Yüklü durumda
  // "30.0 FPS" görmek, tarayıcının TAVANI 30 olduğu için de olabilir —
  // o zaman sayı bizim uygulamamız hakkında hiçbir şey söylemez.
  //
  // Kontrol tavanın nerede olduğunu söylüyor. P-41'in dersi: iki
  // değişkeni birden değiştiren bir kıyas, kıyas değildir.
  const kontrolFps: number = await page.evaluate(async () => {
    let sayac = 0
    let calisiyor = true
    const say = () => {
      sayac++
      if (calisiyor) requestAnimationFrame(say)
    }
    requestAnimationFrame(say)
    const t0 = performance.now()
    await new Promise((r) => setTimeout(r, 5000))
    calisiyor = false
    return sayac / ((performance.now() - t0) / 1000)
  })
  console.log(`\nKONTROL (0 kamera açık) çizim FPS: ${kontrolFps.toFixed(1)}`)

  // ─── TÜM kameraları aç ───
  const sayi = await hazirlar.count()
  for (let i = 0; i < sayi; i++) {
    await hazirlar.nth(i).getByRole('button', { name: 'izle', exact: true }).click()
    await page.waitForTimeout(250)
  }
  console.log(`\n${sayi} kamera açıldı · ısınma ${ISINMA_SN} sn`)
  await page.waitForTimeout(ISINMA_SN * 1000)

  // ─── Ölçüm ───
  const olcum: Olcum = await page.evaluate(async (sure) => {
    const videolar = Array.from(document.querySelectorAll('video'))
    const kalite = (v: HTMLVideoElement) =>
      typeof v.getVideoPlaybackQuality === 'function'
        ? v.getVideoPlaybackQuality()
        : { totalVideoFrames: 0, droppedVideoFrames: 0 }

    const ilk = videolar.map(kalite)
    let paintSayaci = 0
    let calisiyor = true
    const say = () => {
      paintSayaci++
      if (calisiyor) requestAnimationFrame(say)
    }
    requestAnimationFrame(say)

    const t0 = performance.now()
    await new Promise((r) => setTimeout(r, sure * 1000))
    calisiyor = false
    const gecen = (performance.now() - t0) / 1000

    const son = videolar.map(kalite)
    let toplam = 0
    let dusen = 0
    for (let i = 0; i < videolar.length; i++) {
      toplam += son[i].totalVideoFrames - ilk[i].totalVideoFrames
      dusen += son[i].droppedVideoFrames - ilk[i].droppedVideoFrames
    }
    return {
      paintFps: paintSayaci / gecen,
      videoKareToplam: toplam,
      videoKareDusen: dusen,
      videoFpsToplam: toplam / gecen,
      acikKamera: videolar.length,
      gorunenKamera: videolar.filter((v) => v.videoWidth > 0).length,
    }
  }, OLCUM_SN)

  const dusenOran = olcum.videoKareToplam
    ? olcum.videoKareDusen / olcum.videoKareToplam
    : 0
  const kameraBasi = olcum.gorunenKamera
    ? olcum.videoFpsToplam / olcum.gorunenKamera
    : 0

  console.log('\n═══ K10 — UI AKICILIĞI ═══')
  console.log(`  açık kamera            : ${olcum.acikKamera}`)
  console.log(`  görüntü gelen kamera   : ${olcum.gorunenKamera}`)
  console.log(`  çizim (paint) FPS      : ${olcum.paintFps.toFixed(1)}   ⬅ K10 ölçütü`)
  console.log(`  video kare (toplam/sn) : ${olcum.videoFpsToplam.toFixed(1)}`)
  console.log(`  video FPS / kamera     : ${kameraBasi.toFixed(1)}`)
  console.log(`  düşen kare             : ${olcum.videoKareDusen} / ${olcum.videoKareToplam}`
    + `  (%${(dusenOran * 100).toFixed(1)})`)
  console.log(`  KONTROL (0 kamera)     : ${kontrolFps.toFixed(1)} FPS`)
  const dusus = kontrolFps > 0 ? 1 - olcum.paintFps / kontrolFps : 0
  console.log(`  yükün getirdiği düşüş  : %${(dusus * 100).toFixed(1)}`)
  console.log(`\n  K10 (≥30 FPS çizim)    : ${olcum.paintFps >= 30 ? '✅ TUTUYOR' : '❌ TUTMUYOR'}`)
  if (Math.abs(kontrolFps - olcum.paintFps) < 1) {
    console.log('  ⚠ Kontrol ile yüklü ölçüm neredeyse AYNI → tarayıcı')
    console.log('    tavana dayanmış olabilir; çizim FPS bu ortamda')
    console.log('    ayırt edici DEĞİL. Video kare/düşen kare bakılmalı.')
  }

  mkdirSync('../benchmarks', { recursive: true })
  const damga = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  writeFileSync(
    `../benchmarks/k10_ui_fps_${damga}.json`,
    JSON.stringify(
      {
        olculdu: new Date().toISOString(),
        kriter: 'K10 — UI akıcılığı',
        hedef_fps: 30,
        olcum_sn: OLCUM_SN,
        isinma_sn: ISINMA_SN,
        ...olcum,
        kontrol_fps_kamerasiz: Number(kontrolFps.toFixed(2)),
        yukun_getirdigi_dusus: Number(dusus.toFixed(4)),
        video_fps_kamera_basina: Number(kameraBasi.toFixed(2)),
        dusen_kare_orani: Number(dusenOran.toFixed(4)),
        tutuyor: olcum.paintFps >= 30,
        yontem:
          'requestAnimationFrame sayımı (çizim) + getVideoPlaybackQuality ' +
          '(video kare/düşen). Üç büyüklük AYRI raporlanıyor.',
        not:
          'Tarayıcı 20 H.264 akışını CPU’da çözüyor; bu donanım/tarayıcı ' +
          'sınırıdır, kod hatası değil (P-24).',
      },
      null,
      2,
    ),
    'utf8',
  )
  console.log(`\nyazıldı: benchmarks/k10_ui_fps_${damga}.json`)
})
