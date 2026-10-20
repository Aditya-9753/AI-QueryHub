/** Read-only SQL view with light keyword highlighting (no extra dependency). */
const KW = /\b(SELECT|FROM|WHERE|AND|OR|NOT|GROUP|BY|ORDER|HAVING|LIMIT|AS|ON|JOIN|LEFT|INNER|WITH|CASE|WHEN|THEN|ELSE|END|DESC|ASC|NULLIF|DISTINCT|UNION|IN|IS|NULL|CAST|OVER|PARTITION)\b/i
const FN = /\b(SUM|COUNT|AVG|MIN|MAX|DATE|STRFTIME|DATE_TRUNC|ROUND|COALESCE)\b(?=\s*\()/i
const TOKEN = /('(?:[^']|'')*'|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]+\b|\s+|.)/g

export default function SqlBlock({ sql, maxHeight = 260 }: { sql: string; maxHeight?: number }) {
  const pretty = sql.replace(/\s+(FROM|WHERE|GROUP BY|ORDER BY|LIMIT|AND)\s/gi, (_m: string, k: string) => `\n${k.toUpperCase() === 'AND' ? '  AND' : k.toUpperCase()} `)
  const parts = pretty.match(TOKEN) ?? []
  return (
    <pre className="overflow-auto rounded-md border border-line bg-[#0a111f] p-3 font-mono text-[11.5px] leading-relaxed text-ink"
      style={{ maxHeight }}>
      {parts.map((p, i) => {
        if (p.startsWith("'")) return <span key={i} className="text-salmon">{p}</span>
        if (/^\d/.test(p)) return <span key={i} className="text-warn">{p}</span>
        if (FN.test(p) && /^[A-Za-z_]+$/.test(p)) return <span key={i} className="text-ok">{p}</span>
        if (KW.test(p) && /^[A-Za-z_]+$/.test(p)) return <span key={i} className="font-semibold text-accent">{p.toUpperCase()}</span>
        return <span key={i}>{p}</span>
      })}
    </pre>
  )
}
