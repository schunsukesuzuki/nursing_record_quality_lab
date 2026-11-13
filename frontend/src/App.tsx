import { useEffect, useState, type FormEvent } from 'react';
import type { AuditResponse, Field, Status, StructuredRecord, PromptVariant } from './types';

const LABELS: Record<Field, string> = {fall_status:'転倒', dizziness_status:'ふらつき', assistance_status:'介助'};
const STATUS_LABELS: Record<Status, string> = {present:'あり', absent:'なし', unknown:'未記録'};
const FIELDS: Field[] = ['fall_status','dizziness_status','assistance_status'];
const DEFAULT_RECORD: StructuredRecord = {fall_status:'unknown', dizziness_status:'present', assistance_status:'present'};
const DEFAULT_NOTE = '10:30 歩行時ふらつきあり。移乗時は看護師が介助。転倒は認めず。';
const PROMPT_LABELS: Record<PromptVariant,string> = {basic:'基本 (v1.4相当)', semantic:'意味定義付き (推奨)', few_shot:'意味定義 + Few-shot'};
const API_ROOT = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

function StatusChip({value, unknownLabel}: {value:Status; unknownLabel?:string}) {
  return <span className={`status status-${value}`}>{value === 'unknown' && unknownLabel ? unknownLabel : STATUS_LABELS[value]}</span>;
}

