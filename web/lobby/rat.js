// Game 3 - Rat Catching. One big hand hovers over a lane. Rats run right -> left, one at a time. The card
// (top-left) shows the rat to catch. FLICK either stick UP to slam: the target rat under the hand turns it
// green and is caught; a wrong rat or an empty slam just makes the hand shake. 3 rounds, a new target each round.
import * as THREE from 'three'
import { addSun } from './lights.js'
import { RETURN_DELAY, box, choice, clamp, cyl, makeHand, mat, mergeStatic, ownMat, perspectiveCam, setLens, shuffle, sphere, uniform } from './util.js'

const TYPES = [
  { key: 'grey', name: 'Grey Rat', rgb: [0.42, 0.42, 0.46] },
  { key: 'white', name: 'White Rat', rgb: [0.96, 0.96, 0.98], redEyes: true },
  { key: 'ginger', name: 'Ginger Rat', rgb: [0.8, 0.4, 0.12], stripe: true },
]
const ROUNDS = 3
const HAND_HOVER = 3.6, HAND_SLAM_Z = 0.9, HIT_HALF = 0.7, SLAM_TIME = 0.09
const X0 = 9, X1 = -9 // run from the right hole to the left hole
const SPEED = [4.68, 6.864] // m/s (original 3.0-4.4, then +20%, then +30% more)
const SKIN = [0.85, 0.58, 0.42]
const CARD = [-5.6, 3.4, -12]

function buildRat(t) {
  const g = new THREE.Group()
  const body = mat(t.rgb, { rough: 0.8 }), pink = mat([0.95, 0.62, 0.66], { rough: 0.8 })
  const eye = t.redEyes ? mat([0.85, 0.05, 0.05], { rough: 0.3 }) : mat([0.02, 0.02, 0.02], { rough: 0.3 })
  sphere(g, 0.5, [0, 0, 0.3], body, [1, 0.5, 0.45], 10)
  sphere(g, 0.28, [0.52, 0, 0.3], body, [1.1, 0.85, 0.85], 8)
  cyl(g, 0.12, 0.3, [0.82, 0, 0.28], pink, 6, 0.03).rotation.y = Math.PI / 2
  cyl(g, 0.05, 0.9, [-0.95, 0, 0.22], pink, 5, 0.012).rotation.y = -Math.PI / 2
  for (const sy of [-1, 1]) {
    sphere(g, 0.12, [0.42, sy * 0.2, 0.55], pink, [0.5, 1, 1], 6)
    sphere(g, 0.045, [0.66, sy * 0.13, 0.38], eye, [1, 1, 1], 5)
    for (const sx of [-0.3, 0.3]) sphere(g, 0.09, [sx, sy * 0.2, 0.08], pink, [1.3, 1, 0.7], 5)
  }
  if (t.stripe) sphere(g, 0.35, [0, 0, 0.5], mat([0.2, 0.1, 0.04], { rough: 0.9 }), [1, 0.18, 0.25], 6)
  return g
}

