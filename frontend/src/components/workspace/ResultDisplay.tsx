import React, { useState } from 'react';
import { Card, Tabs, Tag, Space, Button, Tooltip, Collapse, Empty, Divider, Rate } from 'antd';
import {
  CopyOutlined,
  DownloadOutlined,
  ExpandOutlined,
  BookOutlined,
  ExperimentOutlined,
  BulbOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { message } from 'antd';
import type { ResearchResult, Literature } from '@/types';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

interface ResultDisplayProps {
  results: ResearchResult[];
}

export const ResultDisplay: React.FC<ResultDisplayProps> = ({ results }) => {
  const [activeKey, setActiveKey] = useState('0');
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});

  if (results.length === 0) {
    return (
      <Empty
        description="暂无研究结果"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      void message.success('已复制到剪贴板');
    } catch (error) {
      console.error('Failed to copy content:', error);
      void message.error('复制失败，请重试');
    }
  };

  const handleDownload = (result: ResearchResult) => {
    try {
      const content = generateExportContent(result);
      const blob = new Blob([content], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `research-result-${result.id || Date.now()}.md`;
      a.click();
      URL.revokeObjectURL(url);
      void message.success('下载成功');
    } catch (error) {
      console.error('Failed to download report:', error);
      void message.error('下载失败，请重试');
    }
  };

  interface ResultMetadataSummary {
    modelUsed?: string;
    tokensUsed?: number | string;
    experienceUsed?: boolean;
  }

  const resolveMetadata = (meta: unknown): ResultMetadataSummary => {
    if (!isRecord(meta)) {
      return {};
    }

    const summary: ResultMetadataSummary = {};

    if (typeof meta.model_used === 'string') {
      summary.modelUsed = meta.model_used;
    }
    if (typeof meta.tokens_used === 'number' || typeof meta.tokens_used === 'string') {
      summary.tokensUsed = meta.tokens_used;
    }
    if (typeof meta.experience_used === 'boolean') {
      summary.experienceUsed = meta.experience_used;
    }

    return summary;
  };

  const generateExportContent = (result: ResearchResult) => {
    const metadata = resolveMetadata(result.metadata);
    const references = Array.isArray(result.references)
      ? result.references.filter((ref): ref is Literature => isRecord(ref) && typeof ref.title === 'string')
      : [];
    return `# 研究结果报告

## 研究问题
${result.query}

## 研究模式
${result.mode === 'rag' ? 'RAG检索模式' : result.mode === 'deep' ? '深度研究模式' : '全自动模式'}

## 研究结果
${result.answer}

## 参考文献
${references.length > 0
        ? references
            .map((ref) => `- ${ref.title}${ref.authors?.length ? ` (${ref.authors.join(', ')})` : ''}`)
            .join('\n')
        : '暂无参考文献'}

## 元数据
- 置信度：${result.confidence_score}
- 处理时间：${result.processing_time}秒
- 生成时间：${result.created_at}
${metadata.tokensUsed ? `- Token使用：${metadata.tokensUsed}` : ''}
${metadata.modelUsed ? `- 使用模型：${metadata.modelUsed}` : ''}
`;
  };

  const toggleSection = (key: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const renderMetadataSummary = (result: ResearchResult) => {
    const metadata = resolveMetadata(result.metadata);
    const details: Array<React.ReactNode> = [];

    if (metadata.modelUsed) {
      details.push(<div key={`${result.id}-model`}>使用模型：{metadata.modelUsed}</div>);
    }
    if (metadata.tokensUsed !== undefined) {
      details.push(<div key={`${result.id}-tokens`}>Token 使用：{metadata.tokensUsed}</div>);
    }
    if (metadata.experienceUsed !== undefined) {
      details.push(
        <div key={`${result.id}-experience`}>
          是否使用主经验：{metadata.experienceUsed ? '是' : '否'}
        </div>
      );
    }

    return details.length > 0 ? <div className="text-xs text-gray-500 space-y-1">{details}</div> : null;
  };

  return (
    <div className="result-display">
      <Tabs
        activeKey={activeKey}
        onChange={setActiveKey}
        items={results.map((result, index) => {
          const metadata = resolveMetadata(result.metadata);
          const references = Array.isArray(result.references)
            ? result.references.filter((ref): ref is Literature => isRecord(ref) && typeof ref.title === 'string')
            : [];

          return {
            key: String(index),
            label: (
              <span>
                结果 {index + 1}
                <Tag
                  className="ml-2"
                  color={result.mode === 'rag' ? 'green' : result.mode === 'deep' ? 'purple' : 'blue'}
                >
                  {result.mode.toUpperCase()}
                </Tag>
              </span>
            ),
            children: (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3 }}
              >
                <Space direction="vertical" className="w-full" size="large">
                {/* 研究问题 */}
                <Card size="small" className="bg-blue-50">
                  <div className="flex items-start gap-2">
                    <BulbOutlined className="text-blue-500 text-lg mt-1" />
                    <div className="flex-1">
                      <div className="text-xs text-gray-600 mb-1">研究问题</div>
                      <div className="font-medium">{result.query}</div>
                    </div>
                  </div>
                </Card>

                {/* 主要结果 */}
                <Card
                  title={
                    <div className="flex justify-between items-center">
                      <span>研究结果</span>
                      <Space>
                        <Tooltip title="复制结果">
                          <Button
                            size="small"
                            icon={<CopyOutlined />}
                            onClick={() => handleCopy(result.answer)}
                          />
                        </Tooltip>
                        <Tooltip title="下载报告">
                          <Button
                            size="small"
                            icon={<DownloadOutlined />}
                            onClick={() => handleDownload(result)}
                          />
                        </Tooltip>
                        <Tooltip title={expandedSections[`result-${index}`] ? '收起' : '展开'}>
                          <Button
                            size="small"
                            icon={<ExpandOutlined />}
                            onClick={() => toggleSection(`result-${index}`)}
                          />
                        </Tooltip>
                      </Space>
                    </div>
                  }
                  className="shadow-sm"
                >
                  <div className={expandedSections[`result-${index}`] ? '' : 'max-h-96 overflow-y-auto'}>
                    <ReactMarkdown className="prose prose-sm max-w-none">
                      {result.answer}
                    </ReactMarkdown>
                  </div>

                  {/* 置信度评分 */}
                  <Divider />
                  <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">置信度：</span>
            <Rate
              disabled
                        value={Math.round((result.confidence_score || result.confidence || 0) * 5)}
                        className="text-sm"
                      />
                      <span className="text-sm font-medium">
                        {((result.confidence_score || result.confidence || 0) * 100).toFixed(1)}%
                      </span>
                    </div>
                  <div className="text-xs text-gray-500">
                    处理时间：{result.processing_time}秒
                  </div>
                </div>
                {renderMetadataSummary(result)}
              </Card>

                {/* 参考文献 */}
                {references.length > 0 && (
                  <Collapse ghost>
                    <Collapse.Panel
                      header={
                        <div className="flex items-center gap-2">
                          <BookOutlined />
                          <span>参考文献 ({references.length}篇)</span>
                        </div>
                      }
                      key="references"
                    >
                      <div className="space-y-3">
                        {references.map((ref, refIndex) => (
                          <motion.div
                            key={ref.id ?? refIndex}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: refIndex * 0.05 }}
                          >
                            <Card size="small" className="hover:shadow-md transition-shadow">
                              <div className="flex items-start gap-3">
                                <div className="text-2xl font-bold text-gray-300">
                                  {refIndex + 1}
                                </div>
                                <div className="flex-1">
                                  <div className="font-medium text-sm mb-1">
                                    {ref.title}
                                  </div>
                                  {ref.authors?.length ? (
                                    <div className="text-xs text-gray-600 mb-2">
                                      {ref.authors.join(', ')}
                                    </div>
                                  ) : null}
                                  <Space size="small" wrap>
                                    {ref.journal && (
                                      <Tag icon={<BookOutlined />} color="blue">
                                        {ref.journal}
                                      </Tag>
                                    )}
                                    {ref.publication_year && <Tag>{ref.publication_year}</Tag>}
                                    {ref.doi && (
                                      <Tooltip title="查看DOI">
                                        <Tag
                                          icon={<LinkOutlined />}
                                          color="green"
                                          className="cursor-pointer"
                                          onClick={() => window.open(`https://doi.org/${ref.doi}`, '_blank', 'noopener noreferrer')}
                                        >
                                          DOI
                                        </Tag>
                                      </Tooltip>
                                    )}
                                  </Space>
                                  {ref.abstract && (
                                    <div className="mt-2">
                                      <div
                                        className="text-xs text-gray-500 cursor-pointer"
                                        onClick={() => toggleSection(`ref-${index}-${refIndex}`)}
                                      >
                                        {expandedSections[`ref-${index}-${refIndex}`] ? '收起摘要 ▲' : '查看摘要 ▼'}
                                      </div>
                                      {expandedSections[`ref-${index}-${refIndex}`] && (
                                        <div className="mt-2 p-2 bg-gray-50 rounded text-xs">
                                          {ref.abstract}
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </Card>
                          </motion.div>
                        ))}
                      </div>
                    </Collapse.Panel>
                  </Collapse>
                )}

                {/* 元数据 */}
                {(result.metadata && (metadata.modelUsed || metadata.tokensUsed !== undefined || metadata.experienceUsed !== undefined)) && (
                  <Collapse ghost>
                    <Collapse.Panel
                      header={
                        <div className="flex items-center gap-2">
                          <ExperimentOutlined />
                          <span>技术细节</span>
                        </div>
                      }
                      key="metadata"
                    >
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        {metadata.modelUsed && (
                          <div className="bg-gray-50 p-2 rounded">
                            <div className="text-gray-600">使用模型</div>
                            <div className="font-medium">{metadata.modelUsed}</div>
                          </div>
                        )}
                        {metadata.tokensUsed !== undefined && (
                          <div className="bg-gray-50 p-2 rounded">
                            <div className="text-gray-600">Token消耗</div>
                            <div className="font-medium">{metadata.tokensUsed}</div>
                          </div>
                        )}
                        {metadata.experienceUsed !== undefined && (
                          <div className="bg-gray-50 p-2 rounded">
                            <div className="text-gray-600">使用经验</div>
                            <div className="font-medium">
                              {metadata.experienceUsed ? '是' : '否'}
                            </div>
                          </div>
                        )}
                        <div className="bg-gray-50 p-2 rounded">
                          <div className="text-gray-600">生成时间</div>
                          <div className="font-medium">
                            {result.created_at ? new Date(result.created_at).toLocaleString('zh-CN') : result.timestamp ? new Date(result.timestamp).toLocaleString('zh-CN') : '未知时间'}
                          </div>
                        </div>
                      </div>
                    </Collapse.Panel>
                  </Collapse>
                )}
              </Space>
            </motion.div>
            ),
          };
        })}
      />
    </div>
  );
};
