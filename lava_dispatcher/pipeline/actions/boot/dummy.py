# Copyright (C) 2017 Open Source Foundries Limited
#
# Author: Tyler Baker <tyler@opensourcefoundries.com>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

from lava_dispatcher.pipeline.action import (
    ConfigurationError,
    Pipeline,
)
from lava_dispatcher.pipeline.logical import Boot
from lava_dispatcher.pipeline.actions.boot import (
    BootAction,
    AutoLoginAction,
    OverlayUnpack,
)
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.shell import ExpectShellSession
from lava_dispatcher.pipeline.connections.serial import ConnectDevice
from lava_dispatcher.pipeline.power import ResetDevice


def dummy_accepts(device, parameters):
    if 'method' not in parameters:
        raise ConfigurationError("method not specified in boot parameters")
    if parameters['method'] != 'dummy':
        return False
    if 'actions' not in device:
        raise ConfigurationError("Invalid device configuration")
    if 'boot' not in device['actions']:
        return False
    if 'methods' not in device['actions']['boot']:
        raise ConfigurationError("Device misconfiguration")
    return True


class DummyBoot(Boot):

    compatibility = 1

    def __init__(self, parent, parameters):
        super(DummyBoot, self).__init__(parent)
        self.action = DummyBootAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if not dummy_accepts(device, parameters):
            return False
        return 'dummy' in device['actions']['boot']['methods']


class DummyBootAction(BootAction):


    def __init__(self):
        super(DummyBootAction, self).__init__()
        self.name = "dummy-action"
        self.description = "dummy boot action"
        self.summary = "resets device and allows it to boot"

    def validate(self):
        super(DummyBootAction, self).validate()
        if 'type' in self.parameters:
            self.logger.warning("Specifying a type in the boot action is deprecated. "
                                "Please specify the kernel type in the deploy parameters.")

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # customize the device configuration for this job
        self.internal_pipeline.add_action(ConnectDevice())
        self.internal_pipeline.add_action(DummyRetry())


class DummyRetry(BootAction):

    def __init__(self):
        super(DummyRetry, self).__init__()
        self.name = "dummy-retry"
        self.description = "dummy boot retry action"
        self.summary = "dummy boot with retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # establish a new connection before trying the reset
        self.internal_pipeline.add_action(ResetDevice())
        if self.has_prompts(parameters):
            self.internal_pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.internal_pipeline.add_action(ExpectShellSession())
                if 'transfer_overlay' in parameters:
                    self.internal_pipeline.add_action(OverlayUnpack())
                self.internal_pipeline.add_action(ExportDeviceEnvironment())


    def validate(self):
        super(DummyRetry, self).validate()

    def run(self, connection, max_end_time, args=None):
        connection = super(DummyRetry, self).run(connection, max_end_time, args)
        # Log an error only when needed
        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
        if self.errors:
            self.logger.error(self.errors)
        return connection