export class RatGame {
  constructor() {
    this.scene = new THREE.Scene()
    this.scene.background = new THREE.Color().setRGB(0.45, 0.68, 0.95, THREE.LinearSRGBColorSpace)
    addSun(this.scene, { intensity: 6, fill: 1.8, extent: 16 })
    const st = new THREE.Group()
    this.scene.add(st)
    const fa = mat([0.3, 0.19, 0.09], { rough: 0.95 }), fb = mat([0.24, 0.15, 0.07], { rough: 0.95 })
    const lane = mat([0.16, 0.14, 0.13], { rough: 0.9 })
    const gold = mat([1, 0.8, 0.2], { rough: 0.4, emit: [1, 0.75, 0.1], emitK: 2.5 })
    const dark = mat([0.04, 0.03, 0.02], { rough: 0.9 }), wood = mat([0.45, 0.3, 0.15], { rough: 0.9 })
    const sack = mat([0.72, 0.62, 0.42], { rough: 0.95 }), cheese = mat([0.95, 0.78, 0.15], { rough: 0.6 })
    box(st, [44, 30, 0.4], [0, 2, -0.2], fb)
    for (let k = -7; k < 14; k++) box(st, [44, 0.94, 0.03], [0, k, 0], k % 2 ? fa : fb, [0, 0, 0], false)
    box(st, [30, 1.9, 0.04], [0, 0, 0.02], lane, [0, 0, 0], false)
    const h = HIT_HALF
    for (const [sx, sy, w, d] of [[0, 0.95, 2 * h + 0.08, 0.08], [0, -0.95, 2 * h + 0.08, 0.08], [h, 0, 0.08, 1.9], [-h, 0, 0.08, 1.9]]) box(st, [w, d, 0.05], [sx, sy, 0.06], gold, [0, 0, 0], false) // where the hand lands
    for (const sx of [-7.2, 7.2]) cyl(st, 0.7, 0.05, [sx, 0, 0.05], dark, 12, null, false)
    for (const [x, y] of [[-6.8, 5.0], [7.0, 5.5], [-8.0, 2.8]]) cyl(st, 0.75, 1.2, [x, y, 0.6], wood, 10, 0.65)
    for (const [x, y, s] of [[5.6, 7.5, 1.3], [6.9, 8.2, 1.0], [-5.2, 8.0, 1.2]]) box(st, [s, s, s], [x, y, s / 2], wood, [0, 0, x * 0.3])
    for (const [x, y] of [[-3.0, 8.5], [2.5, 9.0], [-7.5, -2.5]]) sphere(st, 0.8, [x, y, 0.5], sack, [1, 1, 0.8], 8)
    cyl(st, 0.55, 0.35, [-4.2, -2.4, 0.18], cheese, 12)
    mergeStatic(st)

    this.camera = perspectiveCam(28, 100)
    this.camera.position.set(0, -8, 9)
    this.camera.lookAt(0, 0, 0.6)
    this.scene.add(this.camera)

    this.skin = ownMat(SKIN, { rough: 0.6 })
    const hand = makeHand(SKIN, { flip: true, arm: false, glove: this.skin }) // right hand seen from above, no arm
    this.hand = hand.root
    this.hand.rotation.x = -Math.PI / 2 // palm down, fingers away from the camera
    this.hand.scale.setScalar(1.8)
    this.hand.traverse((o) => (o.castShadow = false)) // the gold box shows where it lands
    this.scene.add(this.hand)

    this.rats = {}
    this.cards = {}
    for (const t of TYPES) {
      this.rats[t.key] = buildRat(t)
      this.rats[t.key].visible = false
      this.scene.add(this.rats[t.key])
      // card: paper + the rat seen from above, fixed to the camera at the top-left of the view
      const card = new THREE.Group()
      card.position.set(...CARD)
      box(card, [3.5, 2.7, 0.04], [0, 0, 0], mat([0.1, 0.07, 0.04]), [0, 0, 0], false)
      box(card, [3.3, 2.5, 0.05], [0, 0, 0.03], mat([0.97, 0.93, 0.8], { rough: 0.9 }), [0, 0, 0], false)
      const r = buildRat(t)
      r.scale.setScalar(1.5)
      r.position.z = 0.3
      r.rotation.z = Math.PI
      r.traverse((o) => (o.castShadow = false))
      card.add(r)
      card.visible = false
      this.camera.add(card)
      this.cards[t.key] = card
    }
    this.start()
  }

  resize(aspect) {
    setLens(this.camera, 28, aspect)
  }

  labelPos() {
    return this.camera.localToWorld(new THREE.Vector3(CARD[0], CARD[1] - 1.55, CARD[2]))
  }

