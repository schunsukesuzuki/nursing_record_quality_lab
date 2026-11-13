export type Status = 'present' | 'absent' | 'unknown';
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
  extraction: NarrativeExtraction;
  flags: AuditFlag[];
  source: 'rule' | 'llm';
  elapsed_ms: number;
  disclaimer: string;
}
