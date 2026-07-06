from typing import List, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field

Severity = Literal["critical", "major", "minor", "warning"]
NodeStatus = Literal["up", "down", "degraded"]
CauseStatus = Literal["suspected", "probable", "confirmed"]
RiskLevel = Literal["low", "medium", "high"]


class Alarm(BaseModel):
    alarm_id: str
    device: str
    interface: Optional[str] = None
    severity: Severity
    message: str
    probable_cause: Optional[str] = None
    vendor: Optional[str] = None
    timestamp: datetime
    service_impact: Optional[str] = None
    acknowledged: bool = False


class TopologyNode(BaseModel):
    device_id: str
    device_name: str
    device_type: Literal["router", "switch", "firewall", "server", "ap"]
    vendor: str
    role: Literal["core", "aggregation", "access", "edge", "firewall"]
    status: NodeStatus
    site_id: str
    criticality: Literal["high", "medium", "low"]
    upstream_dependencies: List[str] = Field(default_factory=list)
    downstream_dependencies: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)


class TopologyEdge(BaseModel):
    source: str
    target: str
    link_type: Literal["physical", "logical", "dependency"]
    interface_source: Optional[str] = None
    interface_target: Optional[str] = None
    bandwidth: Optional[str] = None
    status: NodeStatus


class SOPStep(BaseModel):
    step_number: int
    description: str
    expected_result: str
    risk_level: RiskLevel
    tools_required: List[str] = Field(default_factory=list)


class SOP(BaseModel):
    sop_id: str
    title: str
    category: str
    vendor: Optional[str] = None
    device_type: Optional[str] = None
    alarm_type: Optional[str] = None
    steps: List[SOPStep]
    escalation_matrix: List[str] = Field(default_factory=list)
    last_updated: datetime


class Ticket(BaseModel):
    ticket_id: str
    incident_id: Optional[str] = None
    title: str
    description: str
    severity: Severity
    status: Literal["open", "in_progress", "resolved", "closed", "escalated"]
    created_at: datetime
    resolved_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    resolution_summary: Optional[str] = None
    resolution_steps: List[str] = Field(default_factory=list)
    root_cause: Optional[str] = None
    alarm_signatures: List[str] = Field(default_factory=list)
    device_ids: List[str] = Field(default_factory=list)
    site_ids: List[str] = Field(default_factory=list)
    vendor: Optional[str] = None
    recurred: bool = False
    resolution_time_hours: Optional[float] = None
    closure_code: Optional[str] = None


# ---- Recommendation output schema ----

class CorrelatedAlarm(BaseModel):
    alarm_id: str
    device: str
    interface: Optional[str] = None
    severity: Severity
    message: str
    timestamp: datetime
    vendor: Optional[str] = None
    probable_cause: Optional[str] = None


class ImpactedService(BaseModel):
    service_id: str
    service_name: str
    impact: str
    affected_customers: int


class TopologyInsight(BaseModel):
    node: str
    role: str
    downstream_impact: List[str]
    shared_dependency: Optional[str] = None
    blast_radius: str


class SimilarTicketMatch(BaseModel):
    ticket_id: str
    similarity_score: float
    resolved_by: Optional[str] = None
    resolution_summary: str
    resolution_time_hours: Optional[float] = None
    recurred: bool


class SOPMatch(BaseModel):
    sop_id: str
    title: str
    steps: List[str]
    match_score: float


class RootCauseCandidate(BaseModel):
    rank: int
    cause: str
    evidence: List[str]
    probability: float
    status: CauseStatus


class RecommendedAction(BaseModel):
    step: int
    action: str
    reason: str
    risk: RiskLevel
    sop_reference: Optional[str] = None


class Escalation(BaseModel):
    required: bool
    team: Optional[str] = None
    reason: Optional[str] = None
    urgency: Optional[Literal["low", "medium", "high"]] = None
    sla_breach_risk: bool = False


class AuditEvent(BaseModel):
    timestamp: datetime
    event: str
    detail: str


class Recommendation(BaseModel):
    incident_id: str
    timestamp: datetime
    summary: str
    severity: Severity
    correlated_alarms: List[CorrelatedAlarm]
    impacted_services: List[ImpactedService]
    topology_insights: List[TopologyInsight]
    similar_tickets: List[SimilarTicketMatch]
    relevant_sops: List[SOPMatch]
    root_cause_candidates: List[RootCauseCandidate]
    recommended_actions: List[RecommendedAction]
    escalation: Escalation
    confidence: float
    confidence_justification: str
    missing_data: List[str]
    audit_log: List[AuditEvent]
