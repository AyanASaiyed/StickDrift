// Music and sound effects, all synthesised with the Web Audio API - no audio files to download or license.
//
//   audio.init()            call from a click (browsers keep audio locked until then)
//   audio.setTrack(name)    'lobby' | 'apple' | 'fish' | 'rat' | null   (cross-fades)
//   audio.sfx.<name>(...)   one-shot effects, see the SFX table at the bottom
//   M key / the speaker button toggle mute (remembered in localStorage)

const MUTE_KEY = 'stickdrift.lobby.muted'
const midi = (n) => 440 * Math.pow(2, (n - 69) / 12)

const CHORD = { M: [0, 4, 7, 12], m: [0, 3, 7, 12] }

// Each track is a small generative loop: a chord progression played as an arpeggio + bass + optional pad / drums / melody.
const TRACKS = {
  lobby: { bpm: 100, root: 60, prog: [[0, 'M'], [5, 'M'], [7, 'M'], [5, 'M']], arp: [0, 1, 2, 1, 0, 1, 2, 3], lead: 'triangle', leadVol: 0.1, lift: 12, pad: true, bass: [0], hats: 0, kick: false, melody: 0.3 },
  apple: { bpm: 124, root: 67, prog: [[0, 'M'], [5, 'M'], [0, 'M'], [7, 'M']], arp: [0, 2, 1, 2, 0, 2, 1, 3], lead: 'square', leadVol: 0.045, lift: 0, pad: false, bass: [0, 4], hats: 1, kick: false, melody: 0.22 },
  fish: { bpm: 74, root: 62, prog: [[0, 'M'], [9, 'm'], [5, 'M'], [7, 'M']], arp: [0, 1, 2, 3, 2, 1, 0, 1], lead: 'sine', leadVol: 0.12, lift: 12, pad: true, bass: [0], hats: 0, kick: false, melody: 0.16, water: true },
  rat: { bpm: 142, root: 57, prog: [[0, 'm'], [8, 'M'], [3, 'M'], [7, 'M']], arp: [0, 0, 2, 0, 1, 0, 2, 1], lead: 'sawtooth', leadVol: 0.035, lift: 12, pad: false, bass: [0, 2, 4, 6], bassWave: 'sawtooth', hats: 2, kick: true, melody: 0 },
}
const SCALE = [0, 2, 4, 7, 9] // major pentatonic, for the melody

class AudioEngine {
  constructor() {
    this.ctx = null
    this.muted = false
    try {
      this.muted = localStorage.getItem(MUTE_KEY) === '1'
    } catch { /* storage unavailable */ }
    this.listeners = new Set()
    this.cur = null
    this.stamp = {}
    window.addEventListener('keydown', (e) => {
      if (e.code === 'KeyM' && !e.repeat) this.toggleMute()
    })
    document.addEventListener('visibilitychange', () => {
      if (this.ctx) document.hidden ? this.ctx.suspend() : this.ctx.resume()
    })
  }

  /** Create the audio graph. Must be called from a user gesture (the Start click). */
  init() {
    if (this.ctx) return this.ctx.resume()
    const AC = window.AudioContext || window.webkitAudioContext
    if (!AC) return
    const c = (this.ctx = new AC())
    this.master = c.createGain()
    const comp = c.createDynamicsCompressor() // keeps overlapping sounds from clipping
    this.master.connect(comp)
    comp.connect(c.destination)
    this.musicBus = c.createGain()
    this.musicBus.gain.value = 0.55
    this.sfxBus = c.createGain()
    this.sfxBus.gain.value = 0.9
    this.musicBus.connect(this.master)
    this.sfxBus.connect(this.master)
    const len = c.sampleRate * 2
    this.noiseBuf = c.createBuffer(1, len, c.sampleRate)
    const d = this.noiseBuf.getChannelData(0)
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1
    this.applyMute()
    return c.resume()
  }

