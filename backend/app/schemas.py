from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Status = Literal['present', 'absent', 'unknown']

class StructuredRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fall_status: Status = 'unknown'
    dizziness_status: Status = 'unknown'
    assistance_status: Status = 'unknown'

class NarrativeExtraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fall_status: Status = 'unknown'
    dizziness_status: Status = 'unknown'
    assistance_status: Status = 'unknown'
    evidence: dict[str, str] = Field(default_factory=dict)

class AuditRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    record: StructuredRecord
    narrative: str = Field(min_length=1, max_length=2000)
    use_llm: bool = True

class AuditFlag(BaseModel):
    field: str
    kind: Literal['missing_structured', 'conflict']
    recorded: Status
    observed: Status
    evidence: str
    message: str
    source: Literal['rule', 'llm']

class AuditResponse(BaseModel):
    baseline: NarrativeExtraction
    extraction: NarrativeExtraction
    flags: list[AuditFlag]
    source: Literal['rule', 'llm']
    elapsed_ms: float
    disclaimer: str = '架空記録を用いた技術検証です。臨床判断や記録修正には使用できません。'
