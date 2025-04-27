from datetime import date
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.endpoints.auth import get_current_active_user
from app.db.base import get_db
from app.models.models import Baby, BabyProgress, User
from app.schemas.schemas import BabyProgress as BabyProgressSchema
from app.schemas.schemas import BabyProgressCreate, BabyProgressUpdate
from app.services.analytics import process_baby_progress

router = APIRouter()


def check_baby_ownership(db: Session, baby_id: int, current_user: User) -> Baby:
    """Check if the baby belongs to the current user."""
    baby = db.query(Baby).filter(Baby.id == baby_id, Baby.parent_id == current_user.id).first()
    if not baby:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baby not found or you don't have permission",
        )
    return baby


@router.get("/{baby_id}/progress", response_model=List[BabyProgressSchema])
def get_baby_progress(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_id: int,
        skip: int = 0,
        limit: int = 100,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
) -> Any:
    """
    Get progress records for a baby.
    """
    # Check baby ownership
    check_baby_ownership(db, baby_id, current_user)

    # Build query
    query = db.query(BabyProgress).filter(BabyProgress.baby_id == baby_id)

    # Apply date filters if provided
    if start_date:
        query = query.filter(BabyProgress.record_date >= start_date)
    if end_date:
        query = query.filter(BabyProgress.record_date <= end_date)

    # Get results with pagination
    progress_entries = query.order_by(BabyProgress.record_date.desc()).offset(skip).limit(limit).all()

    return progress_entries


@router.post("/{baby_id}/progress", response_model=BabyProgressSchema)
def create_baby_progress(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_id: int,
        progress_in: BabyProgressCreate,
) -> Any:
    """
    Create a new progress record for a baby.
    """
    # Check baby ownership
    baby = check_baby_ownership(db, baby_id, current_user)

    # Check if a record for this date already exists
    existing = db.query(BabyProgress).filter(
        BabyProgress.baby_id == baby_id,
        BabyProgress.record_date == progress_in.record_date
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A progress record already exists for {progress_in.record_date}",
        )

    # Create progress record
    progress_data = progress_in.dict()
    progress = BabyProgress(**progress_data)

    # Process with analytics to calculate insights
    progress = process_baby_progress(db, progress, baby)

    db.add(progress)
    db.commit()
    db.refresh(progress)
    return progress


@router.get("/{baby_id}/progress/{progress_id}", response_model=BabyProgressSchema)
def get_progress_record(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_id: int,
        progress_id: int,
) -> Any:
    """
    Get a specific progress record.
    """
    # Check baby ownership
    check_baby_ownership(db, baby_id, current_user)

    # Get progress record
    progress = db.query(BabyProgress).filter(
        BabyProgress.id == progress_id,
        BabyProgress.baby_id == baby_id
    ).first()

    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progress record not found",
        )

    return progress


@router.put("/{baby_id}/progress/{progress_id}", response_model=BabyProgressSchema)
def update_progress_record(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_id: int,
        progress_id: int,
        progress_in: BabyProgressUpdate,
) -> Any:
    """
    Update a progress record.
    """
    # Check baby ownership
    baby = check_baby_ownership(db, baby_id, current_user)

    # Get progress record
    progress = db.query(BabyProgress).filter(
        BabyProgress.id == progress_id,
        BabyProgress.baby_id == baby_id
    ).first()

    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progress record not found",
        )

    # Update fields
    update_data = progress_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(progress, field, value)

    # Process with analytics to recalculate insights
    progress = process_baby_progress(db, progress, baby)

    db.add(progress)
    db.commit()
    db.refresh(progress)
    return progress


@router.delete("/{baby_id}/progress/{progress_id}", response_model=BabyProgressSchema)
def delete_progress_record(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_id: int,
        progress_id: int,
) -> Any:
    """
    Delete a progress record.
    """
    # Check baby ownership
    check_baby_ownership(db, baby_id, current_user)

    # Get progress record
    progress = db.query(BabyProgress).filter(
        BabyProgress.id == progress_id,
        BabyProgress.baby_id == baby_id
    ).first()

    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progress record not found",
        )

    db.delete(progress)
    db.commit()
    return progress


