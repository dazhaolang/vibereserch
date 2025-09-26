import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { literatureAPI } from '@/services/api/literature';
import type { LiteratureItem, LiteratureCitationResponse } from '@/services/api/literature';
import { useResearchShellStore, type LibraryStatus } from '@/stores/research-shell.store';
import { fetchProjects, type ProjectSummary } from '@/services/api/project';

interface LibraryCollection {
  id: string;
  name: string;
  type: 'collection' | 'tag' | 'smart';
  itemCount: number;
  children?: LibraryCollection[];
}

interface LibraryState {
  collections: LibraryCollection[];
  selectedCollectionId: string | null;
  items: LiteratureItem[];
  total: number;
  page: number;
  pageSize: number;
  isLoading: boolean;
  hasMore: boolean;
  isProjectsLoading: boolean;
  projects: ProjectSummary[];
  selectedProjectId: number | null;
  selectedItemId: number | null;
  selectedItemDetail: LiteratureItem | null;
  citations: LiteratureCitationResponse | null;
  isDetailLoading: boolean;
  detailError: string | null;
  selectedRowIds: number[];
  searchQuery: string;
  filterStarred: boolean;
  error: string | null;
  loadCollections: () => Promise<void>;
  loadItems: (reset?: boolean) => Promise<void>;
  setSelectedCollection: (collectionId: string | null) => void;
  setSelectedProject: (projectId: number | null) => void;
  setSelectedItem: (itemId: number | null) => void;
  setRowSelection: (ids: number[]) => void;
  setSearchQuery: (query: string) => void;
  setFilterStarred: (value: boolean) => void;
  loadItemDetail: (itemId: number) => Promise<void>;
  reset: () => void;
}

const INITIAL_PAGE_SIZE = 50;

const mapProjectStatus = (status: ProjectSummary['status']): LibraryStatus => {
  switch (status) {
    case 'pending':
    case 'processing':
      return 'building';
    case 'completed':
    case 'active':
      return 'ready';
    case 'archived':
    case 'unknown':
    case 'empty':
    default:
      return 'ready';
  }
};

const buildCollections = (project?: ProjectSummary | null): LibraryCollection[] => {
  if (!project) {
    return [];
  }

  return [
    {
      id: 'all',
      name: '全部文献',
      type: 'collection',
      itemCount: project.literature_count ?? 0,
    },
  ];
};

