from pydantic import BaseModel, Field


class TeamCreateRequest(BaseModel):
    team_name: str = Field(min_length=1, max_length=100)
    description: str = ""
    leader_nickname: str = Field(min_length=1, max_length=50)
    members: list[str] = []


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


class TeamDetailResponse(BaseModel):
    team_id: int
    team_name: str
    description: str
    leader: str
    members: list[str]
