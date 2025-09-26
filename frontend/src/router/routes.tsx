import { lazy } from 'react';
import type { ReactElement } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { ResearchConsole } from '@/pages/research/research-console';
import { DashboardPage } from '@/pages/dashboard/dashboard-page';
import { LandingPage } from '@/pages/landing/landing-page';
import { LibraryPage } from '@/pages/library/library-page';
import { TasksPage } from '@/pages/tasks/tasks-page';
import { SettingsPage } from '@/pages/settings/settings-page';
import { PersonalCenterPage } from '@/pages/profile/personal-center-page';
import ResearchWorkspace from '@/pages/workspace/ResearchWorkspace';
import { ProjectListPage } from '@/pages/projects/project-list-page';
import { ProjectLayout } from '@/pages/projects/project-layout';
import { ProjectOverviewPage } from '@/pages/projects/project-overview-page';
import { ProjectWorkspacePage } from '@/pages/projects/project-workspace-page';
import { ProjectLiteraturePage } from '@/pages/projects/project-literature-page';
import { ProjectTasksPage } from '@/pages/projects/project-tasks-page';
import { ProjectSettingsPage } from '@/pages/projects/project-settings-page';

const AuthLanding = lazy(() => import('@/pages/auth/auth-landing'));

export function routes(rootShell: ReactElement) {
  return createBrowserRouter([
    {
      element: rootShell,
      children: [
        { index: true, element: <LandingPage /> },
        { path: '/dashboard', element: <DashboardPage /> },
        { path: '/projects', element: <ProjectListPage /> },
        {
          path: '/projects/:projectId',
          element: <ProjectLayout />,
          children: [
            { index: true, element: <Navigate to="overview" replace /> },
            { path: 'overview', element: <ProjectOverviewPage /> },
            { path: 'workspace', element: <ProjectWorkspacePage /> },
            { path: 'literature', element: <ProjectLiteraturePage /> },
            { path: 'tasks', element: <ProjectTasksPage /> },
            { path: 'settings', element: <ProjectSettingsPage /> },
          ],
        },
        { path: '/workspace', element: <ResearchWorkspace /> },
        { path: '/library', element: <LibraryPage /> },
        { path: '/research', element: <ResearchConsole /> },
        { path: '/tasks', element: <TasksPage /> },
        { path: '/profile', element: <PersonalCenterPage /> },
        { path: '/settings', element: <SettingsPage /> },
      ]
    },
    {
      path: '/auth',
      element: <AuthLanding />
    }
  ]);
}
