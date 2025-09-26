import { useThemeMode } from '@/contexts/theme-context';
import { MotionFade } from '@/animations/motion-fade';
import styles from './settings-page.module.css';

export function SettingsPage() {
  const { mode, setMode } = useThemeMode();

  return (
    <MotionFade>
      <section className={styles.panel}>
        <h2>体验设置</h2>
        <div className={styles.section}>
          <h3>主题模式</h3>
          <div className={styles.optionGroup}>
            {['dark', 'light', 'system'].map((item) => (
              <button
                key={item}
                data-active={mode === item}
                onClick={() => setMode(item as typeof mode)}
              >
                {item.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
        <div className={styles.section}>
          <h3>动效偏好</h3>
          <p>后续将支持自定义 Lottie 动画强度、澄清卡倒计时样式等。</p>
        </div>
      </section>
    </MotionFade>
  );
}
