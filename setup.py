#!/usr/bin/env python

import sys, os, os.path, shlex, subprocess
from subprocess import Popen as execScript
from distutils.core import setup
from distutils.command.bdist_rpm import bdist_rpm as _bdist_rpm

pkg_name = 'openstack-security-integrations'
pkg_version = '1.0.0'
pkg_release = '2'

source_items = "setup.py src"

class bdist_rpm(_bdist_rpm):

    def run(self):

        topdir = os.path.join(os.getcwd(), self.bdist_base, 'rpmbuild')
        builddir = os.path.join(topdir, 'BUILD')
        srcdir = os.path.join(topdir, 'SOURCES')
        specdir = os.path.join(topdir, 'SPECS')
        rpmdir = os.path.join(topdir, 'RPMS')
        srpmdir = os.path.join(topdir, 'SRPMS')
        
        cmdline = "mkdir -p %s %s %s %s %s" % (builddir, srcdir, specdir, rpmdir, srpmdir)
        execScript(shlex.split(cmdline)).communicate()
        
        cmdline = "tar -zcf %s %s" % (os.path.join(srcdir, pkg_name + '.tar.gz'), source_items)
        execScript(shlex.split(cmdline)).communicate()
        
        specOut = open(os.path.join(specdir, pkg_name + '.spec'),'w')
        cmdline = "sed -e 's|@PKGVERSION@|%s|g' -e 's|@PKGRELEASE@|%s|g' project/%s.spec.in" % (pkg_version, pkg_release, pkg_name)
        execScript(shlex.split(cmdline), stdout=specOut, stderr=sys.stderr).communicate()
        specOut.close()
        
        cmdline = "rpmbuild -ba --define '_topdir %s' %s.spec" % (topdir, os.path.join(specdir, pkg_name))
        execScript(shlex.split(cmdline)).communicate()

os_main_dir = 'usr/share/openstack-dashboard/'
templates_dir = os_main_dir + 'openstack_dashboard/templates'
img_dir = os_main_dir + 'static/dashboard/img'
reg_panel_dir = os_main_dir + 'openstack_dashboard/dashboards/admin/registration_manager/templates/registration_manager'
css_dir = 'usr/share/openstack-dashboard/static/dashboard/less'

template_list = [
                    'src/templates/_register_form.html',
                    'src/templates/registration.html',
                    'src/templates/aai_error.html'
                ]

reg_templ_list = [
                    'src/templates/reg_manager.html',
                    'src/templates/reg_approve.html',
                    'src/templates/_reg_approve.html'
                 ]

module_list = [
                'keystone_skey_auth',
                'openstack_auth_shib',
                'registration_manager',
                'project_manager'
              ]

setup(
      name=pkg_name,
      version=pkg_version,
      description='Shibboleth-Openstack integrations',
      long_description='''Shibboleth-Openstack integrations''',
      license='Apache Software License',
      author_email='CREAM group <cream-support@lists.infn.it>',
      packages=module_list,
      package_dir = {'': 'src'},
      data_files=[
                  (templates_dir, template_list),
                  (templates_dir + '/auth', ['src/templates/_login.html']),
                  (reg_panel_dir, reg_templ_list),
                  (css_dir, ['src/templates/aai_infn_integrations.less']),
                  (img_dir, ['src/templates/logoInfnAAI.png'])
                 ],
      cmdclass={'bdist_rpm': bdist_rpm}
     )


