from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model (decided before the first migration, as the roadmap
    requires). Deliberately does NOT store admission numbers, phone numbers
    or any mobile-wallet credentials (proposal section 3.8).
    """

    class YearOfStudy(models.IntegerChoices):
        YEAR_1 = 1, "Year 1"
        YEAR_2 = 2, "Year 2"
        YEAR_3 = 3, "Year 3"
        YEAR_4 = 4, "Year 4"
        YEAR_5 = 5, "Year 5+"

    email = models.EmailField("email address", unique=True)
    university = models.CharField(max_length=120, blank=True)
    year_of_study = models.PositiveSmallIntegerField(
        choices=YearOfStudy.choices, null=True, blank=True
    )
    semester_start = models.DateField(
        null=True, blank=True, help_text="Used for semester reports and runway estimates."
    )
    semester_end = models.DateField(null=True, blank=True)

    # In-app notification preferences
    notify_budget_alerts = models.BooleanField(default=True)
    notify_insight_alerts = models.BooleanField(default=True)
    budget_warning_default = models.PositiveSmallIntegerField(
        default=80, help_text="Default warning threshold (%) for new budgets."
    )

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def display_name(self):
        return self.first_name or self.username
