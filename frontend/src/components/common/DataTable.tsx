import { fmtCell } from '../../utils/format'

export default function DataTable({ columns, rows, maxHeight = 420 }: { columns: string[]; rows: unknown[][]; maxHeight?: number }) {
  return (
    <div className="overflow-auto rounded-md border border-line" style={{ maxHeight }}>
      <table className="tbl">
        <thead className="sticky top-0 bg-panel"><tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((v, j) => (
                <td key={j} className={`whitespace-nowrap ${typeof v === 'number' ? 'num text-right' : ''}`}>{fmtCell(v)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
