export type Status = 'present' | 'absent' | 'unknown';
export type PromptVariant = 'basic' | 'semantic' | 'few_shot';
export type Field = 'fall_status' | 'dizziness_status' | 'assistance_status';
export type StructuredRecord = Record<Field, Status>;
export interface NarrativeExtraction extends StructuredRecord { evidence: Record<string, string> }
export interface AuditFlag {
  field: Field;
  kind: 'missing_structured' | 'conflict';
  recorded: Status;
  observed: Status;
  evidence: string;
  message: string;
  source: 'rule' | 'llm';
}
export interface AuditResponse {
  baseline: NarrativeExtraction;
  baseline_flags: AuditFlag[];
  raw_extraction: NarrativeExtraction | null;
  evidence_checks: Record<string, string>;
  extraction: NarrativeExtraction;
  flags: AuditFlag[];
  source: 'rule' | 'llm';
  prompt_variant: PromptVariant;
  elapsed_ms: number;
  disclaimer: string;
}
