from django.db import models

# Persistent data
class Registration(models.Model):
    regid = models.AutoField(primary_key=True)
    userid = models.CharField(max_length=50, null=True)      #local user id
    username = models.CharField(max_length=50)               #local user name
    fullname = models.CharField(max_length=50)
    domain = models.CharField(max_length=50)
    region = models.CharField(max_length=50)

class Project(models.Model):
    projectname = models.CharField(max_length=50, primary_key=True)
    projectid = models.CharField(max_length=50, null=True)
    description = models.CharField(max_length=300)
    visible = models.BooleanField()

#
#TODO missing project admin table
#

class UserMapping(models.Model):
    globaluser = models.CharField(max_length=50, primary_key=True)
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE)

#Temporary data
class RegRequest(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE)
    password = models.CharField(max_length=50, null=True)
    externalid = models.CharField(max_length=50, null=True)
    email = models.EmailField(max_length=50)
    notes = models.CharField(max_length=300)

class PrjRequest(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE)
    project = models.ForeignKey(Project)
    notes = models.CharField(max_length=300)
