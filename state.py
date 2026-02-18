# state.py
from schema import QuerySpec, PatchSpec

def apply_patch(last: QuerySpec, patch: PatchSpec) -> QuerySpec:
    data = last.model_dump()   # converts your Pydantic object back into a standard Python dictionary

    if patch.time is not None:
        data["time"] = patch.time.model_dump()

    if patch.metrics_replace is not None:
        data["metrics"] = patch.metrics_replace

    if patch.group_by_replace is not None:
        data["group_by"] = patch.group_by_replace

    if patch.sort_replace is not None:
        data["sort"] = [s.model_dump() for s in patch.sort_replace]

    if patch.limit_replace is not None:
        data["limit"] = patch.limit_replace

    if patch.output_replace is not None:
        data["output"] = patch.output_replace

    # filters remove
    if patch.filters_remove_fields:
        data["filters"] = [f for f in data["filters"] if f["field"] not in set(patch.filters_remove_fields)]

    # filters add（Field Override）
    if patch.filters_add:
        existing = {f["field"]: f for f in data["filters"]}
        for f in patch.filters_add:
            existing[f.field] = f.model_dump()
        data["filters"] = list(existing.values())

    return QuerySpec(**data)
