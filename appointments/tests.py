"""Tests for the appointments app."""
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse


class AppointmentsIndexViewTests(TestCase):
    """Tests for the booking homepage."""

    fixtures = ["demo_data.json"]

    def test_index(self):
        """Check that the homepage displays available services."""
        response = self.client.get(reverse("index"))
        self.assertContains(response, "Haircut", status_code=200)

    @patch("django.utils.timezone.now")
    def test_index_hairdresser(self, mock_now):
        """Select a date and create a midday appointment."""
        mock_now.return_value = datetime(
            2010, 1, 1, 10, 0, tzinfo=ZoneInfo("America/Los_Angeles")
        )

        response = self.client.get(
            reverse("index-hairdresser", args=(3, 1))
        )
        first_date = response.context["dates_all"][0][1]

        date_url = reverse("index-date", args=(3, 1, first_date))
        response = self.client.get(date_url)
        self.assertContains(response, "Time", status_code=200)

        appt_time = "12:00"
        self.client.post(
            reverse("create"),
            {
                "service": 3,
                "hairdresser": 1,
                "date": first_date,
                "appointment_time": appt_time,
                "customer_contact": "Demo Customer",
            },
        )

        # FIX THIS: Test that the time is no longer available.
        response = self.client.get(date_url)
        blocked = [
            t["time_formatted"]
            for t in response.context["start_times_all"]
            if t["is_blocked"]
        ]
        assert appt_time in blocked, "Blocked time not found"
