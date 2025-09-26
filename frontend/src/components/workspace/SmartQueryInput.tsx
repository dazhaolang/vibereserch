import React, { useState, useEffect, useCallback } from 'react';
import { Input, Button, Space, Tag, Dropdown, Menu } from 'antd';
import {
  SearchOutlined,
  PlusOutlined,
  HistoryOutlined,
  FileTextOutlined,
  BulbOutlined,
} from '@ant-design/icons';
import { motion, AnimatePresence } from 'framer-motion';
import MDEditor from '@uiw/react-md-editor';
import { useDebounce } from 'ahooks';
import { LiteratureSelector } from './LiteratureSelector';
import { DeepModeControlPanel } from './DeepModeControlPanel';
import type { DeepModeConfig } from './DeepModeControlPanel';
import { AutoModeControlPanel } from './AutoModeControlPanel';
import type { AutoModeConfig } from './AutoModeControlPanel';
import { useAppStore } from '@/stores/app.store';
import type { ResearchMode } from '@/types';

interface SmartQueryInputProps {
  onSubmit: (query: string, options?: {
    attachments?: number[];
    deepConfig?: DeepModeConfig;
    autoConfig?: AutoModeConfig;
  }) => void;
  mode: ResearchMode;
  disabled?: boolean;
  placeholder?: string;
}

interface QueryTemplate {
  title: string;
  query: string;
  keywords: string[];
}

// 查询模板
const QUERY_TEMPLATES: Record<ResearchMode, QueryTemplate[]> = {
  'rag': [
    { title: '文献综述', query: '请总结关于{topic}的最新研究进展', keywords: ['综述', '进展'] },
    { title: '方法比较', query: '比较{method1}和{method2}在{field}中的应用', keywords: ['比较', '方法'] },
  ],
  'deep': [
    { title: '机制研究', query: '深入分析{phenomenon}的分子机制和调控网络', keywords: ['机制', '调控'] },
    { title: '假设验证', query: '基于{theory}，验证{hypothesis}的可行性', keywords: ['假设', '验证'] },
  ],
  'auto': [
    { title: '研究方案', query: '设计关于{topic}的完整研究方案，包括实验设计和预期结果', keywords: ['方案', '设计'] },
    { title: '创新探索', query: '探索{field}领域的创新方向和潜在突破点', keywords: ['创新', '突破'] },
  ],
};

