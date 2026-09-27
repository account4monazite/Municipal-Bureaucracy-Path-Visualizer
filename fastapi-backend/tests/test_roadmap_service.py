from unittest.mock import MagicMock

from app.models import NLPServiceResponse, TaskLocation, TaskState
from app.services.roadmap_service import RoadmapService


def test_build_roadmap_maps_nlp_graph_nodes_and_edges():
    service = RoadmapService(nlp_service=MagicMock(), supabase_service=MagicMock())
    state = TaskState(
        session_id="graph-session",
        intent="driving_license_application",
        location=TaskLocation(city="New Delhi", state="Delhi"),
    )
    nlp_response = NLPServiceResponse(
        task="Driving License Application",
        initialNodes=["apply", "documents"],
        initialEdges=[{"source": "apply", "target": "documents"}],
        nodes={
            "apply": {
                "id": "apply",
                "type": "process",
                "title": "Apply online",
                "chatText": "Submit the application.",
                "actionLink": "https://example.gov.in/apply",
                "prerequisites": ["documents"],
            },
            "documents": {
                "id": "documents",
                "type": "document",
                "title": "Gather documents",
                "chatText": "Prepare identity documents.",
                "actionLink": None,
                "prerequisites": [],
            },
        },
    )

    roadmap = service._build_roadmap(state, nlp_response)

    assert len(roadmap.nodes) == 2
    assert roadmap.nodes[0].id == "apply"
    assert roadmap.nodes[0].description == "Submit the application."
    assert roadmap.nodes[0].source.source_url == "https://example.gov.in/apply"
    assert len(roadmap.edges) == 1
    assert roadmap.edges[0].source == "apply"
    assert roadmap.edges[0].target == "documents"