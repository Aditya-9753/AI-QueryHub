"""Evidence graph: nodes (query / finding / insight / challenge) + edges (supported_by / contradicted_by)."""
from dataclasses import dataclass, field

RELATIONS = {"supported_by", "contradicted_by"}


@dataclass
class Node:
    id: str
    type: str
    label: str
    data: dict = field(default_factory=dict)


@dataclass
class Edge:
    source: str
    target: str
    relation: str


class EvidenceGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []

    def add_node(self, id: str, type: str, label: str, **data) -> Node:
        node = Node(id, type, label, data)
        self.nodes[id] = node
        return node

    def add_edge(self, source: str, target: str, relation: str = "supported_by") -> None:
        if relation not in RELATIONS:
            raise ValueError(f"relation must be one of {RELATIONS}")
        if source not in self.nodes or target not in self.nodes:
            raise KeyError("both nodes must exist")
        self.edges.append(Edge(source, target, relation))

    def neighbours(self, node_id: str, relation: str) -> list[Node]:
        return [self.nodes[e.target] for e in self.edges if e.source == node_id and e.relation == relation]

    def has_contradiction(self, node_id: str) -> bool:
        return bool(self.neighbours(node_id, "contradicted_by"))

    def to_react_flow(self) -> dict:
        nodes = [{"id": n.id, "type": "default", "data": {"label": n.label, "kind": n.type, **n.data},
                  "position": {"x": 0, "y": 0}} for n in self.nodes.values()]
        edges = [{"id": f"{e.source}->{e.target}", "source": e.source, "target": e.target,
                  "label": e.relation, "animated": e.relation == "contradicted_by"} for e in self.edges]
        return {"nodes": nodes, "edges": edges}
