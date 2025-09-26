import React, { useState, useEffect } from 'react';
import {
  Drawer,
  Form,
  Button,
  Space,
  Row,
  Col,
  Select,
  Slider,
  Tag,
  Input,
  Switch,
  Typography,
  Collapse,
  Badge,
} from 'antd';
import {
  FilterOutlined,
  ClearOutlined,
  SearchOutlined,
} from '@ant-design/icons';
const { Text } = Typography;
const { Panel } = Collapse;

export interface AdvancedFilterValues {
  yearRange?: [number, number];
  tags?: string[];
  source?: string[];
  parsingStatus?: string[];
  qualityRange?: [number, number];
  citationRange?: [number, number];
  keywords?: string[];
  authors?: string[];
  hasAbstract?: boolean;
  hasPdf?: boolean;
  isStarred?: boolean;
}

interface LibraryAdvancedFilterProps {
  visible: boolean;
  onClose: () => void;
  onApplyFilter: (filters: AdvancedFilterValues) => void;
  onClearFilter: () => void;
  initialValues?: AdvancedFilterValues;
  availableSources?: string[];
  loading?: boolean;
}

const currentYear = new Date().getFullYear();
const yearMarks = {
  1990: '1990',
  2000: '2000',
  2010: '2010',
  2020: '2020',
  [currentYear]: currentYear.toString(),
};

const qualityMarks = {
  0: '0',
  25: '25',
  50: '50',
  75: '75',
  100: '100',
};

const citationMarks = {
  0: '0',
  10: '10',
  100: '100',
  1000: '1k',
  10000: '10k',
};

