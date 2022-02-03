from typing import Callable, Mapping, Optional, Union

from snuba_sdk.column import Column
from snuba_sdk.function import Function

from sentry.api.event_search import SearchFilter
from sentry.exceptions import InvalidSearchQuery
from sentry.search.events import fields
from sentry.search.events.builder import QueryBuilder
from sentry.search.events.constants import FUNCTION_ALIASES
from sentry.search.events.datasets.base import DatasetConfig
from sentry.search.events.types import SelectType, WhereType
from sentry.sentry_metrics import indexer

METRICS_MAP = {
    "measurements.fp": "sentry.transactions.measurements.fp",
    "measurements.fcp": "sentry.transactions.measurements.fcp",
    "measurements.lcp": "sentry.transactions.measurements.lcp",
    "measurements.fid": "sentry.transactions.measurements.fid",
    "measurements.cls": "sentry.transactions.measurements.cls",
    "measurements.ttfb": "sentry.transactions.measurements.ttfb",
    "measurements.ttfb.requesttime": "sentry.transactions.measurements.ttfb.requesttime",
    "transaction.duration": "sentry.transactions.transaction.duration",
    "user": "sentry.transactions.user",
}


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

    def resolve_metric(self, value: str) -> int:
        metric_id = indexer.resolve(METRICS_MAP.get(value, value))
        if metric_id is None:
            raise InvalidSearchQuery(f"Metric: {value} could not be resolved")

        return metric_id

    @property
    def function_converter(self) -> Mapping[str, fields.SnQLFunction]:
        resolve_metric_id = {
            "name": "metric_id",
            "fn": lambda args: self.resolve_metric(args["column"]),
        }
        function_converter = {
            function.name: function
            for function in [
                fields.SnQLFunction(
                    "p50",
                    optional_args=[
                        fields.with_default("transaction.duration", fields.NumericColumn("column")),
                    ],
                    calculated_args=[resolve_metric_id],
                    snql_aggregate=lambda args, alias: self._resolve_percentile(args, alias, 0.5),
                    default_result_type="duration",
                ),
                fields.SnQLFunction(
                    "p75",
                    optional_args=[
                        fields.with_default("transaction.duration", fields.NumericColumn("column")),
                    ],
                    calculated_args=[resolve_metric_id],
                    snql_aggregate=lambda args, alias: self._resolve_percentile(args, alias, 0.75),
                    default_result_type="duration",
                ),
                fields.SnQLFunction(
                    "p90",
                    optional_args=[
                        fields.with_default("transaction.duration", fields.NumericColumn("column")),
                    ],
                    calculated_args=[resolve_metric_id],
                    snql_aggregate=lambda args, alias: self._resolve_percentile(args, alias, 0.90),
                    default_result_type="duration",
                ),
                fields.SnQLFunction(
                    "p95",
                    optional_args=[
                        fields.with_default("transaction.duration", fields.NumericColumn("column")),
                    ],
                    calculated_args=[resolve_metric_id],
                    snql_aggregate=lambda args, alias: self._resolve_percentile(args, alias, 0.95),
                    default_result_type="duration",
                ),
                fields.SnQLFunction(
                    "p99",
                    optional_args=[
                        fields.with_default("transaction.duration", fields.NumericColumn("column")),
                    ],
                    calculated_args=[resolve_metric_id],
                    snql_aggregate=lambda args, alias: self._resolve_percentile(args, alias, 0.99),
                    default_result_type="duration",
                ),
                fields.SnQLFunction(
                    "epm",
                    snql_aggregate=lambda args, alias: Function(
                        "divide",
                        [
                            Function("countMerge", [Column("count")]),
                            Function("divide", [args["interval"], 60]),
                        ],
                        alias,
                    ),
                    optional_args=[fields.IntervalDefault("interval", 1, None)],
                    default_result_type="number",
                ),
                fields.SnQLFunction(
                    "eps",
                    calculated_args=[resolve_metric_id],
                    snql_aggregate=lambda args, alias: Function(
                        "divide",
                        [Function("countMerge", [Column("count")]), args["interval"]],
                        alias,
                    ),
                    optional_args=[fields.IntervalDefault("interval", 1, None)],
                    default_result_type="number",
                ),
                fields.SnQLFunction(
                    "count_unique",
                    required_args=[fields.ColumnTagArg("column")],
                    calculated_args=[resolve_metric_id],
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

        for alias, name in FUNCTION_ALIASES.items():
            function_converter[alias] = function_converter[name].alias_as(alias)

        return function_converter

    def _resolve_percentile(
        self,
        args: Mapping[str, Union[str, Column, SelectType, int, float]],
        alias: str,
        fixed_percentile: float,
    ) -> SelectType:
        return Function(
            "arrayElement",
            [
                Function(
                    f"quantilesMergeIf({fixed_percentile})",
                    [
                        Column("percentiles"),
                        Function("equals", [Column("metric_id"), args["metric_id"]]),
                    ],
                ),
                1,
            ],
            alias,
        )
