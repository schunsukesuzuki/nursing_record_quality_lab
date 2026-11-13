import { useState, type FormEvent } from 'react';
import type { AuditResponse, Field, Status, StructuredRecord } from './types';

const LABELS: Record<Field, string> = {fall_status:'転倒', dizziness_status:'ふらつき', assistance_status:'介助'};
const STATUS_LABELS: Record<Status, string> = {present:'あり', absent:'なし', unknown:'未記録'};
const FIELDS: Field[] = ['fall_status','dizziness_status','assistance_status'];
const DEFAULT_RECORD: StructuredRecord = {fall_status:'unknown', dizziness_status:'present', assistance_status:'present'};
const DEFAULT_NOTE = '10:30 歩行時ふらつきあり。移乗時は看護師が介助。転倒は認めず。';
const API_ROOT = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

function StatusChip({value}: {value:Status}) {
  return <span className={`status status-${value}`}>{STATUS_LABELS[value]}</span>;
}

function App() {
  const [record, setRecord] = useState<StructuredRecord>(DEFAULT_RECORD);
  const [narrative, setNarrative] = useState(DEFAULT_NOTE);
  const [useLlm, setUseLlm] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<AuditResponse | null>(null);
  const [tab, setTab] = useState<'review'|'json'>('review');

  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError(''); setResult(null);
    try {
      const response = await fetch(`${API_ROOT}/audit`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({record, narrative, use_llm:useLlm})
      });
      if (!response.ok) throw new Error(response.status === 503
        ? '推論サービスを利用できません。「ルールベースのみ」に切り替えて再試行できます。'
        : `API エラー (${response.status})`);
      const data: AuditResponse = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '通信エラー');
    } finally { setLoading(false); }
  }

  return <>
    <header className="topbar">
      <div className="brand"><span className="brand-icon">✳</span><span>Nursing Record <strong>Quality Lab</strong></span></div>
      <span className="environment"><span className="dot"/> LOCAL RESEARCH PROTOTYPE</span>
    </header>
    <main className="layout">
      <section className="intro">
        <div className="eyebrow">CLINICAL DATA QUALITY · RESEARCH DEMO</div>
        <h1>看護記録の整合性を、<br/><span>検証可能な形で。</span></h1>
        <p>構造化記録と自由記述の差分を抽出し、ルールベースと小型Local LLMの結果を比較します。架空データのみを扱う技術検証用PoCです。</p>
      </section>
      <div className="columns">
        <form className="panel input-panel" onSubmit={submit}>
          <div className="panel-head"><div><div className="step">01 · INPUT</div><h2>検証対象の記録</h2></div><span className="pill">Synthetic data</span></div>
          <h3>構造化項目</h3>
          <div className="fields">
            {FIELDS.map(field => <label key={field} className="field-row"><span>{LABELS[field]}</span>
              <select value={record[field]} onChange={e => setRecord({...record, [field]:e.target.value as Status})}>
                <option value="unknown">未記録</option><option value="present">あり</option><option value="absent">なし</option>
              </select></label>)}
          </div>
          <label htmlFor="narrative" className="section-label">自由記述（補足）</label>
          <textarea id="narrative" value={narrative} onChange={e=>setNarrative(e.target.value)} maxLength={2000} required rows={5}/>
          <div className="counter">{narrative.length} / 2,000文字</div>
          <div className="execution-box"><div><strong>抽出方式</strong><small>LLMが利用できない場合はルールベースで動作確認できます</small></div>
            <label className="switch-line"><input type="checkbox" checked={useLlm} onChange={e=>setUseLlm(e.target.checked)}/>{useLlm?'Local LLM':'ルールベースのみ'}</label>
          </div>
          <button className="primary" type="submit" disabled={loading || !narrative.trim()}>{loading?'解析中…':'記録を監査する'} <span aria-hidden>→</span></button>
          {error && <div className="error" role="alert">{error}</div>}
        </form>
        <section className="panel result-panel" aria-live="polite">
          <div className="panel-head"><div><div className="step">02 · ANALYSIS</div><h2>監査結果</h2></div>{result && <span className="pill">{result.elapsed_ms.toFixed(0)} ms</span>}</div>
          {!result ? <div className="empty"><div className="empty-icon">◎</div><h3>結果を待っています</h3><p>左側の架空記録を確認し、「記録を監査する」を押してください。</p></div> : <>
            <div className="summary"><div><strong>{result.flags.length}</strong><span>確認候補</span></div><div><strong>{result.source === 'llm' ? 'LLM':'RULE'}</strong><span>抽出エンジン</span></div></div>
            <div className="tabs"><button type="button" className={tab==='review'?'active':''} onClick={()=>setTab('review')}>検出結果</button><button type="button" className={tab==='json'?'active':''} onClick={()=>setTab('json')}>JSON出力</button></div>
            {tab==='review' ? <>
              {result.flags.length===0 ? <p className="zero">比較対象の矛盾・未記録候補は見つかりませんでした。品質が保証されたことを意味するものではありません。</p>
                : <div className="flag-list">{result.flags.map(flag => <article className="flag" key={flag.field}>
                  <div className="flag-top"><strong>{LABELS[flag.field as Field]}</strong><span className={`flag-badge ${flag.kind}`}>{flag.kind==='conflict'?'不一致':'記録確認'}</span></div>
                  <p>{flag.message}</p><div className="compare"><span>記録 <StatusChip value={flag.recorded}/></span><span>抽出 <StatusChip value={flag.observed}/></span></div>
                  {flag.evidence && <blockquote>根拠: 「{flag.evidence}」</blockquote>}
                </article>)}</div>}
              <h3 className="subheading">抽出結果の比較</h3>
              <table><thead><tr><th>項目</th><th>ルール</th><th>{result.source==='llm'?'LLM':'採用値'}</th></tr></thead><tbody>
                {FIELDS.map(field=><tr key={field}><td>{LABELS[field]}</td><td><StatusChip value={result.baseline[field]}/></td><td><StatusChip value={result.extraction[field]}/></td></tr>)}
              </tbody></table>
            </> : <pre className="json">{JSON.stringify(result, null, 2)}</pre>}
            <p className="disclaimer">{result.disclaimer}</p>
          </>}
        </section>
      </div>
      <footer>Research PoC <span>·</span> React / TypeScript <span>·</span> FastAPI <span>·</span> Ollama adapter <span>·</span> No patient data</footer>
    </main>
  </>;
}
export default App;
