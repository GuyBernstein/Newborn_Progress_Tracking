import json
import os
from datetime import date, datetime, timedelta

import requests

# API base URL
BASE_URL = "http://localhost:8000/api/v1"

# Sample test data
TEST_USER = {
    "email": "test2@example.com",
    "password": "testpassword1234"
}

TEST_BABY = {
    "name": "Baby Test",
    "date_of_birth": (date.today() - timedelta(days=60)).isoformat(),  # 2 months old
    "gender": "female"
}

TEST_PROGRESS = {
    "record_date": date.today().isoformat(),
    "weight": 5.2,  # kg
    "height": 57.5,  # cm
    "head_circumference": 38.2,  # cm
    "feeding_times": [  # Remove json.dumps()
        {
            "start_time": (datetime.now() - timedelta(hours=4)).isoformat(),
            "end_time": (datetime.now() - timedelta(hours=4) + timedelta(minutes=20)).isoformat(),
            "type": "breast",
            "notes": "Fed well"
        },
        {
            "start_time": (datetime.now() - timedelta(hours=2)).isoformat(),
            "end_time": (datetime.now() - timedelta(hours=2) + timedelta(minutes=15)).isoformat(),
            "type": "bottle",
            "amount": 80,
            "notes": "Formula"
        }
    ],
    "feeding_type": "mixed",
    "sleep_schedule": [  # Remove json.dumps()
        {
            "start_time": (datetime.now() - timedelta(hours=8)).isoformat(),
            "end_time": (datetime.now() - timedelta(hours=6)).isoformat(),
            "quality": "good",
            "notes": "Slept well"
        },
        {
            "start_time": (datetime.now() - timedelta(hours=3)).isoformat(),
            "end_time": (datetime.now() - timedelta(hours=2)).isoformat(),
            "quality": "fair",
            "notes": "Short nap"
        }
    ],
    "total_sleep_hours": 3.0,
    "diaper_changes": [  # Remove json.dumps()
        {
            "time": (datetime.now() - timedelta(hours=7)).isoformat(),
            "type": "wet",
            "notes": "Normal"
        },
        {
            "time": (datetime.now() - timedelta(hours=3, minutes=30)).isoformat(),
            "type": "both",
            "notes": "Normal"
        }
    ],
    "milestones": [  # Remove json.dumps()
        {
            "milestone": "Smiles responsively",
            "achieved_date": (date.today() - timedelta(days=10)).isoformat(),
            "notes": "First social smile!"
        }
    ],
    "notes": "Good day overall."
}

# Test image path - update with a real path to a test image
TEST_IMAGE_PATH = "test_baby_photo.jpg"


def register_user():
    """Register a test user."""
    print("\n=== Registering Test User ===")
    response = requests.post(f"{BASE_URL}/auth/register", json=TEST_USER)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()


def login_user():
    """Login and get access token."""
    print("\n=== Logging In ===")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": TEST_USER["email"], "password": TEST_USER["password"]}
    )
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        token = response.json().get("access_token")
        print(f"Access token: {token[:10]}...")
        return token
    else:
        print(f"Login failed: {response.text}")
        return None


def create_baby(token):
    """Create a test baby."""
    print("\n=== Creating Baby ===")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{BASE_URL}/babies/", json=TEST_BABY, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()


def add_progress(token, baby_id):
    """Add progress record for the baby."""
    print("\n=== Adding Progress Record ===")
    headers = {"Authorization": f"Bearer {token}"}

    # Add baby_id to progress data
    progress_data = TEST_PROGRESS.copy()
    progress_data["baby_id"] = baby_id

    response = requests.post(
        f"{BASE_URL}/babies/{baby_id}/progress",
        json=progress_data,
        headers=headers
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()

def get_insights(token, baby_id):
    """Get insights for the baby."""
    print("\n=== Getting Insights ===")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/babies/{baby_id}/insights",
        headers=headers
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()


def upload_media(token, baby_id):
    """Upload a test image."""
    print("\n=== Uploading Media ===")
    headers = {"Authorization": f"Bearer {token}"}

    if not os.path.exists(TEST_IMAGE_PATH):
        print(f"Test image not found at {TEST_IMAGE_PATH}. Skipping media upload test.")
        return None

    with open(TEST_IMAGE_PATH, "rb") as f:
        files = {"file": (os.path.basename(TEST_IMAGE_PATH), f, "image/jpeg")}
        data = {
            "media_type": "photo",
            "notes": "Test photo upload",
            "tags": json.dumps(["test", "baby", "photo"])
        }

        response = requests.post(
            f"{BASE_URL}/babies/{baby_id}/media",
            files=files,
            data=data,
            headers=headers
        )

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    else:
        print(f"Upload failed: {response.text}")
        return None


def run_tests():
    """Run all API tests."""
    # Register user (or get existing)
    try:
        user = register_user()
    except Exception as e:
        print(f"Error registering user: {e}")
        user = None

    # Login to get token
    token = login_user()
    if not token:
        print("Cannot proceed without authentication token.")
        return

    # Create baby
    try:
        baby = create_baby(token)
        baby_id = baby.get("id")
    except Exception as e:
        print(f"Error creating baby: {e}")
        return

    # Add progress record
    try:
        progress = add_progress(token, baby_id)
    except Exception as e:
        print(f"Error adding progress: {e}")

    # Get insights
    try:
        insights = get_insights(token, baby_id)
    except Exception as e:
        print(f"Error getting insights: {e}")

    # Upload media (if test image exists)
    try:
        media = upload_media(token, baby_id)
    except Exception as e:
        print(f"Error uploading media: {e}")

    print("\n=== Tests Completed ===")


if __name__ == "__main__":
    print("\n=== Running Tests ===")
    run_tests()