import React, { useEffect, useRef, useState, useMemo } from 'react';
import { Card, Spin, Empty, Button, Space, Slider, Switch, Typography, Tooltip, Tag } from 'antd';
import {
  FullscreenOutlined,
  FullscreenExitOutlined,
  ReloadOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import ForceGraph2D from 'react-force-graph-2d';
import type {
  ForceGraphMethods,
  GraphData,
  LinkObject,
  NodeObject,
} from 'react-force-graph-2d';
import type { LiteratureCitationResponse } from '@/services/api/literature';

const { Text, Title } = Typography;

type GraphNodeData = {
  name: string;
  authors?: string[];
  year?: number;
  citationCount?: number;
  isCenter?: boolean;
  level: number;
  color: string;
  size: number;
  doi?: string;
  url?: string;
};

type GraphNode = NodeObject<GraphNodeData>;

type GraphLinkData = {
  type: 'citation' | 'reference';
  strength: number;
};

type GraphLink = LinkObject<GraphNodeData, GraphLinkData>;

interface CitationGraphProps {
  citationData: LiteratureCitationResponse;
  loading?: boolean;
  height?: number;
  onNodeClick?: (node: GraphNode) => void;
  className?: string;
}

const getNodeColor = (node: GraphNodeData): string => {
  if (node.isCenter) return '#1890ff'; // 中心节点 - 蓝色
  if (node.level === 1) return '#52c41a'; // 引用文献 - 绿色
  if (node.level === -1) return '#fa8c16'; // 参考文献 - 橙色
  return '#8c8c8c'; // 其他 - 灰色
};

const getNodeSize = (node: GraphNodeData): number => {
  if (node.isCenter) return 12;
  const citationCount = node.citationCount || 0;
  if (citationCount > 1000) return 10;
  if (citationCount > 100) return 8;
  if (citationCount > 10) return 6;
  return 5;
};

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

export const CitationGraph: React.FC<CitationGraphProps> = ({
  citationData,
  loading = false,
  height = 400,
  onNodeClick,
  className = '',
}) => {
  const graphRef = useRef<ForceGraphMethods<GraphNodeData, GraphLinkData> | undefined>();
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [linkDistance, setLinkDistance] = useState(30);
  const [chargeStrength, setChargeStrength] = useState(-300);
  const [showLabels, setShowLabels] = useState(true);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  const handleLinkDistanceChange = (value: number | [number]) => {
    setLinkDistance(Array.isArray(value) ? value[0] : value);
  };

  const handleChargeStrengthChange = (value: number | [number]) => {
    setChargeStrength(Array.isArray(value) ? value[0] : value);
  };

  const graphData = useMemo<GraphData<GraphNodeData, GraphLinkData>>(() => {
    if (!citationData) {
      return { nodes: [], links: [] };
    }

    const nodes: GraphNode[] = [];
    const links: GraphLink[] = [];

    // 添加中心节点
    const centerNode: GraphNode = {
      id: `center-${citationData.literature_id}`,
      name: citationData.title,
      isCenter: true,
      level: 0,
      color: '#1890ff',
      size: 12,
    };
    nodes.push(centerNode);

    // 添加引用文献节点
    citationData.citations?.forEach((citation, index) => {
      const node: GraphNode = {
        id: `citation-${index}`,
        name: citation.title || `Citation ${index + 1}`,
        authors: citation.authors,
        year: citation.year,
        citationCount: citation.citationCount,
        level: 1,
        color: '#52c41a',
        size: getNodeSize({
          level: 1,
          citationCount: citation.citationCount,
        }),
        doi: citation.doi,
        url: citation.url,
      };
      node.color = getNodeColor(node);
      node.size = getNodeSize(node);
      nodes.push(node);

      // 添加链接
      links.push({
        source: node.id,
        target: centerNode.id,
        type: 'citation',
        strength: 1,
      });
    });

    // 添加参考文献节点
    citationData.references?.forEach((reference, index) => {
      const node: GraphNode = {
        id: `reference-${index}`,
        name: reference.title || `Reference ${index + 1}`,
        authors: reference.authors,
        year: reference.year,
        citationCount: reference.citationCount,
        level: -1,
        color: '#fa8c16',
        size: getNodeSize({
          level: -1,
          citationCount: reference.citationCount,
        }),
        doi: reference.doi,
        url: reference.url,
      };
      node.color = getNodeColor(node);
      node.size = getNodeSize(node);
      nodes.push(node);

      // 添加链接
      links.push({
        source: centerNode.id,
        target: node.id,
        type: 'reference',
        strength: 1,
      });
    });

    return { nodes, links };
  }, [citationData]);

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
    onNodeClick?.(node);
  };

  const handleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const handleRefreshGraph = () => {
    graphRef.current?.d3ReheatSimulation();
  };

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) {
      return;
    }

    const chargeForce = graph.d3Force('charge');
    if (chargeForce && typeof (chargeForce as { strength?: unknown }).strength === 'function') {
      (chargeForce as { strength: (fn: () => number) => unknown }).strength(() => chargeStrength);
    }

    const linkForce = graph.d3Force('link');
    if (linkForce && typeof (linkForce as { distance?: unknown }).distance === 'function') {
      (linkForce as { distance: (fn: () => number) => unknown }).distance(() => linkDistance);
    }

    graph.d3ReheatSimulation();
  }, [chargeStrength, linkDistance]);

  const handleZoomIn = () => {
    const graph = graphRef.current;
    if (!graph) return;
    const currentZoom = graph.zoom();
    graph.zoom(currentZoom * 1.2, 200);
  };

  const handleZoomOut = () => {
    const graph = graphRef.current;
    if (!graph) return;
    const currentZoom = graph.zoom();
    graph.zoom(currentZoom * 0.8, 200);
  };

  const truncateText = (text: string, maxLength: number = 30): string => {
    return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
  };

  if (loading) {
    return (
      <Card className={className}>
        <div className="flex items-center justify-center h-96">
          <Spin size="large" tip="加载引用关系图..." />
        </div>
      </Card>
    );
  }

  if (!citationData || (citationData.citations?.length === 0 && citationData.references?.length === 0)) {
    return (
      <Card className={className}>
        <Empty
          description="暂无引用关系数据"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </Card>
    );
  }

  return (
    <Card
      className={`${className} ${isFullscreen ? 'fixed inset-0 z-50 m-0 rounded-none' : ''}`}
      title={
        <Space>
          <span>引用关系图</span>
          <Tooltip title="显示文献的引用和参考关系">
            <InfoCircleOutlined className="text-gray-400" />
          </Tooltip>
        </Space>
      }
      extra={
        <Space>
          <Tooltip title="刷新图形">
            <Button icon={<ReloadOutlined />} onClick={handleRefreshGraph} />
          </Tooltip>
          <Tooltip title="放大">
            <Button icon={<ZoomInOutlined />} onClick={handleZoomIn} />
          </Tooltip>
          <Tooltip title="缩小">
            <Button icon={<ZoomOutOutlined />} onClick={handleZoomOut} />
          </Tooltip>
          <Tooltip title={isFullscreen ? '退出全屏' : '全屏显示'}>
            <Button
              icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
              onClick={handleFullscreen}
            />
          </Tooltip>
        </Space>
      }
    >
      <div className="space-y-4">
        {/* 控制面板 */}
        <div className="flex flex-wrap gap-4 p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center space-x-2">
            <Text className="text-sm font-medium">节点距离:</Text>
            <Slider
              min={10}
              max={100}
              value={linkDistance}
              onChange={handleLinkDistanceChange}
              style={{ width: 100 }}
            />
          </div>

          <div className="flex items-center space-x-2">
            <Text className="text-sm font-medium">斥力强度:</Text>
            <Slider
              min={-500}
              max={-100}
              value={chargeStrength}
              onChange={handleChargeStrengthChange}
              style={{ width: 100 }}
            />
          </div>

          <div className="flex items-center space-x-2">
            <Text className="text-sm font-medium">显示标签:</Text>
            <Switch size="small" checked={showLabels} onChange={setShowLabels} />
          </div>
        </div>

        {/* 图例 */}
        <div className="flex flex-wrap gap-4 p-3 bg-blue-50 rounded-lg">
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
            <Text className="text-sm">当前文献</Text>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            <Text className="text-sm">引用文献 ({citationData.citation_count})</Text>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-orange-500 rounded-full"></div>
            <Text className="text-sm">参考文献 ({citationData.reference_count})</Text>
          </div>
        </div>

        {/* 力导向图 */}
        <div className="relative border border-gray-200 rounded-lg overflow-hidden">
          <ForceGraph2D<GraphNodeData, GraphLinkData>
            ref={graphRef}
            graphData={graphData}
            width={isFullscreen ? window.innerWidth - 48 : undefined}
            height={isFullscreen ? window.innerHeight - 200 : height}
            backgroundColor="#fafafa"
            nodeColor={(node) => node.color}
            nodeVal={(node) => node.size}
            nodeLabel={(node) => {
              const authors = node.authors?.slice(0, 3).join(', ') || '未知作者';
              const year = node.year ? ` (${node.year})` : '';
              const citationInfo = node.citationCount ? `\n引用: ${node.citationCount}` : '';
              return `${node.name}${year}\n作者: ${authors}${citationInfo}`;
            }}
            nodeCanvasObject={(node, ctx, globalScale) => {
              if (!showLabels || globalScale < 2) return;
              const { name, size, x, y } = node;
              if (!isFiniteNumber(x) || !isFiniteNumber(y)) return;

              const label = truncateText(name, 25);
              const fontSize = Math.min(12, 12 / globalScale);
              ctx.font = `${fontSize}px Sans-Serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = '#333';

              // 背景
              const textWidth = ctx.measureText(label).width;
              ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
              ctx.fillRect(x - textWidth / 2 - 2, y - fontSize / 2 - 1, textWidth + 4, fontSize + 2);

              // 文字
              ctx.fillStyle = '#333';
              ctx.fillText(label, x, y + size + 10);
            }}
            onNodeClick={(node) => handleNodeClick(node as GraphNode)}
            linkColor={() => '#ccc'}
            linkWidth={1}
            linkDirectionalArrowLength={6}
            linkDirectionalArrowRelPos={1}
            linkCurvature={0.2}
            cooldownTime={3000}
            warmupTicks={100}
          />
        </div>

        {/* 选中节点信息 */}
        {selectedNode && (
          <Card size="small" className="bg-blue-50 border-blue-200">
            <div className="space-y-2">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <Title level={5} className="mb-1">
                    {selectedNode.name}
                  </Title>
                  {selectedNode.authors && (
                    <Text type="secondary" className="text-sm">
                      作者: {selectedNode.authors.join(', ')}
                    </Text>
                  )}
                </div>
                <Button type="text" size="small" onClick={() => setSelectedNode(null)}>
                  ×
                </Button>
              </div>

              <div className="flex flex-wrap gap-2">
                {selectedNode.year && <Tag color="blue">{selectedNode.year}</Tag>}
                {selectedNode.citationCount !== undefined && (
                  <Tag color="green">引用: {selectedNode.citationCount}</Tag>
                )}
                {selectedNode.isCenter && <Tag color="red">当前文献</Tag>}
                {selectedNode.level === 1 && <Tag color="cyan">引用文献</Tag>}
                {selectedNode.level === -1 && <Tag color="orange">参考文献</Tag>}
              </div>

              {(selectedNode.doi || selectedNode.url) && (
                <div className="flex gap-2">
                  {selectedNode.doi && (
                    <Button
                      type="link"
                      size="small"
                      href={`https://doi.org/${selectedNode.doi}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      查看 DOI
                    </Button>
                  )}
                  {selectedNode.url && (
                    <Button
                      type="link"
                      size="small"
                      href={selectedNode.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      查看原文
                    </Button>
                  )}
                </div>
              )}
            </div>
          </Card>
        )}
      </div>
    </Card>
  );
};

export default CitationGraph;
