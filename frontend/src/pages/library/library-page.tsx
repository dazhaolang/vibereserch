import { useCallback, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Empty, Spin } from 'antd';
import { LibraryShell } from '@/components/library-shell/LibraryShell';
import { LibraryOverview } from '@/components/library-overview/LibraryOverview';
import { useLibraryStore } from '@/stores/library.store';
import styles from './library-page.module.css';

interface LibraryPageProps {
  projectId?: number;
  lockProject?: boolean;
}

export function LibraryPage({ projectId, lockProject = false }: LibraryPageProps) {
  const navigate = useNavigate();
  const {
    loadCollections,
    loadItems,
    isLoading,
    isProjectsLoading,
    error,
    items,
    projects,
    selectedProjectId,
    setSelectedProject,
  } = useLibraryStore((state) => ({
    loadCollections: state.loadCollections,
    loadItems: state.loadItems,
    isLoading: state.isLoading,
    isProjectsLoading: state.isProjectsLoading,
    error: state.error,
    items: state.items,
    projects: state.projects,
    selectedProjectId: state.selectedProjectId,
    setSelectedProject: state.setSelectedProject,
  }));

  useEffect(() => {
    void loadCollections();
  }, [loadCollections]);

  useEffect(() => {
    if (projectId === undefined) {
      return;
    }
    if (selectedProjectId === projectId) {
      return;
    }
    if (projects.some((project) => project.id === projectId)) {
      setSelectedProject(projectId);
    }
  }, [projectId, projects, selectedProjectId, setSelectedProject]);

  useEffect(() => {
    if (selectedProjectId) {
      void loadItems(true);
    }
  }, [selectedProjectId, loadItems]);

  const visibleProjects = useMemo(() => {
    if (lockProject && projectId) {
      return projects.filter((project) => project.id === projectId);
    }
    return projects;
  }, [projects, lockProject, projectId]);

  const handleSelectProject = useCallback((id: number | null) => {
    if (lockProject && projectId && id !== projectId) {
      return;
    }
    setSelectedProject(id);
  }, [lockProject, projectId, setSelectedProject]);

  const handleCreateLibrary = useCallback(() => {
    navigate('/projects');
  }, [navigate]);

  const handleRefresh = useCallback(() => {
    void loadCollections();
  }, [loadCollections]);

  const showShell = Boolean(selectedProjectId);

  return (
    <div className={styles.wrapper}>
      {error ? (
        <Alert
          type="error"
          message="加载文献库失败"
          description={error}
          showIcon
          style={{ marginBottom: 16 }}
        />
      ) : null}

      {!lockProject ? (
        <LibraryOverview
          projects={visibleProjects}
          selectedProjectId={selectedProjectId}
          isLoading={isProjectsLoading && projects.length === 0}
          isRefreshing={isProjectsLoading && projects.length > 0}
          onSelect={handleSelectProject}
          onCreateNew={handleCreateLibrary}
          onRefresh={handleRefresh}
        />
      ) : null}

      {lockProject && projectId && visibleProjects.length === 0 && !isProjectsLoading ? (
        <Alert
          type="warning"
          showIcon
          message="未找到指定的文献库"
          description="请检查项目 ID 是否正确，或返回项目列表重新进入。"
          style={{ marginBottom: 16 }}
        />
      ) : null}

      {showShell ? (
        <section className={styles.shellSection}>
          <LibraryShell />
          {isLoading && items.length === 0 ? (
            <div className={styles.loadingOverlay}>
              <Spin size="large" />
            </div>
          ) : null}
        </section>
      ) : !isProjectsLoading ? (
        <div className={styles.emptyState}>
          <Empty
            description="请选择一个文献库以查看详情"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </div>
      ) : null}
    </div>
  );
}

export default LibraryPage;
