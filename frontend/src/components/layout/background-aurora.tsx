import { memo } from 'react';
import { motion } from 'framer-motion';
import styles from './background-aurora.module.css';

const blobs = [
  { id: 'blob-1', x: '10%', y: '15%', scale: 1.4, color: 'rgba(59,130,246,0.32)' },
  { id: 'blob-2', x: '70%', y: '25%', scale: 1.1, color: 'rgba(251,191,36,0.26)' },
  { id: 'blob-3', x: '40%', y: '70%', scale: 1.6, color: 'rgba(236,72,153,0.28)' }
];

export const BackgroundAurora = memo(function BackgroundAurora() {
  return (
    <div className={styles.canvas} aria-hidden>
      {blobs.map((blob) => (
        <motion.span
          key={blob.id}
          className={styles.blob}
          style={{ background: blob.color, left: blob.x, top: blob.y }}
          animate={{
            scale: [blob.scale, blob.scale * 1.08, blob.scale * 0.92],
            filter: ['blur(120px)', 'blur(140px)', 'blur(110px)']
          }}
          transition={{
            duration: 18,
            repeat: Infinity,
            repeatType: 'mirror'
          }}
        />
      ))}
    </div>
  );
});
