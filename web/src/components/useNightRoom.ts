import { useEffect } from 'react'
import './room.css'

/** Put the page in the evening room (see room.css) for as long as it is mounted. */
export function useNightRoom() {
  useEffect(() => {
    document.documentElement.dataset.room = 'night'
    return () => {
      delete document.documentElement.dataset.room
    }
  }, [])
}
