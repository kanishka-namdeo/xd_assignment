"""Test graph caching for extraction and eligibility graphs."""
from unittest.mock import MagicMock, patch


def test_extraction_graph_caching():
    """Test that extraction graph is cached and not rebuilt on every call."""
    from src.agents.extraction.graph import get_extraction_subgraph

    import src.agents.extraction.graph as extraction_module

    extraction_module._compiled_graph = None

    with patch("src.agents.extraction.graph.build_extraction_subgraph") as mock_build:
        mock_build.return_value = MagicMock()

        graph1 = get_extraction_subgraph()
        graph2 = get_extraction_subgraph()

        assert mock_build.call_count == 1
        assert graph1 is graph2


def test_eligibility_graph_caching():
    """Test that eligibility graph is cached and not rebuilt on every call."""
    from src.agents.eligibility.graph import get_eligibility_graph

    import src.agents.eligibility.graph as eligibility_module

    eligibility_module._compiled_graph = None

    with patch("src.agents.eligibility.graph.build_eligibility_graph") as mock_build:
        mock_graph = MagicMock()
        mock_compiled = MagicMock()
        mock_graph.compile.return_value = mock_compiled
        mock_build.return_value = mock_graph

        graph1 = get_eligibility_graph()
        graph2 = get_eligibility_graph()

        assert mock_build.call_count == 1
        assert graph1 is graph2
