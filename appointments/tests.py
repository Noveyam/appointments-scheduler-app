from django.test import SimpleTestCase

class HomepageIntegrationTests(SimpleTestCase):
    def test_homepage_returns_expected_message(self):
      response = self.client.get('/')

      self.assertContains(
        response,
        "Appointments Scheduler is running.",
        status_code=200
      )