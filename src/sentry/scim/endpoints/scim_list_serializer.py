# @dataclass
# class SCIMListResponse:
#     schemas: List[str]
#     total_results: int
#     start_index: str
#     items_per_page: int
#     resources: List[T]


from typing import Any, List, Mapping, TypedDict

from sentry.api.serializers.base import Serializer
from sentry.api.serializers.models.organization_member import (
    OrganizationMemberSCIMSerializerResponse,
)
from sentry.api.serializers.models.team import OrganizationTeamSCIMSerializerResponse
from sentry.apidocs.decorators import mark_serializer_public


class SCIMListResponseDict(TypedDict):
    schemas: List[str]
    totalResults: int
    startIndex: int
    itemsPerPage: int
    Resources: List[OrganizationMemberSCIMSerializerResponse]


class SCIMListResponseDictTeams(TypedDict):
    schemas: List[str]
    totalResults: int
    startIndex: int
    itemsPerPage: int
    Resources: List[OrganizationTeamSCIMSerializerResponse]


@mark_serializer_public
class SCIMListResponseSerializer(Serializer):
    partial = False

    def serialize(
        self, obj: SCIMListResponseDict, attrs: Mapping[str, Any], user: Any, **kwargs: Any
    ) -> SCIMListResponseDict:
        return {
            "schemas": obj.schemas,
            "totalResults": obj.total_results,  # TODO: audit perf of queryset.count()
            "startIndex": obj.start_index,
            "itemsPerPage": obj.items_per_page,  # what's max?
            "Resources": obj.resources,
        }


@mark_serializer_public
class SCIMListResponseSerializerTeams(Serializer):
    partial = False

    def serialize(
        self, obj: SCIMListResponseDict, attrs: Mapping[str, Any], user: Any, **kwargs: Any
    ) -> SCIMListResponseDictTeams:
        return {
            "schemas": obj.schemas,
            "totalResults": obj.total_results,  # TODO: audit perf of queryset.count()
            "startIndex": obj.start_index,
            "itemsPerPage": obj.items_per_page,  # what's max?
            "Resources": obj.resources,
        }
