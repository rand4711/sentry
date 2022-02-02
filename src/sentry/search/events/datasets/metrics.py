from typing import Callable, Mapping, Optional

from snuba_sdk.column import Column
from snuba_sdk.function import Function

from sentry.api.event_search import SearchFilter
from sentry.search.events import fields
from sentry.search.events.builder import QueryBuilder
from sentry.search.events.datasets.base import DatasetConfig
from sentry.search.events.types import SelectType, WhereType
from sentry.sentry_metrics import indexer


class MetricsDatasetConfig(DatasetConfig):
    def __init__(self, builder: QueryBuilder):
        self.builder = builder

    @property
    def search_filter_converter(
        self,
    ) -> Mapping[str, Callable[[SearchFilter], Optional[WhereType]]]:
        return {}

    @property
    def field_alias_converter(self) -> Mapping[str, Callable[[str], SelectType]]:
        return {}

    @property
    def function_converter(self) -> Mapping[str, fields.SnQLFunction]:
        return {
            function.name: function
            for function in [
                fields.SnQLFunction(
                    "p50",
                    optional_args=[
                        fields.with_default("transaction.duration", fields.NumericColumn("column")),
                    ],
                    calculated_args=[
                        {"name": "metric_id", "fn": lambda args: indexer.resolve(args["column"])}
                    ],
                    snql_aggregate=lambda args, alias: Function(
                        "quantilesMergeIf(0.5)",
                        [
                            Column("percentiles"),
                            Function("equals", [Column("metric_id"), args["metric_id"]]),
                        ],
                        alias,
                    ),
                    default_result_type="duration",
                ),
                fields.SnQLFunction(
                    "count_unique",
                    required_args=[fields.ColumnTagArg("column")],
                    calculated_args=[
                        {"name": "metric_id", "fn": lambda args: indexer.resolve(args["column"])}
                    ],
                    snql_aggregate=lambda args, alias: Function(
                        "uniqCombinedIf",
                        [
                            Column("value"),
                            Function("equals", [Column("metric_id"), args["metric_id"]]),
                        ],
                        alias,
                    ),
                    default_result_type="integer",
                ),
            ]
        }
