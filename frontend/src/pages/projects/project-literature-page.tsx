import { useParams } from 'react-router-dom';
import { LibraryPage } from '@/pages/library/library-page';

export const ProjectLiteraturePage = () => {
  const { projectId } = useParams();
  const numericProjectId = Number(projectId);
  if (!projectId || Number.isNaN(numericProjectId)) {
    return null;
  }
  return <LibraryPage projectId={numericProjectId} lockProject />;
};

export default ProjectLiteraturePage;
