"""TSNetPlus model type alias."""

from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    import tsnetplus

    TSNetPlusModel: TypeAlias = tsnetplus.network.TransientModel
else:
    try:
        import tsnetplus

        TSNetPlusModel: TypeAlias = tsnetplus.network.TransientModel
    except Exception:  # pragma: no cover - optional dependency
        TSNetPlusModel = object  # type: ignore[misc, assignment]
