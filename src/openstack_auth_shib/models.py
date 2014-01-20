from django.db import models

class UserMapping(models.Model):
    globaluser = models.CharField(max_length=50, primary_key=True)
    localuser = models.CharField(max_length=50)

class RegRequest(models.Model):
    reqid = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50)
    password = models.CharField(max_length=50, null=True)
    email = models.EmailField(max_length=50)
    notes = models.CharField(max_length=300)
    domain = models.CharField(max_length=50)
    region = models.CharField(max_length=50)

class ReqProject(models.Model):
    registration = models.ForeignKey(RegRequest)
    projectname = models.CharField(max_length=50)
