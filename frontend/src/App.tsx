import { Suspense, useEffect } from 'react';
import { Outlet, RouterProvider, useLocation, useNavigate } from 'react-router-dom';
import { routes } from './router/routes';
import { AppLayout } from './components/layout/app-layout';
import { useAppStartup } from './hooks/use-app-startup';
import { SplashScreen } from './components/common/splash-screen';
import { MotionFade } from './animations/motion-fade';
import { useAuthStore } from '@/stores/auth-store';

function RootShell() {
  useAppStartup();
  const navigate = useNavigate();
  const location = useLocation();
  const accessToken = useAuthStore((state) => state.accessToken);

  useEffect(() => {
    const path = location.pathname;
    if (!accessToken && path !== '/auth') {
      navigate('/auth', { replace: true, state: { from: path } });
    } else if (accessToken && path === '/auth') {
      navigate('/', { replace: true });
    }
  }, [accessToken, location.pathname, navigate]);

  return (
    <AppLayout>
      <Suspense fallback={<SplashScreen message="正在加载模块…" />}>        
        <MotionFade>
          <Outlet />
        </MotionFade>
      </Suspense>
    </AppLayout>
  );
}

export default function App() {
  return (
    <Suspense fallback={<SplashScreen message="正在加载应用…" />}>
      <RouterProvider router={routes(<RootShell />)} />
    </Suspense>
  );
}
