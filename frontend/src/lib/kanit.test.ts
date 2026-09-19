/** Alarm kanıtının ekrandaki biçimi. */
import { describe, expect, it } from 'vitest'
import { kanitDegeri, kanitEtiketi } from './kanit'

describe('kanitDegeri', () => {
  it('uzun ondalıkları 3 basamağa indiriyor', () => {
    expect(kanitDegeri(0.17876635710916314)).toBe('0.179')
    expect(kanitDegeri(0.8736640115889265)).toBe('0.874')
  })

  it('tam sayıları olduğu gibi bırakıyor', () => {
    expect(kanitDegeri(0)).toBe('0')
    expect(kanitDegeri(12)).toBe('12')
  })

  it('sondaki sıfırları atıyor', () => {
    expect(kanitDegeri(1.5)).toBe('1.5')
    expect(kanitDegeri(0.1)).toBe('0.1')
  })

  it('100 ve üstünü tek ondalıkla gösteriyor', () => {
    expect(kanitDegeri(104.539)).toBe('104.5')
    expect(kanitDegeri(127.33)).toBe('127.3')
  })

  it('negatif değerleri de kısaltıyor', () => {
    expect(kanitDegeri(-0.0971234)).toBe('-0.097')
  })

  it('sayı olmayan değeri metin olarak bırakıyor', () => {
    expect(kanitDegeri('yok')).toBe('yok')
    expect(kanitDegeri(Number.NaN)).toBe('NaN')
  })
})

describe('kanitEtiketi', () => {
  it('bilinen alanı Türkçe ad ve birimle veriyor', () => {
    expect(kanitEtiketi('video_pts')).toEqual(['video konumu', ' sn'])
    expect(kanitEtiketi('b_bilek')).toEqual(['bilek hızı ve sarsıntısı', ''])
  })

  it('bilinmeyen alanı ham adıyla bırakıyor', () => {
    expect(kanitEtiketi('yeni_alan')).toEqual(['yeni_alan', ''])
  })
})
