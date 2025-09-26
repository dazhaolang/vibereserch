import { useParams } from 'react-router-dom';
import ResearchWorkspace from '@/pages/workspace/ResearchWorkspace';

export const ProjectWorkspacePage = () => {
  const { projectId } = useParams();
  const numericProjectId = Number(projectId);
  if (!projectId || Number.isNaN(numericProjectId)) {
    return null;
  }
  return <ResearchWorkspace projectId={numericProjectId} hideProjectSelector />;
};

export default ProjectWorkspacePage;
