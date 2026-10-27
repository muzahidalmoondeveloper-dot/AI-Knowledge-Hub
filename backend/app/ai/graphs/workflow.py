from langgraph.graph import END, START, StateGraph

from app.ai.graphs.nodes import build_nodes
from app.ai.graphs.state import ChatState
from app.ai.greetings import is_social_turn


def build_graph(service, checkpointer):
    graph = StateGraph(ChatState)
    for name, node in build_nodes(service).items():
        graph.add_node(name, node)
    graph.add_edge(START, "load_settings")
    graph.add_edge("load_settings", "load_context")
    graph.add_conditional_edges(
        "load_context",
        lambda state: "greeting"
        if service.bot.strict_rag and is_social_turn(state["question"])
        else "prepare_query",
        {"greeting": "greeting", "prepare_query": "prepare_query"},
    )
    graph.add_edge("greeting", "prepare_sources")
    for start, end in [
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
