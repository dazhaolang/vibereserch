import { useEffect, useState } from 'react';
import { Outlet, useNavigate, useParams } from 'react-router-dom';
import { App } from 'antd';
import { projectAPI } from '@/services/api/project';
import { useAppStore } from '@/stores/app.store';

export const ProjectLayout = () => {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const { projectId } = useParams();
  const numericProjectId = Number(projectId);
  const { currentProject, setCurrentProject } = useAppStore((state) => ({
    currentProject: state.currentProject,
    setCurrentProject: state.setCurrentProject,
  }));
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!projectId || Number.isNaN(numericProjectId)) {
      navigate('/projects', { replace: true });
      return;
    }

    let cancelled = false;
    const ensureProject = async () => {
      if (currentProject && currentProject.id === numericProjectId) {
        return;
      }
      setLoading(true);
      try {
        const project = await projectAPI.getProject(numericProjectId);
        if (!cancelled) {
          setCurrentProject({
            id: project.id,
            title: project.title,
            description: project.description ?? undefined,
            created_at: project.created_at,
            updated_at: project.updated_at ?? undefined,
          });
        }
      } catch (error) {
        console.error('Failed to load project', error);
        if (!cancelled) {
          void message.error('项目不存在或无访问权限');
          navigate('/projects', { replace: true });
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void ensureProject();

    return () => {
      cancelled = true;
      setCurrentProject(null);
    };
  }, [projectId, numericProjectId, setCurrentProject, currentProject, navigate, message]);

  if (!projectId || Number.isNaN(numericProjectId)) {
    return null;
  }

  if (loading && !currentProject) {
    return null;
  }

  return <Outlet />;
};

export default ProjectLayout;
