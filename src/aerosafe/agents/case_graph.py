"""Build a transparent relationship graph from the existing triage result."""


def build_case_graph(case_id: str, case: dict) -> dict:
    nodes = [{
        "id": "case",
        "kind": "case",
        "label": case_id,
        "detail": "Case text analyzed by the local keyword triage baseline.",
    }]
    edges = []

    for code, name, score in case.get("ata", []):
        node_id = f"ata-{code}"
        nodes.append({
            "id": node_id,
            "kind": "ata",
            "label": f"ATA {code} · {name}",
            "detail": f"Keyword baseline rank score: {score:.0%}.",
        })
        edges.append({"source": "case", "target": node_id, "label": "ranked"})

    seen = set()
    for kind, value in case.get("entities", []):
        normalized = (kind.upper(), value.casefold())
        if normalized in seen:
            continue
        seen.add(normalized)
        node_id = f"tag-{len(seen)}"
        nodes.append({
            "id": node_id,
            "kind": kind.lower(),
            "label": value,
            "detail": f"{kind.title()} keyword detected in the case description.",
        })
        edges.append({"source": "case", "target": node_id, "label": "tagged"})

    return {
        "case_id": case_id,
        "source": "local_keyword_triage",
        "nodes": nodes,
        "edges": edges,
        "limitations": "Shows labels extracted from this case only. No external reports, directives, or aircraft configuration are connected.",
    }
