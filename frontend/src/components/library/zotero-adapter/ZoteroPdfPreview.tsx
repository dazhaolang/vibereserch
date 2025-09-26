import { useState, useCallback, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { Spin, Alert, Button, Space, Slider } from 'antd';
import { useLibraryStore } from '@/stores/library.store';
import styles from './zotero-pdf-preview.module.css';
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

export function ZoteroPdfPreview() {
  const pdfUrl = useLibraryStore((state) => state.selectedItemDetail?.pdf_url);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.1);

  const handleDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setPageNumber(1);
  }, []);

  const handlePrev = useCallback(() => {
    setPageNumber((prev) => Math.max(prev - 1, 1));
  }, []);

  const handleNext = useCallback(() => {
    setPageNumber((prev) => (numPages ? Math.min(prev + 1, numPages) : prev + 1));
  }, [numPages]);

  const sliderValue = useMemo(() => Number(scale.toFixed(1)), [scale]);

  const handleZoomChange = useCallback((value: number | number[]) => {
    const nextValue = Array.isArray(value) ? value[0] : value;
    setScale(nextValue);
  }, []);

  if (!pdfUrl) {
    return (
      <div className={styles.previewPlaceholder}>
        <Alert message="暂无 PDF 可预览" type="info" showIcon />
      </div>
    );
  }

  return (
    <div className={styles.previewContainer}>
      <Document
        file={pdfUrl}
        loading={<Spin tip="加载 PDF…" />}
        onLoadSuccess={handleDocumentLoadSuccess}
      >
        <Page pageNumber={pageNumber} scale={scale} width={320} />
      </Document>
      <div className={styles.controls}>
        <Space size={12} align="center">
          <Button size="small" onClick={handlePrev} disabled={pageNumber <= 1}>
            上一页
          </Button>
          <span className={styles.pageInfo}>
            第 {pageNumber}
            {numPages ? ` / ${numPages}` : ''} 页
          </span>
          <Button
            size="small"
            onClick={handleNext}
            disabled={numPages !== null ? pageNumber >= numPages : false}
          >
            下一页
          </Button>
        </Space>
        <div className={styles.zoomControl}>
          <span>缩放</span>
          <Slider
            min={0.5}
            max={2}
            step={0.1}
            value={sliderValue}
            onChange={handleZoomChange}
            tooltip={{ formatter: (value) => `${value}x` }}
          />
        </div>
      </div>
    </div>
  );
}
