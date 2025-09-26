import { useEffect } from 'react';
import { useSystemStore } from '@/stores/system-store';
import { useAuthStore } from '@/stores/auth-store';
import { fetchUserProfile } from '@/services/api/user';

export function useAppStartup() {
  const { hydrated, setHydrated, setProfile } = useSystemStore();
  const accessToken = useAuthStore((state) => state.accessToken);

  useEffect(() => {
    if (!accessToken) {
      if (!hydrated) {
        // 没有令牌时仍然标记为已初始化，避免重复重定向循环
        setHydrated(true);
      }
      return;
    }

    if (hydrated) {
      return;
    }

    const controller = new AbortController();

    async function bootstrap() {
      try {
        const profile = await fetchUserProfile({ signal: controller.signal });
        setProfile(profile);
      } catch (error) {
        console.warn('Bootstrap user profile failed', error);
      } finally {
        setHydrated(true);
      }
    }

    void bootstrap();

    return () => controller.abort();
  }, [accessToken, hydrated, setHydrated, setProfile]);
}
