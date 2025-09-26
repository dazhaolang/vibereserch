import { memo, useMemo } from 'react';
/* eslint-disable @typescript-eslint/no-unsafe-assignment */
/* eslint-disable @typescript-eslint/no-unsafe-return */
/* eslint-disable @typescript-eslint/no-unsafe-member-access */
import { DataGrid, type GridColDef, type GridRowIdGetter } from '@mui/x-data-grid';
import type { LiteratureItem } from '@/services/api/literature';
import { useLibraryStore } from '@/stores/library.store';
import styles from './zotero-items-table.module.css';

export const ZoteroItemsTable = memo(() => {
  const {
    items,
    isLoading,
    selectedRowIds,
    filterStarred,
    setRowSelection,
  } = useLibraryStore((state) => ({
    items: state.items,
    isLoading: state.isLoading,
    selectedRowIds: state.selectedRowIds,
    filterStarred: state.filterStarred,
    setRowSelection: state.setRowSelection,
  }));

  const getRowId = useMemo<GridRowIdGetter<LiteratureItem>>(
    () => (row) => row.id,
    [],
  );

  const columns = useMemo<GridColDef[]>(() => [
    {
      field: 'title',
      headerName: '标题',
      flex: 2,
      minWidth: 200,
    },
    {
      field: 'authors',
      headerName: '作者',
      flex: 1,
      valueGetter: ({ row }) => {
        const record = row as LiteratureItem;
        const authors = record.authors ?? [];
        return authors.slice(0, 2).join(', ');
      },
    },
    {
      field: 'publication_year',
      headerName: '年份',
      width: 100,
    },
    {
      field: 'source_platform',
      headerName: '来源',
      width: 130,
    },
  ], []);

  return (
    <div className={styles.wrapper}>
      <DataGrid<LiteratureItem>
        rows={filterStarred ? items.filter((item) => Boolean(item.is_starred)) : items}
        columns={columns}
        density="comfortable"
        loading={isLoading}
        disableColumnMenu
        checkboxSelection
        hideFooter
        autoHeight={false}
        rowHeight={44}
        onRowClick={(params) => {
          const id = Number(params.id);
          setRowSelection([id]);
        }}
        getRowId={getRowId}
        hideFooterSelectedRowCount
        initialState={{
          columns: {
            columnVisibilityModel: {
              source_platform: true,
            },
          },
          sorting: {
            sortModel: [{ field: 'publication_year', sort: 'desc' }],
          },
        }}
        sx={{
          color: 'rgba(226, 232, 240, 0.9)',
          backgroundColor: 'transparent',
          '& .MuiDataGrid-row': {
            cursor: 'pointer',
          },
          '& .Mui-selected': {
            backgroundColor: 'rgba(59, 130, 246, 0.14) !important',
          },
        }}
        rowSelectionModel={selectedRowIds}
        disableRowSelectionOnClick={false}
        onRowSelectionModelChange={(model) => {
          const ids = Array.isArray(model) ? model.map((id) => Number(id)) : [];
          setRowSelection(ids);
        }}
      />
    </div>
  );
});

ZoteroItemsTable.displayName = 'ZoteroItemsTable';
