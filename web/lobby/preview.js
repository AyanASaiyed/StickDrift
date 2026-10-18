// A live, self-playing view of the 3D lobby for the dashboard. It renders the real lobby scene (same Hub as the game)
// and walks grandma around the paths from pad to pad, so the dashboard shows exactly what the resident will step into.
// It is cheap on purpose: 30 fps, paused while off-screen or in a background tab, one still frame for reduced-motion users.
import * as THREE from 'three'
import { Hub } from './hub.js'

// Where grandma wanders: along the three paths from the plaza to each pad and back, pausing at each pad.
const ROUTE = [
  [0, -3.6, 0], [-3.4, -1.2, 0], [-6.0, 0.55, 1.4], [-3.4, -1.2, 0], [0, -3.6, 0],
  [0, 0.4, 0], [0, 2.5, 1.4], [0, 0.4, 0], [0, -3.6, 0],
  [3.4, -2.2, 0], [5.6, -0.9, 1.4], [3.4, -2.2, 0], [0, -3.6, 0.6],
]

export function mountPreview(canvas, { onFrame } = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'low-power' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFShadowMap
  renderer.toneMapping = THREE.AgXToneMapping
  renderer.toneMappingExposure = 0.8

  const hub = new Hub()
  hub.follow = false // the whole garden in view
  hub.tilt = 0.62
  hub.grandma.root.position.set(ROUTE[0][0], ROUTE[0][1], 0)

  const resize = () => {
    const { clientWidth: w, clientHeight: h } = canvas
    if (!w || !h) return
    renderer.setSize(w, h, false)
    hub.resize(w / h)
  }
  const ro = new ResizeObserver(resize)
  ro.observe(canvas)
  resize()

  const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  let visible = true
  const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting))
  io.observe(canvas)

  let stop = false, last = performance.now(), t = 0, leg = 1, wait = 0, told = false
  const pad = { move: [0, 0, 0], look: [0, 0], zoom: 0, cam: false, enter: false, back: false, source: 'preview' }

  const frame = (now) => {
    if (stop) return
    requestAnimationFrame(frame)
    const dt = Math.min((now - last) / 1000, 0.1)
    if (dt < 1 / 32 && told) return // ~30 fps is plenty for a preview
    last = now
    if (!visible || document.hidden) return
    t += dt
    const p = hub.grandma.root.position
    const [tx, ty, pause] = ROUTE[leg]
    const dx = tx - p.x, dy = ty - p.y
    const d = Math.hypot(dx, dy)
    if (wait > 0) {
      wait -= dt
      pad.move = [0, 0, 0]
    } else if (d < 0.25) {
      wait = pause
      leg = (leg + 1) % ROUTE.length
      pad.move = [0, 0, 0]
    } else pad.move = [dx / d, dy / d, 0.85]
    hub.yaw = 0.16 * Math.sin(t * 0.12) // a slow sway so it feels alive
    hub.update(dt, pad)
    renderer.render(hub.scene, hub.camera)
    if (!told) {
      told = true
      onFrame?.()
    }
  }
  if (still) {
    requestAnimationFrame(() => {
      hub.update(0.016, pad)
      renderer.render(hub.scene, hub.camera)
      onFrame?.()
    })
  } else requestAnimationFrame(frame)

  return {
    dispose() {
      stop = true
      ro.disconnect()
      io.disconnect()
      renderer.dispose()
      renderer.forceContextLoss()
    },
  }
}
