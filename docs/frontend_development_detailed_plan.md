# 科研文献智能分析平台 - 前端开发详细方案

## 一、项目初始化和基础配置

### 1.1 项目结构
```
frontend/
├── src/
│   ├── components/          # 通用组件
│   │   ├── common/          # 基础UI组件
│   │   ├── interaction/     # 智能交互组件
│   │   ├── literature/      # 文献相关组件
│   │   ├── task/           # 任务相关组件
│   │   └── visualization/   # 可视化组件
│   ├── pages/              # 页面组件
│   │   ├── workspace/      # 研究工作台
│   │   ├── library/        # 文献库
│   │   ├── tasks/          # 任务中心
│   │   ├── dashboard/      # 仪表盘
│   │   └── settings/       # 设置页面
│   ├── services/           # API服务
│   │   ├── api/            # API封装
│   │   ├── websocket/      # WebSocket服务
│   │   └── storage/        # 本地存储
│   ├── stores/             # 状态管理
│   │   ├── research.store.ts
│   │   ├── literature.store.ts
│   │   ├── task.store.ts
│   │   └── interaction.store.ts
│   ├── hooks/              # 自定义Hooks
│   ├── utils/              # 工具函数
│   ├── styles/             # 全局样式
│   ├── types/              # TypeScript类型
│   └── assets/             # 静态资源
├── public/                 # 公共资源
├── tests/                  # 测试文件
└── package.json
```

### 1.2 技术栈详细配置

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "antd": "^5.11.0",
    "@ant-design/icons": "^5.2.6",
    "@ant-design/pro-components": "^2.6.0",
    "zustand": "^4.4.7",
    "@tanstack/react-query": "^5.12.0",
    "axios": "^1.6.2",
    "socket.io-client": "^4.5.4",
    "framer-motion": "^10.16.0",
    "lottie-react": "^2.4.0",
    "echarts": "^5.4.3",
    "echarts-for-react": "^3.0.2",
    "d3": "^7.8.5",
    "@monaco-editor/react": "^4.6.0",
    "react-markdown": "^9.0.0",
    "react-dropzone": "^14.2.3",
    "dayjs": "^1.11.10",
    "lodash-es": "^4.17.21",
    "classnames": "^2.3.2",
    "uuid": "^9.0.1"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@types/node": "^20.10.0",
    "@vitejs/plugin-react": "^4.2.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "tailwindcss": "^3.3.0",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.32",
    "eslint": "^8.55.0",
    "prettier": "^3.1.0"
  }
}
```

## 二、核心页面详细实现

### 2.1 研究工作台（Workspace）

#### 2.1.1 主界面组件结构
```typescript
// src/pages/workspace/index.tsx
import React, { useState, useCallback } from 'react';
import { Layout, Row, Col, Card, Space } from 'antd';
import { SmartQueryInput } from '@/components/workspace/SmartQueryInput';
import { ModeSelector } from '@/components/workspace/ModeSelector';
import { ProgressPanel } from '@/components/workspace/ProgressPanel';
import { InteractionCards } from '@/components/interaction/InteractionCards';
import { ResultDisplay } from '@/components/workspace/ResultDisplay';
import { useResearchStore } from '@/stores/research.store';

