// The top-down lobby: grandma walks between three game pads. Port of the Blender hub.
import * as THREE from 'three'
import { addSun } from './lights.js'
import { bestFor } from './scores.js'
import { TAU, blob, box, clamp, cyl, mat, mergeStatic, rng, sphere, textSprite, torus } from './util.js'

const HALF_X = 9.6, HALF_Y = 6.1
const SPEED = 2.1 // m/s
const PORTAL_R = 1.9
const PLAYER_R = 0.38
const START = [0, -5]
const CAM_DIST = 22
const MAX_TILT = (45 * Math.PI) / 180
const ORBIT_SPEED = (120 * Math.PI) / 180
const TILT_SPEED = (60 * Math.PI) / 180
const ZOOM_RANGE = [8, 16], ZOOM_SPEED = 3

export const PORTALS = [
  { name: 'Game1', label: 'Game 1', game: 'apple', title: 'Apple Picking', x: -7.4, y: 0.8, color: [0.25, 0.6, 1.0] },
  { name: 'Game2', label: 'Game 2', game: 'fish', title: 'Harbour Fishing', x: 0.0, y: 3.8, color: [0.3, 1.0, 0.55] },
  { name: 'Game3', label: 'Game 3', game: 'rat', title: 'Rat Catching', x: 6.9, y: -0.8, color: [0.8, 0.35, 1.0] },
]
const TREES = [
  [-5.0, 4.9, 1.5], [-2.8, 4.4, 0.8], [-4.2, 2.1, 1.1], [5.4, 3.0, 1.0], [7.8, 4.7, 0.9], [6.5, 3.9, 0.7],
  [3.2, 2.9, 1.0], [1.8, -1.4, 1.0], [-6.8, -4.2, 0.9], [7.3, -4.9, 1.3], [-8.6, 4.8, 0.8], [5.2, -3.6, 0.8], // none sits on a path
]
const KINDS = ['oak', 'pine', 'oak', 'autumn', 'pine', 'oak', 'birch', 'pine', 'oak', 'autumn', 'oak', 'pine']
const ROCKS = [[-8.8, 3.7, 0.45], [3.9, 0.6, 0.5], [-5.0, -2.6, 0.8], [-1.6, 0.2, 0.9], [3.6, -4.3, 0.5], [-1.4, -1.8, 0.4], [8.2, -2.6, 0.55]]
const BENCH = [-3.0, -4.9, 0]
const LAMPS = [[-3.6, -1.0], [3.6, -1.0], [-3.4, 2.7], [3.6, 2.8]]
const COLLIDERS = [
  ...TREES.map(([x, y, s]) => [x, y, 0.35 * s + 0.15]),
  ...ROCKS.map(([x, y, s]) => [x, y, s * 0.9]),
  [BENCH[0], BENCH[1], 0.9],
  ...LAMPS.map(([x, y]) => [x, y, 0.25]),
]

