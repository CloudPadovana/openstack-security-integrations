import sys

from datetime import datetime
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from openstack_auth_shib.models import Registration

from keystoneclient.v3 import client

class Command(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('--config',
            dest='conffile',
            action='store',
            default=None,
            help='The configuration file for this plugin'
        ),
    )
    
    def readParameters(self, conffile):
        result = dict()

        cfile = open(conffile)
        for line in cfile:
            tmps = line.strip()
            if len(tmps) == 0 or tmps.startswith('#'):
                continue
            
            tmpl = tmps.split('=')
            if len(tmpl) == 2:
                result[tmpl[0].strip()] = tmpl[1].strip()
        
        cfile.close()
        
        return result
    
    def handle(self, *args, **options):
    
        conffile = options.get('conffile', None)
        if not conffile:
            raise CommandError("Missing configuration file\n")
    
        try:
            params = self.readParameters(conffile)
            
            expired_regs = Registration.objects.filter(expdate__lt=datetime.now())
            
            for reg_item in expired_regs:
                
                keystone = client.Client(username=params['username'],
                                         password=params['passwd'],
                                         project_name=params['tenantname'],
                                         cacert=params['cafile'],
                                         auth_url=params['authurl'])
                
                keystone.users.update(reg_item.userid, enabled=False)
                
        except:
            etype, evalue, etraceback = sys.exc_info()
            sys.excepthook(etype, evalue, etraceback)
            raise CommandError("Check expiration failed")


