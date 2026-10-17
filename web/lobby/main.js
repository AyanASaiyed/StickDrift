// Entry point: owns the renderer, the lobby, the three games and the on-screen UI.
import * as THREE from 'three'
import './util.js'
import { Input } from './input.js'
import { Hub, PORTALS } from './hub.js'
import { bestFor } from './scores.js'
import { render as renderUi } from './overlay.js'
import { AppleGame } from './apple.js'
import { FishGame } from './fish.js'
import { RatGame } from './rat.js'
import { LiveStream } from './live.js'

const canvas = document.getElementById('c')
const $ = (id) => document.getElementById(id)

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
renderer.shadowMap.enabled = true
renderer.shadowMap.type = THREE.PCFSoftShadowMap
renderer.toneMapping = THREE.AgXToneMapping // the same tone mapper Blender uses, so colours match
renderer.toneMappingExposure = 0.8

const input = new Input()
let hub, games
let active = null // the running game, or null while in the lobby
const live = new LiveStream()
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
  active = games[portal.game]
  active.start()
  live.enter(portal.game)
}
function leaveGame() {
  active = null
  live.enter('lobby')
  hub.reset()
  refreshScores()
}

const clock = new THREE.Clock()
let running = false
function frame() {
  requestAnimationFrame(frame)
  if (!hub) return
  const dt = Math.min(clock.getDelta(), 0.05)
  if (!running) return
  const pad = input.read()
  live.sample(...pad.raw)
  let ui
  if (active) {
    if (active.update(dt, pad)) leaveGame()
  } else {
    const enter = hub.update(dt, pad)
    if (enter) startGame(enter)
  }
  if (active) ui = active.ui(pad)
  else ui = { ...hub.ui(pad), scores: scoreList }
  const label = renderUi(ui, !!active)
  if (active && active.labelPos && ui.label) {
    const v = active.labelPos().project(active.camera)
    label.style.left = ((v.x + 1) / 2) * window.innerWidth + 'px'
    label.style.top = ((1 - v.y) / 2) * window.innerHeight + 'px'
  }
  const view = active || hub
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
  refreshScores()
  // handy for debugging / automated checks
  window.__lobby = { hub, games, input, get active() { return active }, startGame, leaveGame, renderer, renderUi }
}

$('go').addEventListener('click', () => {
  $('start').style.display = 'none'
  running = true
  clock.getDelta()
  live.start(input.read().source !== 'gamepad', ['lobby', ...Object.keys(games)])
})
init()
requestAnimationFrame(frame)
