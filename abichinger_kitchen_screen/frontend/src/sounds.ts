import { useState } from './state'

export interface Sound {
  id: string
  url: string | null
}

let sounds: Sound[] = []
export function getSounds(): Sound[] {
  if (sounds.length == 0) {
    sounds = [
      {
        id: 'none',
        url: null,
      },
      {
        id: 'alert',
        url: import.meta.env.BASE_URL + '/sounds/alert.mp3',
      },
      {
        id: 'champagne',
        url: import.meta.env.BASE_URL + '/sounds/champagne-cork.mp3',
      },
      {
        id: 'dingaling',
        url: import.meta.env.BASE_URL + '/sounds/dingaling.mp3',
      },
      {
        id: 'dripecho',
        url: import.meta.env.BASE_URL + '/sounds/drip-echo.mp3',
      },
      {
        id: 'rooster',
        url: import.meta.env.BASE_URL + '/sounds/rooster-call.mp3',
      },
    ]
  }
  return sounds
}

export function soundById(id: string): Sound | undefined {
  return getSounds().find((s) => s.id == id)
}

const player = new Audio()
let audioUnlocked = false

export function isAudioUnlocked(): boolean {
  return audioUnlocked
}

export async function play(sound: Sound) {
  if (sound.url == null) {
    return
  }
  player.setAttribute('src', sound.url)
  player.load()
  await player.play()
  audioUnlocked = true
}

// Call this function on user interaction to unlock audio for future autoplay
export async function unlockAudio(sound?: Sound): Promise<boolean> {
  try {
    if (sound && sound.url) {
      await play(sound)
    } else {
      // Play a silent audio to unlock
      player.volume = 0
      player.setAttribute('src', 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=')
      player.load()
      await player.play()
      player.volume = 1
    }
    audioUnlocked = true
    return true
  } catch {
    return false
  }
}

let _muted = 'none'
export function mute() {
  const state = useState()
  if (state.sound.value !== 'none') {
    _muted = state.sound.value
  }
  state.sound.value = 'none'
}

export function unmute() {
  if (_muted !== 'none') {
    const state = useState()
    state.sound.value = _muted
  }
}
