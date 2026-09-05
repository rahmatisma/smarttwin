from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NotificationSchema(BaseModel):
    id: int
    type: str
    title: str
    message: str
    severity: str
    isRead: bool
    referenceId: str | None = None
    createdAt: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    success: bool
    data: list[NotificationSchema]


class NotificationMarkReadRequest(BaseModel):
    isRead: bool = True