function buildTree(g, i, x, y, s) {
  const kind = KINDS[i % KINDS.length]
  const bark = mat([0.3, 0.19, 0.1], { rough: 0.95 })
  const birch = mat([0.88, 0.86, 0.8], { rough: 0.9 })
  const greens = [mat([0.12, 0.45, 0.14]), mat([0.17, 0.56, 0.18]), mat([0.27, 0.66, 0.22])]
  const pines = [mat([0.06, 0.31, 0.17]), mat([0.08, 0.4, 0.21])]
  const autumn = [mat([0.8, 0.36, 0.08]), mat([0.9, 0.55, 0.1]), mat([0.72, 0.2, 0.07])]
  const t = new THREE.Group()
  t.position.set(x, y, 0)
  t.rotation.z = i * 0.9
  g.add(t)
  cyl(t, 1.0 * s, 0.01, [0, 0, 0.015], mat([0.08, 0.2, 0.08]), 20, null, false) // ground shadow blob
  cyl(t, 0.3 * s, 0.25 * s, [0, 0, 0.12 * s], bark, 8, 0.2 * s)
  if (kind === 'pine') {
    cyl(t, 0.17 * s, 1.0 * s, [0, 0, 0.5 * s], bark, 8)
    for (let k = 0; k < 5; k++) cyl(t, (1.15 - k * 0.2) * s, 0.95 * s, [0, 0, (0.9 + k * 0.62) * s], pines[k % 2], 9, 0.05 * s)
  } else {
    cyl(t, 0.2 * s, 1.5 * s, [0, 0, 0.75 * s], kind === 'birch' ? birch : bark, 8, 0.14 * s)
    const pal = kind === 'autumn' ? autumn : greens
    let spots = [[0, 0, 2.15, 0.95], [0.55, 0.15, 1.8, 0.7], [-0.5, -0.2, 1.85, 0.72], [0.1, 0.55, 2.0, 0.65], [-0.1, -0.5, 2.3, 0.6], [0.35, -0.3, 2.55, 0.55]]
    if (kind === 'birch') spots = [[0, 0, 2.3, 0.7], [0.3, 0.2, 1.9, 0.5], [-0.3, -0.1, 2.0, 0.5], [0, 0.2, 2.7, 0.45]]
    spots.forEach(([dx, dy, z, r], k) => blob(t, r * s, [dx * s, dy * s, z * s], pal[k % 3], 0.85, i * 10 + k))
  }
}

function buildRock(g, i, x, y, s) {
  const r = rng(i + 11)
  const m = blob(g, s, [x, y, s * 0.4], mat([0.5, 0.5, 0.52], { rough: 0.95 }), 0.65, i + 3)
  m.rotation.z = r() * TAU
}

function buildBench(g) {
  const wood = mat([0.55, 0.35, 0.17]), iron = mat([0.12, 0.12, 0.13], { rough: 0.5 })
  const b = new THREE.Group()
  b.position.set(BENCH[0], BENCH[1], 0)
  b.rotation.z = (BENCH[2] * Math.PI) / 180
  g.add(b)
  for (let k = 0; k < 3; k++) box(b, [1.7, 0.16, 0.06], [0, -0.18 + k * 0.18, 0.5], wood)
  for (let k = 0; k < 3; k++) box(b, [1.7, 0.05, 0.14], [0, 0.36, 0.72 + k * 0.16], wood)
  for (const sx of [-0.75, 0.75]) {
    box(b, [0.07, 0.6, 0.5], [sx, 0, 0.25], iron)
    box(b, [0.07, 0.06, 0.75], [sx, 0.36, 0.55], iron)
  }
}

function buildGround(g) {
  const grass = mat([0.2, 0.46, 0.18]), grass2 = mat([0.16, 0.38, 0.15])
  const path = mat([0.62, 0.5, 0.33], { rough: 0.95 })
  const stone = mat([0.45, 0.45, 0.47]), wood = mat([0.4, 0.26, 0.14])
  box(g, [2 * (HALF_X + 0.6), 2 * (HALF_Y + 0.6), 0.4], [0, 0, -0.2], grass)
  const r = rng(4)
  for (let i = 0; i < 18; i++) cyl(g, 0.5 + r() * 0.8, 0.02, [(r() * 2 - 1) * HALF_X, (r() * 2 - 1) * HALF_Y, 0.01], grass2, 8, null, false)
  for (let i = 0; i < 30; i++) cyl(g, 0.06, 0.22, [(r() * 2 - 1) * HALF_X, (r() * 2 - 1) * HALF_Y, 0.11], grass2, 4, 0)
  for (const p of PORTALS) {
    const a = [START[0], START[1] + 0.9], b = [p.x, p.y]
    const dx = b[0] - a[0], dy = b[1] - a[1]
    box(g, [Math.hypot(dx, dy), 0.9, 0.04], [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0.02], path, [0, 0, Math.atan2(dy, dx)], false)
  }
  cyl(g, 1.6, 0.04, [START[0], START[1] + 0.3, 0.02], path, 24, null, false)
  const fx = HALF_X + 0.35, fy = HALF_Y + 0.35
  for (const sy of [fy, -fy]) {
    box(g, [2 * fx, 0.12, 0.12], [0, sy, 0.55], wood)
    box(g, [2 * fx, 0.12, 0.12], [0, sy, 0.95], wood)
  }
  for (const sx of [-fx, fx]) {
    box(g, [0.12, 2 * fy, 0.12], [sx, 0, 0.55], wood)
    box(g, [0.12, 2 * fy, 0.12], [sx, 0, 0.95], wood)
  }
  for (let i = -10; i <= 10; i++) for (const y of [fy, -fy]) box(g, [0.16, 0.16, 1.2], [(i * fx) / 10, y, 0.6], stone)
  for (let j = -6; j <= 6; j++) for (const x of [fx, -fx]) box(g, [0.16, 0.16, 1.2], [x, (j * fy) / 6, 0.6], stone)
}

