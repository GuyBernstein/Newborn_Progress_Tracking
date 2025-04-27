import json
import math
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from sqlalchemy.orm import Session

from app.models.models import Baby, BabyProgress

# WHO Growth Standards data (simplified example)
# In a real implementation, you would load this from a database or file
WHO_WEIGHT_FOR_AGE = {
    # Male standards: age_in_months -> [P3, P15, P50, P85, P97]
    "male": {
        0: [2.5, 2.9, 3.3, 3.7, 4.0],
        1: [3.4, 3.9, 4.5, 5.1, 5.5],
        2: [4.3, 4.9, 5.6, 6.3, 6.8],
        3: [5.0, 5.7, 6.4, 7.2, 7.8],
        # ... more data points
    },
    # Female standards
    "female": {
        0: [2.4, 2.8, 3.2, 3.6, 3.9],
        1: [3.2, 3.6, 4.2, 4.8, 5.2],
        2: [3.9, 4.5, 5.1, 5.8, 6.2],
        3: [4.5, 5.2, 5.8, 6.6, 7.1],
        # ... more data points
    }
}

WHO_HEIGHT_FOR_AGE = {
    # Similar structure to weight data
    "male": {
        0: [46.1, 48.0, 49.9, 51.8, 53.4],
        1: [50.8, 52.8, 54.7, 56.7, 58.4],
        # ... more data points
    },
    "female": {
        0: [45.4, 47.3, 49.1, 51.0, 52.7],
        1: [49.8, 51.7, 53.7, 55.6, 57.4],
        # ... more data points
    }
}

WHO_HEAD_CIRCUMFERENCE_FOR_AGE = {
    # Similar structure
    "male": {
        0: [32.4, 33.6, 34.5, 35.4, 36.1],
        # ... more data points
    },
    "female": {
        0: [31.9, 33.0, 33.9, 34.8, 35.5],
        # ... more data points
    }
}


def calculate_age_in_months(birth_date: date, reference_date: date) -> int:
    """Calculate age in months between birth date and reference date."""
    months = (reference_date.year - birth_date.year) * 12
    months += reference_date.month - birth_date.month

    # Adjust for partial months
    if reference_date.day < birth_date.day:
        months -= 1

    return max(0, months)


def interpolate_percentile(value: float, standards: List[float],
                           percentiles: List[float] = [3, 15, 50, 85, 97]) -> float:
    """
    Interpolate to find the percentile of a given value within standards.

    Args:
        value: The measurement value (weight, height, etc.)
        standards: The standard values at specific percentiles
        percentiles: The percentile values corresponding to standards

    Returns:
        The interpolated percentile (0-100)
    """
    if value <= standards[0]:
        return percentiles[0] * (value / standards[0])

    if value >= standards[-1]:
        return percentiles[-1]

    for i in range(len(standards) - 1):
        if standards[i] <= value < standards[i + 1]:
            # Linear interpolation
            range_percent = (value - standards[i]) / (standards[i + 1] - standards[i])
            return percentiles[i] + range_percent * (percentiles[i + 1] - percentiles[i])

    return percentiles[-1]


def calculate_growth_percentile(
        baby: Baby,
        weight: Optional[float],
        height: Optional[float],
        head_circumference: Optional[float],
        record_date: date
) -> Dict[str, float]:
    """
    Calculate growth percentiles based on WHO growth standards.

    Returns:
        Dictionary with weight_percentile, height_percentile, and head_percentile
    """
    gender = baby.gender.lower() if baby.gender else "male"  # Default to male if unspecified
    age_months = calculate_age_in_months(baby.date_of_birth, record_date)

    # Round to nearest month in our data
    closest_month = min(WHO_WEIGHT_FOR_AGE[gender].keys(), key=lambda m: abs(m - age_months))

    result = {}

    if weight is not None:
        weight_standards = WHO_WEIGHT_FOR_AGE[gender][closest_month]
        result["weight_percentile"] = interpolate_percentile(weight, weight_standards)

    if height is not None:
        height_standards = WHO_HEIGHT_FOR_AGE[gender][closest_month]
        result["height_percentile"] = interpolate_percentile(height, height_standards)

    if head_circumference is not None:
        head_standards = WHO_HEAD_CIRCUMFERENCE_FOR_AGE[gender][closest_month]
        result["head_percentile"] = interpolate_percentile(head_circumference, head_standards)

    # Calculate overall percentile (average of available percentiles)
    if result:
        result["overall_percentile"] = sum(result.values()) / len(result)
    else:
        result["overall_percentile"] = 50.0  # Default to 50th percentile if no data

    return result


