/* Keep missing results distinct from zero; every benchmark retains its own scale. */
export function rankedRows(benchmark) {
  return (benchmark?.rows ?? []).map((row, index) => ({...row, index})).sort((a, b) => {
    const aValid = a.status === 'complete' && Number.isFinite(a.score);
    const bValid = b.status === 'complete' && Number.isFinite(b.score);
    return Number(bValid) - Number(aValid) || (aValid && bValid ? b.score - a.score : 0) || a.index - b.index;
  });
}
export function barPercent(row, scale) {
  if (row.status !== 'complete' || !Number.isFinite(row.score) || !Number.isFinite(scale) || scale <= 0) return null;
  return Math.min(100, Math.max(0, row.score / scale * 100));
}

// Research text and Public DI have different evaluation scopes. Sort within
// each scope without presenting them as a single comparable ranking.
export function comparisonGroups(benchmark) {
  const rows = rankedRows(benchmark);
  if (benchmark.id !== 'decisionindex') return [{id: 'comparable', rows}];
  return [...new Set(rows.map(row => row.evaluation_scope ?? 'unspecified'))]
    .sort((a, b) => (a === 'research-text' ? -1 : b === 'research-text' ? 1 : a.localeCompare(b)))
    .map(id => ({id, rows: rows.filter(row => (row.evaluation_scope ?? 'unspecified') === id)}));
}
