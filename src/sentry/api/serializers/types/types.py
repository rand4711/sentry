from typing import List, Optional, TypedDict


class AvatarReturnType(TypedDict):
    avatarUuid: Optional[str]
    avatarType: str


class OrganizationSerializerReturnType(TypedDict):
    id: str
    slug: str
    status: int
    name: str
    dateCreated: str
    isearlyAdopter: bool
    require2FA: bool
    requireEmailVerification: bool
    avatar: AvatarReturnType
    features: List[str]


class ExternalActorSerializerReturnType(TypedDict, total=False):
    id: str
    provider: str
    externalName: str
    integrationId: str
    externalId: str
    userId: str
    teamId: str


class ProjectSerializerReturnTypeRequired(TypedDict, total=True):
    id: str
    slug: str
    name: str
    isPublic: bool
    isBookmarked: bool
    color: str
    dateCreated: Optional[str]
    firstEvent: Optional[str]
    features: List[str]
    status: str
    platform: Optional[str]
    isInternal: bool
    isMember: bool
    hasAccess: bool
    avatar: AvatarReturnType
    stats: str
    transactionStats: str
    sessionStats: str


class TeamSerializerReturnType(TypedDict, total=False):
    id: str
    slug: str
    name: str
    dateCreated: str
    isMember: bool
    hasAccess: bool
    isPending: bool
    memberCount: int
    avatar: AvatarReturnType
    projects: List[ProjectSerializerReturnTypeRequired]
    externalTeams: List[ExternalActorSerializerReturnType]
    organization: OrganizationSerializerReturnType
