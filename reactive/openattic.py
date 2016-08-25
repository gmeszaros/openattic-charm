import os
from subprocess import check_output

from charms.reactive import when_not, set_state, when
from charmhelpers.core.hookenv import (
    log,
    open_port, status_set)
import jinja2

TEMPLATES_DIR = 'templates'


def render_template(template_name, context, template_dir=TEMPLATES_DIR):
    templates = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir))
    template = templates.get_template(template_name)
    return template.render(context)


@when('ceph-admin.available')
def connect_to_ceph(ceph_client):
    charm_ceph_conf = os.path.join(os.sep,
                                   'etc',
                                   'ceph',
                                   'ceph.conf')
    cephx_key = os.path.join(os.sep,
                             'etc',
                             'ceph',
                             'ceph.client.admin.keyring')

    ceph_context = {
        'auth_supported': ceph_client.auth(),
        'mon_hosts': ceph_client.mon_hosts(),
        'fsid': ceph_client.fsid(),
        'use_syslog': 'true',
        'loglevel': '0',
    }

    with open(charm_ceph_conf, 'w') as cephconf:
        cephconf.write(render_template('ceph.conf', ceph_context))

    with open(cephx_key, 'w') as key_file:
        key_file.write("[client.admin]\n\tkey = {}\n".format(
            ceph_client.key()
        ))
    status_set('active', '')


@when_not('apt.needs_update')
@when_not('openattic.installed')
def install_openattic():
    # Tell debconf where to find answers fo the openattic questions
    charm_debconf = os.path.join(os.getenv('CHARM_DIR'),
                                 'files',
                                 'openattic-answers')
    check_output(['debconf-set-selections', charm_debconf])

    # Install openattic in noninteractive mode
    my_env = os.environ.copy()
    my_env['DEBIAN_FRONTEND'] = "noninteractive"
    status_set('maintenance', 'installing openattic')
    try:
        check_output(
            [
                'apt-get',
                '-y',
                'install',
                # This is needed for the openattic LIO module
                'linux-image-extra-{}'.format(os.uname()[2]),
                'openattic',
                'openattic-module-ceph'
            ],
            env=my_env)
    except OSError as e:
        log("apt-get install failed with error: {}".format(e))
        raise e
    try:
        # Setup openattic post apt-get install and start the service
        check_output(['oaconfig', 'install', '--allow-broken-hostname'])
    except OSError as e:
        log("oaconfig install failed with {}".format(e))
        raise e
    open_port(port=80)
    status_set('maintenance', '')

    set_state('openattic.installed')
