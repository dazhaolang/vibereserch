import type {
  ResearchExperienceSummary,
  ResearchResult,
  ResearchSource,
} from '@/types';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const toStringOrUndefined = (value: unknown): string | undefined =>
  typeof value === 'string' && value.trim().length > 0 ? value : undefined;

const toStringWithFallback = (value: unknown, fallback = ''): string =>
  typeof value === 'string' && value.trim().length > 0 ? value : fallback;

const toNumberOrUndefined = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === 'string') {
    const parsed = Number.parseFloat(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return undefined;
};

const toBoundedNumber = (value: unknown, fallback: number, min: number, max: number): number => {
  const parsed = toNumberOrUndefined(value);
  if (typeof parsed === 'number') {
    return Math.min(Math.max(parsed, min), max);
  }
  return Math.min(Math.max(fallback, min), max);
};

const toIntegerOrZero = (value: unknown): number => {
  const parsed = toNumberOrUndefined(value);
  if (typeof parsed === 'number') {
    return Math.round(parsed);
  }
  return 0;
};

const toStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    .map((item) => item.trim());
};

const toSegments = (value: unknown): Array<number | string> => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is number | string =>
    typeof item === 'number' || typeof item === 'string');
};

const toSources = (value: unknown): ResearchSource[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  const sources: ResearchSource[] = [];
  value.forEach((item, index) => {
    if (!isRecord(item)) {
      return;
    }

    const idValue = item.id;
    const id = typeof idValue === 'number' || typeof idValue === 'string'
      ? idValue
      : `source-${index}`;

    sources.push({
      id,
      title: toStringOrUndefined(item.title),
      authors: toStringArray(item.authors),
      year: toNumberOrUndefined(item.year),
      journal: toStringOrUndefined(item.journal),
      doi: toStringOrUndefined(item.doi),
      confidence: toNumberOrUndefined(item.confidence),
      relevance: toStringOrUndefined(item.relevance),
      segments: toSegments(item.segments),
    });
  });

  return sources;
};

const toExperiences = (value: unknown): ResearchExperienceSummary[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  const experiences: ResearchExperienceSummary[] = [];
  value.forEach((item) => {
    if (!isRecord(item)) {
      return;
    }

    experiences.push({
      id: typeof item.id === 'number' ? item.id : undefined,
      title: toStringOrUndefined(item.title),
      experience_type: toStringOrUndefined(item.experience_type),
      research_domain: toStringOrUndefined(item.research_domain),
      content: toStringOrUndefined(item.content),
      key_findings: toStringArray(item.key_findings),
      practical_guidelines: toStringArray(item.practical_guidelines),
      quality_score: toNumberOrUndefined(item.quality_score),
    });
  });

  return experiences;
};

const buildMetadata = (
  nested: Record<string, unknown> | undefined,
  rawPayload: Record<string, unknown> | undefined,
  extra?: Record<string, unknown>
): Record<string, unknown> | undefined => {
  const metadata: Record<string, unknown> = {};

  if (nested) {
    Object.assign(metadata, nested);
  }

  if (extra) {
    Object.assign(metadata, extra);
  }

  if (rawPayload) {
    metadata.raw_payload = rawPayload;
  }

  return Object.keys(metadata).length > 0 ? metadata : undefined;
};

export interface NormalizeResearchResultOptions {
  base: Pick<ResearchResult, 'id' | 'project_id' | 'mode' | 'question'>;
  timestamp?: string;
  fallbackAnswer?: string;
  fallbackAnalysis?: string;
  defaultConfidence?: number;
  metadata?: Record<string, unknown>;
}

const isValidStatus = (value: unknown): value is ResearchResult['status'] =>
  typeof value === 'string' && ['pending', 'processing', 'completed', 'error'].includes(value);

const preferredTimestamp = (raw: Record<string, unknown> | undefined, fallback?: string): string => {
  const ts = raw?.timestamp;
  if (typeof ts === 'string' && ts.trim().length > 0) {
    return ts;
  }
  return fallback ?? new Date().toISOString();
};

export const normalizeResearchResult = (
  raw: unknown,
  options: NormalizeResearchResultOptions
): ResearchResult => {
  const payload = isRecord(raw) ? raw : undefined;

  const status = payload?.status;
  const normalizedStatus: ResearchResult['status'] = isValidStatus(status) ? status : 'completed';

  const answer = toStringWithFallback(payload?.answer, options.fallbackAnswer ?? '');
  const detailedAnalysis = toStringWithFallback(
    payload?.detailed_analysis,
    options.fallbackAnalysis ?? ''
  );

  const confidence = toBoundedNumber(
    payload?.confidence,
    options.defaultConfidence ?? 0.8,
    0,
    1
  );

  const literatureCount = toIntegerOrZero(payload?.literature_count);

  const nestedMetadata = isRecord(payload?.metadata) ? payload.metadata : undefined;
  const metadata = buildMetadata(nestedMetadata, payload, options.metadata);

  const result: ResearchResult = {
    id: options.base.id,
    project_id: options.base.project_id,
    mode: options.base.mode,
    question: options.base.question,
    task_id: (() => {
      if (typeof payload?.task_id === 'number' && Number.isFinite(payload.task_id)) {
        return payload.task_id;
      }
      const extraTaskIdCandidate = options.metadata?.['task_id'];
      if (typeof extraTaskIdCandidate === 'number' && Number.isFinite(extraTaskIdCandidate)) {
        return extraTaskIdCandidate;
      }
      return undefined;
    })(),
    status: normalizedStatus,
    timestamp: preferredTimestamp(payload, options.timestamp),
    answer,
    detailed_analysis: detailedAnalysis,
    key_findings: toStringArray(payload?.key_findings),
    confidence,
    sources: toSources(payload?.sources),
    research_gaps: toStringArray(payload?.research_gaps),
    next_questions: toStringArray(payload?.next_questions),
    methodology_suggestions: toStringArray(payload?.methodology_suggestions),
    literature_count: literatureCount,
    main_experiences: toExperiences(payload?.main_experiences),
    suggestions: toStringArray(payload?.suggestions),
    metadata,
    error_message: toStringOrUndefined(payload?.error_message),
    query: toStringOrUndefined(payload?.query),
    confidence_score: toNumberOrUndefined(payload?.confidence_score),
    processing_time: toNumberOrUndefined(payload?.processing_time),
    created_at: toStringOrUndefined(payload?.created_at),
  };

  return result;
};
