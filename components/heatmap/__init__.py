import streamlit.components.v1 as components
from pathlib import Path

_component_func = components.declare_component(
    "habit_heatmap",
    path=str(Path(__file__).parent / "frontend"),
)


def habit_heatmap(grid_data: dict, height: int = 300, key=None):
    """Render heatmap; returns clicked manual cell as 'habit|date' or None."""
    return _component_func(grid_data=grid_data, height=height, key=key, default=None)
