/** Alarm kanıtının ekranda gösterimi: alan adları ve sayı biçimi.
 *
 * Alarm paneli, kamera detayı ve zaman çizelgesi aynı kanıtı gösteriyor;
 * üçü de bu dosyayı kullanıyor ki aynı alan her yerde aynı adla ve aynı
 * biçimde görünsün. */

/** Kanıt alanlarının okunabilir adları ve birimleri.
 *
 * Birim zorunlu — ilk sürümde yoktu ve kafa karıştırdı.
 * "kişi 7 normal 2.1 eşik 5.24" satırını ilk bakışta "kişilerin numarası
 * mı?" diye okudum. Birimsiz bir sayı, okuyanın onu ne sandığına bağlı
 * olarak anlam kazanıyor.
 *
 * Ham anahtarları (`govde_egimi_derece`) ekrana basmak da bir şey
 * anlatmaz; panel ve rapor aynı dili konuşmalı. */
export const KANIT_TR: Record<string, [etiket: string, birim: string]> = {
  en_boy_orani: ['en/boy oranı', ''],
  govde_egimi_derece: ['gövde eğimi', '°'],
  egim_degisim_hizi: ['eğim değişimi', '°/sn'],
  govde_hizi_govde_sn: ['hız', ' gövde/sn'],
  olculen_p99: ['ölçülen p99', ' gövde/sn'],
  oyalanma_saniye: ['aynı yerde', ' sn'],
  // Bu bölgede normalde duran kişilerin oranı. Yüksekse (örneğin bir
  // bekleme alanı) oyalanma olağan sayılıyor.
  bolgede_duranlarin_orani: ['bu bölgede duranların oranı', ''],
  kisi: ['kişi sayısı', ''],
  taban: ['bu kameranın normali', ' kişi'],
  esik: ['eşik', ''],
  // Alarmın kaynak videodaki konumu (P-68): alarmı videoda bulup elle
  // doğrulamak için.
  video_pts: ['video konumu', ' sn'],

  // ─── Katman A kanıtları (anomaly/normalcy.py) ───
  // Bunlar kuraldan değil öğrenilen profilden geliyor; etiketleri de
  // "eşik aşıldı" değil "bu kameranın normaline uymuyor" dilinde.
  nadir_bolge: ['buraya nadiren gidilir', ''],
  bolge_ziyaret: ['bu bölgede toplam gözlem', ' kez'],
  hiz_sapmasi_sigma: ['bölge normalinden sapma', 'σ'],
  bolge_normal_hiz: ['bu bölgenin normal hızı', ' gövde/sn'],
  yon_orani: ['bu yöne gidenlerin oranı', ''],
  kisi_sapmasi_sigma: ['kişi sayısı sapması', 'σ'],
  kamera_normal_kisi: ['bu kameranın normali', ' kişi'],

  // ─── Saldırganlık kanıtları (analytics/aggression.py) ───
  //
  // Bunlar 26.08.2026'ya kadar çevrilmemişti: panelde ham anahtar
  // adları (`b_yakinlik`, `b_bilek`) görünüyordu. Modülün en önemli
  // özelliği açıklanabilir olması — "skor 0.72 çünkü şu, şu, şu" —
  // ama operatör okuyamıyorsa açıklanabilirlik kâğıt üstünde kalır.
  //
  // `b_` öneki "bileşen" demek: her biri 0-1 arası, ağırlıklı toplama
  // giriyor. Etiketler ağırlık sırasına göre yazıldı.
  tirmanma_skoru: ['tırmanma skoru', ''],
  // Eğim, projenin özgün katkısının ta kendisi: yüksek ama sabit
  // skor süregelen bir durumdur, yükselen skor tırmanmadır.
  tirmanma_egimi: ['skorun yükselme hızı', '/sn'],
  b_yakinlik: ['yakınlık + karşılıklı duruş', ''],
  b_bilek: ['bilek hızı ve sarsıntısı', ''],
  b_yaklasma: ['birbirine yaklaşma', ''],
  b_enerji: ['hareket enerjisi', ''],
  b_durus: ['duruş (kol, eğim, açıklık)', ''],
  // Çarpımsal kapı: yalnız bir kişinin hızlı hareketi saldırganlık
  // değildir. Sıfırsa skor da bastırılıyor.
  b_etkilesim: ['etkileşim kapısı', ''],

  // ─── Füzyon kanıtları (analytics/fusion.py) ───
  //
  // `katkida_bulunan_sinyal` süs değil, güven ölçüsü.
  // Tek sinyalli bir 0.4 ile üç sinyalli bir 0.4 aynı şey değil:
  // ikincisi çok daha ikna edici. Füzyon alarmı zaten iki sinyalin
  // altında hiç yayınlanmıyor, ama operatör kaç sinyalin birleştiğini
  // görmeli.
  risk_skoru: ['birleşik risk', ''],
  katkida_bulunan_sinyal: ['birleşen sinyal sayısı', ' adet'],
  s_saldirganlik: ['· saldırganlık', ''],
  s_anomali: ['· kamera normalinden sapma', ''],
  s_kural: ['· kural ihlali', ''],
  s_ifade: ['· yüz ifadesi', ''],
  s_kalabalik: ['· kalabalık', ''],
}

/** Kanıt alanının ekrandaki adı ve birimi; bilinmeyen alan ham adıyla. */
export function kanitEtiketi(anahtar: string): [etiket: string, birim: string] {
  return KANIT_TR[anahtar] ?? [anahtar, '']
}

/** Kanıt değerini okunur biçime çevirir.
 *
 * Modelden gelen skorlar 0.17876635710916314 gibi tam duyarlıkla
 * geliyor ve ilk sürüm bunları olduğu gibi basıyordu. Operatör için
 * 0.179 ile 0.17876… arasında fark yok; satırı okunmaz yapıyordu.
 *
 * Tam sayılar olduğu gibi kalıyor (kişi sayısı, sinyal sayısı). Küçük
 * değerler en fazla 3 ondalıkla, 100 ve üstü tek ondalıkla gösteriliyor
 * (video konumu 104.539 sn → 104.5 sn). Sondaki sıfırlar atılıyor. */
export function kanitDegeri(deger: unknown): string {
  if (typeof deger !== 'number' || !Number.isFinite(deger)) return String(deger)
  if (Number.isInteger(deger)) return String(deger)
  const basamak = Math.abs(deger) >= 100 ? 1 : 3
  return String(Number(deger.toFixed(basamak)))
}