def calculate_sleep_quality_index(sleep_schedule: List[Dict]) -> float:
    """
    Calculate sleep quality index based on sleep patterns.

    Args:
        sleep_schedule: List of sleep sessions with start_time, end_time, and quality

    Returns:
        Sleep quality index (0-100)
    """
    if not sleep_schedule:
        return 50.0  # Default score

    total_sleep_minutes = 0
    total_interruptions = 0
    night_sleep_minutes = 0

    # Expected sleep durations by age (in hours)
    # This would ideally come from a medical database
    expected_sleep = {
        0: 16,  # Newborn
        1: 15.5,
        2: 15,
        3: 14.5,
        # ... more data
    }

    # Convert to datetime objects
    sessions = []
    for session in sleep_schedule:
        start = session["start_time"]
        end = session["end_time"] if session.get("end_time") else datetime.now()

        if isinstance(start, str):
            start = datetime.fromisoformat(start.replace('Z', '+00:00'))
        if isinstance(end, str):
            end = datetime.fromisoformat(end.replace('Z', '+00:00'))

        duration = (end - start).total_seconds() / 60  # Duration in minutes
        is_night = 20 <= start.hour or start.hour <= 6  # Rough definition of night sleep

        sessions.append({
            "start": start,
            "end": end,
            "duration": duration,
            "is_night": is_night,
            "quality": session.get("quality", "good")
        })

        total_sleep_minutes += duration
        if is_night:
            night_sleep_minutes += duration

    # Sort sessions by start time
    sessions.sort(key=lambda x: x["start"])

    # Calculate interruptions (gaps less than 30 minutes between sessions)
    for i in range(len(sessions) - 1):
        gap = (sessions[i + 1]["start"] - sessions[i]["end"]).total_seconds() / 60
        if gap < 30:
            total_interruptions += 1

    # Calculate metrics
    hours_slept = total_sleep_minutes / 60
    night_sleep_ratio = night_sleep_minutes / total_sleep_minutes if total_sleep_minutes > 0 else 0

    # Quality factor based on reported quality
    quality_factor = sum(1.0 if s["quality"] == "good" else 0.7 if s["quality"] == "fair" else 0.4
                         for s in sessions) / len(sessions)

    # Interruption penalty
    interruption_factor = max(0.5, 1 - (total_interruptions * 0.1))

    # Calculate final score (0-100)
    score = 0

    # Sleep duration score (40% of total)
    duration_score = min(100, (hours_slept / 14) * 100)  # Assuming 14 hours is optimal for newborns

    # Night sleep ratio score (30% of total)
    night_ratio_score = night_sleep_ratio * 100

    # Quality and interruption score (30% of total)
    continuity_score = (quality_factor * interruption_factor) * 100

    # Weighted final score
    score = (duration_score * 0.4) + (night_ratio_score * 0.3) + (continuity_score * 0.3)

    return min(100, max(0, score))


