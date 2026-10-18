import { useRef, type CSSProperties, type ReactNode } from 'react'
import { Link } from 'react-router'
import { ArrowRight, ArrowUpRight, Plant, ShieldCheck } from '@phosphor-icons/react'
import { Headline } from '../components/Headline'
import './Auth.css'
import './Welcome.css'

const GAMES = ['Apple Picking', 'Harbour Fishing', 'Rat Catching']

/** A role card: nested bezel, border that lights up under the cursor, and a beam running round the edge. */
function RoleCard({
  tone,
  icon,
  badge,
  title,
  text,
  primary,
  secondary,
  delay,
}: {
  tone: 'resident' | 'care'
  icon: ReactNode
  badge: string
  title: string
  text: string
  primary: { to: string; label: string }
  secondary: { to: string; label: string }
  delay: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  return (
    <div
      ref={ref}
      className={`au-card wl-role ${tone === 'care' ? 'wl-care' : ''}`}
      data-in
      style={{ '--d': delay } as CSSProperties}
      onPointerMove={(e) => {
        const r = ref.current!.getBoundingClientRect()
        ref.current!.style.setProperty('--mx', `${e.clientX - r.left}px`)
        ref.current!.style.setProperty('--my', `${e.clientY - r.top}px`)
      }}
    >
      <div className="au-core">
        <p className="wl-badge">
          {icon}
          {badge}
        </p>
        <h2>{title}</h2>
        <p className="au-sub">{text}</p>
        <Link className="au-btn wl-btn" to={primary.to}>
          {primary.label}
          <span className="arrow" aria-hidden>
            <ArrowUpRight size={22} weight="light" />
          </span>
        </Link>
        <Link className="au-swap" to={secondary.to}>
          {secondary.label}
          <span aria-hidden>
            <ArrowRight size={18} weight="light" />
          </span>
        </Link>
      </div>
    </div>
  )
}

export default function Welcome() {
  const frame = useRef<HTMLDivElement>(null)
  return (
    <main className="au">
      <div className="au-orbs" aria-hidden>
        <i />
        <i />
      </div>

      <div className="au-grid">
        <section
          className="au-stage"
          aria-label="About Stick Drift"
          onPointerMove={(e) => {
            const f = frame.current
            if (!f) return
            const r = f.getBoundingClientRect()
            f.style.setProperty('--ry', `${((e.clientX - (r.left + r.width / 2)) / window.innerWidth) * 9}deg`)
            f.style.setProperty('--rx', `${(-(e.clientY - (r.top + r.height / 2)) / window.innerHeight) * 7}deg`)
          }}
          onPointerLeave={() => {
            frame.current?.style.setProperty('--rx', '0deg')
            frame.current?.style.setProperty('--ry', '0deg')
          }}
        >
          <Headline text="Games you play with *two thumbs.*" />
          <p className="au-lede" data-in style={{ '--d': 4 } as CSSProperties}>
            Short games for a PS5 controller, with one stick for each hand. Pick one and play at your own pace. Your care
            team can see how each visit went.
          </p>
          <div ref={frame} className="au-frame" data-in style={{ '--d': 6 } as CSSProperties}>
            <div>
              <img
                src="/lobby/lobby.jpg"
                alt="The game lobby: a garden with three glowing game pads and a grandmother walking between them"
                width={1280}
                height={720}
              />
              {GAMES.map((g) => (
                <span key={g} className="tag">
                  <i /> {g}
                </span>
              ))}
            </div>
          </div>
        </section>

        <div className="wl-side">
          <section className="wl-roles" aria-label="Choose how to continue">
            <RoleCard
              tone="resident"
              icon={<Plant size={20} weight="light" aria-hidden />}
              badge="Resident"
              title="I’m here to play"
              text="Open the lobby and pick a game."
              primary={{ to: '/login', label: 'Resident log in' }}
              secondary={{ to: '/signup', label: 'New here? Create an account' }}
              delay={2}
            />
            <RoleCard
              tone="care"
              icon={<ShieldCheck size={20} weight="light" aria-hidden />}
              badge="Care team"
              title="I’m on the care team"
              text="See residents’ results, trends and anything worth checking in on."
              primary={{ to: '/caregiver/login', label: 'Care team log in' }}
              secondary={{ to: '/caregiver/signup', label: 'New to the team? Register' }}
              delay={3}
            />
          </section>
        </div>
      </div>

    </main>
  )
}
