from django.db import models


class IR_Identification(models.Model):
    # If ir_reported = yes, ira_reported will always be yes since there has to be at least one IR.

    def save(self, *args, **kwargs):
        self.ira_reported = "yes" if self.ir_reported == "yes" else self.ira_reported
        super().save(*args, **kwargs)


    IR_CHOICES = [
        ("yes", "Yes"),
        ("no", "No"),
        ("exception", "No, or only 1 IR occurs naturally in this species."),
    ]

    IRB_CHOICES = [
        ("yes", "Yes"),
        ("no", "No"),
    ]

    accession = models.CharField(max_length=50, unique=True)
    title = models.TextField(default="No Title")
    updated = models.DateTimeField(null=True, blank=True, verbose_name="Last Updated")
    ir_reported = models.CharField(
        max_length=50,
        choices=IR_CHOICES,
        verbose_name="Inverted Repeats Reported",
        default="no"
    )
    ira_reported = models.CharField(max_length=50)
    ira_reported_start = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Start of Inverted Repeat A (bp position)"
    )
    ira_reported_end = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="End of Inverted Repeat A (bp position)"
    )
    ira_reported_length = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Length of Inverted Repeat A (bp)"
    )
    irb_reported = models.CharField(
        max_length=50,
        choices=IRB_CHOICES,
        null=True,
        blank=True
    )
    irb_reported_start = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Start of Inverted Repeat B (bp position)"
    )
    irb_reported_end = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="End of Inverted Repeat B (bp position)"
    )
    irb_reported_length = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Length of Inverted Repeat B (bp)"
    )

    def __str__(self):
        return f"{self.accession} - {self.title} - {self.updated}"

    class Meta:
        verbose_name = "IR Identification"

