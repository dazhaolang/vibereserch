import React from 'react';
import { motion } from 'framer-motion';
import styles from './background-aurora.module.css';

interface UnifiedBackgroundProps {
  variant?: 'aurora' | 'gradient' | 'minimal';
  children: React.ReactNode;
  className?: string;
}

export const UnifiedBackground: React.FC<UnifiedBackgroundProps> = ({
  variant = 'gradient',
  children,
  className = ''
}) => {
  const backgroundVariants = {
    aurora: `${styles.canvas} bg-gradient-to-br from-neural-900 via-neural-800 to-primary-900`,
    gradient: 'bg-gradient-to-br from-neural-50 via-neutral-100 to-primary-50',
    minimal: 'bg-neural-50'
  };

  const AuroraEffect = () => (
    <div className={styles.canvas}>
      <motion.div
        className={`${styles.blob} bg-gradient-to-r from-primary-400 to-accent-400 opacity-30`}
        animate={{
          x: [0, 100, 0],
          y: [0, -100, 0],
          scale: [1, 1.2, 1],
        }}
        transition={{
          duration: 20,
          repeat: Infinity,
          ease: "easeInOut"
        }}
        style={{ top: '10%', left: '10%' }}
      />
      <motion.div
        className={`${styles.blob} bg-gradient-to-r from-accent-400 to-primary-400 opacity-20`}
        animate={{
          x: [0, -150, 0],
          y: [0, 120, 0],
          scale: [1.2, 1, 1.2],
        }}
        transition={{
          duration: 25,
          repeat: Infinity,
          ease: "easeInOut",
          delay: 5
        }}
        style={{ top: '60%', right: '10%' }}
      />
      <motion.div
        className={`${styles.blob} bg-gradient-to-r from-primary-300 to-neural-400 opacity-25`}
        animate={{
          x: [0, 80, 0],
          y: [0, -80, 0],
          scale: [1, 1.3, 1],
        }}
        transition={{
          duration: 30,
          repeat: Infinity,
          ease: "easeInOut",
          delay: 10
        }}
        style={{ bottom: '20%', left: '50%' }}
      />
    </div>
  );

  return (
    <div className={`relative min-h-screen ${backgroundVariants[variant]} ${className}`}>
      {variant === 'aurora' && <AuroraEffect />}

      {/* Content overlay with backdrop filter for better readability */}
      <div className={`relative z-10 ${variant === 'aurora' ? 'backdrop-blur-[1px]' : ''}`}>
        {children}
      </div>

      {/* Subtle overlay for better text contrast */}
      {variant === 'aurora' && (
        <div className="absolute inset-0 bg-black/5 pointer-events-none z-[1]" />
      )}
    </div>
  );
};

export default UnifiedBackground;