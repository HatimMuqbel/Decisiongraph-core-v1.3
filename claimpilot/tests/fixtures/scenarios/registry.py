"""
Scenario registry - collects all scenarios for parametrized testing.

Usage:
    from tests.fixtures.scenarios import all_scenarios

    @pytest.mark.parametrize("scenario", all_scenarios(), ids=lambda s: s.id)
    def test_scenarios(scenario):
        ...
"""
from .auto import all_auto_scenarios
from .property import all_property_scenarios
from .marine import all_marine_scenarios
from .health import all_health_scenarios
from .wsib import all_wsib_scenarios
from .cgl import all_cgl_scenarios
from .eo import all_eo_scenarios
from .travel import all_travel_scenarios


def all_scenarios():
    """Return all scenarios across all lines of business."""
    return (
        all_auto_scenarios()
        + all_property_scenarios()
        + all_marine_scenarios()
        + all_health_scenarios()
        + all_wsib_scenarios()
        + all_cgl_scenarios()
        + all_eo_scenarios()
        + all_travel_scenarios()
    )


def scenarios_by_line(line: str):
    """Return scenarios for a specific line of business."""
    line_map = {
        "auto": all_auto_scenarios,
        "property": all_property_scenarios,
        "marine": all_marine_scenarios,
        "health": all_health_scenarios,
        "workers_comp": all_wsib_scenarios,
        "cgl": all_cgl_scenarios,
        "eo": all_eo_scenarios,
        "travel": all_travel_scenarios,
    }
    if line not in line_map:
        raise ValueError(f"Unknown line: {line}. Available: {list(line_map.keys())}")
    return line_map[line]()
