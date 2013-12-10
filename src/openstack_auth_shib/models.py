from django.db import models

class Candidate(models.Model):
    uname = models.CharField(max_length=50, primary_key=True)
    domain = models.CharField(max_length=50)
    project = models.CharField(max_length=200)