export const useLibraryStore = create<LibraryState>()(
  devtools((set, get) => ({
    collections: [],
    selectedCollectionId: null,
    items: [],
    total: 0,
    page: 1,
    pageSize: INITIAL_PAGE_SIZE,
    isLoading: false,
    hasMore: false,
    isProjectsLoading: false,
    projects: [],
    selectedProjectId: null,
    selectedItemId: null,
    selectedItemDetail: null,
    citations: null,
    isDetailLoading: false,
    detailError: null,
    selectedRowIds: [],
    searchQuery: '',
    filterStarred: false,
    error: null,

    loadCollections: async () => {
      set({ isProjectsLoading: true, error: null });
      try {
        const projects = await fetchProjects();
        const researchShell = useResearchShellStore.getState();
        const preferredId = get().selectedProjectId ?? researchShell.libraryId ?? null;
        const fallbackId = preferredId ?? projects[0]?.id ?? null;
        const activeProject = projects.find((project) => project.id === fallbackId) ?? null;

        if (fallbackId && activeProject) {
          researchShell.setLibraryId(fallbackId);
          researchShell.setLibraryStatus(mapProjectStatus(activeProject.status));
        } else {
          researchShell.setLibraryId(null);
          researchShell.setLibraryStatus('unselected');
        }

        set({
          projects,
          selectedProjectId: fallbackId,
          collections: buildCollections(activeProject),
          selectedCollectionId: activeProject ? 'all' : null,
        });
      } catch (error) {
        set({ error: error instanceof Error ? error.message : '加载文献集合失败' });
      } finally {
        set({ isProjectsLoading: false });
      }
    },

    loadItems: async (reset = false) => {
      const { selectedProjectId, page, pageSize, items, isLoading, selectedRowIds, selectedItemId } = get();
      if (!selectedProjectId || isLoading) {
        return;
      }

      set({ isLoading: true, error: null });
      try {
        const targetPage = reset ? 1 : page;
        const response = await literatureAPI.getLiterature({
          project_id: selectedProjectId,
          page: targetPage,
          size: pageSize,
          query: get().searchQuery || undefined,
        });

        const newItems = reset ? response.items : [...items, ...response.items];
        const filteredSelection = selectedRowIds.filter((id) => newItems.some((item) => item.id === id));
        const nextSelected = filteredSelection.length === 1
          ? filteredSelection[0]
          : reset
            ? newItems[0]?.id ?? null
            : selectedItemId ?? newItems[0]?.id ?? null;
        set({
          items: newItems,
          total: response.total,
          page: response.page ? response.page + 1 : targetPage + 1,
          pageSize: response.page_size ?? pageSize,
          hasMore: response.has_more ?? newItems.length < response.total,
          selectedRowIds: filteredSelection,
          selectedItemId: nextSelected,
          selectedItemDetail: reset ? null : get().selectedItemDetail,
          citations: reset ? null : get().citations,
        });
        if (nextSelected) {
          void get().loadItemDetail(nextSelected);
        }
      } catch (error) {
        set({ error: error instanceof Error ? error.message : '加载文献失败' });
      } finally {
        set({ isLoading: false });
      }
    },

    setSelectedCollection: (collectionId) => {
      set({
        selectedCollectionId: collectionId,
        page: 1,
        items: [],
        selectedItemId: null,
        selectedItemDetail: null,
        citations: null,
        detailError: null,
      });
    },

    setSelectedProject: (projectId) => {
      const researchShell = useResearchShellStore.getState();
      researchShell.setLibraryId(projectId);

      const { projects } = get();
      const project = projects.find((item) => item.id === projectId) ?? null;
      if (project) {
        researchShell.setLibraryStatus(mapProjectStatus(project.status));
      } else if (projectId === null) {
        researchShell.setLibraryStatus('unselected');
      }

      set({
        selectedProjectId: projectId,
        collections: buildCollections(project),
        selectedCollectionId: project ? 'all' : null,
        items: [],
        page: 1,
        hasMore: false,
        selectedItemId: null,
        selectedItemDetail: null,
        citations: null,
        detailError: null,
      });
    },

    setSelectedItem: (itemId) => {
      if (itemId === null) {
        set({
          selectedItemId: null,
          selectedItemDetail: null,
          citations: null,
          detailError: null,
          selectedRowIds: [],
        });
        return;
      }
      set({
        selectedItemId: itemId,
        selectedItemDetail: null,
        citations: null,
        detailError: null,
        selectedRowIds: [itemId],
      });
      void get().loadItemDetail(itemId);
    },

    setRowSelection: (ids) => {
      const uniqueIds = Array.from(new Set(ids));
      set({
        selectedRowIds: uniqueIds,
        selectedItemId: uniqueIds.length === 1 ? uniqueIds[0] : null,
        selectedItemDetail: uniqueIds.length === 1 ? get().selectedItemDetail : null,
        citations: uniqueIds.length === 1 ? get().citations : null,
        detailError: null,
      });
      if (uniqueIds.length === 1) {
        void get().loadItemDetail(uniqueIds[0]);
      }
    },

    setSearchQuery: (query) => {
      set({ searchQuery: query, page: 1 });
    },

    setFilterStarred: (value) => {
      set({ filterStarred: value, page: 1 });
    },

    loadItemDetail: async (itemId: number) => {
      set({ isDetailLoading: true, detailError: null });
      try {
        const detail = await literatureAPI.getLiteratureById(itemId);
        let citations: LiteratureCitationResponse | null = null;
        try {
          citations = await literatureAPI.getLiteratureCitations(itemId, {
            include_references: true,
            include_citations: true,
            max_citations: 10,
          });
        } catch (citationsError) {
          console.warn('Failed to fetch citations', citationsError);
        }
        set({ selectedItemDetail: detail, citations, isDetailLoading: false });
      } catch (error) {
        set({
          detailError: error instanceof Error ? error.message : '加载文献详情失败',
          isDetailLoading: false,
        });
      }
    },

    reset: () => {
      set({
        items: [],
        total: 0,
        page: 1,
        hasMore: false,
        selectedItemId: null,
        selectedItemDetail: null,
        citations: null,
        isDetailLoading: false,
        detailError: null,
        selectedRowIds: [],
        searchQuery: '',
        filterStarred: false,
        error: null,
      });
    },
  }))
);

export type { LibraryCollection };
export type { LibraryState };