export const Workspace: React.FC = () => {
  const [mode, setMode] = useState<ResearchMode>('auto');
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [showInteraction, setShowInteraction] = useState(false);

  const { submitQuery, currentSession } = useResearchStore();

  const handleQuerySubmit = useCallback(async (query: string) => {
    const result = await submitQuery(query, mode);
    if (result.requiresInteraction) {
      setShowInteraction(true);
    }
    setActiveTaskId(result.taskId);
  }, [mode, submitQuery]);

  return (
    <Layout className="h-screen bg-gray-50">
      <Layout.Content className="p-6">
        <Row gutter={[24, 24]}>
          {/* 左侧主要工作区 */}
          <Col xs={24} lg={16}>
            <Space direction="vertical" className="w-full" size="large">
              {/* 模式选择器 */}
              <ModeSelector value={mode} onChange={setMode} />

              {/* 智能输入框 */}
              <Card className="shadow-lg">
                <SmartQueryInput
                  onSubmit={handleQuerySubmit}
                  mode={mode}
                  placeholder="输入您的研究问题..."
                />
              </Card>

              {/* 结果展示区 */}
              {activeTaskId && (
                <Card className="shadow-lg">
                  <ResultDisplay taskId={activeTaskId} />
                </Card>
              )}
            </Space>
          </Col>

          {/* 右侧辅助区 */}
          <Col xs={24} lg={8}>
            <Space direction="vertical" className="w-full" size="large">
              {/* 进度面板 */}
              {activeTaskId && (
                <Card title="执行进度" className="shadow-lg">
                  <ProgressPanel taskId={activeTaskId} />
                </Card>
              )}

              {/* 智能交互卡片 */}
              {showInteraction && currentSession && (
                <InteractionCards
                  sessionId={currentSession.id}
                  onComplete={() => setShowInteraction(false)}
                />
              )}
            </Space>
          </Col>
        </Row>
      </Layout.Content>
    </Layout>
  );
};
```

#### 2.1.2 智能输入组件
```typescript
// src/components/workspace/SmartQueryInput.tsx
import React, { useState, useRef, useEffect } from 'react';
import { Input, Button, Space, Tooltip, AutoComplete, Tag } from 'antd';
import { SearchOutlined, PlusOutlined, HistoryOutlined } from '@ant-design/icons';
import { motion, AnimatePresence } from 'framer-motion';
import MDEditor from '@uiw/react-md-editor';

interface SmartQueryInputProps {
  onSubmit: (query: string, attachments?: string[]) => void;
  mode: ResearchMode;
  placeholder?: string;
}

