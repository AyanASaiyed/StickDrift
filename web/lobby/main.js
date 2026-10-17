// Entry point: owns the renderer, the lobby, the three games and the overlay text.
import * as THREE from 'three'
import './util.js'
import { Input } from './input.js'
import { Hub, PORTALS } from './hub.js'
import { bestFor, starText } from './scores.js'
import { AppleGame } from './apple.js'
import { FishGame } from './fish.js'
import { RatGame } from './rat.js'
import { LiveStream } from './live.js'
import { Measure } from './measure.js'

const canvas = document.getElementById('c')
const $ = (id) => document.getElementById(id)
const overlay = { header: $('header'), hud: $('hud'), big: $('big'), label: $('label') }
const setText = (el, text) => {
  if (el._t !== text) {
    el._t = text
    el.textContent = text
  }
}

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
renderer.shadowMap.enabled = true
renderer.shadowMap.type = THREE.PCFSoftShadowMap
renderer.toneMapping = THREE.AgXToneMapping // the same tone mapper Blender uses, so colours match
renderer.toneMappingExposure = 0.8

const input = new Input()
const hub = new Hub()
const games = { apple: new AppleGame(), fish: new FishGame(), rat: new RatGame() }
let active = null // the running game, or null while in the lobby
const live = new LiveStream()
const measure = new Measure()

function resize() {
  const w = window.innerWidth, h = window.innerHeight
  renderer.setSize(w, h, false)
  hub.resize(w / h)
  Object.values(games).forEach((g) => g.resize(w / h))
}
window.addEventListener('resize', resize)
resize()

/** The high-score panel shown in the lobby. */
function refreshScores() {
  const el = $('scores')
  el.innerHTML =
    '<b>High scores</b>' +
    PORTALS.map((p) => {
      const b = bestFor(p.game)
      return `<div class="row"><span>${p.title}</span><span>${b.best ? b.best + ' ' + starText(b.stars) : '-'}</span></div>`
    }).join('')
}
refreshScores()

function startGame(portal) {
  $('scores').style.display = 'none'
  active = games[portal.game]
  active.start()
  live.enter(portal.game)
  measure.enter(portal.game)
}
function leaveGame() {
  active = null
  live.enter('lobby')
  measure.enter(null)
  hub.reset()
  refreshScores()
  $('scores').style.display = ''
  setText(overlay.hud, '')
  setText(overlay.big, '')
  setText(overlay.label, '')
}

const clock = new THREE.Clock()
let running = false
function frame() {
  requestAnimationFrame(frame)
  const dt = Math.min(clock.getDelta(), 0.05)
  if (!running) return
  const pad = input.read()
  live.sample(measure.frame(active, live.now(), pad.raw, (e) => live.event(e.type, e)))
  if (active) {
    if (active.update(dt, pad)) leaveGame()
  } else {
    const enter = hub.update(dt, pad)
    if (enter) startGame(enter)
  }
  const view = active || hub
  const ui = active ? active.ui(pad) : { header: pad.source === 'none' ? 'No controller found - connect a PS5 pad and press a button (or use the keyboard)' : hub.header(), hud: '', big: '', label: '' }
  setText(overlay.header, ui.header)
  setText(overlay.hud, ui.hud || '')
  setText(overlay.big, ui.big || '')
  setText(overlay.label, ui.label || '')
  if (active && active.labelPos) {
    const v = active.labelPos().project(active.camera)
    overlay.label.style.left = ((v.x + 1) / 2) * window.innerWidth + 'px'
    overlay.label.style.top = ((1 - v.y) / 2) * window.innerHeight + 'px'
  }
  renderer.render(view.scene, view.camera)
}

$('go').addEventListener('click', () => {
  $('start').style.display = 'none'
  running = true
  clock.getDelta()
  live.start(input.read().source !== 'gamepad', ['lobby', ...Object.keys(games)])
})
requestAnimationFrame(frame)

// handy for debugging / automated checks
window.__lobby = { hub, games, input, get active() { return active }, startGame, leaveGame, renderer }
