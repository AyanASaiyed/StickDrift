import type { CSSProperties } from 'react'

/** Headline with the *starred* words in the accent colour; every word rises in on its own beat. */
export function Headline({ text }: { text: string }) {
  let n = 0
  return (
    <h1>
      {text.split(/(\*[^*]+\*)/).map((part, i) => {
        const em = part.startsWith('*')
        return part
          .replace(/\*/g, '')
          .split(' ')
          .filter(Boolean)
          .map((w) => {
            const node = (
              <span key={`${i}-${n}`} className="w" style={{ '--w': n } as CSSProperties}>
                {em ? <em>{w}</em> : w}
                {' '}
              </span>
            )
            n += 1
            return node
          })
      })}
    </h1>
  )
}
