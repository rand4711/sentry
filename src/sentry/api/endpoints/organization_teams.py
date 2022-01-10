from typing import List

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.bases.organization import OrganizationEndpoint, OrganizationPermission
from sentry.api.paginator import OffsetPaginator
from sentry.api.serializers import serialize
from sentry.api.serializers.models.team import TeamSerializer
from sentry.api.serializers.types.types import TeamSerializerReturnType
from sentry.apidocs.constants import RESPONSE_FORBIDDEN, RESPONSE_NOTFOUND, RESPONSE_UNAUTHORIZED
from sentry.apidocs.decorators import declare_public
from sentry.apidocs.parameters import GLOBAL_PARAMS
from sentry.apidocs.schemaserializer import inline_sentry_response_serializer
from sentry.models import (
    AuditLogEntryEvent,
    ExternalActor,
    OrganizationMember,
    OrganizationMemberTeam,
    Team,
    TeamStatus,
)
from sentry.search.utils import tokenize_query
from sentry.signals import team_created

CONFLICTING_SLUG_ERROR = "A team with this slug already exists."


# OrganizationPermission + team:write
class OrganizationTeamsPermission(OrganizationPermission):
    scope_map = {
        "GET": ["org:read", "org:write", "org:admin"],
        "POST": ["org:write", "org:admin", "team:write"],
        "PUT": ["org:write", "org:admin", "team:write"],
        "DELETE": ["org:admin", "team:write"],
    }


class TeamPostSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64, required=False, allow_null=True, allow_blank=True)
    slug = serializers.RegexField(
        r"^[a-z0-9_\-]+$",
        max_length=50,
        required=False,
        allow_null=True,
        error_messages={
            "invalid": _(
                "Enter a valid slug consisting of lowercase letters, "
                "numbers, underscores or hyphens."
            )
        },
    )

    def validate(self, attrs):
        if not (attrs.get("name") or attrs.get("slug")):
            raise serializers.ValidationError("Name or slug is required")
        return attrs


