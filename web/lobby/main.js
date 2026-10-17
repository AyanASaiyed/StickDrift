// Entry point: owns the renderer, the lobby, the three games and the on-screen UI.
import * as THREE from 'three'
import './util.js'
import { Input } from './input.js'
import { Hub, PORTALS } from './hub.js'
import { bestFor } from './scores.js'
import { render as renderUi } from './overlay.js'
import { audio, sfx } from './audio.js'
import { AppleGame } from './apple.js'
import { FishGame } from './fish.js'
import { RatGame } from './rat.js'
import { LiveStream } from './live.js'
import { Measure } from './measure.js'

const canvas = document.getElementById('c')
const $ = (id) => document.getElementById(id)

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' })
// Resolution adapts to the machine: start sharp, step down if frames run long, step back up when there is headroom.
const MAX_DPR = Math.min(window.devicePixelRatio || 1, 1.75), MIN_DPR = 0.75
let dpr = MAX_DPR
renderer.setPixelRatio(dpr)
renderer.shadowMap.enabled = true
renderer.shadowMap.type = THREE.PCFShadowMap // cheaper than PCFSoft
renderer.toneMapping = THREE.AgXToneMapping // the same tone mapper Blender uses, so colours match
renderer.toneMappingExposure = 0.8

const input = new Input()
let hub, games
let active = null // the running game, or null while in the lobby
const live = new LiveStream()
const measure = new Measure()
let scoreList = []

function resize() {
  const w = window.innerWidth, h = window.innerHeight
  renderer.setSize(w, h, false)
  hub.resize(w / h)
  Object.values(games).forEach((g) => g.resize(w / h))
}

/** The high-score panel shown in the lobby. */
function refreshScores() {
  scoreList = PORTALS.map((p) => ({ title: p.title, ...bestFor(p.game) }))
}

function startGame(portal) {
  sfx.enterGame()
  audio.setTrack(portal.game)
  active = games[portal.game]
  active.start()
  live.enter(portal.game)
  measure.enter(portal.game)
}
function leaveGame() {
  active = null
  sfx.back()
  audio.setTrack('lobby')
  live.enter('lobby')
  measure.enter(null)
  hub.reset()
  refreshScores()
}

const clock = new THREE.Clock()
let running = false
let slow = 0, fast = 0, uiAcc = 1, lastView = null

/** Frame-time governor: ~1 s of slow frames lowers the render resolution one step; ~4 s of fast frames raises it. */
function adapt(dt) {
  if (dt > 1 / 40) { slow += dt; fast = 0 } else if (dt < 1 / 55) { fast += dt; slow = Math.max(0, slow - dt) } else { slow = Math.max(0, slow - dt); fast = 0 }
  if (slow > 1 && dpr > MIN_DPR) {
    dpr = Math.max(MIN_DPR, dpr - 0.25)
    renderer.setPixelRatio(dpr)
    renderer.setSize(window.innerWidth, window.innerHeight, false)
    slow = 0
  } else if (fast > 4 && dpr < MAX_DPR) {
    dpr = Math.min(MAX_DPR, dpr + 0.25)
    renderer.setPixelRatio(dpr)
    renderer.setSize(window.innerWidth, window.innerHeight, false)
    fast = 0
  }
}
function frame() {
  requestAnimationFrame(frame)
  if (!hub) return
  const dt = Math.min(clock.getDelta(), 0.05)
  if (!running) return
  const pad = input.read()
  live.sample(measure.frame(active, live.now(), pad.raw, (e) => live.event(e.type, e)))
  let ui
  if (active) {
    if (active.update(dt, pad)) leaveGame()
  } else {
    const enter = hub.update(dt, pad)
    if (enter) startGame(enter)
  }
  const view = active || hub
  // the DOM overlay only needs ~15 updates a second (and straight away when switching between lobby and a game)
  uiAcc += dt
  if (uiAcc > 0.066 || view !== lastView) {
    uiAcc = 0
    lastView = view
    if (active) ui = active.ui(pad)
    else ui = { ...hub.ui(pad), scores: scoreList }
    const label = renderUi(ui, !!active)
    if (active && active.labelPos && ui.label) {
      const v = active.labelPos().project(active.camera)
      label.style.left = ((v.x + 1) / 2) * window.innerWidth + 'px'
      label.style.top = ((1 - v.y) / 2) * window.innerHeight + 'px'
    }
  }
  if (!document.hidden) adapt(dt)
  renderer.render(view.scene, view.camera)
}

async function init() {
  // wait for the display font so the in-world text (pad labels) is drawn with it
  try {
    await Promise.race([document.fonts.load('700 48px Fredoka'), new Promise((r) => setTimeout(r, 2500))])
  } catch {
    /* fall back to the system font */
  }
  hub = new Hub()
  games = { apple: new AppleGame(), fish: new FishGame(), rat: new RatGame() }
  window.addEventListener('resize', resize)
  resize()
  // compile every scene's shaders up front so entering a game doesn't stall for a moment
  for (const v of [hub, ...Object.values(games)]) renderer.compile(v.scene, v.camera)
  refreshScores()
  // handy for debugging / automated checks
  window.__lobby = { hub, games, input, get active() { return active }, startGame, leaveGame, renderer, renderUi }
}

$('go').addEventListener('click', () => {
  $('start').style.display = 'none'
  audio.init() // browsers only allow sound after a click
  audio.setTrack('lobby')
  running = true
  clock.getDelta()
  live.start(input.read().source !== 'gamepad', ['lobby', 'apple', 'fish', 'rat'])
})
init()
requestAnimationFrame(frame)
