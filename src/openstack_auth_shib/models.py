from django.db import models

class Candidate(models.Model):
    uname = models.CharField(max_length=50, primary_key=True)
    domain = models.CharField(max_length=50)
    project = models.CharField(max_length=200)

class UserMapping(models.Model):
    globaluser = models.CharField(max_length=50, primary_key=True)
    localuser = models.CharField(max_length=50)

class RegRequest(models.Model):
    globaluser = models.CharField(max_length=50, null=True)
    domain = models.CharField(max_length=50, null=True)
    localuser = models.CharField(max_length=50)
    password = models.CharField(max_length=50)
    email = models.CharField(max_length=50)
    notes = models.CharField(max_length=300)