export const SmartQueryInput: React.FC<SmartQueryInputProps> = ({
  onSubmit,
  mode,
  placeholder
}) => {
  const [query, setQuery] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [selectedLiterature, setSelectedLiterature] = useState<string[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // 智能提示逻辑
  useEffect(() => {
    if (query.length > 10) {
      setIsAnalyzing(true);
      // 调用API获取智能提示
      fetchSmartSuggestions(query).then(setSuggestions);
      setIsAnalyzing(false);
    }
  }, [query]);

  const handleSubmit = () => {
    if (!query.trim()) return;
    onSubmit(query, selectedLiterature);
    setQuery('');
    setSelectedLiterature([]);
  };

  return (
    <div className="smart-query-input">
      <Space direction="vertical" className="w-full" size="middle">
        {/* Markdown编辑器 */}
        <div className="relative">
          <MDEditor
            value={query}
            onChange={(val) => setQuery(val || '')}
            preview="edit"
            height={200}
            commands={[]}
            extraCommands={[]}
          />

          {/* AI分析指示器 */}
          <AnimatePresence>
            {isAnalyzing && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute top-2 right-2"
              >
                <Tag color="processing">AI分析中...</Tag>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* 智能建议 */}
        {suggestions.length > 0 && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            className="bg-blue-50 p-3 rounded-lg"
          >
            <div className="text-sm text-gray-600 mb-2">AI建议的相关问题：</div>
            <Space wrap>
              {suggestions.map((suggestion, index) => (
                <Tag
                  key={index}
                  className="cursor-pointer hover:bg-blue-100"
                  onClick={() => setQuery(query + '\n' + suggestion)}
                >
                  {suggestion}
                </Tag>
              ))}
            </Space>
          </motion.div>
        )}

        {/* 高级选项 */}
        <AnimatePresence>
          {showAdvanced && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
            >
              <LiteratureSelector
                selected={selectedLiterature}
                onChange={setSelectedLiterature}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* 操作按钮 */}
        <div className="flex justify-between">
          <Space>
            <Button
              icon={<PlusOutlined />}
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              {showAdvanced ? '收起' : '高级选项'}
            </Button>
            <Button icon={<HistoryOutlined />}>历史记录</Button>
          </Space>

          <Button
            type="primary"
            size="large"
            icon={<SearchOutlined />}
            onClick={handleSubmit}
            loading={isAnalyzing}
          >
            开始研究
          </Button>
        </div>
      </Space>
    </div>
  );
};
```

### 2.2 智能交互组件

#### 2.2.1 交互卡片组件
```typescript
// src/components/interaction/InteractionCards.tsx
import React, { useState, useEffect, useRef } from 'react';
import { Card, Button, Progress, Space, Input, message } from 'antd';
import { CheckCircleOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { motion, AnimatePresence } from 'framer-motion';
import Lottie from 'lottie-react';
import thinkingAnimation from '@/assets/animations/thinking.json';

interface InteractionCardsProps {
  sessionId: string;
  onComplete: () => void;
}

export const InteractionCards: React.FC<InteractionCardsProps> = ({
  sessionId,
  onComplete
}) => {
  const [currentCard, setCurrentCard] = useState<ClarificationCard | null>(null);
  const [timeLeft, setTimeLeft] = useState(5);
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [customInput, setCustomInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout>();
  const countdownRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    fetchCurrentCard();
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [sessionId]);

  useEffect(() => {
    if (currentCard && currentCard.timeout_seconds > 0) {
      setTimeLeft(currentCard.timeout_seconds);

      // 倒计时
      countdownRef.current = setInterval(() => {
        setTimeLeft(prev => {
          if (prev <= 1) {
            handleTimeout();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);

      // 超时自动选择
      timeoutRef.current = setTimeout(handleTimeout, currentCard.timeout_seconds * 1000);
    }

    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [currentCard]);

  const fetchCurrentCard = async () => {
    setIsLoading(true);
    try {
      const response = await api.getInteractionCard(sessionId);
      setCurrentCard(response.data);
    } catch (error) {
      message.error('获取交互信息失败');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOptionSelect = async (optionId: string) => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);

    setIsLoading(true);
    try {
      const response = await api.selectOption(sessionId, optionId);
      if (response.data.next_action === 'continue') {
        fetchCurrentCard();
      } else {
        onComplete();
      }
    } catch (error) {
      message.error('选择失败，请重试');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTimeout = async () => {
    if (!currentCard) return;

    const recommendedOption = currentCard.options.find(
      opt => opt.option_id === currentCard.recommended_option_id
    );

    if (recommendedOption) {
      message.info(`已自动选择推荐选项：${recommendedOption.label}`);
      await handleOptionSelect(recommendedOption.option_id);
    }
  };

  const handleCustomSubmit = async () => {
    if (!customInput.trim()) return;

    setIsLoading(true);
    try {
      const response = await api.submitCustomInput(sessionId, customInput);
      setCustomInput('');
      setShowCustomInput(false);

      if (response.data.next_action === 'continue') {
        fetchCurrentCard();
      } else {
        onComplete();
      }
    } catch (error) {
      message.error('提交失败，请重试');
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading && !currentCard) {
    return (
      <Card className="shadow-xl">
        <div className="flex flex-col items-center justify-center py-8">
          <Lottie animationData={thinkingAnimation} className="w-32 h-32" />
          <div className="mt-4 text-gray-600">AI正在分析您的需求...</div>
        </div>
      </Card>
    );
  }

  if (!currentCard) return null;

  const progressPercent = ((currentCard.timeout_seconds - timeLeft) / currentCard.timeout_seconds) * 100;

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={currentCard.session_id}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        transition={{ duration: 0.3 }}
      >
        <Card
          title={
            <div className="flex justify-between items-center">
              <span>{currentCard.question}</span>
              {currentCard.timeout_seconds > 0 && (
                <div className="flex items-center gap-2">
                  <ClockCircleOutlined />
                  <span className="text-sm">{timeLeft}s</span>
                </div>
              )}
            </div>
          }
          className="shadow-xl border-2 border-blue-100"
          extra={
            currentCard.timeout_seconds > 0 && (
              <Progress
                type="circle"
                percent={progressPercent}
                width={40}
                format={() => `${timeLeft}s`}
                status={timeLeft <= 2 ? 'exception' : 'active'}
              />
            )
          }
        >
          <Space direction="vertical" className="w-full" size="middle">
            {/* 选项列表 */}
            <div className="grid grid-cols-1 gap-3">
              {currentCard.options.map((option) => (
                <motion.div
                  key={option.option_id}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <Button
                    block
                    size="large"
                    type={option.option_id === currentCard.recommended_option_id ? 'primary' : 'default'}
                    onClick={() => handleOptionSelect(option.option_id)}
                    disabled={isLoading}
                    className={`
                      h-auto py-3 px-4 text-left
                      ${option.option_id === currentCard.recommended_option_id ?
                        'bg-gradient-to-r from-blue-500 to-blue-600 border-0' :
                        'hover:border-blue-400'
                      }
                    `}
                  >
                    <div className="flex items-start gap-3">
                      {option.option_id === currentCard.recommended_option_id && (
                        <CheckCircleOutlined className="text-white mt-1" />
                      )}
                      <div>
                        <div className={
                          option.option_id === currentCard.recommended_option_id ?
                          'text-white font-semibold' :
                          'font-medium'
                        }>
                          {option.label}
                        </div>
                        {option.description && (
                          <div className={
                            option.option_id === currentCard.recommended_option_id ?
                            'text-blue-100 text-sm mt-1' :
                            'text-gray-500 text-sm mt-1'
                          }>
                            {option.description}
                          </div>
                        )}
                      </div>
                    </div>
                  </Button>
                </motion.div>
              ))}
            </div>

            {/* 自定义输入 */}
            {currentCard.custom_input_allowed && (
              <>
                {!showCustomInput ? (
                  <Button
                    type="dashed"
                    block
                    onClick={() => setShowCustomInput(true)}
                  >
                    其他选择（自定义输入）
                  </Button>
                ) : (
                  <motion.div
                    initial={{ height: 0 }}
                    animate={{ height: 'auto' }}
                  >
                    <Input.TextArea
                      value={customInput}
                      onChange={(e) => setCustomInput(e.target.value)}
                      placeholder="请输入您的想法..."
                      rows={3}
                      className="mb-2"
                    />
                    <Space>
                      <Button type="primary" onClick={handleCustomSubmit} loading={isLoading}>
                        提交
                      </Button>
                      <Button onClick={() => setShowCustomInput(false)}>
                        取消
                      </Button>
                    </Space>
                  </motion.div>
                )}
              </>
            )}
          </Space>
        </Card>
      </motion.div>
    </AnimatePresence>
  );
};
```

### 2.3 实时进度展示

#### 2.3.1 进度面板组件
```typescript
// src/components/workspace/ProgressPanel.tsx
import React, { useEffect, useState } from 'react';
import { Steps, Progress, Timeline, Tag, Collapse, Space } from 'antd';
import {
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
import { motion, AnimatePresence } from 'framer-motion';
import { useWebSocket } from '@/hooks/useWebSocket';

interface ProgressPanelProps {
  taskId: string;
}

interface TaskProgress {
  stage: string;
  progress: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  message: string;
  details?: Record<string, any>;
  timestamp: number;
}

export const ProgressPanel: React.FC<ProgressPanelProps> = ({ taskId }) => {
  const [taskProgress, setTaskProgress] = useState<TaskProgress[]>([]);
  const [currentStage, setCurrentStage] = useState(0);
  const [overallProgress, setOverallProgress] = useState(0);
  const [estimatedTime, setEstimatedTime] = useState<number | null>(null);
  const [logs, setLogs] = useState<string[]>([]);

  const { subscribe, unsubscribe } = useWebSocket();

  useEffect(() => {
    // 订阅任务进度
    const handleProgress = (data: any) => {
      if (data.task_id === taskId) {
        if (data.type === 'progress') {
          updateProgress(data);
        } else if (data.type === 'log') {
          setLogs(prev => [...prev, data.message]);
        }
      }
    };

    subscribe('task_progress', handleProgress);

    return () => {
      unsubscribe('task_progress', handleProgress);
    };
  }, [taskId]);

  const updateProgress = (data: any) => {
    setTaskProgress(prev => {
      const existing = prev.find(p => p.stage === data.stage);
      if (existing) {
        return prev.map(p =>
          p.stage === data.stage ? { ...p, ...data } : p
        );
      }
      return [...prev, data];
    });

    setCurrentStage(data.current_stage);
    setOverallProgress(data.overall_progress);
    setEstimatedTime(data.estimated_time);
  };

  const getStageIcon = (status: string) => {
    switch (status) {
      case 'processing':
        return <LoadingOutlined className="text-blue-500" />;
      case 'completed':
        return <CheckCircleOutlined className="text-green-500" />;
      case 'failed':
        return <CloseCircleOutlined className="text-red-500" />;
      default:
        return <ClockCircleOutlined className="text-gray-400" />;
    }
  };

  const stages = [
    { title: '初始化', description: '准备执行环境' },
    { title: '文献搜索', description: '搜索相关文献' },
    { title: 'AI筛选', description: '智能质量评估' },
    { title: 'PDF处理', description: '下载和解析PDF' },
    { title: '结构化', description: '提取结构化数据' },
    { title: '生成经验', description: '生成研究经验' },
    { title: '完成', description: '任务完成' }
  ];

  return (
    <div className="progress-panel">
      <Space direction="vertical" className="w-full" size="large">
        {/* 总体进度 */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 p-4 rounded-lg">
          <div className="flex justify-between items-center mb-2">
            <span className="font-semibold">总体进度</span>
            {estimatedTime && (
              <Tag color="blue">预计剩余 {Math.ceil(estimatedTime / 60)} 分钟</Tag>
            )}
          </div>
          <Progress
            percent={overallProgress}
            status="active"
            strokeColor={{
              '0%': '#108ee9',
              '100%': '#87d068',
            }}
          />
        </div>

        {/* 阶段进度 */}
        <Steps
          current={currentStage}
          direction="vertical"
          size="small"
          items={stages.map((stage, index) => {
            const progress = taskProgress.find(p => p.stage === stage.title);
            return {
              title: (
                <div className="flex items-center gap-2">
                  <span>{stage.title}</span>
                  {progress && progress.status === 'processing' && (
                    <Tag color="processing" className="ml-2">
                      {progress.progress}%
                    </Tag>
                  )}
                </div>
              ),
              description: stage.description,
              status: progress?.status || 'wait',
              icon: progress ? getStageIcon(progress.status) : undefined
            };
          })}
        />

        {/* 详细日志 */}
        <Collapse ghost>
          <Collapse.Panel header="详细日志" key="logs">
            <Timeline
              items={logs.map((log, index) => ({
                key: index,
                children: (
                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.05 }}
                  >
                    <div className="text-sm text-gray-600">{log}</div>
                  </motion.div>
                )
              }))}
            />
          </Collapse.Panel>
        </Collapse>
      </Space>
    </div>
  );
};
```

### 2.4 文献库管理

#### 2.4.1 文献上传组件
```typescript
// src/components/literature/UploadModal.tsx
import React, { useState } from 'react';
import { Modal, Upload, Tabs, Input, Button, message, Progress, List } from 'antd';
import { InboxOutlined, FileTextOutlined, LinkOutlined } from '@ant-design/icons';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';

interface UploadModalProps {
  visible: boolean;
  onClose: () => void;
  projectId: number;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  visible,
  onClose,
  projectId
}) => {
  const [activeTab, setActiveTab] = useState('pdf');
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [dois, setDois] = useState('');
  const [zoteroFile, setZoteroFile] = useState<File | null>(null);

  const { getRootProps, getInputProps, acceptedFiles, isDragActive } = useDropzone({
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: true,
    onDrop: handlePDFUpload
  });

  async function handlePDFUpload(files: File[]) {
    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('project_id', projectId.toString());

      try {
        await uploadWithProgress(
          '/api/literature/upload',
          formData,
          (progress) => {
            setUploadProgress(prev => ({
              ...prev,
              [file.name]: progress
            }));
          }
        );
        message.success(`${file.name} 上传成功`);
      } catch (error) {
        message.error(`${file.name} 上传失败`);
      }
    }
  }

  async function handleDOIImport() {
    const doiList = dois.split('\n').filter(d => d.trim());
    if (doiList.length === 0) {
      message.warning('请输入至少一个DOI');
      return;
    }

    try {
      const response = await api.importDOIs({
        project_id: projectId,
        dois: doiList
      });
      message.success(`成功导入 ${response.data.success_count} 篇文献`);
      setDois('');
    } catch (error) {
      message.error('DOI导入失败');
    }
  }

  async function handleZoteroImport() {
    if (!zoteroFile) {
      message.warning('请选择Zotero导出文件');
      return;
    }

    const formData = new FormData();
    formData.append('file', zoteroFile);
    formData.append('project_id', projectId.toString());

    try {
      const response = await api.importZotero(formData);
      message.success(`成功导入 ${response.data.imported_count} 篇文献`);
      setZoteroFile(null);
    } catch (error) {
      message.error('Zotero导入失败');
    }
  }

  return (
    <Modal
      title="导入文献"
      open={visible}
      onCancel={onClose}
      width={700}
      footer={null}
      className="upload-modal"
    >
      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        {/* PDF上传标签页 */}
        <Tabs.TabPane tab="上传PDF" key="pdf" icon={<FileTextOutlined />}>
          <div {...getRootProps()} className={`
            border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
            transition-colors duration-200
            ${isDragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-400'}
          `}>
            <input {...getInputProps()} />
            <InboxOutlined className="text-4xl text-gray-400 mb-4" />
            <p className="text-gray-600">
              {isDragActive ? '释放文件以上传' : '拖拽PDF文件到此处，或点击选择文件'}
            </p>
            <p className="text-sm text-gray-400 mt-2">支持批量上传</p>
          </div>

          {/* 上传进度列表 */}
          {Object.keys(uploadProgress).length > 0 && (
            <List
              className="mt-4"
              dataSource={Object.entries(uploadProgress)}
              renderItem={([filename, progress]) => (
                <List.Item>
                  <div className="w-full">
                    <div className="flex justify-between mb-1">
                      <span className="text-sm">{filename}</span>
                      <span className="text-sm">{progress}%</span>
                    </div>
                    <Progress percent={progress} size="small" />
                  </div>
                </List.Item>
              )}
            />
          )}
        </Tabs.TabPane>

        {/* DOI导入标签页 */}
        <Tabs.TabPane tab="DOI导入" key="doi" icon={<LinkOutlined />}>
          <div className="space-y-4">
            <div>
              <p className="text-gray-600 mb-2">
                输入DOI列表（每行一个）：
              </p>
              <Input.TextArea
                value={dois}
                onChange={(e) => setDois(e.target.value)}
                placeholder="10.1038/nature12373&#10;10.1126/science.1234567"
                rows={10}
              />
            </div>
            <Button type="primary" onClick={handleDOIImport} block>
              开始导入
            </Button>
          </div>
        </Tabs.TabPane>

        {/* Zotero导入标签页 */}
        <Tabs.TabPane tab="Zotero导入" key="zotero">
          <div className="space-y-4">
            <div className="bg-blue-50 p-4 rounded-lg">
              <p className="font-semibold mb-2">导入步骤：</p>
              <ol className="list-decimal list-inside space-y-1 text-sm">
                <li>在Zotero中选择要导出的文献</li>
                <li>点击 文件 → 导出文献库</li>
                <li>选择格式为 "Zotero RDF" 或 "BibTeX"</li>
                <li>上传导出的文件</li>
              </ol>
            </div>

            <Upload
              accept=".rdf,.bib,.bibtex"
              beforeUpload={(file) => {
                setZoteroFile(file);
                return false;
              }}
              maxCount={1}
            >
              <Button icon={<InboxOutlined />} block>
                选择Zotero导出文件
              </Button>
            </Upload>

            {zoteroFile && (
              <div className="bg-gray-50 p-3 rounded">
                已选择：{zoteroFile.name}
              </div>
            )}

            <Button
              type="primary"
              onClick={handleZoteroImport}
              disabled={!zoteroFile}
              block
            >
              开始导入
            </Button>
          </div>
        </Tabs.TabPane>
      </Tabs>
    </Modal>
  );
};
```

## 三、WebSocket服务集成

### 3.1 WebSocket管理器
```typescript
// src/services/websocket/WebSocketManager.ts
import { io, Socket } from 'socket.io-client';
import { EventEmitter } from 'events';

class WebSocketManager extends EventEmitter {
  private socket: Socket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  connect(url: string, token: string) {
    if (this.socket?.connected) {
      return;
    }

    this.socket = io(url, {
      auth: { token },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: this.reconnectDelay,
    });

    this.setupEventHandlers();
  }

  private setupEventHandlers() {
    if (!this.socket) return;

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.emit('connected');
    });

    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      this.emit('disconnected', reason);
    });

    this.socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      this.reconnectAttempts++;

      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        this.emit('max_reconnect_exceeded');
        this.fallbackToPolling();
      }
    });

    // 业务事件
    this.socket.on('task_progress', (data) => {
      this.emit('task_progress', data);
    });

    this.socket.on('interaction_update', (data) => {
      this.emit('interaction_update', data);
    });

    this.socket.on('notification', (data) => {
      this.emit('notification', data);
    });
  }

  private fallbackToPolling() {
    console.log('Falling back to polling mode');
    // 实现轮询降级逻辑
    setInterval(async () => {
      try {
        const updates = await api.getLatestUpdates();
        updates.forEach(update => {
          this.emit(update.type, update.data);
        });
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 3000);
  }

  subscribe(event: string, handler: Function) {
    this.on(event, handler);
  }

  unsubscribe(event: string, handler: Function) {
    this.off(event, handler);
  }

  send(event: string, data: any) {
    if (this.socket?.connected) {
      this.socket.emit(event, data);
    } else {
      console.warn('WebSocket not connected, queuing message');
      this.once('connected', () => {
        this.socket?.emit(event, data);
      });
    }
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }
}

export const wsManager = new WebSocketManager();
```

## 四、状态管理设计

### 4.1 Research Store
```typescript
// src/stores/research.store.ts
import { create } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';

interface ResearchState {
  // 状态
  currentQuery: string | null;
  currentMode: ResearchMode;
  currentSession: InteractionSession | null;
  activeTasks: Task[];
  results: ResearchResult[];

  // Actions
  submitQuery: (query: string, mode: ResearchMode) => Promise<any>;
  updateSession: (session: InteractionSession) => void;
  addTask: (task: Task) => void;
  updateTask: (taskId: string, updates: Partial<Task>) => void;
  addResult: (result: ResearchResult) => void;
  clearResults: () => void;
}

export const useResearchStore = create<ResearchState>()(
  devtools(
    subscribeWithSelector(
      immer((set, get) => ({
        // 初始状态
        currentQuery: null,
        currentMode: 'auto',
        currentSession: null,
        activeTasks: [],
        results: [],

        // 提交查询
        submitQuery: async (query: string, mode: ResearchMode) => {
          set((state) => {
            state.currentQuery = query;
            state.currentMode = mode;
          });

          try {
            const response = await api.submitResearchQuery({
              query,
              mode,
              project_id: getCurrentProjectId()
            });

            if (response.data.session) {
              set((state) => {
                state.currentSession = response.data.session;
              });
            }

            if (response.data.task) {
              set((state) => {
                state.activeTasks.push(response.data.task);
              });
            }

            return response.data;
          } catch (error) {
            console.error('Submit query error:', error);
            throw error;
          }
        },

        // 更新会话
        updateSession: (session) => {
          set((state) => {
            state.currentSession = session;
          });
        },

        // 添加任务
        addTask: (task) => {
          set((state) => {
            state.activeTasks.push(task);
          });
        },

        // 更新任务
        updateTask: (taskId, updates) => {
          set((state) => {
            const taskIndex = state.activeTasks.findIndex(t => t.id === taskId);
            if (taskIndex !== -1) {
              Object.assign(state.activeTasks[taskIndex], updates);
            }
          });
        },

        // 添加结果
        addResult: (result) => {
          set((state) => {
            state.results.push(result);
          });
        },

        // 清空结果
        clearResults: () => {
          set((state) => {
            state.results = [];
          });
        }
      }))
    )
  )
);
```

## 五、关键Hooks实现

### 5.1 useWebSocket Hook
```typescript
// src/hooks/useWebSocket.ts
import { useEffect, useRef, useCallback } from 'react';
import { wsManager } from '@/services/websocket/WebSocketManager';
import { useAuthStore } from '@/stores/auth.store';

export function useWebSocket() {
  const { token } = useAuthStore();
  const handlersRef = useRef<Map<string, Function>>(new Map());

  useEffect(() => {
    if (token) {
      wsManager.connect(import.meta.env.VITE_WS_URL, token);
    }

    return () => {
      wsManager.disconnect();
    };
  }, [token]);

  const subscribe = useCallback((event: string, handler: Function) => {
    handlersRef.current.set(event, handler);
    wsManager.subscribe(event, handler);
  }, []);

  const unsubscribe = useCallback((event: string, handler?: Function) => {
    const targetHandler = handler || handlersRef.current.get(event);
    if (targetHandler) {
      wsManager.unsubscribe(event, targetHandler);
      handlersRef.current.delete(event);
    }
  }, []);

  const send = useCallback((event: string, data: any) => {
    wsManager.send(event, data);
  }, []);

  // 清理所有事件监听
  useEffect(() => {
    return () => {
      handlersRef.current.forEach((handler, event) => {
        wsManager.unsubscribe(event, handler);
      });
      handlersRef.current.clear();
    };
  }, []);

  return { subscribe, unsubscribe, send };
}
```

### 5.2 useTaskProgress Hook
```typescript
// src/hooks/useTaskProgress.ts
import { useState, useEffect } from 'react';
import { useWebSocket } from './useWebSocket';
import { useQuery } from '@tanstack/react-query';

export function useTaskProgress(taskId: string | null) {
  const [progress, setProgress] = useState<TaskProgress | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const { subscribe, unsubscribe } = useWebSocket();

  // 初始加载任务状态
  const { data: initialData } = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => taskId ? api.getTaskStatus(taskId) : null,
    enabled: !!taskId,
  });

  useEffect(() => {
    if (!taskId) return;

    const handleProgress = (data: any) => {
      if (data.task_id === taskId) {
        setProgress(data);
        if (data.log) {
          setLogs(prev => [...prev, data.log]);
        }
      }
    };

    subscribe('task_progress', handleProgress);

    return () => {
      unsubscribe('task_progress', handleProgress);
    };
  }, [taskId, subscribe, unsubscribe]);

  return {
    progress: progress || initialData,
    logs,
    isCompleted: progress?.status === 'completed',
    isFailed: progress?.status === 'failed',
  };
}
```

## 六、启动脚本和配置

### 6.1 package.json配置
```json
{
  "name": "vibe-research-frontend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "format": "prettier --write \"src/**/*.{ts,tsx,css,md}\""
  }
}
```

### 6.2 Vite配置
```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          antd: ['antd', '@ant-design/icons'],
          utils: ['lodash-es', 'dayjs', 'axios'],
        },
      },
    },
  },
});
```

## 七、总结

本前端开发方案已经详细规划了：

1. **完整的项目结构**：模块化组织，便于维护和扩展
2. **核心功能实现**：智能问答、交互卡片、实时进度、文献管理
3. **技术架构**：React + TypeScript + Ant Design + WebSocket
4. **状态管理**：Zustand统一管理应用状态
5. **实时通信**：WebSocket with fallback to polling
6. **用户体验**：动画、微交互、响应式设计

### 下一步行动：
1. 初始化前端项目框架
2. 实现基础布局和路由
3. 开发核心组件
4. 集成API和WebSocket
5. 优化用户体验
6. 测试和部署

整个前端系统预计6周完成，将完全实现愿景中描述的智能研究平台界面。