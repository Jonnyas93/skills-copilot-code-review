"""Announcement endpoints for the High School Management System API."""

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator

from ..database import announcements_collection, teachers_collection

router = APIRouter(prefix="/announcements", tags=["announcements"])


class AnnouncementPayload(BaseModel):
    title: str
    message: str
    expiration_date: date
    start_date: Optional[date] = None

    @field_validator("title", "message")
    @classmethod
    def require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field is required")
        return value

def require_signed_in(username: Optional[str]) -> Dict[str, Any]:
    if not username:
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")
    return teacher


def serialize(announcement: Dict[str, Any]) -> Dict[str, Any]:
    announcement["id"] = str(announcement.pop("_id"))
    return announcement


@router.get("", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    today = date.today().isoformat()
    query = {
        "expiration_date": {"$gte": today},
        "$or": [{"start_date": {"$exists": False}}, {"start_date": {"$lte": today}}]
    }
    return [serialize(announcement) for announcement in announcements_collection.find(query).sort("expiration_date", 1)]


@router.get("/manage", response_model=List[Dict[str, Any]])
def get_all_announcements(username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    require_signed_in(username)
    return [serialize(announcement) for announcement in announcements_collection.find().sort("expiration_date", 1)]


@router.post("", response_model=Dict[str, Any])
def create_announcement(payload: AnnouncementPayload, username: Optional[str] = Query(None)) -> Dict[str, Any]:
    require_signed_in(username)
    if payload.start_date and payload.start_date > payload.expiration_date:
        raise HTTPException(status_code=400, detail="Start date must be before expiration date")

    announcement = {"_id": str(uuid4()), **payload.model_dump(mode="json")}
    announcements_collection.insert_one(announcement)
    return serialize(announcement)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(announcement_id: str, payload: AnnouncementPayload, username: Optional[str] = Query(None)) -> Dict[str, Any]:
    require_signed_in(username)
    if payload.start_date and payload.start_date > payload.expiration_date:
        raise HTTPException(status_code=400, detail="Start date must be before expiration date")

    result = announcements_collection.replace_one({"_id": announcement_id}, {"_id": announcement_id, **payload.model_dump(mode="json")})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return serialize(announcements_collection.find_one({"_id": announcement_id}))


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, username: Optional[str] = Query(None)) -> Dict[str, str]:
    require_signed_in(username)
    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"message": "Announcement deleted"}