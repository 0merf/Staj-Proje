/** WebSocket kanalı — analiz sonuçlarını dinler.
 *
 * ⚠ Gelen mesajlar React state'ine YAZILMIYOR. Saniyede ~60 mesaj
 * geliyor; her biri için render tetiklemek 20 kutucukta arayüzü
 * dizlerine düşürürdü. Mesajlar React dışındaki tampona yazılıyor
 * (`store.ts::buffers`), çizim döngüsü oradan okuyor.
 */
import { useEffect, useRef } from 'react'
import { pushResult, useStore } from '../store'
import type { FrameResult } from '../types'

export function useLiveResults() {
  const setConnection = useStore((s) => s.setConnection)
  const bump = useStore((s) => s.bumpMessages)
  const setAiLatency = useStore((s) => s.setAiLatency)
  const retry = useRef<number | null>(null)

  useEffect(() => {
    let socket: WebSocket | null = null
    let closed = false
    // Sayaç: her mesajda değil, saniyede bir React'e haber ver.
    let since = 0

    const connect = () => {
      if (closed) return
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
      socket = new WebSocket(`${proto}//${location.host}/ws/live`)

      socket.onopen = () => {
        setConnection('bağlı')
        socket?.send(JSON.stringify({ type: 'subscribe', cameras: [] }))
      }
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data) as FrameResult
        if (message.type !== 'frame') return
        // rx: tarayıcının KENDİ saati. Sunucunun ts'i monotoniktir,
        // Date.now() ile karşılaştırılamaz — hizalama bu yüzden
        // varış anına dayanıyor.
        pushResult({ ...message, rx: performance.now() })
        if (typeof message.lat === 'number') setAiLatency(message.lat)
        since++
      }
      socket.onclose = () => {
        setConnection('kopuk')
        if (!closed) retry.current = window.setTimeout(connect, 2000)
      }
      socket.onerror = () => socket?.close()
    }

    connect()
    const ticker = window.setInterval(() => {
      if (since > 0) {
        bump()
        since = 0
      }
    }, 1000)

    return () => {
      closed = true
      if (retry.current) clearTimeout(retry.current)
      clearInterval(ticker)
      socket?.close()
    }
  }, [setConnection, bump, setAiLatency])
}
