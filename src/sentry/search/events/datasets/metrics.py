from typing import Callable, List, Mapping, Optional, Union

import sentry_sdk
from snuba_sdk.column import Column
from snuba_sdk.conditions import Op
from snuba_sdk.function import Function

from sentry.api.event_search import SearchFilter, SearchKey, SearchValue
from sentry.discover.models import TeamKeyTransaction
from sentry.exceptions import InvalidSearchQuery
from sentry.models import Project, ProjectTeam
from sentry.search.events import constants, fields
from sentry.search.events.builder import QueryBuilder
from sentry.search.events.datasets.base import DatasetConfig
from sentry.search.events.filter import to_list
from sentry.search.events.types import SelectType, WhereType
from sentry.sentry_metrics import indexer
from sentry.utils.numbers import format_grouped_length

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
        return {
            constants.PROJECT_ALIAS: self._project_slug_filter_converter,
            constants.PROJECT_NAME_ALIAS: self._project_slug_filter_converter,
        }

    # Query Filters
    def _project_slug_filter_converter(self, search_filter: SearchFilter) -> Optional[WhereType]:
        """Convert project slugs to ids and create a filter based on those.
        This is cause we only store project ids in clickhouse.
        """
        value = search_filter.value.value

        if Op(search_filter.operator) == Op.EQ and value == "":
            raise InvalidSearchQuery(
                'Cannot query for has:project or project:"" as every event will have a project'
            )

        slugs = to_list(value)
        project_slugs: Mapping[str, int] = {
            slug: project_id
            for slug, project_id in self.builder.project_slugs.items()
            if slug in slugs
        }
        missing: List[str] = [slug for slug in slugs if slug not in project_slugs]
        if missing and search_filter.operator in constants.EQUALITY_OPERATORS:
            raise InvalidSearchQuery(
                f"Invalid query. Project(s) {', '.join(missing)} do not exist or are not actively selected."
            )
        # Sorted for consistent query results
        project_ids = list(sorted(project_slugs.values()))
        if project_ids:
            # Create a new search filter with the correct values
            converted_filter = self.builder.convert_search_filter_to_condition(
                SearchFilter(
                    SearchKey("project.id"),
                    search_filter.operator,
                    SearchValue(project_ids if search_filter.is_in_filter else project_ids[0]),
                )
            )
            if converted_filter:
                if search_filter.operator in constants.EQUALITY_OPERATORS:
                    self.builder.projects_to_filter.update(project_ids)
                return converted_filter

        return None

    @property
    def field_alias_converter(self) -> Mapping[str, Callable[[str], SelectType]]:
        return {
            constants.PROJECT_ALIAS: self._resolve_project_slug_alias,
            constants.PROJECT_NAME_ALIAS: self._resolve_project_slug_alias,
            constants.TEAM_KEY_TRANSACTION_ALIAS: self._resolve_team_key_transaction_alias,
        }

    def _resolve_project_slug_alias(self, alias: str) -> SelectType:
        project_ids = {
            project_id
            for project_id in self.builder.params.get("project_id", [])
            if isinstance(project_id, int)
        }

        # Try to reduce the size of the transform by using any existing conditions on projects
        # Do not optimize projects list if conditions contain OR operator
        if not self.builder.has_or_condition and len(self.builder.projects_to_filter) > 0:
            project_ids &= self.builder.projects_to_filter

        projects = Project.objects.filter(id__in=project_ids).values("slug", "id")

        return Function(
            "transform",
            [
                self.builder.column("project.id"),
                [project["id"] for project in projects],
                [project["slug"] for project in projects],
                "",
            ],
            alias,
        )

    def _resolve_team_key_transaction_alias(self, _: str) -> SelectType:
        org_id = self.builder.params.get("organization_id")
        project_ids = self.builder.params.get("project_id")
        team_ids = self.builder.params.get("team_id")

        if org_id is None or team_ids is None or project_ids is None:
            raise TypeError("Team key transactions parameters cannot be None")

        team_key_transactions = [
            (project, indexer.resolve(transaction))
            for project, transaction in TeamKeyTransaction.objects.filter(
                organization_id=org_id,
                project_team__in=ProjectTeam.objects.filter(
                    project_id__in=project_ids, team_id__in=team_ids
                ),
            )
            .order_by("transaction", "project_team__project_id")
            .values_list("project_team__project_id", "transaction")
            .distinct("transaction", "project_team__project_id")[
                : fields.MAX_QUERYABLE_TEAM_KEY_TRANSACTIONS
            ]
        ]

        count = len(team_key_transactions)

        # NOTE: this raw count is not 100% accurate because if it exceeds
        # `MAX_QUERYABLE_TEAM_KEY_TRANSACTIONS`, it will not be reflected
        sentry_sdk.set_tag("team_key_txns.count", count)
        sentry_sdk.set_tag(
            "team_key_txns.count.grouped", format_grouped_length(count, [10, 100, 250, 500])
        )

        if count == 0:
            return Function("toInt8", [0], constants.TEAM_KEY_TRANSACTION_ALIAS)

        return Function(
            "in",
            [
                (self.builder.column("project_id"), self.builder.column("transaction")),
                team_key_transactions,
            ],
            constants.TEAM_KEY_TRANSACTION_ALIAS,
        )

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
                            Function(
                                "countMergeIf",
                                [
                                    Column("count"),
                                    Function(
                                        "equals",
                                        [
                                            Column("metric_id"),
                                            self.resolve_metric("transaction.duration"),
                                        ],
                                    ),
                                ],
                            ),
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
                        [
                            Function(
                                "countMergeIf",
                                [
                                    Column("count"),
                                    Function(
                                        "equals",
                                        [
                                            Column("metric_id"),
                                            self.resolve_metric("transaction.duration"),
                                        ],
                                    ),
                                ],
                            ),
                            args["interval"],
                        ],
                        alias,
                    ),
                    optional_args=[fields.IntervalDefault("interval", 1, None)],
                    default_result_type="number",
                ),
                # TODO(wmak): actually implement user_misery
                fields.SnQLFunction(
                    "user_misery",
                    snql_aggregate=lambda _, alias: Function(
                        "countMergeIf",
                        [
                            Column("count"),
                            Function(
                                "equals",
                                [
                                    Column("metric_id"),
                                    self.resolve_metric("transaction.duration"),
                                ],
                            ),
                        ],
                        alias,
                    ),
                ),
                # TODO(wmak): actually implement apdex
                fields.SnQLFunction(
                    "apdex",
                    snql_aggregate=lambda _, alias: Function(
                        "countMergeIf",
                        [
                            Column("count"),
                            Function(
                                "equals",
                                [
                                    Column("metric_id"),
                                    self.resolve_metric("transaction.duration"),
                                ],
                            ),
                        ],
                    ),
                    default_result_type="integer",
                ),
                # TODO(wmak): actually implement apdex
                fields.SnQLFunction(
                    "count_miserable",
                    required_args=[fields.ColumnTagArg("column")],
                    snql_aggregate=lambda _, alias: Function(
                        "countMergeIf",
                        [
                            Column("count"),
                            Function(
                                "equals",
                                [
                                    Column("metric_id"),
                                    self.resolve_metric("transaction.duration"),
                                ],
                            ),
                        ],
                    ),
                    default_result_type="integer",
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
                fields.SnQLFunction(
                    "failure_rate",
                    snql_aggregate=lambda args, alias: Function(
                        "divide",
                        [
                            self._build_failure_count(args),
                            Function(
                                "countMergeIf",
                                [
                                    Column("count"),
                                    Function(
                                        "equals",
                                        [
                                            Column("metric_id"),
                                            self.resolve_metric("transaction.duration"),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                        alias,
                    ),
                    default_result_type="integer",
                ),
            ]
        }

        for alias, name in constants.FUNCTION_ALIASES.items():
            function_converter[alias] = function_converter[name].alias_as(alias)

        return function_converter

    def _build_failure_count(
        self,
        args: Mapping[str, Union[str, Column, SelectType, int, float]],
    ) -> SelectType:
        statuses = [indexer.resolve(status) for status in ["ok", "cancelled", "unknown"]]
        return Function(
            "countMergeIf",
            [
                Column("count"),
                Function(
                    "and",
                    [
                        Function(
                            "equals",
                            [
                                Column("metric_id"),
                                self.resolve_metric("transaction.duration"),
                            ],
                        ),
                        Function(
                            "notIn",
                            [
                                self.builder.column("transaction.status"),
                                list(status for status in statuses if status is not None),
                            ],
                        ),
                    ],
                ),
            ],
        )

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
