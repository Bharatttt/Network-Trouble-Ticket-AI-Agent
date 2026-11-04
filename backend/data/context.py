"""Load an operator-supplied inventory and incident history at startup."""
import hashlib
import json
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field

from backend.config import DATA_FILE
from backend.data import seed
from backend.models import Alarm, SOP, Ticket, TopologyEdge, TopologyNode


class Service(BaseModel):
    service_id: str
    service_name: str
    affected_customers: int = Field(ge=0)


class Context(BaseModel):
    devices: List[TopologyNode]
    edges: List[TopologyEdge]
    tickets: List[Ticket]
    sops: List[SOP]
    services: Dict[str, Service] = Field(default_factory=dict)
    alarms: List[Alarm] = Field(default_factory=list)
    change_records: Dict[str, List[dict]] = Field(default_factory=dict)
    maintenance_windows: Dict[str, List[dict]] = Field(default_factory=dict)


SOURCE = 'seeded_demo'
VERSION = 'demo-v1'
if DATA_FILE:
    raw = Path(DATA_FILE).read_bytes()
    context = Context.model_validate_json(raw)
    devices = {d.device_id for d in context.devices}
    for values, field in [(context.devices, 'device_id'), (context.tickets, 'ticket_id'),
                          (context.sops, 'sop_id'), (context.alarms, 'alarm_id')]:
        ids = [getattr(item, field) for item in values]
        if len(ids) != len(set(ids)):
            raise ValueError('Context contains duplicate ' + field)
    if any(e.source not in devices or e.target not in devices for e in context.edges):
        raise ValueError('Topology edges reference unknown devices')
    if any(set(d.upstream_dependencies + d.downstream_dependencies) - devices
           for d in context.devices):
        raise ValueError('Topology dependencies reference unknown devices')
    if any(set(d.services) - context.services.keys() for d in context.devices):
        raise ValueError('Devices reference unknown services')
    if any(key != value.service_id for key, value in context.services.items()):
        raise ValueError('Service keys must match their IDs')
    if any(a.device not in devices for a in context.alarms):
        raise ValueError('Alarms reference unknown devices')
    dumped = context.model_dump(mode='json')
    for name in dumped:
        setattr(seed, name.upper(), dumped[name])
    SOURCE = 'operator_supplied'
    VERSION = hashlib.sha256(raw).hexdigest()[:16]