function buildLamp(g, x, y) {
  cyl(g, 0.05, 1.8, [x, y, 0.9], mat([0.15, 0.15, 0.16], { rough: 0.5 }), 8)
  sphere(g, 0.17, [x, y, 1.9], mat([1, 0.9, 0.6], { rough: 0.3, emit: [1, 0.85, 0.5], emitK: 3 }), [1, 1, 1], 8, false)
}

/** Static pad scenery goes in `g` (merged later); the spinning parts are returned for animation. */
function buildPortal(g, scene, p) {
  const stone = mat([0.5, 0.5, 0.55], { rough: 0.7 }), dark = mat([0.22, 0.22, 0.27], { rough: 0.6 })
  const col = p.color
  const bright = mat(col, { rough: 0.1, emit: col, emitK: 3 })
  const glowM = mat(col, { rough: 0.2, emit: col, emitK: 1.2 }).clone()
  const { x, y } = p
  cyl(g, 1.65, 0.1, [x, y, 0.05], dark, 20)
  cyl(g, 1.45, 0.2, [x, y, 0.15], stone, 20)
  cyl(g, 1.12, 0.22, [x, y, 0.16], dark, 20)
  const glow = cyl(scene, 1.05, 0.22, [x, y, 0.17], glowM, 20)
  glow.castShadow = false
  for (let k = 0; k < 12; k++) {
    const a = (k * TAU) / 12
    box(g, [0.25, 0.06, 0.04], [x + 1.28 * Math.cos(a), y + 1.28 * Math.sin(a), 0.26], bright, [0, 0, a + Math.PI / 2], false)
  }
  for (let k = 0; k < 6; k++) {
    const a = (k * TAU) / 6 + 0.26
    const px = x + 1.5 * Math.cos(a), py = y + 1.5 * Math.sin(a)
    cyl(g, 0.14, 0.95, [px, py, 0.55], stone, 8)
    cyl(g, 0.18, 0.1, [px, py, 1.05], dark, 8)
    sphere(g, 0.1, [px, py, 1.17], bright, [1, 1, 1], 8, false)
  }
  const ring = torus(scene, 0.85, 0.035, [x, y, 0.9], bright, 20, 4)
  ring.castShadow = false
  const crystal = new THREE.Mesh(new THREE.IcosahedronGeometry(0.38, 1), bright)
  crystal.scale.set(0.7, 0.7, 1.5)
  crystal.position.set(x, y, 0.9)
  scene.add(crystal)
  const light = new THREE.PointLight(new THREE.Color().setRGB(...col, THREE.LinearSRGBColorSpace), 9, 7, 2)
  light.position.set(x, y, 1.3)
  scene.add(light)
  const label = textSprite(p.label, { size: 0.5, width: 3 })
  label.position.set(x, y + 2.2, 0.03)
  scene.add(label)
  return { crystal, ring, glowM, p }
}

