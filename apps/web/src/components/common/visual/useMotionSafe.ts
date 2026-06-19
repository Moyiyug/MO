import { useReducedMotion } from 'motion/react'

export function useMotionSafe() {
  const prefersReducedMotion = useReducedMotion()

  return {
    prefersReducedMotion,
    initial: prefersReducedMotion ? false : { opacity: 0, y: 8 },
    animate: prefersReducedMotion ? undefined : { opacity: 1, y: 0 },
    transition: prefersReducedMotion
      ? undefined
      : { duration: 0.2, ease: 'easeOut' as const },
  }
}
