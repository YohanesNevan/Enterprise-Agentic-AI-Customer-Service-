import { useState } from 'react'

export function useForm(initial) {
  const [v, setV] = useState(initial)
  const set = (k) => (e) => {
    const t = e.target
    const val = t.type === 'checkbox' ? t.checked : t.value
    setV((o) => ({ ...o, [k]: val }))
  }
  const reset = () => setV(initial)
  return [v, set, reset, setV]
}

export default useForm