function App() {
  const [record, setRecord] = useState<StructuredRecord>(DEFAULT_RECORD);
  const [narrative, setNarrative] = useState(DEFAULT_NOTE);
  const [useLlm, setUseLlm] = useState(true);
  const [promptVariant, setPromptVariant] = useState<PromptVariant>('semantic');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<AuditResponse | null>(null);
  const [tab, setTab] = useState<'review'|'json'>('review');
  const [llmHealth, setLlmHealth] = useState<{available: boolean; code: string; message: string; model?: string} | null>(null);
  const [checkingHealth, setCheckingHealth] = useState(false);
  const checkLabels: Record<string,string> = {quoted:'引用文字列は原文に存在（意味の妥当性は未検証）',rule_supported:'LLM判定とルールが一致・ルールの根拠を使用（独立検証ではない）',model_unknown:'LLMが判定保留',unverified_quote:'LLM根拠が原文にないため保留',missing_quote:'LLM根拠がなくルールでも確認できず保留',rule_disagreement:'LLMとルールが不一致のため保留'};

  async function refreshStatus() {
    setCheckingHealth(true);
    try {
      const r = await fetch(`${API_ROOT}/inference/status`);
      if (!r.ok) throw new Error('推論状態を取得できません');
      setLlmHealth(await r.json());
    } catch {
      setLlmHealth({available:false, code:'backend_unreachable', message:'バックエンドに接続できません'});
    } finally { setCheckingHealth(false); }
  }
  useEffect(() => { void refreshStatus(); }, []);


  async function runAudit(llmEnabled: boolean) {
    setLoading(true); setError(''); setResult(null);
    try {
      const response = await fetch(`${API_ROOT}/audit`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({record, narrative, use_llm:llmEnabled, prompt_variant:promptVariant})
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        const detail = body?.detail;
        const message = (typeof detail === 'object' && typeof detail?.message === 'string')
          ? detail.message : `API エラー (${response.status})`;
        throw new Error(message);
      }
      const data: AuditResponse = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '通信エラー');
      if (llmEnabled) void refreshStatus();
    } finally { setLoading(false); }
  }

  // Same finding detected by rule and LLM is one candidate with two sources,
  // never two distinct findings. Still preserve both in the API JSON for research.
  const mergedFlags = result ? [...result.flags, ...result.baseline_flags].filter((flag, i, all) =>
    all.findIndex(other => other.field === flag.field && other.kind === flag.kind && other.observed === flag.observed) === i
  ) : [];
  const abstainedCount = result?.source === 'llm' ? FIELDS.filter(field =>
    result.raw_extraction?.[field] !== 'unknown' && result.extraction[field] === 'unknown'
  ).length : 0;

  function submit(event: FormEvent) {
    event.preventDefault();
    void runAudit(useLlm);
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
          <div className="llm-health" role="status">
            <div>
              <strong>LLM状態: {checkingHealth ? '確認中' : llmHealth?.available ? `準備完了 (${llmHealth.model || 'local'})` : '利用不可'}</strong>
              <small>{llmHealth?.message || 'モデルの登録状況を確認しています'}</small>
            </div>
            <button type="button" onClick={() => void refreshStatus()} disabled={checkingHealth}>再確認</button>
          </div>
          <div className="execution-box"><div><strong>抽出方式</strong><small>LLMが利用できない場合はルールベースで動作確認できます</small></div>
            <label className="switch-line"><input type="checkbox" checked={useLlm} onChange={e=>setUseLlm(e.target.checked)}/>{useLlm?'Local LLM':'ルールベースのみ'}</label>
          </div>
          {useLlm && <div className="prompt-selector">
            <label htmlFor="prompt-variant" className="section-label">プロンプト比較条件</label>
            <select id="prompt-variant" value={promptVariant} onChange={e => setPromptVariant(e.target.value as PromptVariant)}>
              {(Object.keys(PROMPT_LABELS) as PromptVariant[]).map(key => <option key={key} value={key}>{PROMPT_LABELS[key]}</option>)}
            </select>
            <small>同一モデルで条件のみ変更します。改善効果は評価セットで比較してください。</small>
          </div>}
          <button className="primary" type="submit" disabled={loading || !narrative.trim()}>{loading?'解析中…':'記録を監査する'} <span aria-hidden>→</span></button>
          {error && <div className="error" role="alert">
            <p>{error}</p>
            {useLlm && <button type="button" className="fallback" disabled={loading} onClick={() => {setUseLlm(false); void runAudit(false);}}>ルールベースのみで再試行</button>}
          </div>}
        </form>
        <section className="panel result-panel" aria-live="polite">
          <div className="panel-head"><div><div className="step">02 · ANALYSIS</div><h2>監査結果</h2></div>{result && <span className="pill">{result.elapsed_ms.toFixed(0)} ms</span>}</div>
          {!result ? <div className="empty"><div className="empty-icon">◎</div><h3>結果を待っています</h3><p>左側の架空記録を確認し、「記録を監査する」を押してください。</p></div> : <>
            <div className="summary">
              <div><strong>{mergedFlags.length}</strong><span>確認候補（ルール・LLMの重複を統合）</span></div>
              <div><strong>{abstainedCount}</strong><span>LLM生判定から根拠不足で保留になった項目</span></div>
            </div>
            {result.source === 'llm' && <p className="audit-note">
              条件: {PROMPT_LABELS[result.prompt_variant]}。分類の生判定、引用文字列の照合、監査採用は別の段階です。
              原文引用の完全一致は<span className="emphasis">意味的に正しい根拠であることの証明ではありません</span>。
              ルール補完もモデルの独立した成功には数えません。
            </p>}
            {result.source === 'llm' && result.flags.length === 0 && result.baseline_flags.length > 0 &&
              <p className="audit-note critical">LLM由来の確認候補は0件ですが、ルールベースでは{result.baseline_flags.length}件検出されています。</p>}
            <div className="tabs"><button type="button" className={tab==='review'?'active':''} onClick={()=>setTab('review')}>検出結果</button><button type="button" className={tab==='json'?'active':''} onClick={()=>setTab('json')}>JSON出力</button></div>
            {tab==='review' ? <>
              {mergedFlags.length===0 ? <p className="zero">確認候補は見つかりませんでした。LLMの誤判定・保留を含む可能性があり、記録品質が保証されたことを意味しません。</p>
                : <div className="flag-list">{mergedFlags.map(flag => {
                  const fromLlm = result.flags.some(f => f.field === flag.field && f.kind === flag.kind && f.observed === flag.observed);
                  const fromRule = result.baseline_flags.some(f => f.field === flag.field && f.kind === flag.kind && f.observed === flag.observed);
                  return <article className="flag" key={`${flag.field}-${flag.kind}-${flag.observed}`}>
                    <div className="flag-top"><strong>{LABELS[flag.field as Field]}</strong><span className={`flag-badge ${flag.kind}`}>{flag.kind==='conflict'?'不一致':'記録確認'}</span></div>
                    <p>{flag.message}</p>
                    <p className="source-note">検出元: {fromLlm ? 'LLM採用候補' : ''}{fromLlm && fromRule ? ' ＋ ' : ''}{fromRule ? 'ルール' : ''}</p>
                    <div className="compare"><span>構造化 <StatusChip value={flag.recorded}/></span><span>抽出 <StatusChip value={flag.observed}/></span></div>
                    {flag.evidence && <blockquote>根拠の文字列: 「{flag.evidence}」</blockquote>}
                  </article>;
                })}</div>}
              <h3 className="subheading">抽出結果の比較</h3>
              <table><thead><tr><th>項目</th><th>ルール</th>{result.source === 'llm' && <th>LLM生判定</th>}<th>監査採用値</th></tr></thead><tbody>
                {FIELDS.map(field=><tr key={field}><td>{LABELS[field]}</td><td><StatusChip value={result.baseline[field]}/></td>
                  {result.source === 'llm' && <td><StatusChip value={result.raw_extraction?.[field] ?? 'unknown'}/></td>}
                  <td><StatusChip value={result.extraction[field]} unknownLabel={result.source==='llm' ? (result.raw_extraction?.[field] === 'unknown' ? '未言及／不明' : '根拠不足で保留') : undefined}/></td></tr>)}
              </tbody></table>
              {result.source === 'llm' && <>
                <h3 className="subheading">LLM生判定と引用文字列の検証</h3>
                <table><thead><tr><th>項目</th><th>モデルの出力</th><th>採用・保留の理由</th></tr></thead><tbody>
                  {FIELDS.map(field => <tr key={`diag-${field}`}><td>{LABELS[field]}</td><td><StatusChip value={result.raw_extraction?.[field] ?? 'unknown'} unknownLabel="未言及／不明"/></td><td className="diag-reason">{checkLabels[result.evidence_checks[field]] || '未確認'}{result.raw_extraction?.evidence?.[field] &&
                    <div className="raw-quote">モデル引用: 「{result.raw_extraction.evidence[field]}」</div>}</td></tr>)}
                </tbody></table>
              </>}
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