  setHandColor(state) {
    if (state === this.handColor) return
    this.handColor = state
    const rgb = state === 'ok' ? [0.15, 0.85, 0.25] : SKIN
    this.skin.color.setRGB(...rgb, THREE.LinearSRGBColorSpace)
    this.skin.emissive = new THREE.Color().setRGB(...rgb, THREE.LinearSRGBColorSpace)
    this.skin.emissiveIntensity = state === 'ok' ? 0.6 : 0
  }

  start() {
    this.targets = shuffle(TYPES.map((t) => t.key))
    this.round = 0
    this.clock = 0
    this.state = 'intro'
    this.timer = 2.6
    this.stats = { caught: 0, missed: 0, wrong: 0, empty: 0 }
    this.armed = true
    this.hist = []
    this.hs = 'idle'
    this.ht = 0
    this.shake = false
    this.ok = false
    this.rat = null
    this.ratX = X0
    this.ratV = 0
    this.hop = 0
    for (const o of [...Object.values(this.rats), ...Object.values(this.cards)]) o.visible = false
    this.handColor = null
    this.setHandColor('normal')
    this.hand.position.set(0, 0, HAND_HOVER)
    this.bigText = 'Rat Catching\nSlam the rat on the card!\nFlick either stick UP to slam'
    this.cardName = ''
  }

  name(key) {
    return TYPES.find((t) => t.key === key).name
  }

  beginRound() {
    const t = this.targets[this.round]
    const others = TYPES.map((x) => x.key).filter((k) => k !== t)
    this.runs = shuffle([t, t, choice(others), choice(others)])
    this.runI = 0
    this.caughtThis = false
    for (const [k, c] of Object.entries(this.cards)) c.visible = k === t
    this.cardName = this.name(t)
    this.bigText = `Round ${this.round + 1}/${ROUNDS}\nCatch the ${this.name(t)}!`
    this.state = 'round_intro'
    this.timer = 2.2
  }

  spawn() {
    this.rat = this.runs[this.runI]
    this.ratX = X0
    this.ratV = uniform(...SPEED)
    this.caughtThis = false
    this.hop = 0
    const ob = this.rats[this.rat]
    ob.visible = true
    ob.scale.setScalar(1.8)
    ob.rotation.set(0, 0, Math.PI)
    this.state = 'run'
  }

  endRun() {
    if (this.rat === this.targets[this.round] && !this.caughtThis) this.stats.missed++ // the target ran past
    this.rats[this.rat].visible = false
    this.rat = null
    this.runI++
    if (this.runI >= this.runs.length) {
      this.round++
      if (this.round >= ROUNDS) this.finish()
      else this.beginRound()
    } else {
      this.state = 'gap'
      this.timer = uniform(0.4, 0.9)
    }
  }

  finish() {
    const s = this.stats
    this.state = 'done'
    this.timer = 0
    for (const c of Object.values(this.cards)) c.visible = false
    this.cardName = ''
    this.bigText = `Rat Catching complete!\nCaught ${s.caught}/${2 * ROUNDS} target rats\nWrong rat slammed: ${s.wrong}   Empty slams: ${s.empty}`
  }

  /** True once per flick: either stick snaps up past 0.75 within ~0.15 s; it must come back down to re-arm. */
  flick(pad) {
    const mv = pad.move, lk = pad.look
    const up = Math.max(mv[1] * mv[2], lk[1])
    this.hist = [...this.hist, up].slice(-9)
    if (up < 0.4) this.armed = true
    else if (up > 0.75 && this.armed && Math.min(...this.hist) < 0.35) {
      this.armed = false
      return true
    }
    return false
  }

  impact() {
    const hit = this.state === 'run' && Math.abs(this.ratX) < HIT_HALF ? this.rat : null
    if (hit && hit === this.targets[this.round]) {
      this.ok = true
      this.caughtThis = true
      this.stats.caught++
      const ob = this.rats[hit]
      ob.scale.set(2.2, 2.2, 0.2)
      ob.position.set(this.ratX, 0, 0.03)
      this.state = 'squash'
      this.timer = 0.9
      this.setHandColor('ok')
    } else {
      this.shake = true
      if (hit) {
        this.stats.wrong++
        this.hop = 0.35 // the wrong rat hops out of the way
      } else this.stats.empty++
    }
  }

