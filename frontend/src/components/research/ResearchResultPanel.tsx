import React, { useMemo } from 'react';
import { Card, Tabs, Button, Space, Tag, List, Typography, Tooltip, Progress, Badge, Empty } from 'antd';
import {
  FileTextOutlined,
  BulbOutlined,
  ExperimentOutlined,
  DownloadOutlined,
  ShareAltOutlined,
  SyncOutlined,
  BookOutlined,
  OrderedListOutlined,
  QuestionCircleOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import { Children } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import type { ResearchResult } from '@/types';

const { Title, Text, Paragraph } = Typography;
const prismTheme = vscDarkPlus;
type MarkdownCodeProps = React.ComponentPropsWithoutRef<'code'> & { inline?: boolean };

interface ResearchResultPanelProps {
  result: ResearchResult;
  onExport?: (result: ResearchResult) => void;
  onShare?: (result: ResearchResult) => void;
  onRegenerateExperience?: (result: ResearchResult) => void;
}

const modeColorMap: Record<ResearchResult['mode'], string> = {
  rag: '#52c41a',
  deep: '#1890ff',
  auto: '#722ed1',
};

const statusBadge = (status: ResearchResult['status'], error?: string) => {
  switch (status) {
    case 'pending':
      return <Badge status="default" text="等待中" />;
    case 'processing':
      return <Badge status="processing" text="处理中" />;
    case 'completed':
      return <Badge status="success" text="已完成" />;
    case 'error':
      return <Badge status="error" text={error || '处理失败'} />;
    default:
      return null;
  }
};

const markdownComponents: Components = {
  code({ inline, className, children, ...props }: MarkdownCodeProps) {
    const languageMatch = /language-(\w+)/.exec(className ?? '');
    if (inline || !languageMatch) {
      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    }

    const codeContent = Children.toArray(children)
      .map((child) => (typeof child === 'string' ? child : String(child ?? '')))
      .join('');

    return (
      <SyntaxHighlighter
        style={prismTheme}
        language={languageMatch[1]}
        PreTag="div"
      >
        {codeContent.replace(/\n$/, '')}
      </SyntaxHighlighter>
    );
  },
};

const renderMarkdown = (content: string) => (
  <ReactMarkdown components={markdownComponents}>
    {content || '_暂无内容_'}
  </ReactMarkdown>
);

const confidencePercent = (confidence: number | undefined) =>
  Math.round(Math.min(Math.max((confidence ?? 0) * 100, 0), 100));

export const ResearchResultPanel: React.FC<ResearchResultPanelProps> = ({
  result,
  onExport,
  onShare,
  onRegenerateExperience,
}) => {
  const modeTag = useMemo(() => (
    <Tag color={modeColorMap[result.mode] || '#999'}>
      {result.mode === 'rag' && 'RAG模式'}
      {result.mode === 'deep' && '深度研究'}
      {result.mode === 'auto' && '全自动'}
    </Tag>
  ), [result.mode]);

  const confidence = confidencePercent(result.confidence);

  return (
    <Card className="research-result-panel">
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-3">
          {modeTag}
          {statusBadge(result.status, result.error_message)}
          <Text type="secondary">{new Date(result.timestamp).toLocaleString()}</Text>
        </div>
        <Space>
          {result.status === 'completed' && onRegenerateExperience && (
            <Tooltip title="重新生成经验">
              <Button icon={<SyncOutlined />} onClick={() => onRegenerateExperience(result)} />
            </Tooltip>
          )}
          <Tooltip title="导出结果">
            <Button icon={<DownloadOutlined />} onClick={() => onExport?.(result)} disabled={!onExport} />
          </Tooltip>
          <Tooltip title="分享结果">
            <Button icon={<ShareAltOutlined />} onClick={() => onShare?.(result)} disabled={!onShare} />
          </Tooltip>
        </Space>
      </div>

      {result.status === 'error' ? (
        <Card className="bg-red-50 border-red-100">
          <Text type="danger">{result.error_message || '处理过程中出现错误，请稍后再试。'}</Text>
        </Card>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-6 mb-4">
            <div>
              <Text type="secondary">整体可信度</Text>
              <Progress
                percent={confidence}
                status={confidence > 70 ? 'success' : confidence > 40 ? 'active' : 'exception'}
                size="small"
                className="w-48"
              />
            </div>
            <div>
              <Text type="secondary">引用文献数量</Text>
              <div className="text-lg font-semibold">{result.literature_count}</div>
            </div>
          </div>

          <Tabs defaultActiveKey="answer">
            <Tabs.TabPane tab={<span><FileTextOutlined /> 研究答案</span>} key="answer">
              <AnimatePresence mode="wait">
                <motion.div
                  key="answer-content"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                >
                  <Card bordered={false} className="bg-white">
                    {renderMarkdown(result.answer)}

                    {result.key_findings?.length ? (
                      <div className="mt-6">
                        <Title level={5}>
                          <OrderedListOutlined className="mr-2" /> 关键发现
                        </Title>
                        <List
                          size="small"
                          dataSource={result.key_findings}
                          renderItem={(item, index) => (
                            <List.Item>
                              <Text>{index + 1}. {item}</Text>
                            </List.Item>
                          )}
                        />
                      </div>
                    ) : null}
                  </Card>
                </motion.div>
              </AnimatePresence>
            </Tabs.TabPane>

            <Tabs.TabPane tab={<span><BulbOutlined /> 详细分析</span>} key="analysis">
              <Card bordered={false}>{renderMarkdown(result.detailed_analysis)}</Card>
            </Tabs.TabPane>

            <Tabs.TabPane tab={<span><ExperimentOutlined /> 研究建议</span>} key="suggestions">
              <Card bordered={false}>
                <Space direction="vertical" className="w-full" size="large">
                  <div>
                    <Title level={5}><QuestionCircleOutlined className="mr-2" /> 研究空白</Title>
                    {result.research_gaps?.length ? (
                      <List
                        size="small"
                        dataSource={result.research_gaps}
                        renderItem={(item) => <List.Item>{item}</List.Item>}
                      />
                    ) : (
                      <Empty description="暂无研究空白" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    )}
                  </div>

                  <div>
                    <Title level={5}><QuestionCircleOutlined className="mr-2" /> 后续问题</Title>
                    {result.next_questions?.length ? (
                      <List
                        size="small"
                        dataSource={result.next_questions}
                        renderItem={(item) => <List.Item>{item}</List.Item>}
                      />
                    ) : (
                      <Empty description="暂无后续问题" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    )}
                  </div>

                  <div>
                    <Title level={5}><ToolOutlined className="mr-2" /> 方法学建议</Title>
                    {result.methodology_suggestions?.length ? (
                      <List
                        size="small"
                        dataSource={result.methodology_suggestions}
                        renderItem={(item) => <List.Item>{item}</List.Item>}
                      />
                    ) : (
                      <Empty description="暂无方法学建议" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    )}
                  </div>
                </Space>
              </Card>
            </Tabs.TabPane>

            <Tabs.TabPane tab={<span><BookOutlined /> 参考文献</span>} key="sources">
              <Card bordered={false}>
                {result.sources?.length ? (
                  <List
                    dataSource={result.sources}
                    renderItem={(source, index) => (
                      <List.Item key={source.id || index}>
                        <List.Item.Meta
                          title={
                            <span>
                              {index + 1}. {source.title || '未命名文献'}
                              {source.confidence !== undefined && (
                                <Tag color={source.confidence > 0.7 ? 'green' : source.confidence > 0.4 ? 'blue' : 'orange'} className="ml-2">
                                  置信度 {Math.round((source.confidence || 0) * 100)}%
                                </Tag>
                              )}
                            </span>
                          }
                          description={
                            <div className="text-sm text-gray-600 space-y-1">
                              {source.authors?.length ? <div>作者：{source.authors.join(', ')}</div> : null}
                              {source.journal ? <div>期刊：{source.journal}{source.year ? ` (${source.year})` : ''}</div> : null}
                              {source.doi ? <div>DOI：{source.doi}</div> : null}
                            </div>
                          }
                        />
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty description="暂无引用文献" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </Card>
            </Tabs.TabPane>

            {result.main_experiences?.length ? (
              <Tabs.TabPane tab={<span><BookOutlined /> 主经验</span>} key="experiences">
                <Card bordered={false}>
                  <List
                    dataSource={result.main_experiences}
                    renderItem={(experience, index) => (
                      <List.Item key={experience.id || index}>
                        <List.Item.Meta
                          title={experience.title || `经验 ${index + 1}`}
                          description={
                            <div className="space-y-2 text-sm text-gray-600">
                              {experience.content && <Paragraph>{experience.content}</Paragraph>}
                              {experience.key_findings?.length ? (
                                <div>
                                  <Text strong>关键要点：</Text>
                                  <List
                                    size="small"
                                    dataSource={experience.key_findings}
                                    renderItem={(item) => <List.Item>{item}</List.Item>}
                                  />
                                </div>
                              ) : null}
                            </div>
                          }
                        />
                      </List.Item>
                    )}
                  />
                </Card>
              </Tabs.TabPane>
            ) : null}
          </Tabs>
        </>
      )}
    </Card>
  );
};

export default ResearchResultPanel;
