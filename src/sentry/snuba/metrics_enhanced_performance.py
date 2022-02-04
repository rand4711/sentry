from datetime import timedelta
from typing import Dict, Optional, Sequence

from sentry.discover.arithmetic import categorize_columns
from sentry.search.events.builder import MetricsQueryBuilder, MetricsTimeseriesQueryBuilder
from sentry.search.utils import InvalidQuery
from sentry.snuba import discover
from sentry.utils.snuba import SnubaTSResult


def query(
    selected_columns,
    query,
    params,
    equations=None,
    orderby=None,
    offset=None,
    limit=50,
    referrer=None,
    auto_fields=False,
    auto_aggregations=False,
    use_aggregate_conditions=False,
    conditions=None,
    extra_snql_condition=None,
    functions_acl=None,
    use_snql=False,
):
    """ """
    metrics_compatible = False
    if use_snql:
        metrics_compatible = True

    results = None
    if metrics_compatible:
        try:
            metrics_query = MetricsQueryBuilder(
                params,
                query=query,
                selected_columns=selected_columns,
                equations=equations,
                orderby=orderby,
                auto_fields=auto_fields,
                auto_aggregations=auto_aggregations,
                use_aggregate_conditions=use_aggregate_conditions,
                functions_acl=functions_acl,
                limit=limit,
                offset=offset,
            )
            # Getting the 0th result for now, will need to consolidate multiple query results later
            results = metrics_query.run_query(referrer + ".metrics-enhanced")
            results = discover.transform_results(
                results, metrics_query.function_alias_map, {}, None
            )
            results["meta"]["mep"] = True
            return results
        # raise InvalidQuery since the same thing will happen with discover
        except InvalidQuery as error:
            raise error
        # any remaining errors mean we should try again with discover
        # except Exception:
        #     results = []

    # Either metrics failed, or this isn't a query we can enhance with metrics
    if results is None or not metrics_compatible:
        results = discover.query(
            selected_columns,
            query,
            params,
            equations=equations,
            orderby=orderby,
            offset=offset,
            limit=limit,
            referrer=referrer,
            auto_fields=auto_fields,
            use_aggregate_conditions=use_aggregate_conditions,
            conditions=conditions,
            extra_snql_condition=extra_snql_condition,
            functions_acl=functions_acl,
            use_snql=use_snql,
        )
        results["meta"]["mep"] = False

    # TODO: set meta to include whether query was MEP or not
    return results


def timeseries_query(
    selected_columns: Sequence[str],
    query: str,
    params: Dict[str, str],
    rollup: int,
    referrer: str,
    zerofill_results: bool = True,
    comparison_delta: Optional[timedelta] = None,
    functions_acl: Optional[Sequence[str]] = None,
    use_snql: Optional[bool] = False,
):
    """
    High-level API for doing arbitrary user timeseries queries against events.

    this API should match that of sentry.snuba.discover.timeseries_query
    """
    metrics_compatible = False
    equations, columns = categorize_columns(selected_columns)
    # TODO: Parse query to determine if we can do metrics instead of only allowing blank
    # TODO: Technically could do comparison_delta here too, but since we don't use it in performance I'm skipping it
    # use_snql must be enabled since we aren't backporting metrics to the older query functions
    if comparison_delta is None and use_snql:
        metrics_compatible = True

    # This query cannot be enahnced with metrics, use discover
    results = []
    if metrics_compatible:
        try:
            metrics_query = MetricsTimeseriesQueryBuilder(
                params,
                rollup,
                query=query,
                selected_columns=columns,
                equations=equations,
                functions_acl=functions_acl,
            )
            # Getting the 0th result for now, will need to consolidate multiple query results later
            result = metrics_query.run_query(referrer + ".metrics-enhanced")
            result = discover.transform_results(result, metrics_query.function_alias_map, {}, None)
            result["data"] = (
                discover.zerofill(
                    result["data"],
                    params["start"],
                    params["end"],
                    rollup,
                    "time",
                )
                if zerofill_results
                else result["data"]
            )
            results = SnubaTSResult(
                {"data": result["data"]}, params["start"], params["end"], rollup, meta=True
            )
        # raise InvalidQuery since the same thing will happen with discover
        except InvalidQuery as error:
            raise error
        # any remaining errors mean we should try again with discover
        # except Exception:
        #     results = []

    # Either metrics failed, or this isn't a query we can enhance with metrics
    if results is None or not metrics_compatible:
        results = discover.timeseries_query(
            selected_columns,
            query,
            params,
            rollup,
            referrer,
            zerofill_results,
            comparison_delta,
            functions_acl,
            use_snql,
        )

    # TODO: set meta to include whether query was MEP or not
    return results