function buildGrandma() {
  const skin = mat([0.95, 0.76, 0.62]), dress = mat([0.72, 0.22, 0.45])
  const hair = mat([0.85, 0.85, 0.88]), shoe = mat([0.2, 0.12, 0.08])
  const shawl = mat([0.95, 0.8, 0.35]), glasses = mat([0.1, 0.1, 0.1], { rough: 0.4 })
  const root = new THREE.Group()
  const body = new THREE.Group()
  root.add(body)
  cyl(body, 0.34, 0.75, [0, 0, 0.5], dress, 20, 0.2)
  sphere(body, 0.27, [0, 0, 0.9], shawl, [1, 1.35, 0.55])
  sphere(body, 0.2, [0.03, 0, 1.15], skin)
  sphere(body, 0.215, [-0.03, 0, 1.2], hair, [1, 1.02, 0.9])
  sphere(body, 0.11, [-0.2, 0, 1.38], hair)
  sphere(body, 0.04, [0.22, 0, 1.13], skin)
  for (const sy of [-0.09, 0.09]) sphere(body, 0.045, [0.2, sy, 1.19], glasses, [0.4, 1, 1], 8)
  const arms = [], legs = []
  for (const sy of [-1, 1]) {
    const arm = new THREE.Group()
    arm.position.set(0, sy * 0.33, 0.88)
    sphere(arm, 0.075, [0, 0, -0.18], skin, [1, 1, 2.6], 8)
    body.add(arm)
    arms.push(arm)
    const leg = new THREE.Group()
    leg.position.set(0, sy * 0.13, 0.2)
    sphere(leg, 0.1, [0.05, 0, -0.14], shoe, [1.5, 1, 0.8], 8)
    root.add(leg)
    legs.push(leg)
  }
  return { root, body, arms, legs }
}

export class Hub {
  constructor() {
    this.scene = new THREE.Scene()
    this.scene.background = new THREE.Color().setRGB(0.09, 0.14, 0.11, THREE.LinearSRGBColorSpace)
    addSun(this.scene, { intensity: 6.5, fill: 1.7, extent: 17 })
    const g = new THREE.Group() // static scenery, merged below
    this.scene.add(g)
    buildGround(g)
    TREES.forEach(([x, y, s], i) => buildTree(g, i, x, y, s))
    ROCKS.forEach(([x, y, s], i) => buildRock(g, i, x, y, s))
    buildBench(g)
    LAMPS.forEach(([x, y]) => buildLamp(g, x, y))
    this.portals = PORTALS.map((p) => buildPortal(g, this.scene, p))
    mergeStatic(g)
    const gl = textSprite('Grandma', { size: 0.4, width: 3 })
    gl.position.set(START[0], START[1] - 1, 0.03)
    this.scene.add(gl)

    const m = buildGrandma()
    this.grandma = m
    m.root.position.set(START[0], START[1], 0)
    m.root.rotation.z = Math.PI / 2
    this.scene.add(m.root)

    this.camera = new THREE.OrthographicCamera(-10, 10, 6, -6, 0.1, 100)
    this.aspect = 1.6
    this.follow = true
    this.focus = [0, 0]
    this.yaw = 0
    this.tilt = (14 * Math.PI) / 180
    this.zoom = 12
    this.scale = 12
    this.walk = 0
    this.heading = Math.PI / 2
    this.clock = 0
    this.near = null
    this.nearState = {}
    this.layout()
  }

  reset() {
    this.promptFor = null // re-read the high score next time a pad prompt shows
    this.grandma.root.position.set(START[0], START[1], 0)
  }

  /** Blender ortho_scale = width of the view (for a wide window). */
  layout() {
    const a = this.aspect
    const halfW = a >= 1 ? this.scale / 2 : (this.scale / 2) * a
    const halfH = halfW / a
    Object.assign(this.camera, { left: -halfW, right: halfW, top: halfH, bottom: -halfH })
    this.camera.updateProjectionMatrix()
  }

  resize(aspect) {
    this.aspect = aspect
    this.layout()
  }

