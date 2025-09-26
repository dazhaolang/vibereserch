import { useMemo } from 'react';
import type { ReactNode } from 'react';
import { MotionConfig } from 'framer-motion';

function detectReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch (error) {
    console.warn('matchMedia not available', error);
    return false;
  }
}

export function MotionProvider({ children }: { children: ReactNode }) {
  const prefersReducedMotion = detectReducedMotion();

  const transition = useMemo(
    () => ({
      type: 'spring',
      stiffness: 220,
      damping: 26,
      mass: 0.9
    }),
    []
  );

  return (
    <MotionConfig reducedMotion={prefersReducedMotion ? 'always' : 'never'} transition={transition}>
      {children}
    </MotionConfig>
  );
}