def calculate_feeding_efficiency(feeding_times: List[Dict], baby_age_months: int) -> float:
    """
    Calculate feeding efficiency based on feeding patterns.

    Args:
        feeding_times: List of feeding sessions
        baby_age_months: Baby's age in months

    Returns:
        Feeding efficiency score (0-100)
    """
    if not feeding_times:
        return 50.0  # Default score

    # Expected feeding patterns by age
    if baby_age_months < 1:
        expected_feeds_per_day = 8  # Newborns feed 8-12 times per day
        expected_feed_interval = 2  # ~2-3 hours between feeds
    elif baby_age_months < 3:
        expected_feeds_per_day = 7
        expected_feed_interval = 3
    elif baby_age_months < 6:
        expected_feeds_per_day = 6
        expected_feed_interval = 3.5
    else:
        expected_feeds_per_day = 5
        expected_feed_interval = 4

    # Convert to datetime objects and calculate metrics
    feeds = []
    total_duration = 0
    total_amount = 0

    for feed in feeding_times:
        start = feed["start_time"]
        end = feed.get("end_time")

        if isinstance(start, str):
            start = datetime.fromisoformat(start.replace('Z', '+00:00'))

        if end:
            if isinstance(end, str):
                end = datetime.fromisoformat(end.replace('Z', '+00:00'))
            duration = (end - start).total_seconds() / 60  # Duration in minutes
        else:
            duration = 15  # Default duration if not specified

        feeds.append({
            "start": start,
            "duration": duration,
            "amount": feed.get("amount", 0),
            "type": feed.get("type", "unknown")
        })

        total_duration += duration
        if feed.get("amount"):
            total_amount += feed["amount"]

    # Sort feeds by start time
    feeds.sort(key=lambda x: x["start"])

    # Calculate interval regularity
    intervals = []
    for i in range(len(feeds) - 1):
        interval = (feeds[i + 1]["start"] - feeds[i]["start"]).total_seconds() / 3600  # Hours
        intervals.append(interval)

    interval_regularity = 0
    if intervals:
        # Calculate how close intervals are to expected
        deviations = [abs(interval - expected_feed_interval) for interval in intervals]
        avg_deviation = sum(deviations) / len(deviations)
        interval_regularity = max(0, 1 - (avg_deviation / expected_feed_interval))

    # Calculate number of feeds per day
    if len(feeds) >= 2:
        time_span = (feeds[-1]["start"] - feeds[0]["start"]).total_seconds() / 3600  # Hours
        if time_span >= 12:  # Only calculate if we have at least 12 hours of data
            feeds_per_day = (len(feeds) / time_span) * 24
            feed_frequency_score = 1 - min(1, abs(feeds_per_day - expected_feeds_per_day) / expected_feeds_per_day)
        else:
            feed_frequency_score = 0.7  # Default if not enough data
    else:
        feed_frequency_score = 0.7  # Default if not enough data

    # Calculate feed duration appropriateness
    avg_duration = total_duration / len(feeds) if feeds else 0
    duration_score = 0

    # Appropriate durations vary by feeding type
    bottle_feeds = [f for f in feeds if f.get("type") == "bottle"]
    breast_feeds = [f for f in feeds if f.get("type") == "breast"]

    if bottle_feeds:
        bottle_avg = sum(f["duration"] for f in bottle_feeds) / len(bottle_feeds)
        # Bottle feeds typically 10-20 minutes
        bottle_score = 1 - min(1, abs(bottle_avg - 15) / 15)
    else:
        bottle_score = 0.7

    if breast_feeds:
        breast_avg = sum(f["duration"] for f in breast_feeds) / len(breast_feeds)
        # Breast feeds typically 15-30 minutes
        breast_score = 1 - min(1, abs(breast_avg - 25) / 25)
    else:
        breast_score = 0.7

    if bottle_feeds and breast_feeds:
        duration_score = (bottle_score + breast_score) / 2
    elif bottle_feeds:
        duration_score = bottle_score
    elif breast_feeds:
        duration_score = breast_score
    else:
        duration_score = 0.7  # Default if feeding type not specified

    # Calculate final score (0-100)
    regularity_weight = 0.4
    frequency_weight = 0.3
    duration_weight = 0.3

    final_score = (
                          (interval_regularity * regularity_weight) +
                          (feed_frequency_score * frequency_weight) +
                          (duration_score * duration_weight)
                  ) * 100

    return min(100, max(0, final_score))


