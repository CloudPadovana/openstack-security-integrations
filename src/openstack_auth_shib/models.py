from django.db import models

# Used bit mask for project status
PRJ_PRIVATE = 0
PRJ_PUBLIC = 1
PRJ_GUEST = 3

# Status for project approval
PSTATUS_REG = 0
PSTATUS_PENDING = 1
PSTATUS_APPR = 2
PSTATUS_REJ = 3

# Status for registration approval
RSTATUS_PENDING = 0
RSTATUS_CHECKED = 1

# Persistent data
class Registration(models.Model):
    regid = models.AutoField(primary_key=True)
    userid = models.CharField(max_length=50, null=True)      #local user id
    username = models.CharField(max_length=50, unique=True)  #local user name
    fullname = models.CharField(max_length=50)
    domain = models.CharField(max_length=50)
    region = models.CharField(max_length=50)

class Project(models.Model):
    projectname = models.CharField(max_length=50, primary_key=True)
    projectid = models.CharField(max_length=50, null=True)
    description = models.CharField(max_length=300)
    status = models.IntegerField()

class UserMapping(models.Model):
    globaluser = models.CharField(max_length=50, primary_key=True)
    registration = models.ForeignKey(Registration,
                                    db_index=False,
                                    on_delete=models.CASCADE)

#Temporary data
class RegRequest(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE)
    password = models.CharField(max_length=50, null=True)
    externalid = models.CharField(max_length=50, null=True)
    email = models.EmailField(max_length=50)
    flowstatus = models.IntegerField(default=RSTATUS_PENDING)
    notes = models.CharField(max_length=300)

class PrjRequest(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    flowstatus = models.IntegerField(default=PSTATUS_REG)
    notes = models.CharField(max_length=300)