  applyMute() {
    if (this.master) this.master.gain.setTargetAtTime(this.muted ? 0 : 0.8, this.ctx.currentTime, 0.03)
  }
  toggleMute() {
    this.muted = !this.muted
    try {
      localStorage.setItem(MUTE_KEY, this.muted ? '1' : '0')
    } catch { /* ignore */ }
    this.applyMute()
    this.listeners.forEach((f) => f(this.muted))
  }
  onMute(f) {
    this.listeners.add(f)
    f(this.muted)
  }

  /** Skip an effect that fired less than `gap` seconds ago (for things that could otherwise spam). */
  ready(key, gap) {
    const now = performance.now() / 1000
    if (this.stamp[key] && now - this.stamp[key] < gap) return false
    this.stamp[key] = now
    return true
  }

  // ---- building blocks ---------------------------------------------------------------
  tone(type, freq, t, dur, vol, dest, { attack = 0.004, slideTo = null, detune = 0, lp = null } = {}) {
    const c = this.ctx
    const o = c.createOscillator(), g = c.createGain()
    o.type = type
    o.frequency.setValueAtTime(freq, t)
    if (slideTo) o.frequency.exponentialRampToValueAtTime(Math.max(20, slideTo), t + dur)
    o.detune.value = detune
    g.gain.setValueAtTime(0.0001, t)
    g.gain.linearRampToValueAtTime(vol, t + attack)
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur)
    if (lp) {
      const f = c.createBiquadFilter()
      f.type = 'lowpass'
      f.frequency.value = lp
      o.connect(f)
      f.connect(g)
    } else o.connect(g)
    g.connect(dest)
    o.start(t)
    o.stop(t + dur + 0.05)
  }

  noise(t, dur, vol, dest, { type = 'bandpass', freq = 1000, q = 1, slideTo = null } = {}) {
    const c = this.ctx
    const s = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain()
    s.buffer = this.noiseBuf
    f.type = type
    f.Q.value = q
    f.frequency.setValueAtTime(freq, t)
    if (slideTo) f.frequency.exponentialRampToValueAtTime(Math.max(40, slideTo), t + dur)
    g.gain.setValueAtTime(vol, t)
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur)
    s.connect(f)
    f.connect(g)
    g.connect(dest)
    s.start(t, Math.random() * 0.8)
    s.stop(t + dur + 0.05)
  }

  // ---- music ---------------------------------------------------------------------------
  setTrack(name) {
    if (!this.ctx || name === this.name) return
    this.name = name
    const c = this.ctx
    if (this.cur) { // fade the old track out and stop it
      const old = this.cur
      old.gain.gain.cancelScheduledValues(c.currentTime)
      old.gain.gain.setValueAtTime(old.gain.gain.value, c.currentTime)
      old.gain.gain.linearRampToValueAtTime(0, c.currentTime + 0.6)
      clearInterval(old.timer)
      setTimeout(() => {
        old.stop?.()
        old.gain.disconnect()
      }, 800)
    }
    this.cur = null
    const tr = TRACKS[name]
    if (!tr) return
    const gain = c.createGain()
    gain.gain.setValueAtTime(0, c.currentTime)
    gain.gain.linearRampToValueAtTime(1, c.currentTime + 1.2)
    gain.connect(this.musicBus)
    const run = { gain, step: 0, next: c.currentTime + 0.15, tr, stepDur: 60 / tr.bpm / 2 }
    if (tr.water) { // gentle lapping water under the fishing music
      const src = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain(), lfo = c.createOscillator(), lg = c.createGain()
      src.buffer = this.noiseBuf
      src.loop = true
      f.type = 'lowpass'
      f.frequency.value = 650
      g.gain.value = 0.05
      lfo.frequency.value = 0.18
      lg.gain.value = 0.035
      lfo.connect(lg)
      lg.connect(g.gain)
      src.connect(f)
      f.connect(g)
      g.connect(gain)
      src.start()
      lfo.start()
      run.stop = () => {
        src.stop()
        lfo.stop()
      }
    }
    run.timer = setInterval(() => this.schedule(run), 30)
    this.cur = run
  }

  schedule(run) {
    const c = this.ctx
    while (run.next < c.currentTime + 0.14) {
      this.playStep(run, run.step, run.next)
      run.next += run.stepDur
      run.step++
    }
  }

  playStep(run, i, t) {
    const { tr, gain, stepDur } = run
    const s = i % 8
    const [off, q] = tr.prog[Math.floor(i / 8) % tr.prog.length]
    const ch = CHORD[q]
    const base = tr.root + off
    this.tone(tr.lead, midi(base + ch[tr.arp[s]] + tr.lift), t, stepDur * 1.8, tr.leadVol * (s % 4 === 0 ? 1.25 : 1), gain, { attack: 0.006, lp: 2800 })
    if (tr.bass.includes(s)) this.tone(tr.bassWave || 'sine', midi(base - 12), t, stepDur * 1.7, tr.bassWave ? 0.07 : 0.2, gain, { lp: 520 })
    if (tr.pad && s === 0) {
      for (const tone of ch.slice(0, 3)) {
        this.tone('sawtooth', midi(base + tone), t, stepDur * 8.5, 0.018, gain, { attack: 0.9, lp: 800, detune: -6 })
        this.tone('sawtooth', midi(base + tone), t, stepDur * 8.5, 0.018, gain, { attack: 0.9, lp: 800, detune: 6 })
      }
    }
    if (tr.hats === 1 && s % 2 === 1) this.noise(t, 0.05, 0.05, gain, { type: 'highpass', freq: 7500 })
    if (tr.hats === 2) this.noise(t, 0.04, s % 2 ? 0.05 : 0.025, gain, { type: 'highpass', freq: 8000 })
    if (tr.kick && s % 2 === 0) this.tone('sine', 150, t, 0.16, 0.34, gain, { slideTo: 45 })
    if (tr.melody && s % 2 === 1 && Math.random() < tr.melody) {
      const n = base + 12 + SCALE[Math.floor(Math.random() * SCALE.length)] + (Math.random() < 0.3 ? 12 : 0)
      this.tone('triangle', midi(n), t, stepDur * 2.6, 0.08, gain, { attack: 0.01, lp: 3200 })
    }
  }

  // ---- one-shot effects ---------------------------------------------------------------
  /** Run an effect; `fn(t, bus)` builds it starting at time t. Silent until init() has run. */
  fx(fn) {
    if (!this.ctx || this.ctx.state !== 'running') return
    fn(this.ctx.currentTime + 0.005, this.sfxBus)
  }
}