  update(dt, pad) {
    if (pad.back) return true // O: leave at any time
    this.clock += dt
    const flick = this.flick(pad)
    const s = this.state
    if (s === 'done') {
      this.timer += dt
      return this.timer >= RETURN_DELAY
    }
    if (['intro', 'round_intro', 'gap', 'squash'].includes(s)) {
      this.timer -= dt
      if (this.timer <= 0) {
        if (s === 'intro') this.beginRound()
        else if (s === 'round_intro') {
          this.bigText = ''
          this.state = 'gap'
          this.timer = 0.6
        } else if (s === 'gap') this.spawn()
        else this.endRun()
      }
    } else if (s === 'run') {
      this.ratX -= this.ratV * dt
      const ob = this.rats[this.rat]
      const run = this.clock * this.ratV * 4
      this.hop = Math.max(0, this.hop - dt)
      ob.position.set(this.ratX, 0, 0.04 * Math.abs(Math.sin(run)) + (this.hop > 0 ? 0.9 * Math.sin((Math.PI * this.hop) / 0.35) ** 2 : 0))
      ob.rotation.set(0.06 * Math.sin(run), 0, Math.PI)
      if (this.ratX < X1) this.endRun()
    }

    // the hand: idle hover -> fast slam -> hold (green / shake) -> lift back up
    const hand = this.hand
    if (this.hs === 'idle') {
      this.setHandColor('normal')
      hand.position.set(0, 0, HAND_HOVER + 0.08 * Math.sin(this.clock * 2))
      if (flick && ['gap', 'run', 'squash'].includes(this.state)) {
        this.hs = 'down'
        this.ht = 0
        this.shake = false
        this.ok = false
      }
    } else if (this.hs === 'down') {
      this.ht += dt
      const q = Math.min(this.ht / SLAM_TIME, 1)
      hand.position.set(0, 0, HAND_HOVER + (HAND_SLAM_Z - HAND_HOVER) * q * q)
      if (q >= 1) {
        this.impact()
        this.hs = 'hold'
        this.ht = 0
      }
    } else if (this.hs === 'hold') {
      this.ht += dt
      const amp = this.shake ? 0.25 * Math.max(0, 1 - this.ht / 0.45) : 0
      hand.position.set(amp * Math.sin(this.ht * 70), amp * 0.4 * Math.sin(this.ht * 53), HAND_SLAM_Z)
      if (this.ht >= 0.45) {
        this.hs = 'up'
        this.ht = 0
      }
    } else if (this.hs === 'up') {
      this.ht += dt
      const q = Math.min(this.ht / 0.3, 1)
      hand.position.set(0, 0, HAND_SLAM_Z + (HAND_HOVER - HAND_SLAM_Z) * q)
      if (q >= 1) this.hs = 'idle'
    }
    return false
  }

  ui() {
    const s = this.stats
    const target = this.name(this.targets[Math.min(this.round, ROUNDS - 1)])
    const header =
      this.state === 'done'
        ? `Rat Catching done - caught ${s.caught}/${2 * ROUNDS}   |   back to the lobby in ${Math.max(0, RETURN_DELAY - this.timer).toFixed(0)}s   |   O: back now`
        : `Rat Catching   Round ${Math.min(this.round + 1, ROUNDS)}/${ROUNDS}   Caught ${s.caught}   |   flick a stick UP: slam the ${target}   |   O: back`
    return { header, hud: `Round ${Math.min(this.round + 1, ROUNDS)}/${ROUNDS}    Caught ${s.caught}`, big: this.bigText, label: this.cardName }
  }
}
