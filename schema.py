# schema.py
from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Literal, Optional, Union

ALLOWED_FIELDS = {
    "Year", "Quarter", "Month", "Week", "Date",
    "Country", "Media Category", "Media Name", "Communication",
    "Campaign Category", "Product", "Campaign Name",
    "Revenue", "Cost", "Profit"
}

Metric = Literal["Revenue", "Cost", "Profit"]
Op = Literal["=", "!=", "in", "between"]

class Filter(BaseModel):
    field: str
    op: Op
    value: Union[str, int, float, List[Union[str, int, float]]]

    @field_validator("field")
    @classmethod
    def must_be_allowed_field(cls, v: str):
        if v not in ALLOWED_FIELDS:
            raise ValueError(f"Unknown field: {v}")
        return v

    @model_validator(mode="after")
    def validate_value_shape(self):
        if self.op == "in" and not isinstance(self.value, list):
            raise ValueError("op=in requires value as a list")
        if self.op == "between":
            if not (isinstance(self.value, list) and len(self.value) == 2):
                raise ValueError("op=between requires value=[start,end]")
        return self

class TimeSpec(BaseModel):
    type: Literal["none","year","quarter","month","date_between","last_quarter","last_month"] = "none"
    value: Optional[Union[str, int, List[str]]] = None

class SortSpec(BaseModel):
    by: Metric
    dir: Literal["asc","desc"] = "desc"

class QuerySpec(BaseModel):
    metrics: List[Metric] = Field(default_factory=lambda: ["Revenue"])
    group_by: List[str] = Field(default_factory=list)
    time: TimeSpec = Field(default_factory=TimeSpec)
    filters: List[Filter] = Field(default_factory=list)
    sort: List[SortSpec] = Field(default_factory=list)
    limit: Optional[int] = None
    output: Literal["single_value","table","trend"] = "table"

    @field_validator("group_by")
    @classmethod
    def group_by_allowed(cls, v: List[str]):
        for f in v:
            if f not in ALLOWED_FIELDS:
                raise ValueError(f"Unknown group_by field: {f}")
            if f in {"Revenue","Cost","Profit"}:
                raise ValueError("Cannot group_by metric fields")
        return v

class PatchSpec(BaseModel):
    time: Optional[TimeSpec] = None
    filters_add: List[Filter] = Field(default_factory=list)
    filters_remove_fields: List[str] = Field(default_factory=list)
    metrics_replace: Optional[List[Metric]] = None
    group_by_replace: Optional[List[str]] = None
    sort_replace: Optional[List[SortSpec]] = None
    limit_replace: Optional[int] = None
    output_replace: Optional[Literal["single_value","table","trend"]] = None 