# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from dataclasses import dataclass
import hashlib
import json

MAX_ID = 96
MAX_TEXT = 2400
MAX_CONSTRAINTS = 8

@allow_storage
@dataclass
class Anchor:
    owner: Address
    domain: str
    sensitivity: str
    root_version_id: str
    version_count: u64
    proposal_count: u64
    active: bool

@allow_storage
@dataclass
class MemoryVersion:
    anchor_id: str
    parent_version_id: str
    scope: str
    meaning: str
    constraints_json: str
    status: str
    content_fingerprint: str

@allow_storage
@dataclass
class Proposal:
    anchor_id: str
    parent_version_id: str
    proposed_version_id: str
    scope: str
    meaning: str
    constraints_json: str
    status: str

@allow_storage
@dataclass
class Evaluation:
    meaning_relation: str
    scope_relation: str
    constraint_relation: str
    ambiguity: str
    disposition: str
    candidate_fingerprint: str

class AgentMemoryAnchor(gl.Contract):
    anchors: TreeMap[str, Anchor]
    anchor_exists: TreeMap[str, bool]
    versions: TreeMap[str, MemoryVersion]
    version_exists: TreeMap[str, bool]
    proposals: TreeMap[str, Proposal]
    proposal_exists: TreeMap[str, bool]
    evaluations: TreeMap[str, Evaluation]
    evaluation_exists: TreeMap[str, bool]
    active_heads: TreeMap[str, str]
    total_anchors: u64
    total_versions: u64
    total_proposals: u64

    def __init__(self) -> None:
        self.total_anchors = u64(0)
        self.total_versions = u64(0)
        self.total_proposals = u64(0)

    @gl.public.write
    def create_memory_anchor(self, anchor_id: str, version_id: str,
                             domain: str, sensitivity: str, scope: str,
                             meaning: str, constraints_json: str) -> None:
        aid = self._id(anchor_id, "anchor")
        vid = self._id(version_id, "version")
        if self.anchor_exists.get(aid, False) or self.version_exists.get(vid, False):
            raise gl.vm.UserError("EXPECTED: anchor or version already exists")
        level = sensitivity.strip().upper()
        if level not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            raise gl.vm.UserError("EXPECTED: invalid sensitivity")
        clean_scope = self._required(scope, "scope", 480)
        constraints = self._constraints(constraints_json)
        version = MemoryVersion(
            anchor_id=aid, parent_version_id="", scope=clean_scope,
            meaning=self._required(meaning, "meaning", MAX_TEXT),
            constraints_json=constraints, status="ACTIVE",
            content_fingerprint=self._content_fingerprint(
                aid, "", clean_scope, meaning, constraints))
        self.anchors[aid] = Anchor(
            owner=gl.message.sender_address, domain=self._id(domain.lower(), "domain"),
            sensitivity=level, root_version_id=vid, version_count=u64(1),
            proposal_count=u64(0), active=True)
        self.anchor_exists[aid] = True
        self.versions[vid] = version
        self.version_exists[vid] = True
        self.active_heads[self._head_key(aid, clean_scope)] = vid
        self.total_anchors += u64(1)
        self.total_versions += u64(1)

    @gl.public.write
    def propose_memory_update(self, proposal_id: str, anchor_id: str,
                              parent_version_id: str, proposed_version_id: str,
                              scope: str, meaning: str,
                              constraints_json: str) -> None:
        pid = self._id(proposal_id, "proposal")
        aid = self._id(anchor_id, "anchor")
        parent = self._id(parent_version_id, "parent version")
        proposed = self._id(proposed_version_id, "proposed version")
        anchor = self._anchor(aid)
        if anchor.owner != gl.message.sender_address:
            raise gl.vm.UserError("EXPECTED: only anchor owner may propose")
        if self.proposal_exists.get(pid, False) or self.version_exists.get(proposed, False):
            raise gl.vm.UserError("EXPECTED: proposal or version already exists")
        if not self.version_exists.get(parent, False) or self.versions[parent].anchor_id != aid:
            raise gl.vm.UserError("EXPECTED: invalid parent version")
        self.proposals[pid] = Proposal(
            anchor_id=aid, parent_version_id=parent, proposed_version_id=proposed,
            scope=self._required(scope, "scope", 480),
            meaning=self._required(meaning, "meaning", MAX_TEXT),
            constraints_json=self._constraints(constraints_json), status="PROPOSED")
        self.proposal_exists[pid] = True
        anchor.proposal_count += u64(1)
        self.anchors[aid] = anchor
        self.total_proposals += u64(1)

    @gl.public.write
    def evaluate_update(self, proposal_id: str) -> None:
        pid = self._id(proposal_id, "proposal")
        proposal = self._proposal(pid)
        if proposal.status != "PROPOSED":
            raise gl.vm.UserError("EXPECTED: proposal is not pending")
        parent = self.versions[proposal.parent_version_id]
        anchor = self.anchors[proposal.anchor_id]

        def build_candidate():
            raw = gl.nondet.exec_prompt(
                self._prompt(anchor, parent, proposal), response_format="json")
            return self._normalize(raw, pid, parent, proposal)

        def validator_fn(leaders_res) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return False
            leader = leaders_res.calldata
            if not self._valid(leader):
                return False
            validator = build_candidate()
            return self._valid(validator) and self._same(leader, validator)

        candidate = gl.vm.run_nondet_unsafe(build_candidate, validator_fn)
        if not self._valid(candidate):
            raise gl.vm.UserError("LLM_ERROR: invalid memory evaluation")
        disposition = self._derive_disposition(anchor.sensitivity, candidate)
        self.evaluations[pid] = Evaluation(
            meaning_relation=candidate["meaning_relation"],
            scope_relation=candidate["scope_relation"],
            constraint_relation=candidate["constraint_relation"],
            ambiguity=candidate["ambiguity"], disposition=disposition,
            candidate_fingerprint=candidate["candidate_fingerprint"])
        self.evaluation_exists[pid] = True
        if disposition in ["ACCEPT_UPDATE", "ACCEPT_FORK"]:
            self._activate(proposal, disposition)
            proposal.status = "ACTIVATED"
        else:
            proposal.status = "HUMAN_REVIEW" if disposition == "REVIEW" else "REJECTED"
        self.proposals[pid] = proposal

    @gl.public.write
    def resolve_review(self, proposal_id: str, accept: bool) -> None:
        pid = self._id(proposal_id, "proposal")
        proposal = self._proposal(pid)
        anchor = self.anchors[proposal.anchor_id]
        if anchor.owner != gl.message.sender_address:
            raise gl.vm.UserError("EXPECTED: only anchor owner may resolve")
        if proposal.status != "HUMAN_REVIEW":
            raise gl.vm.UserError("EXPECTED: proposal is not awaiting review")
        if accept:
            self._activate(proposal, "OWNER_OVERRIDE")
            proposal.status = "ACTIVATED_BY_OWNER"
        else:
            proposal.status = "REJECTED_BY_OWNER"
        self.proposals[pid] = proposal

    @gl.public.view
    def get_anchor(self, anchor_id: str) -> Anchor:
        return self._anchor(self._id(anchor_id, "anchor"))

    @gl.public.view
    def get_version(self, version_id: str) -> MemoryVersion:
        vid = self._id(version_id, "version")
        if not self.version_exists.get(vid, False):
            raise gl.vm.UserError("EXPECTED: unknown version")
        return self.versions[vid]

    @gl.public.view
    def get_proposal(self, proposal_id: str) -> Proposal:
        return self._proposal(self._id(proposal_id, "proposal"))

    @gl.public.view
    def get_evaluation(self, proposal_id: str) -> Evaluation:
        pid = self._id(proposal_id, "proposal")
        if not self.evaluation_exists.get(pid, False):
            raise gl.vm.UserError("EXPECTED: unknown evaluation")
        return self.evaluations[pid]

    @gl.public.view
    def get_active_memory(self, anchor_id: str, scope: str) -> str:
        aid = self._id(anchor_id, "anchor")
        self._anchor(aid)
        return self.active_heads.get(
            self._head_key(aid, self._required(scope, "scope", 480)), "")

    @gl.public.view
    def verify_memory_integrity(self, version_id: str) -> bool:
        version = self.get_version(version_id)
        expected = self._content_fingerprint(
            version.anchor_id, version.parent_version_id, version.scope,
            version.meaning, version.constraints_json)
        return expected == version.content_fingerprint

    def _activate(self, proposal: Proposal, mode: str) -> None:
        vid = proposal.proposed_version_id
        fingerprint = self._content_fingerprint(
            proposal.anchor_id, proposal.parent_version_id, proposal.scope,
            proposal.meaning, proposal.constraints_json)
        self.versions[vid] = MemoryVersion(
            anchor_id=proposal.anchor_id,
            parent_version_id=proposal.parent_version_id,
            scope=proposal.scope, meaning=proposal.meaning,
            constraints_json=proposal.constraints_json, status=mode,
            content_fingerprint=fingerprint)
        self.version_exists[vid] = True
        self.active_heads[self._head_key(proposal.anchor_id, proposal.scope)] = vid
        anchor = self.anchors[proposal.anchor_id]
        anchor.version_count += u64(1)
        self.anchors[proposal.anchor_id] = anchor
        self.total_versions += u64(1)

    def _prompt(self, anchor: Anchor, parent: MemoryVersion,
                proposal: Proposal) -> str:
        return """Independently classify a proposed long-term agent-memory update against its immutable parent. Return JSON only with exactly: meaning_relation PRESERVED|REFINED|CONTRADICTED|UNRELATED|UNKNOWN; scope_relation SAME|NARROWER|BROADER|DISJOINT|UNKNOWN; constraint_relation PRESERVED|STRENGTHENED|WEAKENED|CONFLICT|UNKNOWN; ambiguity CLEAR|AMBIGUOUS|UNKNOWN. Do not return scores, explanations, summaries or prose. A scope-specific exception may be a DISJOINT fork rather than an overwrite. Judge only the supplied texts.
DOMAIN: """ + anchor.domain + "\nSENSITIVITY: " + anchor.sensitivity + "\nPARENT SCOPE: " + parent.scope + "\nPARENT MEANING: " + parent.meaning + "\nPARENT CONSTRAINTS: " + parent.constraints_json + "\nPROPOSED SCOPE: " + proposal.scope + "\nPROPOSED MEANING: " + proposal.meaning + "\nPROPOSED CONSTRAINTS: " + proposal.constraints_json

    def _normalize(self, raw, pid: str, parent: MemoryVersion,
                   proposal: Proposal) -> dict:
        if not isinstance(raw, dict):
            return {}
        value = {
            "meaning_relation": str(raw.get("meaning_relation", "UNKNOWN")).strip().upper(),
            "scope_relation": str(raw.get("scope_relation", "UNKNOWN")).strip().upper(),
            "constraint_relation": str(raw.get("constraint_relation", "UNKNOWN")).strip().upper(),
            "ambiguity": str(raw.get("ambiguity", "UNKNOWN")).strip().upper()}
        canonical = json.dumps({"proposal_id": pid,
            "parent_fingerprint": parent.content_fingerprint,
            "proposed_scope": proposal.scope,
            "proposed_meaning": proposal.meaning,
            "proposed_constraints": proposal.constraints_json,
            "vector": value}, sort_keys=True, separators=(",", ":"))
        value["candidate_fingerprint"] = hashlib.sha256(canonical.encode()).hexdigest()
        return value

    def _valid(self, c) -> bool:
        if not isinstance(c, dict): return False
        if c.get("meaning_relation") not in ["PRESERVED", "REFINED", "CONTRADICTED", "UNRELATED", "UNKNOWN"]: return False
        if c.get("scope_relation") not in ["SAME", "NARROWER", "BROADER", "DISJOINT", "UNKNOWN"]: return False
        if c.get("constraint_relation") not in ["PRESERVED", "STRENGTHENED", "WEAKENED", "CONFLICT", "UNKNOWN"]: return False
        if c.get("ambiguity") not in ["CLEAR", "AMBIGUOUS", "UNKNOWN"]: return False
        return isinstance(c.get("candidate_fingerprint"), str) and len(c["candidate_fingerprint"]) == 64

    def _same(self, a: dict, b: dict) -> bool:
        for field in ["meaning_relation", "scope_relation",
                      "constraint_relation", "ambiguity",
                      "candidate_fingerprint"]:
            if a.get(field) != b.get(field): return False
        return True

    def _derive_disposition(self, sensitivity: str, c: dict) -> str:
        if c["ambiguity"] != "CLEAR" or "UNKNOWN" in [
                c["meaning_relation"], c["scope_relation"],
                c["constraint_relation"]]:
            return "REVIEW"
        if c["scope_relation"] == "DISJOINT" and c["constraint_relation"] not in ["CONFLICT", "WEAKENED"]:
            return "ACCEPT_FORK"
        if c["meaning_relation"] in ["PRESERVED", "REFINED"] and c["scope_relation"] in ["SAME", "NARROWER"] and c["constraint_relation"] in ["PRESERVED", "STRENGTHENED"]:
            return "ACCEPT_UPDATE"
        if sensitivity in ["HIGH", "CRITICAL"]:
            return "REVIEW"
        if c["meaning_relation"] in ["CONTRADICTED", "UNRELATED"] or c["constraint_relation"] == "CONFLICT":
            return "REJECT"
        return "REVIEW"

    def _anchor(self, aid: str) -> Anchor:
        if not self.anchor_exists.get(aid, False):
            raise gl.vm.UserError("EXPECTED: unknown anchor")
        return self.anchors[aid]

    def _proposal(self, pid: str) -> Proposal:
        if not self.proposal_exists.get(pid, False):
            raise gl.vm.UserError("EXPECTED: unknown proposal")
        return self.proposals[pid]

    def _constraints(self, raw: str) -> str:
        try: values = json.loads(raw)
        except Exception: raise gl.vm.UserError("EXPECTED: constraints must be JSON")
        if not isinstance(values, list) or len(values) == 0 or len(values) > MAX_CONSTRAINTS:
            raise gl.vm.UserError("EXPECTED: provide 1 to 8 constraints")
        clean = []
        for value in values:
            item = self._required(str(value), "constraint", 360)
            if item in clean: raise gl.vm.UserError("EXPECTED: duplicate constraint")
            clean.append(item)
        return json.dumps(clean, separators=(",", ":"))

    def _content_fingerprint(self, aid: str, parent: str, scope: str,
                             meaning: str, constraints: str) -> str:
        payload = json.dumps({"anchor": aid, "parent": parent, "scope": scope,
            "meaning": " ".join(meaning.strip().split()),
            "constraints": constraints}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def _head_key(self, aid: str, scope: str) -> str:
        return hashlib.sha256((aid + "|" + scope.lower()).encode()).hexdigest()

    def _id(self, value: str, label: str) -> str:
        clean = value.strip()
        if len(clean) == 0 or len(clean) > MAX_ID:
            raise gl.vm.UserError("EXPECTED: invalid " + label)
        return clean

    def _required(self, value: str, label: str, maximum: int) -> str:
        clean = " ".join(value.strip().split())
        if len(clean) == 0 or len(clean) > maximum:
            raise gl.vm.UserError("EXPECTED: invalid " + label)
        return clean

