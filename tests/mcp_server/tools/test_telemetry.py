from unittest.mock import Mock

import pytest

from mcp_server.dependencies import DependencyProvider
from mcp_server.tools.telemetry import read_building_state


def test_read_building_state_calls_parser() -> None:
    parser = Mock()
    expected = Mock()

    parser.parse.return_value = expected

    dependencies = DependencyProvider(
        telemetry_parser=parser,
    )

    metadata = Mock()

    result = read_building_state(
        dependencies=dependencies,
        sql_file="output/eplusout.sql",
        metadata=metadata,
        runtime_seconds=10.5,
    )

    parser.parse.assert_called_once_with(
        sql_file="output/eplusout.sql",
        metadata=metadata,
        runtime_seconds=10.5,
    )

    assert result is expected


def test_read_building_state_propagates_exceptions() -> None:
    parser = Mock()

    parser.parse.side_effect = RuntimeError("Parser failed")

    dependencies = DependencyProvider(
        telemetry_parser=parser,
    )

    with pytest.raises(RuntimeError, match="Parser failed"):
        read_building_state(
            dependencies=dependencies,
            sql_file="output/eplusout.sql",
            metadata=Mock(),
            runtime_seconds=1.0,
        )