@declare_public({"GET", "POST"})
class OrganizationTeamsEndpoint(OrganizationEndpoint):
    permission_classes = (OrganizationTeamsPermission,)

    def team_serializer_for_post(self):
        # allow child routes to supply own serializer, used in SCIM teams route
        return TeamSerializer()

    @extend_schema(
        operation_id="List an Organization's Teams",
        parameters=[GLOBAL_PARAMS.ORG_SLUG],
        request=None,
        responses={
            200: inline_sentry_response_serializer("ListTeams+", List[TeamSerializerReturnType]),
            401: RESPONSE_UNAUTHORIZED,
            403: RESPONSE_FORBIDDEN,
            404: RESPONSE_NOTFOUND,
        },
        examples=[  # TODO: see if this can go on serializer object instead
            OpenApiExample(
                "Successful response",
                value=[
                    {
                        "avatar": {"avatarType": "letter_avatar", "avatarUuid": None},
                        "dateCreated": "2018-11-06T21:20:08.115Z",
                        "hasAccess": True,
                        "id": "3",
                        "isMember": True,
                        "isPending": False,
                        "memberCount": 1,
                        "name": "Ancient Gabelers",
                        "projects": [],
                        "slug": "ancient-gabelers",
                    },
                    {
                        "avatar": {"avatarType": "letter_avatar", "avatarUuid": None},
                        "dateCreated": "2018-11-06T21:19:55.114Z",
                        "hasAccess": True,
                        "id": "2",
                        "isMember": True,
                        "isPending": False,
                        "memberCount": 1,
                        "name": "Powerful Abolitionist",
                        "projects": [
                            {
                                "avatar": {"avatarType": "letter_avatar", "avatarUuid": None},
                                "color": "#bf5b3f",
                                "dateCreated": "2018-11-06T21:19:58.536Z",
                                "features": [
                                    "releases",
                                    "sample-events",
                                    "minidump",
                                    "servicehooks",
                                    "rate-limits",
                                    "data-forwarding",
                                ],
                                "firstEvent": None,
                                "hasAccess": True,
                                "id": "3",
                                "isBookmarked": False,
                                "isInternal": False,
                                "isMember": True,
                                "isPublic": False,
                                "name": "Prime Mover",
                                "platform": None,
                                "slug": "prime-mover",
                                "status": "active",
                            },
                            {
                                "avatar": {"avatarType": "letter_avatar", "avatarUuid": None},
                                "color": "#3fbf7f",
                                "dateCreated": "2018-11-06T21:19:55.121Z",
                                "features": [
                                    "releases",
                                    "sample-events",
                                    "minidump",
                                    "servicehooks",
                                    "rate-limits",
                                    "data-forwarding",
                                ],
                                "firstEvent": None,
                                "hasAccess": True,
                                "id": "2",
                                "isBookmarked": False,
                                "isInternal": False,
                                "isMember": True,
                                "isPublic": False,
                                "name": "Pump Station",
                                "platform": None,
                                "slug": "pump-station",
                                "status": "active",
                            },
                            {
                                "avatar": {"avatarType": "letter_avatar", "avatarUuid": None},
                                "color": "#bf6e3f",
                                "dateCreated": "2018-11-06T21:20:08.064Z",
                                "features": [
                                    "servicehooks",
                                    "sample-events",
                                    "data-forwarding",
                                    "rate-limits",
                                    "minidump",
                                ],
                                "firstEvent": None,
                                "hasAccess": True,
                                "id": "4",
                                "isBookmarked": False,
                                "isInternal": False,
                                "isMember": True,
                                "isPublic": False,
                                "name": "The Spoiled Yoghurt",
                                "platform": None,
                                "slug": "the-spoiled-yoghurt",
                                "status": "active",
                            },
                        ],
                        "slug": "powerful-abolitionist",
                    },
                ],
            ),
        ],
    )
    def get(self, request: Request, organization) -> Response:
        """
        List an Organization's Teams
        ````````````````````````````

        Return a list of teams bound to a organization.

        :pparam string organization_slug: the slug of the organization for
                                          which the teams should be listed.
        :param string detailed: Specify "0" to return team details that do not include projects
        :auth: required
        """
        # TODO(dcramer): this should be system-wide default for organization
        # based endpoints
        if request.auth and hasattr(request.auth, "project"):
            return Response(status=403)

        queryset = Team.objects.filter(
            organization=organization, status=TeamStatus.VISIBLE
        ).order_by("slug")

        query = request.GET.get("query")

        if query:
            tokens = tokenize_query(query)
            for key, value in tokens.items():
                if key == "hasExternalTeams":
                    has_external_teams = "True" in value
                    if has_external_teams:
                        queryset = queryset.filter(
                            actor_id__in=ExternalActor.objects.filter(
                                organization=organization
                            ).values_list("actor_id")
                        )
                    else:
                        queryset = queryset.exclude(
                            actor_id__in=ExternalActor.objects.filter(
                                organization=organization
                            ).values_list("actor_id")
                        )

                elif key == "query":
                    value = " ".join(value)
                    queryset = queryset.filter(Q(name__icontains=value) | Q(slug__icontains=value))
                elif key == "slug":
                    queryset = queryset.filter(slug__in=value)
                elif key == "id":
                    queryset = queryset.filter(id__in=value)
                else:
                    queryset = queryset.none()

        is_detailed = request.GET.get("detailed", "1") != "0"

        expand = ["projects", "externalTeams"] if is_detailed else []

        return self.paginate(
            request=request,
            queryset=queryset,
            order_by="slug",
            on_results=lambda x: serialize(x, request.user, TeamSerializer(expand=expand)),
            paginator_cls=OffsetPaginator,
        )

    def should_add_creator_to_team(self, request: Request):
        return request.user.is_authenticated

    @extend_schema(
        operation_id="Create a new Team",
        parameters=[GLOBAL_PARAMS.ORG_SLUG],
        request=TeamPostSerializer,
        responses={
            201: TeamSerializer,
            401: RESPONSE_UNAUTHORIZED,
            403: RESPONSE_FORBIDDEN,
            404: RESPONSE_NOTFOUND,
        },
        examples=[  # TODO: see if this can go on serializer object instead
            OpenApiExample(
                "Successful response",
                value={
                    "memberCount": 0,
                    "name": "Ancient Gabelers",
                    "isMember": False,
                    "hasAccess": True,
                    "isPending": False,
                    "dateCreated": "2020-08-19T21:46:47.877073Z",
                    "id": "542610",
                    "avatar": {"avatarUuid": None, "avatarType": "letter_avatar"},
                    "slug": "ancient-gabelers",
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
    )
    def post(self, request: Request, organization, **kwargs) -> Response:
        """
        Create a new team bound to an organization.  Only the name of the
        team is needed to create it, the slug can be auto generated.
        """
        serializer = TeamPostSerializer(data=request.data)

        if serializer.is_valid():
            result = serializer.validated_data

            try:
                with transaction.atomic():
                    team = Team.objects.create(
                        name=result.get("name") or result["slug"],
                        slug=result.get("slug"),
                        organization=organization,
                    )
            except IntegrityError:
                return Response(
                    {
                        "non_field_errors": [CONFLICTING_SLUG_ERROR],
                        "detail": CONFLICTING_SLUG_ERROR,
                    },
                    status=409,
                )
            else:
                team_created.send_robust(
                    organization=organization, user=request.user, team=team, sender=self.__class__
                )
            if self.should_add_creator_to_team(request):
                try:
                    member = OrganizationMember.objects.get(
                        user=request.user, organization=organization
                    )
                except OrganizationMember.DoesNotExist:
                    pass
                else:
                    OrganizationMemberTeam.objects.create(team=team, organizationmember=member)

            self.create_audit_entry(
                request=request,
                organization=organization,
                target_object=team.id,
                event=AuditLogEntryEvent.TEAM_ADD,
                data=team.get_audit_log_data(),
            )
            return Response(
                serialize(team, request.user, self.team_serializer_for_post()),
                status=201,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
