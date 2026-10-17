// Controller input. A PS5 / Xbox pad is read through the browser Gamepad API ("standard" mapping):
//   left stick = axes 0/1, right stick = axes 2/3, Cross = button 0, Circle = 1, Triangle = 3, L1 = 4, R1 = 5.
// Keyboard is only a fallback for machines without a pad: WASD = left stick, IJKL = right stick,
// Space = Cross, O/Backspace = Circle, T = Triangle, Q/E = L1/R1.
const DEADZONE = 0.2

function stick(x, y) {
  const m = Math.hypot(x, y)
  if (m < DEADZONE) return [0, 0, 0]
  return [x / m, y / m, (Math.min(m, 1) - DEADZONE) / (1 - DEADZONE)] // direction + magnitude that ramps from 0
}

export class Input {
  constructor() {
    this.keys = new Set()
    this.prev = { enter: false, cam: false, back: false }
    window.addEventListener('keydown', (e) => {
      if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Backspace'].includes(e.code)) e.preventDefault()
      this.keys.add(e.code)
    })
    window.addEventListener('keyup', (e) => this.keys.delete(e.code))
    window.addEventListener('blur', () => this.keys.clear())
  }

  /** -> { move:[dx,dy,mag], look:[x,y], enter, cam, back (one-shot presses), zoom (-1/0/1), source } */
  read() {
    const pads = navigator.getGamepads ? Array.from(navigator.getGamepads()) : []
    const gp = pads.find((p) => p && p.connected)
    let lx = 0, ly = 0, rx = 0, ry = 0, enter = false, cam = false, back = false, l1 = false, r1 = false
    let source = 'none'
    if (gp) {
      source = 'gamepad'
      lx = gp.axes[0] || 0
      ly = -(gp.axes[1] || 0)
      rx = gp.axes[2] || 0
      ry = -(gp.axes[3] || 0)
      const b = (i) => !!(gp.buttons[i] && gp.buttons[i].pressed)
      enter = b(0)
      back = b(1)
      cam = b(3)
      l1 = b(4)
      r1 = b(5)
    }
    const k = this.keys
    const ax = (neg, pos) => (k.has(pos) ? 1 : 0) - (k.has(neg) ? 1 : 0)
    const kx = ax('KeyA', 'KeyD'), ky = ax('KeyS', 'KeyW')
    const kx2 = ax('KeyJ', 'KeyL') + ax('ArrowLeft', 'ArrowRight'), ky2 = ax('KeyK', 'KeyI') + ax('ArrowDown', 'ArrowUp')
    if (kx || ky || kx2 || ky2 || k.has('Space') || k.has('KeyO') || k.has('Backspace') || k.has('KeyT') || k.has('KeyQ') || k.has('KeyE')) {
      if (source === 'none') source = 'keyboard'
      lx = lx || kx
      ly = ly || ky
      rx = rx || kx2
      ry = ry || ky2
      enter = enter || k.has('Space') || k.has('Enter')
      back = back || k.has('KeyO') || k.has('Backspace')
      cam = cam || k.has('KeyT')
      l1 = l1 || k.has('KeyQ')
      r1 = r1 || k.has('KeyE')
    }
    const edge = (now, key) => {
      const e = now && !this.prev[key]
      this.prev[key] = now
      return e
    }
    const look = stick(rx, ry)
    return {
      source,
      raw: [lx, ly, rx, ry], // unprocessed sticks, for the caregiver's live view
      move: stick(lx, ly),
      look: [look[0] * look[2], look[1] * look[2]],
      enter: edge(enter, 'enter'),
      cam: edge(cam, 'cam'),
      back: edge(back, 'back'),
      zoom: (r1 ? 1 : 0) - (l1 ? 1 : 0),
    }
  }
}
