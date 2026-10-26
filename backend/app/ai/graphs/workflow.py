from langgraph.graph import END, START, StateGraph

from app.ai.graphs.nodes import build_nodes
from app.ai.graphs.state import ChatState


def build_graph(service, checkpointer):
    graph = StateGraph(ChatState)
    for name, node in build_nodes(service).items():
        graph.add_node(name, node)
    graph.add_edge(START, "load_settings")
    for start, end in [
        ("load_settings", "load_context"),
        ("load_context", "prepare_query"),
        ("prepare_query", "retrieve"),
        ("retrieve", "check_evidence"),
    ]:
        graph.add_edge(start, end)
    graph.add_conditional_edges(
        "check_evidence",
        lambda state: "generate" if state["evidence"] else "insufficient",
        {"generate": "generate", "insufficient": "insufficient"},
    )
    graph.add_edge("generate", "prepare_sources")
    graph.add_edge("insufficient", "prepare_sources")
    graph.add_edge("prepare_sources", "persist")
    graph.add_edge("persist", END)
    return graph.compile(checkpointer=checkpointer)