def calculate_developmental_score(milestones: List[Dict], baby_age_months: int, baby: Baby) -> float:
    """
    Calculate developmental score based on achieved milestones.

    Args:
        milestones: List of developmental milestones
        baby_age_months: Baby's age in months
        baby: Baby instance containing date_of_birth and other attributes

    Returns:
        Developmental score (0-100)
    """
    if not milestones:
        return 50.0  # Default score

    # Expected milestones by age (simplified)
    # In a real application, this would be a comprehensive database
    expected_milestones = {
        1: ["responds to sounds", "follows objects with eyes", "lifts head briefly"],
        2: ["holds head up", "begins to smile", "coos and makes sounds"],
        3: ["recognizes faces", "reaches for objects", "laughs"],
        4: ["rolls over", "holds head steady", "pushes up on arms"],
        # ... more milestones
    }

    # Flatten expected milestones up to baby's age
    all_expected = []
    for month, month_milestones in expected_milestones.items():
        if month <= baby_age_months:
            all_expected.extend(month_milestones)

    if not all_expected:
        return 70.0  # Very young baby with no expected milestones yet

    # Count achieved milestones
    achieved = [m["milestone"].lower() for m in milestones]

    # Simple matching algorithm - in a real app, use NLP for better matching
    matched = 0
    for expected in all_expected:
        if any(expected in a or a in expected for a in achieved):
            matched += 1

    # Calculate score
    if all_expected:
        base_score = (matched / len(all_expected)) * 100
    else:
        base_score = 50

    # Bonus for early achievements
    bonus = 0
    for milestone in milestones:
        if "achieved_date" in milestone and isinstance(milestone["achieved_date"], (str, date)):
            achieved_date = milestone["achieved_date"]
            if isinstance(achieved_date, str):
                try:
                    achieved_date = date.fromisoformat(achieved_date)
                except ValueError:
                    continue

            # Find which month this milestone is typically achieved
            for month, month_milestones in expected_milestones.items():
                if any(milestone["milestone"].lower() in m or m in milestone["milestone"].lower()
                       for m in month_milestones):
                    # Calculate age when achieved in months
                    age_when_achieved = calculate_age_in_months(baby.date_of_birth, achieved_date)

                    # Bonus for early achievement
                    if age_when_achieved < month:
                        bonus += 5  # 5 points bonus per early milestone

                    break

    final_score = min(100, base_score + bonus)
    return final_score


def process_baby_progress(
        db: Session,
        progress: BabyProgress,
        baby: Optional[Baby] = None
) -> BabyProgress:
    """
    Process baby progress data to calculate insights.

    Args:
        db: Database session
        progress: BabyProgress object to process
        baby: Baby object (optional, will be fetched if not provided)

    Returns:
        Updated BabyProgress object with calculated insights
    """
    if baby is None:
        baby = db.query(Baby).filter(Baby.id == progress.baby_id).first()
        if not baby:
            return progress

    # Calculate age in months
    baby_age_months = calculate_age_in_months(baby.date_of_birth, progress.record_date)

    # Calculate growth percentile
    if any(x is not None for x in [progress.weight, progress.height, progress.head_circumference]):
        growth_data = calculate_growth_percentile(
            baby,
            progress.weight,
            progress.height,
            progress.head_circumference,
            progress.record_date
        )
        progress.growth_percentile = growth_data.get("overall_percentile")

    # Calculate sleep quality index
    if progress.sleep_schedule:
        sleep_data = progress.sleep_schedule
        if isinstance(sleep_data, str):
            try:
                sleep_data = json.loads(sleep_data)
            except:
                sleep_data = []

        progress.sleep_quality_index = calculate_sleep_quality_index(sleep_data)

    # Calculate feeding efficiency
    if progress.feeding_times:
        feeding_data = progress.feeding_times
        if isinstance(feeding_data, str):
            try:
                feeding_data = json.loads(feeding_data)
            except:
                feeding_data = []

        progress.feeding_efficiency = calculate_feeding_efficiency(feeding_data, baby_age_months)

    # Calculate developmental score
    if progress.milestones:
        milestone_data = progress.milestones
        if isinstance(milestone_data, str):
            try:
                milestone_data = json.loads(milestone_data)
            except:
                milestone_data = []

        progress.developmental_score = calculate_developmental_score(
            milestone_data,
            baby_age_months,
            baby
        )

    return progress