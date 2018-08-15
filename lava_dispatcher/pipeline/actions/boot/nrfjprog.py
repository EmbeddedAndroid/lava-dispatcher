# Copyright (C) 2018 Foundries.io
#
# Author: Tyler Baker <tyler@foundries.io
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

from lava_dispatcher.pipeline.action import (
    Pipeline,
    Action,
    JobError,
)
from lava_dispatcher.pipeline.logical import Boot, RetryAction
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.power import HardReset
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.utils.strings import substitute


class NrfJprog(Boot):

    compatibility = 4  # FIXME: change this to 5 and update test cases

    def __init__(self, parent, parameters):
        super(NrfJprog, self).__init__(parent)
        self.action = BootNrfJprog()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'nrfjprog' not in device['actions']['boot']['methods']:
            return False
        if 'method' not in parameters:
            return False
        if parameters['method'] != 'nrfjprog':
            return False
        if 'board_id' not in device:
            return False
        return True


class BootNrfJprog(BootAction):

    def __init__(self):
        super(BootNrfJprog, self).__init__()
        self.name = 'boot-nrfjprog-image'
        self.description = "boot nrfjprog image with retry"
        self.summary = "boot nrfjprog image with retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(BootNrfJprogRetry())


class BootNrfJprogRetry(RetryAction):

    def __init__(self):
        super(BootNrfJprogRetry, self).__init__()
        self.name = 'boot-nrfjprog-image'
        self.description = "boot nrfjprog image using the command line interface"
        self.summary = "boot nrfjprog image"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(HardReset())
        self.internal_pipeline.add_action(FlashNrfJprogAction())


class FlashNrfJprogAction(Action):

    def __init__(self):
        super(FlashNrfJprogAction, self).__init__()
        self.name = "flash-nrfjprog"
        self.description = "flash nrfjprog to boot the image"
        self.summary = "flash nrfjprog to boot the image"
        self.base_command = []
        self.exec_list = []

    def validate(self):
        super(FlashNrfJprogAction, self).validate()
        boot = self.job.device['actions']['boot']['methods']['nrfjprog']
        nrfjprog_binary = boot['parameters']['command']
        self.errors = infrastructure_error(nrfjprog_binary)
        self.base_command = ['flock -o /var/lock/lava-nrfjprog.lck', nrfjprog_binary]
        self.base_command.extend(boot['parameters'].get('options', []))
        if self.job.device['board_id'] == '0000000000':
            self.errors = "board_id unset"
        substitutions = {}
        self.base_command.extend(['--snr', self.job.device['board_id']])
        namespace = self.parameters['namespace']
        for action in self.data[namespace]['download-action'].keys():
            nrfjprog_full_command = []
            image_arg = self.get_namespace_data(action='download-action', label=action, key='image_arg')
            action_arg = self.get_namespace_data(action='download-action', label=action, key='file')
            if image_arg:
                if not isinstance(image_arg, str):
                    self.errors = "image_arg is not a string (try quoting it)"
                    continue
                substitutions["{%s}" % action] = action_arg
                nrfjprog_full_command.extend(self.base_command)
                nrfjprog_full_command.extend(substitute([image_arg], substitutions))
                self.exec_list.append(nrfjprog_full_command)
            else:
                nrfjprog_full_command.extend(self.base_command)
                nrfjprog_full_command.extend([action_arg])
                self.exec_list.append(nrfjprog_full_command)
        nrfjprog_erase_command = []
        nrfjprog_erase_command.extend(self.base_command)
        nrfjprog_erase_command.extend(['--eraseall', '-f', 'NRF52'])
        self.exec_list.append(nrfjprog_erase_command)
        if len(self.exec_list) < 2:
            self.errors = "No nrfJProg command to execute"

    def run(self, connection, max_end_time, args=None):
        connection = super(FlashNrfJprogAction, self).run(connection, max_end_time, args)
        for nrfjprog_command in self.exec_list:
            nrfjprog = ' '.join(nrfjprog_command)
            self.logger.info("nrfjprog command: %s", nrfjprog)
            if not self.run_command(nrfjprog.split(' ')):
                raise JobError("%s command failed" % (nrfjprog.split(' ')))
        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
        self.set_namespace_data(action='shared', label='shared', key='connection', value=connection)
        return connection