export const LibraryAdvancedFilter: React.FC<LibraryAdvancedFilterProps> = ({
  visible,
  onClose,
  onApplyFilter,
  onClearFilter,
  initialValues,
  availableSources = [],
  loading = false,
}) => {
  const [form] = Form.useForm<AdvancedFilterValues>();
  const [filterCount, setFilterCount] = useState(0);
  const [tagInput, setTagInput] = useState('');
  const [keywordInput, setKeywordInput] = useState('');
  const [authorInput, setAuthorInput] = useState('');

  const getStringArrayValue = (name: 'tags' | 'keywords' | 'authors'): string[] => {
    const rawValues = form.getFieldsValue();
    const value = rawValues[name];
    if (!Array.isArray(value)) {
      return [];
    }
    return value.filter((item): item is string => typeof item === 'string');
  };

  const defaultSources = [
    'semantic_scholar',
    'pubmed',
    'arxiv',
    'google_scholar',
    'direct_upload',
    'other',
  ];

  const sourceOptions = availableSources.length > 0 ? availableSources : defaultSources;

  const parsingStatusOptions = [
    { label: '已解析', value: 'parsed' },
    { label: '解析中', value: 'parsing' },
    { label: '解析失败', value: 'failed' },
    { label: '未解析', value: 'pending' },
  ];

  useEffect(() => {
    if (initialValues) {
      form.setFieldsValue(initialValues);
      calculateFilterCount(initialValues);
    }
  }, [initialValues, form]);

  const calculateFilterCount = (values: AdvancedFilterValues) => {
    let count = 0;
    if (values.yearRange && (values.yearRange[0] !== 1990 || values.yearRange[1] !== currentYear)) count++;
    if (values.tags && values.tags.length > 0) count++;
    if (values.source && values.source.length > 0) count++;
    if (values.parsingStatus && values.parsingStatus.length > 0) count++;
    if (values.qualityRange && (values.qualityRange[0] !== 0 || values.qualityRange[1] !== 100)) count++;
    if (values.citationRange && (values.citationRange[0] !== 0 || values.citationRange[1] !== 10000)) count++;
    if (values.keywords && values.keywords.length > 0) count++;
    if (values.authors && values.authors.length > 0) count++;
    if (values.hasAbstract) count++;
    if (values.hasPdf) count++;
    if (values.isStarred) count++;
    setFilterCount(count);
  };

  const handleApply = async () => {
    try {
      const values = await form.validateFields();
      calculateFilterCount(values);
      onApplyFilter(values);
      onClose();
    } catch (error) {
      console.error('Filter validation failed:', error);
    }
  };

  const handleClear = () => {
    form.resetFields();
    setFilterCount(0);
    onClearFilter();
  };

  const handleAddTag = () => {
    if (tagInput.trim()) {
      const currentTags = getStringArrayValue('tags');
      const nextTag = tagInput.trim();
      if (!currentTags.includes(nextTag)) {
        form.setFieldValue('tags', [...currentTags, nextTag]);
        setTagInput('');
      }
    }
  };

  const handleRemoveTag = (removedTag: string) => {
    const currentTags = getStringArrayValue('tags');
    form.setFieldValue('tags', currentTags.filter((tag) => tag !== removedTag));
  };

  const handleAddKeyword = () => {
    if (keywordInput.trim()) {
      const currentKeywords = getStringArrayValue('keywords');
      const nextKeyword = keywordInput.trim();
      if (!currentKeywords.includes(nextKeyword)) {
        form.setFieldValue('keywords', [...currentKeywords, nextKeyword]);
        setKeywordInput('');
      }
    }
  };

  const handleRemoveKeyword = (removedKeyword: string) => {
    const currentKeywords = getStringArrayValue('keywords');
    form.setFieldValue('keywords', currentKeywords.filter((keyword) => keyword !== removedKeyword));
  };

  const handleAddAuthor = () => {
    if (authorInput.trim()) {
      const currentAuthors = getStringArrayValue('authors');
      const nextAuthor = authorInput.trim();
      if (!currentAuthors.includes(nextAuthor)) {
        form.setFieldValue('authors', [...currentAuthors, nextAuthor]);
        setAuthorInput('');
      }
    }
  };

  const handleRemoveAuthor = (removedAuthor: string) => {
    const currentAuthors = getStringArrayValue('authors');
    form.setFieldValue('authors', currentAuthors.filter((author) => author !== removedAuthor));
  };

  return (
    <Drawer
      title={
        <Space>
          <FilterOutlined />
          <span>高级筛选</span>
          {filterCount > 0 && (
            <Badge count={filterCount} style={{ backgroundColor: '#1890ff' }} />
          )}
        </Space>
      }
      placement="right"
      width={420}
      onClose={onClose}
      open={visible}
      destroyOnClose
      extra={
        <Space>
          <Button icon={<ClearOutlined />} onClick={handleClear}>
            清除
          </Button>
          <Button type="primary" onClick={handleApply} loading={loading}>
            应用筛选
          </Button>
        </Space>
      }
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          yearRange: [1990, currentYear],
          qualityRange: [0, 100],
          citationRange: [0, 10000],
          hasAbstract: false,
          hasPdf: false,
          isStarred: false,
        }}
      >
        <Collapse defaultActiveKey={['basic', 'content']} ghost>
          <Panel header="基础筛选" key="basic">
            <Form.Item label="发表年份" name="yearRange">
              <Slider
                range
                min={1990}
                max={currentYear}
                marks={yearMarks}
                tooltip={{ formatter: (value) => `${value}年` }}
              />
            </Form.Item>

            <Form.Item label="数据源" name="source">
              <Select
                mode="multiple"
                placeholder="选择数据源"
                options={sourceOptions.map(source => ({
                  label: source === 'semantic_scholar' ? 'Semantic Scholar' :
                         source === 'direct_upload' ? '直接上传' :
                         source.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase()),
                  value: source,
                }))}
                allowClear
              />
            </Form.Item>

            <Form.Item label="解析状态" name="parsingStatus">
              <Select
                mode="multiple"
                placeholder="选择解析状态"
                options={parsingStatusOptions}
                allowClear
              />
            </Form.Item>

            <Form.Item label="质量评分" name="qualityRange">
              <Slider
                range
                min={0}
                max={100}
                marks={qualityMarks}
                tooltip={{ formatter: (value) => `${value}分` }}
              />
            </Form.Item>

            <Form.Item label="引用次数" name="citationRange">
              <Slider
                range
                min={0}
                max={10000}
                marks={citationMarks}
                tooltip={{
                  formatter: (value) =>
                    typeof value === 'number'
                      ? value >= 1000
                        ? `${(value / 1000).toFixed(1)}k`
                        : `${value}`
                      : '',
                }}
              />
            </Form.Item>
          </Panel>

          <Panel header="内容筛选" key="content">
            <Form.Item label="标签">
              <Space direction="vertical" className="w-full">
                <Row gutter={8}>
                  <Col flex={1}>
                    <Input
                      placeholder="添加标签"
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onPressEnter={handleAddTag}
                    />
                  </Col>
                  <Col>
                    <Button icon={<SearchOutlined />} onClick={handleAddTag} />
                  </Col>
                </Row>
                <Form.Item name="tags" noStyle>
                  <div>
                    {getStringArrayValue('tags').map((tag) => (
                      <Tag
                        key={tag}
                        closable
                        onClose={() => handleRemoveTag(tag)}
                        style={{ marginBottom: 4 }}
                      >
                        {tag}
                      </Tag>
                    ))}
                  </div>
                </Form.Item>
              </Space>
            </Form.Item>

            <Form.Item label="关键词">
              <Space direction="vertical" className="w-full">
                <Row gutter={8}>
                  <Col flex={1}>
                    <Input
                      placeholder="添加关键词"
                      value={keywordInput}
                      onChange={(e) => setKeywordInput(e.target.value)}
                      onPressEnter={handleAddKeyword}
                    />
                  </Col>
                  <Col>
                    <Button icon={<SearchOutlined />} onClick={handleAddKeyword} />
                  </Col>
                </Row>
                <Form.Item name="keywords" noStyle>
                  <div>
                    {getStringArrayValue('keywords').map((keyword) => (
                      <Tag
                        key={keyword}
                        closable
                        onClose={() => handleRemoveKeyword(keyword)}
                        style={{ marginBottom: 4 }}
                        color="blue"
                      >
                        {keyword}
                      </Tag>
                    ))}
                  </div>
                </Form.Item>
              </Space>
            </Form.Item>

            <Form.Item label="作者">
              <Space direction="vertical" className="w-full">
                <Row gutter={8}>
                  <Col flex={1}>
                    <Input
                      placeholder="添加作者"
                      value={authorInput}
                      onChange={(e) => setAuthorInput(e.target.value)}
                      onPressEnter={handleAddAuthor}
                    />
                  </Col>
                  <Col>
                    <Button icon={<SearchOutlined />} onClick={handleAddAuthor} />
                  </Col>
                </Row>
                <Form.Item name="authors" noStyle>
                  <div>
                    {getStringArrayValue('authors').map((author) => (
                      <Tag
                        key={author}
                        closable
                        onClose={() => handleRemoveAuthor(author)}
                        style={{ marginBottom: 4 }}
                        color="green"
                      >
                        {author}
                      </Tag>
                    ))}
                  </div>
                </Form.Item>
              </Space>
            </Form.Item>
          </Panel>

          <Panel header="文件筛选" key="files">
            <Space direction="vertical" className="w-full">
              <Row justify="space-between" align="middle">
                <Col>
                  <Text>包含摘要</Text>
                </Col>
                <Col>
                  <Form.Item name="hasAbstract" valuePropName="checked" noStyle>
                    <Switch size="small" />
                  </Form.Item>
                </Col>
              </Row>

              <Row justify="space-between" align="middle">
                <Col>
                  <Text>包含PDF</Text>
                </Col>
                <Col>
                  <Form.Item name="hasPdf" valuePropName="checked" noStyle>
                    <Switch size="small" />
                  </Form.Item>
                </Col>
              </Row>

              <Row justify="space-between" align="middle">
                <Col>
                  <Text>仅收藏</Text>
                </Col>
                <Col>
                  <Form.Item name="isStarred" valuePropName="checked" noStyle>
                    <Switch size="small" />
                  </Form.Item>
                </Col>
              </Row>
            </Space>
          </Panel>
        </Collapse>
      </Form>
    </Drawer>
  );
};

export default LibraryAdvancedFilter;
