import { useParams } from 'react-router-dom';
import { TasksPage } from '@/pages/tasks/tasks-page';

export const ProjectTasksPage = () => {
  const { projectId } = useParams();
  const numericProjectId = Number(projectId);
  if (!projectId || Number.isNaN(numericProjectId)) {
    return null;
  }
  return <TasksPage projectId={numericProjectId} />;
};

export default ProjectTasksPage;
