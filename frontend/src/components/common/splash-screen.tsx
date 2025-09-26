import { motion } from 'framer-motion';
import styles from './splash-screen.module.css';

const shimmer = {
  animate: {
    backgroundPosition: ['0% 50%', '100% 50%']
  }
};

export function SplashScreen({ message }: { message?: string }) {
  return (
    <div className={styles.wrapper}>
      <motion.div className={styles.logo} animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 12 }} />
      <motion.div
        className={styles.progress}
        variants={shimmer}
        animate="animate"
        transition={{ duration: 3.4, repeat: Infinity, ease: 'linear' }}
      />
      {message && <p className={styles.message}>{message}</p>}
    </div>
  );
}
