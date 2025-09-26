import { motion } from 'framer-motion';
import styles from './library-upload-center.module.css';

interface Props {
  selectedProjectId: number | null;
}

export function LibraryUploadCenter({ selectedProjectId }: Props) {
  const disabled = selectedProjectId === null;

  return (
    <section className={styles.wrapper}>
      <header>
        <h2>导入文献</h2>
        <p>支持 PDF 上传、Zotero 导出、DOI 批量导入，所有任务将后台运行并显示进度。</p>
      </header>
      <div className={styles.actions}>
        <motion.label
          className={styles.action}
          whileHover={disabled ? undefined : { scale: 1.02 }}
          style={{ opacity: disabled ? 0.4 : 1 }}
        >
          <input type="file" accept="application/pdf" disabled={disabled} hidden />
          <span>上传 PDF</span>
        </motion.label>
        <motion.button
          className={styles.action}
          whileHover={disabled ? undefined : { scale: 1.02 }}
          disabled={disabled}
        >
          导入 DOI 列表
        </motion.button>
        <motion.button
          className={styles.action}
          whileHover={disabled ? undefined : { scale: 1.02 }}
          disabled={disabled}
        >
          上传 Zotero 文件
        </motion.button>
      </div>
      {disabled && <div className={styles.helper}>请选择项目后再导入文献。</div>}
    </section>
  );
}
