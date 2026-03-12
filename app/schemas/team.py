from pydantic import AliasChoices, BaseModel, Field, field_validator


class TeamCreateRequest(BaseModel):
    team_name: str = Field(min_length=1, max_length=100)
    description: str = ""
    leader_nickname: str = Field(
        min_length=1,
        max_length=50,
        validation_alias=AliasChoices("leader_nickname", "leader"),
    )
    members: list[str] = Field(default_factory=list)
    average_age: str | None = ""
    region: str | None = ""
    genres: list[str] | None = Field(default_factory=list)
    gender_ratio: str | None = ""
    reference_songs: list[str] | None = Field(default_factory=list, max_length=5)

    @field_validator("genres", "reference_songs", mode="before")
    @classmethod
    def _none_to_list(cls, value):
        if value is None:
            return []
        return value


class TeamCreateResponse(BaseModel):
    team_id: int
    team_name: str
    leader: str
    members: list[str]


class TeamListItemResponse(BaseModel):
    team_id: int
    team_name: str
    description: str
    leader: str
    average_age: str = ""
    region: str = ""
    genres: list[str] = Field(default_factory=list)
    gender_ratio: str = ""
    reference_songs: list[str] = Field(default_factory=list)


class TeamDetailResponse(BaseModel):
    team_id: int
    team_name: str
    description: str
    leader: str
    members: list[str]
    average_age: str = ""
    region: str = ""
    genres: list[str] = Field(default_factory=list)
    gender_ratio: str = ""
    reference_songs: list[str] = Field(default_factory=list)


class MyTeamItemResponse(BaseModel):
    team_id: int
    team_name: str
    description: str
    leader: str
    average_age: str = ""
    region: str = ""
    genres: list[str] = Field(default_factory=list)
    gender_ratio: str = ""
    reference_songs: list[str] = Field(default_factory=list)


class MyTeamResponse(BaseModel):
    has_team: bool
    team: MyTeamItemResponse | None = None


class TeamLeaveRequest(BaseModel):
    nickname: str | None = None


class TeamLeaveResponse(BaseModel):
    ok: bool
    team_deleted: bool
    message: str


class TeamInviteRequest(BaseModel):
    nickname: str | None = Field(default=None, validation_alias=AliasChoices("nickname", "user_nickname"))
    user_id: str | None = Field(default=None, validation_alias=AliasChoices("user_id", "target_user_id"))
    auto_accept_test: bool = False
    team_id: int | None = None


class TeamInviteResponse(BaseModel):
    ok: bool
    team_id: int
    invited_user_id: str
    invited_nickname: str
    status: str


class TeamInviteItemResponse(BaseModel):
    invite_id: int
    team_id: int
    invited_user_id: str
    invited_nickname: str
    invited_by_user_id: str
    invited_by_nickname: str
    status: str


class TeamInviteListResponse(BaseModel):
    invites: list[TeamInviteItemResponse] = Field(default_factory=list)
