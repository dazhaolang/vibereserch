import { useEffect } from 'react';
import { Modal } from 'antd';
import { LibraryOverview } from '@/components/library-overview/LibraryOverview';
import { useLibraryStore } from '@/stores/library.store';

interface LibrarySelectorDialogProps {
  open: boolean;
  onClose: () => void;
  onSelect: (projectId: number | null) => void;
  onCreateNew?: () => void;
  title?: string;
}

export function LibrarySelectorDialog({
  open,
  onClose,
  onSelect,
  onCreateNew,
  title = '选择文献库',
}: LibrarySelectorDialogProps) {
  const {
    projects,
    selectedProjectId,
    isProjectsLoading,
    loadCollections,
  } = useLibraryStore((state) => ({
    projects: state.projects,
    selectedProjectId: state.selectedProjectId,
    isProjectsLoading: state.isProjectsLoading,
    loadCollections: state.loadCollections,
  }));

  useEffect(() => {
    if (open) {
      void loadCollections();
    }
  }, [open, loadCollections]);

  return (
    <Modal
      title={title}
      open={open}
      onCancel={onClose}
      footer={null}
      width={860}
      centered
      destroyOnClose={false}
      styles={{
        body: {
          paddingTop: 0,
        },
      }}
    >
      <LibraryOverview
        projects={projects}
        selectedProjectId={selectedProjectId}
        isLoading={isProjectsLoading && projects.length === 0}
        isRefreshing={isProjectsLoading && projects.length > 0}
        onSelect={(projectId) => {
          onSelect(projectId);
          onClose();
        }}
        onCreateNew={onCreateNew}
        onRefresh={() => void loadCollections()}
      />
    </Modal>
  );
}

export type { LibrarySelectorDialogProps };