export const SmartQueryInput: React.FC<SmartQueryInputProps> = ({
  onSubmit,
  mode,
  disabled = false,
  placeholder,
}) => {
  const [query, setQuery] = useState('');
  const [showMarkdown, setShowMarkdown] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [selectedLiterature, setSelectedLiterature] = useState<number[]>([]);
  const [showLiteratureSelector, setShowLiteratureSelector] = useState(false);
  const [deepModeConfig, setDeepModeConfig] = useState<DeepModeConfig | null>(null);
  const [autoModeConfig, setAutoModeConfig] = useState<AutoModeConfig | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [recentQueries, setRecentQueries] = useState<string[]>([]);

  // 从 App Store 获取当前项目信息
  const { currentProject } = useAppStore();

  // 防抖查询
  const debouncedQuery = useDebounce(query, { wait: 500 });

  // 文献选择器处理函数
  const handleLiteratureConfirm = useCallback((selectedIds: number[]) => {
    setSelectedLiterature(selectedIds);
    setShowLiteratureSelector(false);
  }, []);

  const handleRemoveLiterature = useCallback((id: number) => {
    setSelectedLiterature(prev => prev.filter(i => i !== id));
  }, []);

  // 加载历史查询
  useEffect(() => {
    const stored = localStorage.getItem('recentQueries');
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as unknown;
        if (Array.isArray(parsed) && parsed.every((item) => typeof item === 'string')) {
          setRecentQueries(parsed);
        }
      } catch (error) {
        console.warn('读取历史查询失败', error);
      }
    }
  }, []);

  // AI智能提示
  useEffect(() => {
    if (debouncedQuery && debouncedQuery.length > 10) {
      setIsAnalyzing(true);
      // 模拟AI分析
      setTimeout(() => {
        const templates = QUERY_TEMPLATES[mode];
        const relatedSuggestions: string[] = templates
          .filter((t) =>
            t.keywords.some((k) => debouncedQuery.includes(k))
          )
          .map((t) => t.title);
        setSuggestions(relatedSuggestions);
        setIsAnalyzing(false);
      }, 500);
    } else {
      setSuggestions([]);
    }
  }, [debouncedQuery, mode]);

  const handleSubmit = useCallback(() => {
    if (!query.trim()) return;

    // 保存到历史记录
    const newRecent = [query, ...recentQueries.filter((q) => q !== query)].slice(0, 10);
    setRecentQueries(newRecent);
    localStorage.setItem('recentQueries', JSON.stringify(newRecent));

    // 构建提交选项
    const options: {
      attachments?: number[];
      deepConfig?: DeepModeConfig;
      autoConfig?: AutoModeConfig;
    } = {};

    if (selectedLiterature.length > 0) {
      options.attachments = selectedLiterature;
    }

    if (mode === 'deep' && deepModeConfig) {
      options.deepConfig = deepModeConfig;
    }

    if (mode === 'auto' && autoModeConfig) {
      options.autoConfig = autoModeConfig;
    }

    onSubmit(query, options);
    setQuery('');
    setSelectedLiterature([]);
  }, [query, selectedLiterature, recentQueries, onSubmit, mode, deepModeConfig, autoModeConfig]);

  const handleTemplateSelect = (template: QueryTemplate) => {
    setQuery(template.query);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !showMarkdown) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const templateMenu = (
    <Menu
      items={QUERY_TEMPLATES[mode].map((template, index) => ({
        key: index,
        label: (
          <div onClick={() => handleTemplateSelect(template)}>
            <div className="font-medium">{template.title}</div>
            <div className="text-xs text-gray-500">{template.query}</div>
          </div>
        ),
      }))}
    />
  );

  const historyMenu = (
    <Menu
      items={recentQueries.map((q, index) => ({
        key: index,
        label: (
          <div onClick={() => setQuery(q)} className="max-w-xs truncate">
            {q}
          </div>
        ),
      }))}
    />
  );

  return (
    <div className="smart-query-input">
      <Space direction="vertical" className="w-full" size="middle">
        {/* 输入区域 */}
        {showMarkdown ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="relative"
          >
            <MDEditor
              value={query}
              onChange={(val) => setQuery(val || '')}
              preview="edit"
              height={200}
              data-color-mode="light"
            />
            <Button
              size="small"
              onClick={() => setShowMarkdown(false)}
              className="absolute top-2 right-2 z-10"
            >
              切换到普通模式
            </Button>
          </motion.div>
        ) : (
          <div className="relative">
            <Input.TextArea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={placeholder || '输入您的研究问题...'}
              rows={4}
              disabled={disabled}
              onKeyPress={handleKeyPress}
              className="text-base"
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
                  <Tag icon={<BulbOutlined />} color="processing">
                    AI分析中...
                  </Tag>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* 智能建议 */}
        <AnimatePresence>
          {suggestions.length > 0 && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="bg-blue-50 p-3 rounded-lg"
            >
              <div className="text-sm text-gray-600 mb-2 flex items-center gap-1">
                <BulbOutlined />
                AI建议的相关问题：
              </div>
              <Space wrap>
                {suggestions.map((suggestion, index) => (
                  <Tag
                    key={index}
                    className="cursor-pointer hover:bg-blue-100"
                    onClick={() => {
                      const template = QUERY_TEMPLATES[mode].find((t) => t.title === suggestion);
                      if (template) setQuery(template.query);
                    }}
                  >
                    {suggestion}
                  </Tag>
                ))}
              </Space>
            </motion.div>
          )}
        </AnimatePresence>

        {/* 高级选项 */}
        <AnimatePresence>
          {showAdvanced && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="bg-gray-50 p-4 rounded-lg"
            >
              <div className="mb-3">
                <div className="text-sm text-gray-600 mb-2">关联文献：</div>
                <div className="flex flex-wrap gap-2">
                  {selectedLiterature.map((id) => (
                    <Tag
                      key={id}
                      closable
                      onClose={() => handleRemoveLiterature(id)}
                    >
                      <FileTextOutlined /> 文献 {id}
                    </Tag>
                  ))}
                  <Button
                    size="small"
                    icon={<PlusOutlined />}
                    onClick={() => setShowLiteratureSelector(true)}
                    disabled={!currentProject}
                  >
                    添加文献
                  </Button>
                </div>
              </div>

              {/* 模式特定控制面板 */}
              {mode === 'deep' && (
                <div className="mt-4">
                  <DeepModeControlPanel
                    onConfigChange={setDeepModeConfig}
                    disabled={disabled}
                  />
                </div>
              )}

              {mode === 'auto' && (
                <div className="mt-4">
                  <AutoModeControlPanel
                    onConfigChange={setAutoModeConfig}
                    disabled={disabled}
                  />
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* 操作按钮 */}
        <div className="flex justify-between items-center">
          <Space>
            <Dropdown overlay={templateMenu} placement="topLeft" disabled={disabled}>
              <Button icon={<FileTextOutlined />}>查询模板</Button>
            </Dropdown>

            <Dropdown
              overlay={historyMenu}
              placement="topLeft"
              disabled={disabled || recentQueries.length === 0}
            >
              <Button icon={<HistoryOutlined />}>历史记录</Button>
            </Dropdown>

            <Button
              icon={<PlusOutlined />}
              onClick={() => setShowAdvanced(!showAdvanced)}
              disabled={disabled}
            >
              {showAdvanced ? '收起' : '高级选项'}
            </Button>

            <Button
              onClick={() => setShowMarkdown(!showMarkdown)}
              disabled={disabled}
            >
              {showMarkdown ? '普通模式' : 'Markdown'}
            </Button>
          </Space>

          <Button
            type="primary"
            size="large"
            icon={<SearchOutlined />}
            onClick={handleSubmit}
            disabled={disabled || !query.trim()}
            loading={disabled}
          >
            开始研究
          </Button>
        </div>
      </Space>

      {/* 文献选择器 */}
      <LiteratureSelector
        visible={showLiteratureSelector}
        onCancel={() => setShowLiteratureSelector(false)}
        onConfirm={handleLiteratureConfirm}
        projectId={currentProject?.id}
        initialSelected={selectedLiterature}
        maxSelection={10}
      />
    </div>
  );
};
