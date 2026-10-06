from django.urls import reverse

from users.models import Review

from .tests import BaseTestCase, make_user

REVIEW = {'rating': 5, 'communication': 5, 'professionalism': 4, 'punctuality': 5, 'condition': 4,
          'title': 'Great seller', 'body': 'Fast response and fair price.'}


class ReviewTests(BaseTestCase):
    def url(self):
        return reverse('cars:seller_profile', args=[self.dealer.pk])

    def test_buyer_can_review_seller(self):
        self.client.force_login(self.buyer)
        resp = self.client.post(self.url(), REVIEW)
        self.assertRedirects(resp, self.url() + '#reviews', fetch_redirect_response=False)
        self.assertTrue(Review.objects.filter(profile=self.dealer.profile, reviewer=self.buyer).exists())

    def test_one_review_per_reviewer(self):
        self.client.force_login(self.buyer)
        self.client.post(self.url(), REVIEW)
        self.client.post(self.url(), {**REVIEW, 'rating': 3})
        review = Review.objects.get(profile=self.dealer.profile)
        self.assertEqual(int(review.rating), 3)

    def test_sellers_cannot_review_themselves(self):
        self.client.force_login(self.dealer)
        self.client.post(self.url(), REVIEW)
        self.assertFalse(Review.objects.exists())

    def test_aggregates(self):
        other = make_user('other@example.com')
        Review.objects.create(profile=self.dealer.profile, reviewer=self.buyer, rating=5, communication=5, body='ok great')
        Review.objects.create(profile=self.dealer.profile, reviewer=other, rating=4, communication=4, body='good one')
        resp = self.client.get(self.url())
        self.assertAlmostEqual(float(resp.context['agg']['overall']), 4.5)
        self.assertEqual(resp.context['agg']['n'], 2)

    def test_invalid_review_is_rejected(self):
        self.client.force_login(self.buyer)
        resp = self.client.post(self.url(), {**REVIEW, 'rating': 9})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Review.objects.exists())
