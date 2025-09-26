import styles from './library-search-panel.module.css';
import { motion } from 'framer-motion';
import type { ProjectSummary } from '@/services/api/project';

interface Props {
  projects: ProjectSummary[];
  selectedProjectId: number | null;
  onProjectChange: (id: number | null) => void;
  keyword: string;
  onKeywordChange: (value: string) => void;
}

export function LibrarySearchPanel({ projects, selectedProjectId, onProjectChange, keyword, onKeywordChange }: Props) {
  return (
    <section className={styles.panel}>
      <div className={styles.fieldGroup}>
        <label htmlFor="project">选择项目</label>
        <select
          id="project"
          value={selectedProjectId ?? ''}
          onChange={(event) => {
            const value = event.target.value;
            onProjectChange(value ? Number(value) : null);
          }}
        >
          <option value="">请选择项目</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </div>
      <div className={styles.fieldGroup}>
        <label htmlFor="keyword">关键词</label>
        <input
          id="keyword"
          placeholder="输入文献标题、作者或关键词"
          value={keyword}
          onChange={(event) => onKeywordChange(event.target.value)}
        />
      </div>
      <motion.button whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }} onClick={() => onProjectChange(selectedProjectId ?? null)}>
        搜索文献
      </motion.button>
    </section>
  );
}