@router.get("/{baby_id}/insights", response_model=dict)
def get_baby_insights(
        *,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
        baby_id: int,
        timeframe: str = Query("all", description="Timeframe for insights: 'week', 'month', 'all'"),
) -> Any:
    """
    Get aggregated insights for a baby.
    """
    # Check baby ownership
    baby = check_baby_ownership(db, baby_id, current_user)

    # Build query for progress records
    query = db.query(BabyProgress).filter(BabyProgress.baby_id == baby_id)

    # Apply timeframe filter
    today = date.today()
    if timeframe == "week":
        # Last 7 days
        from datetime import timedelta
        week_ago = today - timedelta(days=7)
        query = query.filter(BabyProgress.record_date >= week_ago)
    elif timeframe == "month":
        # Last 30 days
        from datetime import timedelta
        month_ago = today - timedelta(days=30)
        query = query.filter(BabyProgress.record_date >= month_ago)

    # Get all applicable progress records
    progress_records = query.order_by(BabyProgress.record_date).all()

    if not progress_records:
        return {
            "message": "No progress data available for the selected timeframe",
            "insights": {}
        }

    # Calculate insights
    insights = {
        "total_records": len(progress_records),
        "timeframe": timeframe,
        "baby_age_months": (today.year - baby.date_of_birth.year) * 12 + (today.month - baby.date_of_birth.month),
        "growth": {
            "first_record": {
                "date": progress_records[0].record_date.isoformat(),
                "weight": progress_records[0].weight,
                "height": progress_records[0].height,
                "head_circumference": progress_records[0].head_circumference,
            },
            "latest_record": {
                "date": progress_records[-1].record_date.isoformat(),
                "weight": progress_records[-1].weight,
                "height": progress_records[-1].height,
                "head_circumference": progress_records[-1].head_circumference,
            },
            "average_percentile": sum(r.growth_percentile or 0 for r in progress_records if r.growth_percentile) /
                                  len([r for r in progress_records if r.growth_percentile]) if any(
                r.growth_percentile for r in progress_records) else None,
        },
        "sleep": {
            "average_quality": sum(r.sleep_quality_index or 0 for r in progress_records if r.sleep_quality_index) /
                               len([r for r in progress_records if r.sleep_quality_index]) if any(
                r.sleep_quality_index for r in progress_records) else None,
            "trend": "improving" if progress_records[-1].sleep_quality_index and progress_records[
                0].sleep_quality_index and
                                    progress_records[-1].sleep_quality_index > progress_records[
                                        0].sleep_quality_index else
            "declining" if progress_records[-1].sleep_quality_index and progress_records[0].sleep_quality_index and
                           progress_records[-1].sleep_quality_index < progress_records[
                               0].sleep_quality_index else "stable",
        },
        "feeding": {
            "average_efficiency": sum(r.feeding_efficiency or 0 for r in progress_records if r.feeding_efficiency) /
                                  len([r for r in progress_records if r.feeding_efficiency]) if any(
                r.feeding_efficiency for r in progress_records) else None,
            "trend": "improving" if progress_records[-1].feeding_efficiency and progress_records[
                0].feeding_efficiency and
                                    progress_records[-1].feeding_efficiency > progress_records[
                                        0].feeding_efficiency else
            "declining" if progress_records[-1].feeding_efficiency and progress_records[0].feeding_efficiency and
                           progress_records[-1].feeding_efficiency < progress_records[
                               0].feeding_efficiency else "stable",
        },
        "development": {
            "average_score": sum(r.developmental_score or 0 for r in progress_records if r.developmental_score) /
                             len([r for r in progress_records if r.developmental_score]) if any(
                r.developmental_score for r in progress_records) else None,
            "trend": "improving" if progress_records[-1].developmental_score and progress_records[
                0].developmental_score and
                                    progress_records[-1].developmental_score > progress_records[
                                        0].developmental_score else
            "stable" if progress_records[-1].developmental_score and progress_records[0].developmental_score and
                        progress_records[-1].developmental_score == progress_records[0].developmental_score else
            "as expected" if progress_records[-1].developmental_score else "not enough data",
        }
    }

    # Calculate growth rates (if enough data and timespan)
    if len(progress_records) >= 2:
        first = progress_records[0]
        last = progress_records[-1]

        # Calculate days between measurements
        days_diff = (last.record_date - first.record_date).days
        if days_diff > 0:
            # Weight gain per week (convert to grams for better readability)
            if first.weight and last.weight:
                weight_gain_per_day = (last.weight - first.weight) / days_diff
                insights["growth"]["weight_gain_per_week"] = round(weight_gain_per_day * 7 * 1000, 1)  # g/week

            # Height gain per month
            if first.height and last.height:
                height_gain_per_day = (last.height - first.height) / days_diff
                insights["growth"]["height_gain_per_month"] = round(height_gain_per_day * 30, 1)  # cm/month

            # Head circumference gain per month
            if first.head_circumference and last.head_circumference:
                hc_gain_per_day = (last.head_circumference - first.head_circumference) / days_diff
                insights["growth"]["head_circumference_gain_per_month"] = round(hc_gain_per_day * 30, 1)  # cm/month

    return {
        "baby_name": baby.name,
        "insights": insights
    }