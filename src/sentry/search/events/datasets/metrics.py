from typing import Callable, Mapping, Optional

from snuba_sdk.column import Column
from snuba_sdk.function import Function

from sentry.api.event_search import SearchFilter
from sentry.exceptions import InvalidSearchQuery
from sentry.search.events import fields
from sentry.search.events.builder import QueryBuilder
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
        return {
            function.name: function
            for function in [
                fields.SnQLFunction(
                    "p50",
                    optional_args=[
                        fields.with_default("transaction.duration", fields.NumericColumn("column")),
                    ],
                    calculated_args=[resolve_metric_id],
                    snql_aggregate=lambda args, alias: Function(
                        "arrayElement",
                        [
                            Function(
                                "quantilesMergeIf(0.5)",
                                [
                                    Column("percentiles"),
                                    Function("equals", [Column("metric_id"), args["metric_id"]]),
                                ],
                            ),
                            1,
                        ],
                        alias,
                    ),
                    default_result_type="duration",
                ),
                fields.SnQLFunction(
                    "p75",
                    optional_args=[
                        fields.with_default("transaction.duration", fields.NumericColumn("column")),
                    ],
                    calculated_args=[resolve_metric_id],
                    snql_aggregate=lambda args, alias: Function(
                        "quantilesMergeIf(0.75)",
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