export const audio = new AudioEngine()

const arp = (A, notes, step, type, vol, dur = 0.22, t0 = 0) => (t, bus) => notes.forEach((n, i) => A.tone(type, midi(n), t + t0 + i * step, dur, vol, bus, { lp: 4500 }))

// ---- the effects ----------------------------------------------------------------------
export const sfx = {
  step: () => audio.ready('step', 0.12) && audio.fx((t, b) => audio.noise(t, 0.05, 0.06, b, { type: 'lowpass', freq: 500 + Math.random() * 300, q: 0.7 })),
  padEnter: () => audio.fx((t, b) => { audio.tone('sine', midi(76), t, 0.3, 0.14, b); audio.tone('sine', midi(81), t + 0.09, 0.4, 0.14, b) }),
  enterGame: () => audio.fx((t, b) => { audio.noise(t, 0.5, 0.18, b, { type: 'bandpass', freq: 300, q: 1.5, slideTo: 3500 }); arp(audio, [69, 73, 76, 81], 0.07, 'triangle', 0.14)(t + 0.15, b) }),
  back: () => audio.fx((t, b) => { audio.noise(t, 0.35, 0.14, b, { type: 'bandpass', freq: 3000, q: 1.2, slideTo: 300 }); audio.tone('triangle', midi(72), t, 0.2, 0.1, b, { slideTo: midi(60) }) }),
  tick: () => audio.fx((t, b) => audio.tone('sine', 660, t, 0.1, 0.18, b)),
  go: () => audio.fx(arp(audio, [72, 76, 79, 84], 0.06, 'triangle', 0.18, 0.3)),
  card: () => audio.fx((t, b) => { audio.noise(t, 0.12, 0.12, b, { type: 'highpass', freq: 2500 }); audio.tone('sine', midi(79), t + 0.05, 0.2, 0.1, b) }),
  // apples
  pick: () => audio.fx((t, b) => audio.tone('sine', 480, t, 0.12, 0.28, b, { slideTo: 1000 })),
  drop: () => audio.fx((t, b) => { audio.tone('sine', 190, t, 0.16, 0.4, b, { slideTo: 80 }); audio.noise(t, 0.08, 0.1, b, { type: 'lowpass', freq: 700 }) }),
  wrong: () => audio.ready('wrong', 0.25) && audio.fx((t, b) => audio.tone('square', 130, t, 0.2, 0.1, b, { slideTo: 90, lp: 700 })),
  spawn: () => audio.ready('spawn', 0.2) && audio.fx((t, b) => audio.tone('sine', 1300 + Math.random() * 300, t, 0.07, 0.05, b)),
  // fishing
  cast: () => audio.fx((t, b) => audio.noise(t, 0.35, 0.16, b, { type: 'bandpass', freq: 800, q: 1, slideTo: 2600 })),
  progress: (frac) => audio.ready('prog', 0.09) && audio.fx((t, b) => audio.tone('sine', midi(72 + Math.round(frac * 12)), t, 0.14, 0.09, b, { lp: 3000 })),
  offLane: () => audio.ready('off', 0.5) && audio.fx((t, b) => audio.tone('triangle', 220, t, 0.14, 0.12, b, { slideTo: 150 })),
  splash: () => audio.fx((t, b) => { audio.noise(t, 0.5, 0.3, b, { type: 'bandpass', freq: 1400, q: 0.7, slideTo: 400 }); audio.tone('sine', 260, t, 0.2, 0.15, b, { slideTo: 120 }) }),
  hooked: () => audio.fx((t, b) => { audio.noise(t, 0.4, 0.26, b, { type: 'bandpass', freq: 1500, q: 0.8, slideTo: 500 }); arp(audio, [72, 79, 84], 0.07, 'triangle', 0.16)(t, b) }),
  // rats
  squeak: () => audio.fx((t, b) => { audio.tone('sine', 1900, t, 0.07, 0.07, b, { slideTo: 2600 }); audio.tone('sine', 2100, t + 0.09, 0.07, 0.06, b, { slideTo: 2700 }) }),
  slam: () => audio.fx((t, b) => { audio.tone('sine', 150, t, 0.28, 0.7, b, { slideTo: 38 }); audio.noise(t, 0.14, 0.34, b, { type: 'lowpass', freq: 700 }) }),
  ratOk: () => audio.fx(arp(audio, [72, 76, 79, 84], 0.07, 'sine', 0.2, 0.3)),
  ratWrong: () => audio.fx((t, b) => { audio.tone('triangle', 420, t, 0.3, 0.2, b, { slideTo: 170 }); audio.tone('square', 110, t, 0.18, 0.07, b, { lp: 600 }) }),
  whiff: () => audio.fx((t, b) => audio.noise(t, 0.2, 0.12, b, { type: 'bandpass', freq: 600, q: 0.8, slideTo: 200 })),
  // results: 0-3 stars, plus a sparkle for a new high score
  result: (stars, isNewBest) =>
    audio.fx((t, b) => {
      const notes = [[65, 62], [72, 76], [72, 76, 79], [72, 76, 79, 84]][Math.min(stars, 3)]
      arp(audio, stars === 0 ? [62, 57] : notes, 0.13, 'triangle', 0.2, 0.5)(t, b)
      if (isNewBest) arp(audio, [88, 91, 93, 96, 100], 0.07, 'sine', 0.1, 0.4, 0.55)(t, b)
    }),
}
