from datetime import timedelta
from typing import Dict, Optional, Sequence

from sentry.discover.arithmetic import categorize_columns
from sentry.search.events.builder import MetricsQueryBuilder
from sentry.search.utils import InvalidQuery
from sentry.snuba import discover
from sentry.utils.snuba import Dataset, raw_snql_query

# TODO: determine these based on sentry/snuba/events.py
METRICS_SUPPORTED_COLUMNS = {
    "transaction.duration",
    "avg(transaction.duration)",
}


def timeseries_query(
    selected_columns: Sequence[str],
    query: str,
    params: Dict[str, str],
    rollup: int,
    referrer: Optional[str] = None,
    zerofill_results: bool = True,
    comparison_delta: Optional[timedelta] = None,
    functions_acl: Optional[Sequence[str]] = None,
    use_snql: Optional[bool] = False,
):
    """
    High-level API for doing arbitrary user timeseries queries against events.

    this API should match that of sentry.snuba.discover.timeseries_query
    """
    metrics_compatible = True
    equations, columns = categorize_columns(selected_columns)
    # TODO: Parse query to determine if we can do metrics instead of only allowing blank
    # TODO: Technically could do comparison_delta here too, but since we don't use it in performance I'm skipping it
    # use_snql must be enabled since we aren't backporting metrics to the older query functions
    if not query and comparison_delta is None and use_snql:
        if len(equations) > 0:
            print("equations")
            metrics_compatible = False
        for column in columns:
            if column not in METRICS_SUPPORTED_COLUMNS:
                print("columns")
                metrics_compatible = False
    else:
        print("falsing")
        metrics_compatible = False
    print("mep", metrics_compatible)

    # This query cannot be enahnced with metrics, use discover
    results = []
    if metrics_compatible:
        try:
            base_builder = TimeseriesQueryBuilder(
                Dataset.Metrics,
                params,
                rollup,
                query=query,
                selected_columns=columns,
                equations=equations,
                functions_acl=functions_acl,
            )
            snql_query = base_builder.get_snql_query()
            result = raw_snql_query(snql_query, referrer)
            results.append(
                discover.zerofill(
                    result["data"],
                    snql_query.params["start"],
                    snql_query.params["end"],
                    rollup,
                    "time",
                )
                if zerofill_results
                else result["data"]
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