  /** @returns {object|null} the portal whose game should start, when the player presses Cross on a pad. */
  update(dt, pad) {
    this.clock += dt
    const root = this.grandma.root
    const [mx, my, mag] = pad.move
    this.yaw -= pad.look[0] * ORBIT_SPEED * dt // right stick X: orbit
    this.tilt = clamp(this.tilt - pad.look[1] * TILT_SPEED * dt, 0, MAX_TILT) // Y: top-down .. 45 degrees
    this.zoom = clamp(this.zoom + pad.zoom * ZOOM_SPEED * dt, ZOOM_RANGE[0], ZOOM_RANGE[1])
    if (pad.cam) this.follow = !this.follow

    const c = Math.cos(this.yaw), s = Math.sin(this.yaw)
    const dx = mx * c - my * s, dy = mx * s + my * c // stick direction relative to the camera
    const p = root.position
    const moving = mag > 0
    if (moving) {
      const step = SPEED * mag * dt
      for (const [ax, ay] of [[dx * step, 0], [0, dy * step]]) {
        const nx = clamp(p.x + ax, -HALF_X, HALF_X), ny = clamp(p.y + ay, -HALF_Y, HALF_Y)
        if (COLLIDERS.every(([cx, cy, cr]) => Math.hypot(nx - cx, ny - cy) > cr + PLAYER_R)) {
          p.x = nx
          p.y = ny
        }
      }
      const target = Math.atan2(dy, dx)
      const diff = ((target - this.heading + Math.PI) % TAU + TAU) % TAU - Math.PI
      this.heading += diff * Math.min(1, 14 * dt)
      root.rotation.z = this.heading
      this.walk += dt * 11 * Math.max(mag, 0.4)
    } else this.walk *= 0.8
    const swing = moving ? Math.sin(this.walk) * 0.7 : 0
    this.grandma.arms.forEach((a, i) => (a.rotation.y = i ? swing : -swing))
    this.grandma.legs.forEach((l, i) => (l.rotation.y = i ? -swing : swing))
    this.grandma.body.position.z = moving ? Math.abs(Math.sin(this.walk)) * 0.06 : 0

    this.near = PORTALS.find((q) => Math.hypot(p.x - q.x, p.y - q.y) < PORTAL_R) || null
    for (const pt of this.portals) {
      const near = this.near === pt.p
      pt.crystal.rotation.z = this.clock * (near ? 2.2 : 0.9)
      pt.crystal.position.z = 0.9 + 0.12 * Math.sin(this.clock * 2 + pt.p.x)
      pt.ring.rotation.x = this.clock * 0.6
      pt.ring.rotation.y = this.clock * 0.4
      if (this.nearState[pt.p.name] !== near) {
        this.nearState[pt.p.name] = near
        pt.glowM.emissiveIntensity = near ? 3 : 1.2
      }
    }
    this.updateCamera(dt)
    return this.near && pad.enter ? this.near : null
  }

  updateCamera(dt) {
    const k = Math.min(1, 5 * dt)
    const p = this.grandma.root.position
    this.scale += ((this.follow ? this.zoom : 2 * HALF_X + 2.4) - this.scale) * k
    this.layout()
    const half = this.scale / 2
    const fx = this.follow ? clamp(p.x, -(HALF_X + 1.2 - half), HALF_X + 1.2 - half) : 0
    const fy = this.follow ? clamp(p.y, -(HALF_Y + 0.8 - half / 1.6), HALF_Y + 0.8 - half / 1.6) : 0
    this.focus[0] += (fx - this.focus[0]) * k
    this.focus[1] += (fy - this.focus[1]) * k
    const sp = Math.sin(this.tilt), cp = Math.cos(this.tilt)
    const sy = Math.sin(this.yaw), cy = Math.cos(this.yaw)
    const [tx, ty] = this.focus
    this.camera.position.set(tx + CAM_DIST * sp * sy, ty - CAM_DIST * sp * cy, CAM_DIST * cp) // orbit the focus point
    this.camera.up.set(0, 0, 1)
    this.camera.lookAt(tx, ty, 0)
  }

  ui(pad) {
    if (pad.source === 'none') return { hint: 'No controller found  ·  connect a PS5 pad and press a button (or use the keyboard)', prompt: null }
    let prompt = null
    if (this.near) {
      if (this.promptFor !== this.near.game) {
        this.promptFor = this.near.game
        this.promptBest = bestFor(this.near.game)
      }
      prompt = { title: this.near.title, best: this.promptBest.best, stars: this.promptBest.stars }
    } else this.promptFor = null
    return { hint: 'Left stick: walk  ·  Right stick: orbit / tilt  ·  L1 / R1: zoom  ·  Triangle: follow or overview', prompt }
  }
}
