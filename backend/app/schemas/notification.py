from datetime import datetime


from pydantic import BaseModel, ConfigDict, Field

class NotificationSchema(BaseModel):
    id: str
    type: str
    title: str
    message: str
    severity: str
    isRead: bool = Field(alias="is_read")
    referenceId: str | None = Field(default=None, alias="reference_id")
    createdAt: datetime = Field(alias="created_at")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class NotificationListResponse(BaseModel):
    success: bool
    data: list[NotificationSchema]


class NotificationMarkReadRequest(BaseModel):
    isRead: bool = True
