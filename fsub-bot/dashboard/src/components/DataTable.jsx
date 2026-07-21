export default function DataTable({ columns, data, onRowClick, emptyMessage = 'No data found', loading = false }) {
  if (loading) {
    return (
      <div className="card overflow-hidden">
        <div className="animate-pulse">
          {/* Header skeleton */}
          <div className="border-b border-border px-6 py-4 flex gap-6">
            {Array.from({ length: Math.min(columns.length, 5) }).map((_, i) => (
              <div key={i} className="h-3 bg-border/60 rounded-full flex-1" />
            ))}
          </div>
          {/* Row skeletons */}
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="border-b border-border/50 px-6 py-5 flex gap-6">
              {Array.from({ length: Math.min(columns.length, 5) }).map((_, j) => (
                <div key={j} className="h-3 bg-border/30 rounded-full flex-1" />
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="card p-16 text-center">
        <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-bg-secondary border border-border flex items-center justify-center">
          <svg className="w-7 h-7 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
        </div>
        <p className="text-text-muted text-sm">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-bg-secondary/50">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="px-6 py-3.5 text-left text-[11px] font-semibold text-text-muted uppercase tracking-wider"
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, idx) => (
              <tr
                key={row.id || row.content_id || row.channel_id || idx}
                onClick={() => onRowClick?.(row)}
                className={`
                  border-b border-border/50 last:border-b-0
                  transition-colors duration-150 hover:bg-bg-card-hover
                  ${onRowClick ? 'cursor-pointer' : ''}
                `}
              >
                {columns.map((col) => (
                  <td key={col.key} className="px-6 py-4 text-sm text-text-secondary whitespace-nowrap">
                    {col.render ? col.render(row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
