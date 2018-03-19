# Copyright (C) 2018 Open Source Foundries Limited
#
# Author: Tyler <tyler@opensourcefoundries.com>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can retftp.pyibute it and/or modify
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

from lava_dispatcher.pipeline.actions.deploy.overlay import (
    CustomisationAction,
    OverlayAction,
)
from lava_dispatcher.pipeline.action import (
    ConfigurationError,
    Pipeline
)
from lava_dispatcher.pipeline.logical import Deployment
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.environment import DeployDeviceEnvironment


def dummy_accept(device, parameters):

    if 'to' not in parameters:
        return False
    if parameters['to'] != 'dummy':
        return False
    if not device:
        return False
    if 'actions' not in device:
        raise ConfigurationError("Invalid device configuration")
    if 'deploy' not in device['actions']:
        return False
    if 'methods' not in device['actions']['deploy']:
        raise ConfigurationError("Device misconfiguration")
    return True


class DummyDeploy(Deployment):

    compatibility = 1

    def __init__(self, parent, parameters):
        super(DummyDeploy, self).__init__(parent)
        self.action = DummyDeployAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if not dummy_accept(device, parameters):
            return False
        return True


class DummyDeployAction(DeployAction):  # pylint:disable=too-many-instance-attributes

    def __init__(self):
        super(DummyDeployAction, self).__init__()
        self.name = "dummy-deploy"
        self.description = "Fakes deployment"
        self.summary = "dummy deployment"

    def validate(self):
        super(DummyDeployAction, self).validate()
        if self.test_needs_deployment(self.parameters):
            lava_test_results_base = self.parameters['deployment_data']['lava_test_results_dir']
            lava_test_results_dir = lava_test_results_base % self.job.job_id
            self.set_namespace_data(action='test', label='results', key='lava_test_results_dir', value=lava_test_results_dir)

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_deployment(parameters):
            self.internal_pipeline.add_action(CustomisationAction())
            self.internal_pipeline.add_action(OverlayAction())
        if self.test_needs_deployment(parameters):
            self.internal_pipeline.add_action(DeployDeviceEnvironment())
