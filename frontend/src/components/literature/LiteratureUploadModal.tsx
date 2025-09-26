import React, { useState } from 'react';
import { Modal, Upload, Tabs, Input, Button, message, Progress, List, Tag, Alert } from 'antd';
import type { UploadFile as AntdUploadFile } from 'antd/es/upload/interface';
import {
  InboxOutlined,
  FileTextOutlined,
  LinkOutlined,
  CloudUploadOutlined,
  FilePdfOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import { motion } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import { apiClient } from '@/services/api/client';
import { literatureAPI, type LiteratureItem } from '@/services/api/literature';

interface UploadModalProps {
  visible: boolean;
  onClose: () => void;
  projectId: number;
  onSuccess?: () => void;
}

interface QueuedUploadFile {
  name: string;
  size: number;
  status: 'waiting' | 'uploading' | 'success' | 'error';
  progress: number;
  message?: string;
}

export const LiteratureUploadModal: React.FC<UploadModalProps> = ({
  visible,
  onClose,
  projectId,
  onSuccess,
}) => {
  const [activeTab, setActiveTab] = useState('pdf');
  const [uploadFiles, setUploadFiles] = useState<QueuedUploadFile[]>([]);
  const [dois, setDois] = useState('');
  const [zoteroFile, setZoteroFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: true,
    onDrop: (files) => {
      void handlePDFDrop(files);
    },
  });

  async function handlePDFDrop(files: File[]) {
    if (!projectId) {
      void message.warning('请先选择项目再上传文献');
      return;
    }
    const newFiles: QueuedUploadFile[] = files.map((file) => ({
      name: file.name,
      size: file.size,
      status: 'waiting' as const,
      progress: 0,
    }));

    setUploadFiles((prev) => [...prev, ...newFiles]);

    // 批量上传
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const fileIndex = uploadFiles.length + i;

      try {
        setUploadFiles((prev) =>
          prev.map((f, idx) => (idx === fileIndex ? { ...f, status: 'uploading' } : f))
        );

        const formData = new FormData();
        formData.append('file', file);
        formData.append('project_id', projectId.toString());

        await apiClient.post<{ success: boolean; data: LiteratureItem }>(
          '/api/literature/upload',
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
            onUploadProgress: (progressEvent) => {
              if (!progressEvent.total) return;
              const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
              setUploadFiles((prev) =>
                prev.map((f, idx) => (idx === fileIndex ? { ...f, progress } : f))
              );
            }
          }
        );

        setUploadFiles((prev) =>
          prev.map((f, idx) =>
            idx === fileIndex ? { ...f, status: 'success', progress: 100 } : f
          )
        );

        void message.success(`${file.name} 上传成功`);
      } catch (error) {
        setUploadFiles((prev) =>
          prev.map((f, idx) =>
            idx === fileIndex
              ? {
                  ...f,
                  status: 'error',
                  message: '上传失败',
                }
              : f
          )
        );
        void message.error(`${file.name} 上传失败`);
      }
    }

    onSuccess?.();
  }

  async function handleDOIImport() {
    if (!projectId) {
      void message.warning('请先选择项目再导入DOI');
      return;
    }
    const doiList = dois.split('\n')
      .map(d => d.trim())
      .filter(d => d && (d.startsWith('10.') || d.includes('doi.org')));

    if (doiList.length === 0) {
      void message.warning('请输入有效的DOI');
      return;
    }

    setIsProcessing(true);

    try {
      const searchResponse = await literatureAPI.searchWithAI({
        query: doiList.join(' '),
        project_id: projectId,
        max_results: doiList.length,
      });

      const papers = searchResponse?.papers ?? [];

      if (papers.length === 0) {
        void message.info('未检索到匹配的文献');
        return;
      }

      const normalizeString = (value: unknown): string => (typeof value === 'string' ? value : '');
      const normalizeNumber = (value: unknown): number | undefined => {
        if (typeof value === 'number') return Number.isFinite(value) ? value : undefined;
        if (typeof value === 'string') {
          const parsed = Number.parseInt(value, 10);
          return Number.isFinite(parsed) ? parsed : undefined;
        }
        return undefined;
      };

      const normalizeAuthors = (value: unknown): string[] => {
        if (Array.isArray(value)) {
          return value
            .filter((author): author is string => typeof author === 'string')
            .map((author) => author.trim())
            .filter(Boolean);
        }
        if (typeof value === 'string') {
          return value
            .split(',')
            .map((author) => author.trim())
            .filter(Boolean);
        }
        return [];
      };

      const literaturePayload = papers.map((paper) => ({
        title: normalizeString(paper.title),
        authors: normalizeAuthors(paper.authors),
        abstract: normalizeString(paper.abstract),
        journal: normalizeString(paper.journal),
        publication_year: normalizeNumber(paper.year),
        doi: normalizeString(paper.doi),
        source_platform: 'semantic_scholar',
        source_url: normalizeString(paper.url),
        citation_count: normalizeNumber(paper.citations) ?? 0,
        quality_score: 0,
      }));

      const batchAddResponse = await literatureAPI.batchAdd(projectId, literaturePayload);

      if (batchAddResponse?.message) {
        void message.success(batchAddResponse.message);
      } else {
        void message.success(`成功添加 ${batchAddResponse?.added_count ?? literaturePayload.length} 篇文献`);
      }

      if (batchAddResponse?.skipped_count) {
        void message.warning(`跳过 ${batchAddResponse.skipped_count} 篇重复文献`);
      }

      setDois('');
      onSuccess?.();
    } catch (error) {
      void message.error('DOI导入失败');
    } finally {
      setIsProcessing(false);
    }
  }

  async function handleZoteroImport() {
    if (!projectId) {
      void message.warning('请先选择项目再导入Zotero文件');
      return;
    }
    if (!zoteroFile) {
      void message.warning('请选择Zotero导出文件');
      return;
    }

    setIsProcessing(true);

    try {
      const formData = new FormData();
      formData.append('file', zoteroFile);
      formData.append('project_id', projectId.toString());
      formData.append('import_type', 'zotero');

      const { data } = await apiClient.post<{ imported_count?: number; message?: string }>(
        '/api/literature/upload',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );

      const importedCount = data.imported_count ?? 0;
      void message.success(data.message || `成功导入 ${importedCount} 篇文献`);
      setZoteroFile(null);
      onSuccess?.();
    } catch (error) {
      void message.error('Zotero导入失败');
    } finally {
      setIsProcessing(false);
    }
  }

  const zoteroUploadList: AntdUploadFile[] = zoteroFile
    ? [
        {
          uid: '-1',
          name: zoteroFile.name,
          status: 'done',
          size: zoteroFile.size,
        },
      ]
    : [];

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const getStatusIcon = (status: QueuedUploadFile['status']) => {
    switch (status) {
      case 'success':
        return <CheckCircleOutlined className="text-green-500" />;
      case 'error':
        return <CloseCircleOutlined className="text-red-500" />;
      case 'uploading':
        return <LoadingOutlined className="text-blue-500" />;
      default:
        return <CloudUploadOutlined className="text-gray-400" />;
    }
  };

  return (
    <Modal
      title="导入文献"
      open={visible}
      onCancel={onClose}
      width={800}
      footer={null}
      className="literature-upload-modal"
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'pdf',
            label: (
              <span>
                <FilePdfOutlined /> PDF上传
              </span>
            ),
            children: (
              <div className="space-y-4">
                <div
                  {...getRootProps()}
                  className={`
                    border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
                    transition-all duration-200
                    ${isDragActive
                      ? 'border-blue-400 bg-blue-50'
                      : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
                    }
                  `}
                >
                  <input {...getInputProps()} />
                  <InboxOutlined className="text-5xl text-gray-400 mb-4" />
                  <p className="text-lg text-gray-600 mb-2">
                    {isDragActive ? '释放文件以上传' : '拖拽PDF文件到此处，或点击选择文件'}
                  </p>
                  <p className="text-sm text-gray-400">支持批量上传，单个文件最大50MB</p>
                </div>

                {/* 上传列表 */}
                {uploadFiles.length > 0 && (
                  <div className="mt-4">
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-medium">上传列表</span>
                      <Button
                        size="small"
                        onClick={() => setUploadFiles([])}
                        disabled={uploadFiles.some(f => f.status === 'uploading')}
                      >
                        清空列表
                      </Button>
                    </div>
                    <List
                      dataSource={uploadFiles}
                      renderItem={(file, index) => (
                        <List.Item>
                          <motion.div
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: index * 0.05 }}
                            className="w-full"
                          >
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                {getStatusIcon(file.status)}
                                <span className="text-sm font-medium">{file.name}</span>
                                <Tag>{formatFileSize(file.size)}</Tag>
                              </div>
                              {file.status === 'error' && (
                                <span className="text-xs text-red-500">{file.message}</span>
                              )}
                            </div>
                            {file.status === 'uploading' && (
                              <Progress
                                percent={file.progress}
                                size="small"
                                strokeColor="#1890ff"
                              />
                            )}
                          </motion.div>
                        </List.Item>
                      )}
                    />
                  </div>
                )}
              </div>
            ),
          },
          {
            key: 'doi',
            label: (
              <span>
                <LinkOutlined /> DOI导入
              </span>
            ),
            children: (
              <div className="space-y-4">
                <Alert
                  message="DOI导入说明"
                  description="输入DOI号码，每行一个。支持完整URL或仅DOI号码（如：10.1038/nature12373）"
                  type="info"
                  showIcon
                />

                <div>
                  <div className="mb-2 font-medium">输入DOI列表：</div>
                  <Input.TextArea
                    value={dois}
                    onChange={(e) => setDois(e.target.value)}
                    placeholder={`10.1038/nature12373
10.1126/science.1234567
https://doi.org/10.1016/j.cell.2020.01.001`}
                    rows={10}
                    disabled={isProcessing}
                  />
                  <div className="text-xs text-gray-500 mt-1">
                    已输入 {dois.split('\n').filter(d => d.trim()).length} 个DOI
                  </div>
                </div>

                <Button
                  type="primary"
                  onClick={handleDOIImport}
                  loading={isProcessing}
                  disabled={!dois.trim()}
                  block
                >
                  开始导入
                </Button>
              </div>
            ),
          },
          {
            key: 'zotero',
            label: (
              <span>
                <FileTextOutlined /> Zotero导入
              </span>
            ),
            children: (
              <div className="space-y-4">
                <Alert
                  message="Zotero导入步骤"
                  description={
                    <ol className="list-decimal list-inside space-y-1 mt-2">
                      <li>在Zotero中选择要导出的文献</li>
                      <li>点击 文件 → 导出文献库</li>
                      <li>
                        选择格式为 <code>Zotero RDF</code> 或 <code>BibTeX</code>
                      </li>
                      <li>
                        勾选 <code>导出文件</code> 选项（如需要PDF）
                      </li>
                      <li>上传导出的文件</li>
                    </ol>
                  }
                  type="info"
                  showIcon
                />

                <Upload.Dragger
                  accept=".rdf,.bib,.bibtex,.json"
                  beforeUpload={(file) => {
                    setZoteroFile(file);
                    return false;
                  }}
                  maxCount={1}
                  onRemove={() => setZoteroFile(null)}
                  fileList={zoteroUploadList}
                >
                  <p className="ant-upload-drag-icon">
                    <InboxOutlined className="text-4xl text-gray-400" />
                  </p>
                  <p className="ant-upload-text">点击或拖拽Zotero导出文件到此处</p>
                  <p className="ant-upload-hint">支持 .rdf, .bib, .bibtex, .json 格式</p>
                </Upload.Dragger>

                <Button
                  type="primary"
                  onClick={handleZoteroImport}
                  loading={isProcessing}
                  disabled={!zoteroFile}
                  block
                >
                  开始导入
                </Button>
              </div>
            ),
          },
        ]}
      />
    </Modal>
  );
};
