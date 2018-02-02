import os
import shutil

import sys
from click_default_group import DefaultGroup

from subprocess import check_output

import click as click

CONFIG_PATH = '/etc/amazon-dash.yml'
SYSTEMD_PATHS = [
    '/usr/lib/systemd/system',
    '/lib/systemd/system',
]

__dir__ = os.path.dirname(os.path.abspath(__file__))

CONFIG_EXAMPLE = os.path.join(__dir__, 'amazon-dash.yml')
SYSTEMD_SERVICE = os.path.join(__dir__, 'services', 'amazon-dash.service')


def get_pid(name):
    return check_output(["pidof", name])


def get_systemd_services_path():
    for path in SYSTEMD_PATHS:
        if os.path.lexists(path):
            return path


def catch(fn, exception_cls=None):
    exception_cls = exception_cls or InstallException

    def wrap(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except exception_cls as e:
            click.echo('{}'.format(e), err=True)
    return wrap


def install_success(name):
    click.echo('[OK] {} has been installed successfully'.format(name))
    return True


class InstallException(Exception):
    name = 'Install Error'
    tpl = '[{name}] {body}'

    def __init__(self, body='No details'):
        self.body = body

    def __str__(self):
        return self.tpl.format(name=self.name, body=self.body)


class IsInstallableException(InstallException):
    name = 'Unable to install'


class IsNecessaryException(InstallException):
    name = 'Already installed'


class InstallBase(object):
    name = ''

    def is_installable(self):
        raise NotImplementedError

    def is_necessary(self):
        raise NotImplementedError

    def installation(self):
        raise NotImplementedError

    def install(self):
        self.is_installable()
        self.is_necessary()
        self.installation()
        return True


class InstallConfig(InstallBase):
    name = 'config'

    def is_installable(self):
        directory = os.path.dirname(CONFIG_PATH)
        if not os.path.lexists(directory):
            raise IsInstallableException('/{} does not exists'.format(directory))

    def is_necessary(self):
        if os.path.lexists(CONFIG_PATH):
            raise IsNecessaryException('{} already exists'.format(CONFIG_PATH))

    def installation(self):
        shutil.copy(CONFIG_EXAMPLE, CONFIG_PATH)
        os.chmod(CONFIG_PATH, 0o600)
        os.chown(CONFIG_PATH, 0, 0)


class InstallSystemd(InstallBase):
    name = 'systemd'
    service_name = os.path.split(SYSTEMD_SERVICE)[-1]

    @property
    def service_path(self):
        path = get_systemd_services_path()
        if not path:
            return
        return os.path.join(path, self.service_name)

    def is_installable(self):
        if not get_pid('systemd') and get_systemd_services_path():
            raise IsInstallableException('Systemd is not available')

    def is_necessary(self):
        if os.path.lexists(self.service_path):
            raise IsNecessaryException('Systemd service is already installed')

    def installation(self):
        shutil.copy(SYSTEMD_SERVICE, self.service_path)
        os.chmod(self.service_path, 0o600)
        os.chown(self.service_path, 0, 0)


SERVICES = [
    InstallSystemd,
]


@click.group(cls=DefaultGroup, default='all', default_if_no_args=True)
def cli():
    if os.getuid():
        click.echo('The installation must be done as root. Maybe you forgot sudo?', err=True)
        sys.exit(1)


@catch
@cli.command()
def config():
    InstallConfig().install() and install_success('config')


@catch
@cli.command()
def systemd():
    InstallSystemd().install() and install_success('systemd service')


@cli.command()
def all():
    click.echo('Executing all install scripts for Amazon-Dash')
    catch(config)()
    has_service = False
    for service in SERVICES:
        try:
            has_service = has_service or (service().install() and
                                          install_success('{} service'.format(service.name)))
        except IsInstallableException:
            pass
        except IsNecessaryException as e:
            has_service = True
            click.echo('{}'.format(e), err=True)
    if not has_service:
        click.echo('Warning: There is no service installed in the system. You must run Amazon-dash manually')


catch(cli)()