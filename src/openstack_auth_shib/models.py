from django.db import models

class UserMapping(models.Model):
    globaluser = models.CharField(max_length=50, primary_key=True)
    localuser = models.CharField(max_length=50)

class RegRequest(models.Model):
    reqid = models.AutoField(primary_key=True)
    localuser = models.CharField(max_length=50)
    password = models.CharField(max_length=50)
    email = models.CharField(max_length=50)
    notes = models.CharField(max_length=300)
    globalid = models.CharField(max_length=50, null=True)
    idp = models.CharField(max_length=50, null=True)
    domain = models.CharField(max_length=50, null=True)

