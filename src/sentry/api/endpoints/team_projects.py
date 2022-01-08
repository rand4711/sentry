from django.db import IntegrityError, transaction
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.base import EnvironmentMixin
from sentry.api.bases.team import TeamEndpoint, TeamPermission
from sentry.api.paginator import OffsetPaginator
from sentry.api.serializers import ProjectSummarySerializer, serialize
from sentry.api.serializers.models.project import ProjectSerializer
from sentry.apidocs.constants import RESPONSE_FORBIDDEN, RESPONSE_NOTFOUND, RESPONSE_UNAUTHORIZED
from sentry.apidocs.decorators import declare_public
from sentry.apidocs.parameters import GLOBAL_PARAMS
from sentry.apidocs.schemaserializer import inline_list_serializer, inline_serializer
from sentry.models import AuditLogEntryEvent, Project, ProjectStatus
from sentry.signals import project_created

ERR_INVALID_STATS_PERIOD = "Invalid stats_period. Valid choices are '', '24h', '14d', and '30d'"


class ProjectRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50, required=True)
    slug = serializers.RegexField(r"^[a-z0-9_\-]+$", max_length=50, required=False, allow_null=True)
    platform = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    default_rules = serializers.BooleanField(required=False, initial=True)

    def validate_platform(self, value):
        if Project.is_valid_platform(value):
            return value
        raise serializers.ValidationError("Invalid platform")


# While currently the UI suggests teams are a parent of a project, in reality
# the project is the core component, and which team it is on is simply an
# attribute. Because you can already change the team of a project via mutating
# it, and because Sentry intends to remove teams as a hierarchy item, we
# allow you to view a teams projects, as well as create a new project as long
# as you are a member of that team and have project scoped permissions.


class TeamProjectPermission(TeamPermission):
    scope_map = {
        "GET": ["project:read", "project:write", "project:admin"],
        "POST": ["project:write", "project:admin"],
        "PUT": ["project:write", "project:admin"],
        "DELETE": ["project:admin"],
    }


@declare_public({"GET"})
class TeamProjectsEndpoint(TeamEndpoint, EnvironmentMixin):
    permission_classes = (TeamProjectPermission,)

    @extend_schema(
        operation_id="List a Team's Projects",
        parameters=[GLOBAL_PARAMS.ORG_SLUG, GLOBAL_PARAMS.TEAM_SLUG],
        request=None,
        responses={
            200: inline_serializer([ProjectSerializer]),
            401: RESPONSE_UNAUTHORIZED,
            403: RESPONSE_FORBIDDEN,
            404: RESPONSE_NOTFOUND,
        },
        examples=[  # TODO: see if this can go on serializer object instead
            OpenApiExample(
                "Successful response",
                value=[
                    {
                        "status": "active",
                        "name": "The Spoiled Yoghurt",
                        "color": "#bf6e3f",
                        "isInternal": False,
                        "isPublic": False,
                        "slug": "the-spoiled-yoghurt",
                        "platform": None,
                        "hasAccess": True,
                        "firstEvent": None,
                        "avatar": {"avatarUuid": None, "avatarType": "letter_avatar"},
                        "isMember": False,
                        "dateCreated": "2020-08-20T14:36:34.171255Z",
                        "isBookmarked": False,
                        "id": "5398494",
                        "features": [
                            "custom-inbound-filters",
                            "discard-groups",
                            "rate-limits",
                            "data-forwarding",
                            "similarity-view",
                            "issue-alerts-targeting",
                            "servicehooks",
                            "minidump",
                            "similarity-indexing",
                        ],
                    }
                ],
            ),
        ],
    )
    def get(self, request: Request, team) -> Response:
        """
        Return a list of projects bound to a team.

        :pparam string organization_slug: the slug of the organization the
                                          team belongs to.
        :pparam string team_slug: the slug of the team to list the projects of.
        :auth: required
        """
        if request.auth and hasattr(request.auth, "project"):
            queryset = Project.objects.filter(id=request.auth.project.id)
        else:
            queryset = Project.objects.filter(teams=team, status=ProjectStatus.VISIBLE)

        stats_period = request.GET.get("statsPeriod")
        if stats_period not in (None, "", "24h", "14d", "30d"):
            return Response(
                {"error": {"params": {"stats_period": {"message": ERR_INVALID_STATS_PERIOD}}}},
                status=400,
            )
        elif not stats_period:
            # disable stats
            stats_period = None

        return self.paginate(
            request=request,
            queryset=queryset,
            order_by="slug",
            on_results=lambda x: serialize(
                x,
                request.user,
                ProjectSummarySerializer(
                    environment_id=self._get_environment_id_from_request(
                        request, team.organization.id
                    ),
                    stats_period=stats_period,
                ),
            ),
            paginator_cls=OffsetPaginator,
        )

    def post(self, request: Request, team) -> Response:
        """
        Create a New Project
        ````````````````````

        Create a new project bound to a team.

        :pparam string organization_slug: the slug of the organization the
                                          team belongs to.
        :pparam string team_slug: the slug of the team to create a new project
                                  for.
        :param string name: the name for the new project.
        :param string slug: optionally a slug for the new project.  If it's
                            not provided a slug is generated from the name.
        :param bool default_rules: create default rules (defaults to True)
        :auth: required
        """
        serializer = ProjectRequestSerializer(data=request.data)

        if serializer.is_valid():
            result = serializer.validated_data

            with transaction.atomic():
                try:
                    with transaction.atomic():
                        project = Project.objects.create(
                            name=result["name"],
                            slug=result.get("slug"),
                            organization=team.organization,
                            platform=result.get("platform"),
                        )
                except IntegrityError:
                    return Response(
                        {"detail": "A project with this slug already exists."}, status=409
                    )
                else:
                    project.add_team(team)

                # XXX: create sample event?

                self.create_audit_entry(
                    request=request,
                    organization=team.organization,
                    target_object=project.id,
                    event=AuditLogEntryEvent.PROJECT_ADD,
                    data=project.get_audit_log_data(),
                )

                project_created.send(
                    project=project,
                    user=request.user,
                    default_rules=result.get("default_rules", True),
                    sender=self,
                )

            return Response(serialize(project, request.user), status=201)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
