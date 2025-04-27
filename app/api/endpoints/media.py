from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.endpoints.auth import get_current_active_user
from app.api.endpoints.progress import check_baby_ownership
from app.db.base import get_db
from app.models.models import MediaItem, User
from app.schemas.schemas import MediaItem as MediaItemSchema
from app.schemas.schemas import MediaItemCreate, MediaItemUpdate
from app.services.s3 import s3_service

router = APIRouter()


@router.get("/{baby_id}/media", response_model=List[MediaItemSchema])
async def get_baby_media(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_id: int,
        skip: int = 0,
        limit: int = 100,
        media_type: Optional[str] = None,
) -> Any:
    """
    Get media items for a baby.
    """
    # Check baby ownership
    check_baby_ownership(db, baby_id, current_user)

    # Build query
    query = db.query(MediaItem).filter(MediaItem.baby_id == baby_id)

    # Apply media type filter if provided
    if media_type:
        query = query.filter(MediaItem.media_type == media_type)

    # Get results with pagination
    media_items = query.order_by(MediaItem.upload_date.desc()).offset(skip).limit(limit).all()

    # Refresh presigned URLs
    for item in media_items:
        item.s3_url = s3_service.generate_presigned_url(item.s3_key)

    return media_items


@router.post("/{baby_id}/media", response_model=MediaItemSchema)
async def upload_media(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_id: int,
        file: UploadFile = File(...),
        media_type: str = Form(...),
        notes: Optional[str] = Form(None),
        tags: Optional[str] = Form(None),
) -> Any:
    """
    Upload a new media file for a baby.
    """
    # Check baby ownership
    check_baby_ownership(db, baby_id, current_user)

    # Validate media type
    valid_media_types = ["photo", "video", "document"]
    if media_type not in valid_media_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(valid_media_types)}",
        )

    # Parse tags if provided
    parsed_tags = None
    if tags:
        try:
            import json
            parsed_tags = json.loads(tags)
        except:
            # If JSON parsing fails, treat as comma-separated list
            parsed_tags = [tag.strip() for tag in tags.split(",")]

    try:
        # Upload file to S3
        upload_result = await s3_service.upload_file(
            file=file,
            baby_id=baby_id,
            content_type=file.content_type
        )

        # Create media item record
        media_item = MediaItem(
            baby_id=baby_id,
            media_type=media_type,
            s3_key=upload_result["s3_key"],
            s3_url=upload_result["s3_url"],
            filename=upload_result["filename"],
            file_size=upload_result["file_size"],
            content_type=upload_result["content_type"],
            notes=notes,
            tags=parsed_tags
        )

        db.add(media_item)
        db.commit()
        db.refresh(media_item)
        return media_item

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}",
        )


@router.get("/{baby_id}/media/{media_id}", response_model=MediaItemSchema)
async def get_media_item(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_id: int,
        media_id: int,
        refresh_url: bool = True,
) -> Any:
    """
    Get a specific media item.
    """
    # Check baby ownership
    check_baby_ownership(db, baby_id, current_user)

    # Get media item
    media_item = db.query(MediaItem).filter(
        MediaItem.id == media_id,
        MediaItem.baby_id == baby_id
    ).first()

    if not media_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media item not found",
        )

    # Refresh presigned URL if requested
    if refresh_url:
        media_item.s3_url = s3_service.generate_presigned_url(media_item.s3_key)
        db.add(media_item)
        db.commit()
        db.refresh(media_item)

    return media_item


@router.put("/{baby_id}/media/{media_id}", response_model=MediaItemSchema)
async def update_media_item(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_id: int,
        media_id: int,
        media_in: MediaItemUpdate,
) -> Any:
    """
    Update a media item's metadata.
    """
    # Check baby ownership
    check_baby_ownership(db, baby_id, current_user)

    # Get media item
    media_item = db.query(MediaItem).filter(
        MediaItem.id == media_id,
        MediaItem.baby_id == baby_id
    ).first()

    if not media_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media item not found",
        )

    # Update fields
    update_data = media_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(media_item, field, value)

    # Refresh presigned URL
    media_item.s3_url = s3_service.generate_presigned_url(media_item.s3_key)

    db.add(media_item)
    db.commit()
    db.refresh(media_item)
    return media_item


@router.delete("/{baby_id}/media/{media_id}", response_model=MediaItemSchema)
async def delete_media_item(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_id: int,
        media_id: int,
) -> Any:
    """
    Delete a media item.
    """
    # Check baby ownership
    check_baby_ownership(db, baby_id, current_user)

    # Get media item
    media_item = db.query(MediaItem).filter(
        MediaItem.id == media_id,
        MediaItem.baby_id == baby_id
    ).first()

    if not media_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media item not found",
        )

    # Delete file from S3
    s3_service.delete_file(media_item.s3_key)

    # Delete record from database
    db.delete(media_item)
    db.commit()
    return media_item