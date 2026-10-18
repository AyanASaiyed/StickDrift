import { useRef, type CSSProperties, type ReactNode } from 'react'
import { Link } from 'react-router'
import { ArrowRight, ArrowUpRight, ChartLineUp, Door, HandPalm, Plant, ShieldCheck } from '@phosphor-icons/react'
import { Headline } from '../components/Headline'
import './Auth.css'
import './Welcome.css'

const GAMES = ['Apple Picking', 'Harbour Fishing', 'Rat Catching']

const STEPS = [
  {
    icon: HandPalm,
    title: 'Two sticks, two hands',
    text: 'Each thumbstick moves one hand, so every game gives both a turn.',
  },
  {
    icon: Door,
    title: 'Short, and easy to stop',
    text: 'A game takes about a minute. Use the door at the edge of the garden to finish whenever you like.',
  },
  {
    icon: ChartLineUp,
    title: 'Your care team can help',
    text: 'Your care team sees how each visit went and anything worth checking in on.',
  },
]

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
          <Headline text="A visit to Mabel’s *garden.*" />
          <p className="au-lede" data-in style={{ '--d': 4 } as CSSProperties}>
            Walk around a little garden with your PS5 controller and pick a game: apple picking, harbour fishing or rat
            catching. It takes a few minutes, and you can rest any time.
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
              text="Step into the garden and take a short visit."
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

      <section className="wl-how" aria-labelledby="wl-how-title">
        <h2 id="wl-how-title" data-in style={{ '--d': 5 } as CSSProperties}>
          How a visit works
        </h2>
        <ol>
          {STEPS.map(({ icon: Icon, title, text }, i) => (
            <li key={title} data-in style={{ '--d': 6 + i } as CSSProperties}>
              <span className="wl-ico" aria-hidden>
                <Icon size={26} weight="light" />
              </span>
              <div>
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </main>
  )
}
