// The on-screen UI. Games and the lobby hand over a plain `ui` object each frame and this file draws it:
//   { hint, chips:[{k, v, tone}], banner:{title, lines[]}|null, result:{...}|null, prompt:{...}|null, scores:[...]|null, label }
// Elements are only rewritten when their content changes, so the CSS animations (pop-ins, stars) play once.
import './overlay.css'
import { MAX_STARS } from './scores.js'
import { audio } from './audio.js'

const STAR = '<svg viewBox="0 0 24 24"><path d="M12 2.4l2.8 6 6.5.8-4.8 4.5 1.3 6.5L12 16.9l-5.8 3.3 1.3-6.5L2.7 9.2l6.5-.8z"/></svg>'
const CROSS = '<svg class="btn" viewBox="0 0 40 40"><circle cx="20" cy="20" r="18" fill="#2b5cd6" stroke="#9db8ff" stroke-width="2"/><path d="M13 13l14 14M27 13L13 27" stroke="#dbe6ff" stroke-width="4" stroke-linecap="round"/></svg>'

export const stars = (n, max = MAX_STARS) =>
  `<span class="stars">${Array.from({ length: max }, (_, i) => `<i class="${i < n ? 'on' : ''}" style="--i:${i}">${STAR}</i>`).join('')}</span>`

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])

const root = document.getElementById('ui')
root.innerHTML = `
  <div id="brand" class="glass"><b>Stick Drift</b><span>Lobby</span></div>
  <div id="scores" class="glass"></div>
  <div id="chips"></div>
  <div id="banner"></div>
  <div id="result" ></div>
  <div id="prompt"></div>
  <div id="hint" class="glass"></div>
  <button id="mute" class="glass" title="Sound on/off (M)" aria-label="Toggle sound"></button>`
const el = Object.fromEntries(['brand', 'scores', 'chips', 'banner', 'result', 'prompt', 'hint'].map((id) => [id, document.getElementById(id)]))
const label = document.getElementById('label')
const memo = {}
const set = (key, sig, render) => {
  if (memo[key] !== sig) {
    memo[key] = sig
    render(el[key])
  }
}

export function render(ui, inGame) {
  el.brand.style.display = inGame ? 'none' : ''
  el.scores.style.display = !inGame && ui.scores ? '' : 'none'

  set('chips', JSON.stringify(ui.chips || []), (e) => {
    e.innerHTML = (ui.chips || []).map((c) => `<div class="chip glass ${c.tone || ''}"><span class="k">${esc(c.k)}</span><span class="v">${esc(c.v)}</span></div>`).join('')
  })

  const b = ui.banner
  set('banner', JSON.stringify(b || null), (e) => {
    if (!b) return (e.innerHTML = '')
    const number = !b.lines?.length && b.title.length <= 4 // "3", "2", "1", "GO!"
    e.innerHTML = number
      ? `<div class="num">${esc(b.title)}</div>`
      : `<div class="card glass"><div class="t">${esc(b.title)}</div>${(b.lines || []).map((l) => `<p>${esc(l)}</p>`).join('')}</div>`
    e.classList.remove('pop')
    void e.offsetWidth
    e.classList.add('pop')
  })

  const r = ui.result
  set('result', r ? JSON.stringify({ ...r, secs: 0 }) : 'null', (e) => {
    if (!r) return (e.innerHTML = '')
    e.innerHTML = `<div class="rc glass">
      <h2>${esc(r.title)}</h2>
      <ul>${r.rows.map((x) => `<li><span>${esc(x.k)}</span><b>${esc(x.v)}</b></li>`).join('')}</ul>
      <div class="score"><small>SCORE</small><strong>${r.score}</strong></div>
      ${stars(r.stars)}
      <div class="badge ${r.isNewBest ? 'new' : ''}">${r.isNewBest ? 'NEW HIGH SCORE!' : 'High score ' + r.best}</div>
      <div class="back"><span></span><div class="bar"><i></i></div></div>
    </div>`
  })
  if (r) {
    const span = el.result.querySelector('.back span'), bar = el.result.querySelector('.bar i')
    if (span) {
      span.textContent = `Back to the lobby in ${Math.ceil(r.secs)}s  ·  press O to go now`
      bar.style.width = Math.max(0, Math.min(100, (r.secs / r.total) * 100)) + '%'
    }
  }

  const p = ui.prompt
  set('prompt', JSON.stringify(p || null), (e) => {
    e.innerHTML = p
      ? `<div class="pc glass ${p.exit ? 'exit' : ''}">${CROSS}<div><h3>${esc(p.title)}${p.best ? ' ' + stars(p.stars) : ''}</h3><p>${
          p.exit ? 'Press <b>X</b> to leave and end your session' : `Press <b>X</b> to play${p.best ? ' · High score ' + p.best : ''}`
        }</p></div></div>`
      : ''
  })

  set('scores', JSON.stringify(ui.scores || null), (e) => {
    e.innerHTML = ui.scores
      ? `<h4>High scores</h4>` +
        ui.scores.map((s) => `<div class="row"><span>${esc(s.title)}</span><span>${s.best ? `<b>${s.best}</b>` : ''}${stars(s.stars)}</span></div>`).join('')
      : ''
  })

  set('hint', ui.hint || '', (e) => (e.innerHTML = ui.hint || ''))

  const l = ui.label || ''
  if (label._t !== l) {
    label._t = l
    label.textContent = l
  }
  return label
}

// speaker button (also toggled with the M key)
const SPEAKER = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9v6h4l5 4V5L8 9z" fill="currentColor"/>'
const muteBtn = document.getElementById('mute')
muteBtn.addEventListener('click', () => audio.toggleMute())
audio.onMute((m) => {
  muteBtn.innerHTML = SPEAKER + (m ? '<path d="M17 9l5 6M22 9l-5 6"/>' : '<path d="M16.5 8.5a5 5 0 010 7M19 6a8.5 8.5 0 010 12"/>') + '</svg>'
  muteBtn.classList.toggle('off', m)
})
